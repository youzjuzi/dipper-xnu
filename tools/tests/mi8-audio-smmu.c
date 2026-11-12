/* SPDX-License-Identifier: MIT */
/* Synthetic MMIO and nonidentity physical RAM; no hardware access. */
#include "mi8_audio_smmu.h"
#include <pthread.h>
#include <stdatomic.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SMR(n) (0x800u + 4u * (n))
#define S2CR(n) (0xc00u + 4u * (n))
#define CBAR(n) (0x1000u + 4u * (n))
#define CBA2R(n) (0x1800u + 4u * (n))
#define CB(n) (0x40000u + 4096u * (n))
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "FAIL line %u: %s\n", __LINE__, #x); exit(1); } } while (0)
static unsigned checks;
struct model {
	uint32_t regs[0x80000 / 4], before[0x80000 / 4];
	uint64_t tables[2560], buffer[4096];
	struct mi8_smmu_memory memory;
	struct mi8_smmu_claim claim;
	unsigned writes, allocations, releases, caches, lines, holds;
	unsigned mismatch_write, drop_forever, unreadable, rewrite, corrupt;
	unsigned syncs, timeout_sync, faults, cb_reads, global_fault;
	uint32_t fault_value, cleanup_drop;
	bool cbar_locked, cbar_writable, no_idle;
	uint32_t unstable_at, restore_ignore, restore_other_at;
	unsigned flip_read, seen_reads;
	bool restore_m, s2cr_range, s2cr_locked;
	unsigned s2cr_writes;
	uint32_t resv_at, resv_or, hold_flip_at, hold_flip; /* bits outside the compare mask that read back set; a hold-time change */
	char logs[38][320];
	uint32_t addresses[128], values[128];
	bool no_memory, tlb_stuck, restore_block;
};

static bool
read_reg(void *ctx, uint32_t at, uint32_t *value)
{
	struct model *m = ctx;
	CHECK(!(at & 3) && at < 0x80000);
	if (at >= 0x40000) m->cb_reads++;
	if (at == m->unreadable) return false;
	if (at >= 0x40000 && ((at & 4095) == 0x610 || (at & 4095) == 0x7f0)) { *value = 0; return true; }
	if (at >= 0x40000 && (at & 4095) == 0x7f4) { *value = m->tlb_stuck ? 1 : 0; return true; }
	*value = m->regs[at / 4];
	if (at == m->unstable_at && ++m->seen_reads == m->flip_read) *value ^= 2;
	return true;
}
static bool
write_reg(void *ctx, uint32_t at, uint32_t value)
{
	struct model *m = ctx;
	CHECK(m->writes < 128);
	m->addresses[m->writes] = at; m->values[m->writes] = value; m->writes++;
	CHECK(at == SMR(8) || at == S2CR(8) || at == CBAR(43) || at == CBA2R(43) ||
	    (at >= CB(43) && at < CB(43) + 4096));
	if (at == CB(43) + 0x610 || at == CB(43) + 0x7f0) {
		if (at == CB(43) + 0x7f0) { m->syncs++; if (m->syncs == m->timeout_sync) m->tlb_stuck = true; }
		return true;
	}
	if (at == m->drop_forever || (m->holds && at == m->cleanup_drop)) return true;
	if (at == CBAR(43) && m->cbar_locked && !m->cbar_writable) return true;
	if (at == S2CR(8) && m->s2cr_range && (value & 0xff) >= 45) return true; /* hypervisor refuses an out-of-range context */
	if (at == S2CR(8) && m->s2cr_locked && m->s2cr_writes++) return true; /* only the first (claim) write takes effect */
	if (m->restore_block && m->holds && at == CB(43) && value == 0) return true;
	if (at == CB(43) + 0x58) { m->regs[at / 4] &= ~value; return true; }
	m->regs[at / 4] = value;
	if (at == CB(43) && m->holds) {
		m->regs[at / 4] |= m->restore_ignore;
		if (m->restore_m) m->regs[at / 4] |= 1;
	}
	if (m->holds && at == m->restore_other_at) m->regs[at / 4] ^= 2;
	if (at == m->resv_at) m->regs[at / 4] |= m->resv_or;
	/* flip a bit inside the register's defined mask (CBA2R and TCR2 define no bit 8) */
	if (m->mismatch_write == m->writes) m->regs[at / 4] ^= (at == CBA2R(43) || at == CB(43) + 0x10) ? 1u : 0x100;
	if (at == CBAR(43) && value) {
		m->cbar_locked = true;
		if (!m->no_idle) m->regs[(CB(43) + 0x58) / 4] = 0x400;
	}
	if (m->global_fault == m->writes) m->regs[0x48/4] = 2;
	if (m->faults == m->writes) m->regs[(CB(43) + 0x58) / 4] = m->fault_value;
	return true;
}
static void
wait_us(void *ctx, uint32_t us)
{
	struct model *m = ctx;
	if (us != 200000) { CHECK(us == 10); return; }
	m->holds++;
	if (m->rewrite) m->regs[m->rewrite / 4] ^= 0x100;
	if (m->hold_flip_at != ~0u) m->regs[m->hold_flip_at / 4] ^= m->hold_flip;
	if (m->corrupt == 2) m->tables[1024] ^= 1ull << 2;
}
static void log_line(void *ctx, const char *text) {
	struct model *m = ctx; CHECK(text && strlen(text) < 320 && m->lines < 38);
	snprintf(m->logs[m->lines++], 320, "%s", text);
}
static bool logged(struct model *m, const char *text) {
	for (unsigned n = 0; n < m->lines; n++) if (strstr(m->logs[n], text)) return true;
	return false;
}
static bool
allocate(void *ctx, struct mi8_smmu_memory *mem)
{
	struct model *m = ctx;
	m->allocations++; if (m->no_memory) return false;
	memset(m->tables, 0, sizeof(m->tables));
	mem->tables = m->tables; mem->buffer = m->buffer;
	for (unsigned n = 0; n < mem->table_count; n++) mem->table_phys[n] = 0x90000000ull + n * 0x4000;
	for (unsigned n = 0; n < 8; n++) mem->pages[n] = 0xa0000000ull + n * 0x2000;
	m->memory = *mem; return true;
}
static void release(void *ctx, struct mi8_smmu_memory *mem) { struct model *m = ctx; CHECK(mem->tables == m->tables); m->releases++; }
static void cache(void *ctx, const struct mi8_smmu_memory *mem) {
	struct model *m = ctx; CHECK(mem->tables == m->tables); m->caches++;
	if (m->corrupt == 1 && m->caches == 1) m->tables[1024] ^= 1ull << 2;
}
static bool
table_read(void *ctx, uint64_t physical, uint64_t *value)
{
	struct model *m = ctx;
	for (unsigned n = 0; n < m->memory.table_count; n++) if (physical >= m->memory.table_phys[n] &&
	    physical - m->memory.table_phys[n] <= 4088 && !(physical & 7)) {
		memcpy(value, (const char *)m->tables + n * 4096 + physical - m->memory.table_phys[n], 8); return true;
	}
	return false;
}
static struct model *
fresh(void)
{
	struct model *m = calloc(1, sizeof(*m)); CHECK(m);
	m->drop_forever = m->unreadable = m->unstable_at = m->restore_other_at = m->cleanup_drop = ~0u;
	m->resv_at = m->hold_flip_at = ~0u;
	m->fault_value = 2;
	m->regs[0] = 0x250406; m->regs[0x20 / 4] = 0x4c017e4c; m->regs[0x24 / 4] = 0x5000002d;
	m->regs[0x28 / 4] = 0x1222; /* 4K / 40-bit UBS,OAS,IAS */
	for (unsigned n = 0; n < 76; n++) m->regs[S2CR(n) / 4] = 2u << 16;
	for (unsigned n = 0; n < 8; n++) { m->regs[SMR(n) / 4] = 0x80000300u + n; m->regs[S2CR(n) / 4] = n; m->regs[CB(n) / 4] = 1; }
	/* Stable dormant residue is accepted initially, then cleared on claim. */
	m->regs[(CB(43) + 0x20) / 4] = 0x12340000; m->regs[(CB(43) + 0x24) / 4] = 0x43210000;
	m->regs[(CB(43) + 0x10) / 4] = 0x123; m->regs[(CB(43) + 0x30) / 4] = 0x44;
	m->regs[(CB(43) + 0x28) / 4] = 0x56780000; m->regs[(CB(43) + 0x2c) / 4] = 0x11110000;
	m->regs[(CB(43) + 0x38) / 4] = 0x12345678; m->regs[(CB(43) + 0x3c) / 4] = 0x87654321;
	memcpy(m->before, m->regs, sizeof(m->regs)); return m;
}
static struct mi8_smmu_result
run(struct model *m, unsigned step)
{
	struct mi8_smmu_result result;
	const struct mi8_smmu_ops ops = { m, read_reg, write_reg, wait_us, log_line, allocate, release, cache, table_read, &m->claim };
	m->lines = 0;
	mi8_smmu_diagnose(&ops, step, &result);
	CHECK(m->lines <= 38 && result.lines == m->lines);
	return result;
}
/* Every word outside our exact register allowlist must remain byte-identical.
 * Claimed banks clear deterministic state rather than restoring random residue. */
static void identical(struct model *m) {
	if (!m->claim.owned) { CHECK(!memcmp(m->regs, m->before, sizeof(m->regs))); return; }
	CHECK(m->regs[SMR(8)/4] == m->before[SMR(8)/4]);
	CHECK(m->regs[S2CR(8)/4] == m->before[S2CR(8)/4]);
	CHECK(!(m->regs[CB(43)/4] & 1));
	const uint32_t zero[] = {CBA2R(43), CB(43)+0x20, CB(43)+0x24, CB(43)+0x10,
	    CB(43)+0x30, CB(43)+0x28, CB(43)+0x2c, CB(43)+0x38, CB(43)+0x3c};
	for (unsigned i=0;i<sizeof(m->regs)/sizeof(*m->regs);i++) {
		bool ours = i*4 == CBAR(43) || i*4 == CB(43) || i*4 == CB(43)+0x58;
		for (unsigned n=0;n<9;n++) if (i*4 == zero[n]) {
			ours=true;
			if (i*4 != m->restore_other_at) CHECK(m->regs[i] == 0);
		}
		if (!ours) CHECK(m->regs[i] == m->before[i]);
	}
}

static void
overlap_tests(void)
{
	CHECK(mi8_smmu_overlap(0x80001821, 0, false, 0x1821));
	CHECK(!mi8_smmu_overlap(0x1821, 0, false, 0x1821));
	CHECK(mi8_smmu_overlap(0x800f1820, 0, false, 0x1821));
	CHECK(!mi8_smmu_overlap(0x80001820, 0, false, 0x1821));
	CHECK(!mi8_smmu_overlap(0x80001821, 0, false, 0x9821));
	/* Narrow ignores bit15 in both SID and mask; wide uses S2CR.EXIDVALID. */
	CHECK(mi8_smmu_overlap(0x9821, 1u << 10, true, 0x9821));
	CHECK(!mi8_smmu_overlap(0x9821, 0, true, 0x9821));
	CHECK(!mi8_smmu_overlap(0x9821, 1u << 10, true, 0x1821));
	CHECK(mi8_smmu_overlap(0x80009821, 1u << 10, true, 0x1821));
	for (unsigned wide = 0; wide < 2; wide++) for (unsigned mask = 0; mask < 256; mask++) for (unsigned sid = 0; sid < 256; sid++) {
		uint32_t smr = mask << 16 | sid | (wide ? 0 : 1u << 31);
		CHECK(mi8_smmu_overlap(smr, wide ? 1u << 10 : 0, wide, 0x21) == (((sid ^ 0x21) & ~mask) == 0));
	}
}

static void
flow_tests(void)
{
	struct model *m = fresh(); struct mi8_smmu_result r = run(m, 11);
	CHECK(r.slot == 8 && r.bank == 43 && !m->writes && !m->allocations); identical(m); free(m);
	m = fresh(); r = run(m, 12); CHECK(r.passed && r.restored && !r.retained && m->releases == 1 && m->holds == 1); identical(m);
	CHECK(m->caches == 2);
	/* The final route is installed only after the context and its TLB sync. */
	CHECK(m->addresses[10] == CB(43) && m->values[10] & 1);
	CHECK(m->addresses[11] == CB(43) + 0x610 && m->addresses[12] == CB(43) + 0x7f0);
	CHECK(m->addresses[13] == S2CR(8) && m->addresses[14] == SMR(8));
	for (unsigned n = 0; n < 8; n++) {
		uint64_t p = 0, a = 0;
		CHECK(mi8_smmu_walk(table_read, m, m->memory.table_phys[0], MI8_AS_IOVA + n * 4096 + 37, &p, &a) == 1);
		CHECK(p == m->memory.pages[n] + 37 && a == MI8_AS_PTE);
	}
	uint64_t p = 0, a = 0;
	CHECK(mi8_smmu_walk(table_read, m, m->memory.table_phys[0], MI8_AS_IOVA + 32768, &p, &a) == 0);
	CHECK(mi8_smmu_walk(table_read, m, m->memory.table_phys[0], 1ull << 39, &p, &a) == -1);
	m->tables[0] = 0xdead0003; CHECK(mi8_smmu_walk(table_read, m, m->memory.table_phys[0], MI8_AS_IOVA, &p, &a) == -1); free(m);
	/* Wi-Fi already owns CB44: it is untouched and CB43 remains the candidate. */
	m = fresh(); m->regs[SMR(9) / 4] = 0x80010040; m->regs[S2CR(9) / 4] = 44; m->regs[CB(44) / 4] = 1;
	memcpy(m->before, m->regs, sizeof(m->regs)); r = run(m, 12); CHECK(r.passed && r.bank == 43); identical(m); free(m);
	/* A live CB, configured CBAR, faulted CB and invalid-SMR translate S2CR all reserve a bank. */
	for (unsigned kind = 0; kind < 4; kind++) {
		m = fresh();
		if (kind == 0) m->regs[CB(43) / 4] = 1;
		if (kind == 1) m->regs[CBAR(43) / 4] = 1u << 16;
		if (kind == 2) m->regs[(CB(43) + 0x58) / 4] = 2;
		if (kind == 3) m->regs[S2CR(20) / 4] = 43;
		r = run(m, 11); CHECK(r.bank == 42 && !m->writes); free(m);
	}
	for (unsigned scenario = 0; scenario < 12; scenario++) {
		m = fresh();
		switch (scenario) {
		case 0: m->regs[SMR(0) / 4] = 0x80001821; break;
		case 1: m->regs[SMR(0) / 4] = 0x800f1820; break;
		case 2: for (unsigned n = 8; n < 76; n++) m->regs[S2CR(n) / 4] = 1u << 16; break;
		case 3: for (unsigned n = 8; n < 45; n++) m->regs[CB(n) / 4] = 1; break;
		case 4: m->regs[0x48 / 4] = 2; break;
		case 5: m->regs[0x20 / 4] ^= 1; break;
		case 6: m->regs[0x24 / 4] ^= 1; break;
		case 7: m->regs[0x28 / 4] &= ~(1u << 12); break;
		case 8: m->unreadable = CB(43); break;
		case 9: m->no_memory = true; break;
		case 10: m->regs[0] |= 1; break;
		case 11: m->regs[0x28 / 4] |= 15; break;
		}
		memcpy(m->before, m->regs, sizeof(m->regs)); r = run(m, 12);
		CHECK(!r.passed && !m->writes && !m->holds && !r.retained); identical(m);
		if (scenario == 5 || scenario == 6 || scenario == 7) CHECK(!m->cb_reads);
		free(m);
	}
	/* A fully occupied SMR table also exercises the log budget: no writes. */
	m = fresh(); for (unsigned n = 8; n < 76; n++) m->regs[SMR(n) / 4] = 0x80000400u + n;
	r = run(m, 12); CHECK(!r.passed && !m->writes && m->lines == 38); free(m);
	/* Every configuration echo can fail once, including route activation. */
	for (unsigned n = 1; n <= 15; n++) {
		if (n == 12 || n == 13) continue; /* WO commands are covered by TLB timeout tests. */
		m = fresh(); m->mismatch_write = n; r = run(m, 12);
		CHECK(!r.passed && r.restored && !r.retained && m->releases == 1); identical(m); free(m);
	}
	for (unsigned n = 0; n < 4; n++) {
		m = fresh();
		if (n == 0) m->rewrite = CB(43) + 0x20;
		if (n == 1) m->rewrite = SMR(8);
		if (n == 2) m->corrupt = 1;
		if (n == 3) m->corrupt = 2;
		r = run(m, 12); CHECK(!r.passed && !r.retained && m->releases == 1); identical(m); free(m);
	}
	/* Device run 20261111-audio-smmu-04: an unconfigured bank's CB_TCR2 read back 0x38075 for 0x38015. Bits outside the compare mask that read
	 * back set are reported once, not compared, and never listed as sticky; the same bits changing during the hold fail it. */
	m = fresh(); m->resv_at = CB(43) + 0x10; m->resv_or = 0x60; r = run(m, 12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1);
	CHECK(logged(m, "bits outside the compare mask differ (not compared): +0x6b010:0x60") && logged(m, "sticky registers: +0x10ac=0x1f300") && !logged(m, "mismatch"));
	free(m);
	m = fresh(); m->hold_flip_at = CB(43) + 0x10; m->hold_flip = 0x20; r = run(m, 12);
	CHECK(!r.passed && r.restored && !r.retained && m->releases == 1 && logged(m, "hold readback changed +0x6b010")); free(m);
	m = fresh(); m->resv_at = CB(43) + 0x10; m->resv_or = 0x60; m->hold_flip_at = CB(43) + 0x10; m->hold_flip = 0x1; r = run(m, 12);
	CHECK(!r.passed && logged(m, "hold readback changed +0x6b010")); free(m);
	/* Device run 20261111-audio-smmu-05: the unused slot reads S2CR 0x200ff (FAULT, CBNDX 0xff); writing that back is refused. An
	 * in-range FAULT value is tried next; if that is refused too the S2CR is sticky (like CBAR): the cleanup is still confirmed
	 * because the SMR is restored and verified (the slot matches nothing) and SCTLR.M is clear. */
	m = fresh(); m->regs[S2CR(8) / 4] = 0x200ff; m->s2cr_range = true; r = run(m, 12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1 && logged(m, "S2CR 8: original 0x200ff refused; in-range FAULT 0x2002b set"));
	CHECK(m->regs[S2CR(8) / 4] == 0x2002b && m->regs[SMR(8) / 4] == 0); free(m);
	m = fresh(); m->regs[S2CR(8) / 4] = 0x200ff; m->s2cr_locked = true; r = run(m, 12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1 && logged(m, "S2CR sticky (inert: SMR invalid)"));
	CHECK(logged(m, "sticky registers: +0xc20=0x2b +0x10ac=0x1f300") && m->regs[S2CR(8) / 4] == 0x2b && m->regs[SMR(8) / 4] == 0); free(m);
	/* A sticky S2CR does not excuse an SMR that cannot be restored. */
	m = fresh(); m->regs[S2CR(8) / 4] = 0x200ff; m->s2cr_locked = true; m->cleanup_drop = SMR(8); r = run(m, 12);
	CHECK(!r.passed && !r.restored && r.retained && !m->releases); free(m);
	m = fresh(); m->timeout_sync = 1; r = run(m, 12); CHECK(!r.passed && r.retained && !m->releases); free(m);
	m = fresh(); m->timeout_sync = 2; r = run(m, 12); CHECK(!r.passed && r.retained && !m->releases); free(m);
	m = fresh(); m->faults = 5; r = run(m, 12); CHECK(!r.passed && r.restored && !r.retained && m->releases == 1 && !m->holds); free(m);
	m = fresh(); m->restore_block = true; r = run(m, 12); CHECK(!r.passed && !r.restored && r.retained && !m->releases); free(m);
	for (unsigned ubs = 0; ubs < 6; ubs++) for (unsigned oas = 0; oas < 6; oas++) {
		static const unsigned bits[] = {32,36,40,42,44,48};
		m = fresh(); m->regs[0x28 / 4] = 0x1002 | ubs << 8 | oas << 4;
		memcpy(m->before, m->regs, sizeof(m->regs)); r = run(m, 12); CHECK(r.passed); identical(m);
		CHECK(m->values[4] == (oas | 1u << 4 | 7u << 15));
		CHECK((m->values[5] & 63) == 64 - (bits[ubs] < 39 ? bits[ubs] : 39)); free(m);
	}
}

static struct model *
residue(void)
{
	struct model *m = fresh();
	/* Recorded SDM845 vectors before claim: CB43 SCTLR=0x3f35c100,
	 * TTBR0=0x6bce20cd:5ba8454b, TCR=0x5e383faa, CBAR/CBA2R/FSR=0.
	 * Configured CB0 has CBAR=0x10003, CB3=0x10000; both have
	 * CBA2R=1, SCTLR=0xe0, FSR=0x400 (CB3 need not have an S2CR). */
	const uint32_t smrs[] = {0x80080880,0x80080c80,0x800f00a0,0x800f00c0,0x800f00e0,0x800f0100,0x80000740,0x80000760};
	const unsigned banks[] = {0,0,1,1,2,2,4,4};
	m->regs[0] = 0x270406; m->regs[0x28 / 4] = 0x5555;
	for (unsigned n = 0; n < 8; n++) { m->regs[SMR(n) / 4] = smrs[n]; m->regs[S2CR(n) / 4] = banks[n]; }
	for (unsigned n = 0; n < 5; n++) {
		m->regs[CBAR(n) / 4] = n == 0 ? 0x10003 : n == 4 ? 0x1f000 : 0x10000;
		m->regs[CBA2R(n) / 4] = 1; m->regs[CB(n) / 4] = 0xe0; m->regs[(CB(n) + 0x58) / 4] = 0x400;
	}
	m->regs[CB(43) / 4] = 0x3f35c100;
	m->regs[(CB(43) + 0x20) / 4] = 0x5ba8454b; m->regs[(CB(43) + 0x24) / 4] = 0x6bce20cd;
	m->regs[(CB(43) + 0x30) / 4] = 0x5e383faa;
	memcpy(m->before, m->regs, sizeof(m->regs)); return m;
}

static void
free_bank_tests(void)
{
	struct model *m = residue();
	m->unstable_at = CB(43); m->flip_read = ~0u;
	struct mi8_smmu_result r = run(m, 11);
	CHECK(r.bank == 43 && !m->writes && !m->allocations && m->seen_reads == 2);
	CHECK(logged(m, "SCTLR=0x3f35c100 TTBR0=0x6bce20cd:5ba8454b TCR=0x5e383faa FSR=0 read twice stable"));
	identical(m); free(m);
	m = residue(); r = run(m, 12);
	CHECK(r.bank == 43 && r.passed && r.restored && !r.retained && m->releases == 1);
	CHECK(m->regs[CB(43) / 4] == 0);
	CHECK(m->regs[CBAR(43) / 4] == 0x1f300 && m->regs[(CB(43)+0x58)/4] == 0x400);
	CHECK(logged(m, "CBAR restore: wrote 0 got 0x1f300 (sticky)"));
	CHECK(logged(m, "bank 43 claimed (CBAR=0x1f300), inert; SMR 8 restored, S2CR 8 restored"));
	identical(m); free(m);
	/* Isolate each exclusion rather than relying on the configured vector's FSR. */
	for (unsigned reason = 0; reason < 6; reason++) {
		m = residue();
		if (reason == 0) m->regs[CBAR(43) / 4] = 0x10000;
		if (reason == 1) m->regs[CBA2R(43) / 4] = 1;
		if (reason == 2) m->regs[CB(43) / 4] |= 1;
		if (reason == 3) m->regs[(CB(43) + 0x58) / 4] = 0x400;
		if (reason == 4) m->regs[S2CR(20) / 4] = 43; /* invalid SMR still reserves it */
		if (reason == 5) { m->regs[SMR(20) / 4] = 0x80000500; m->regs[S2CR(20) / 4] = 43; }
		r = run(m, 11); CHECK(r.bank == 42 && !m->writes); free(m);
	}
	const unsigned fields[] = {0,0x20,0x24,0x30};
	for (unsigned f = 0; f < 4; f++) {
		m = residue(); m->unstable_at = CB(43) + fields[f]; m->flip_read = 2;
		r = run(m, 11); CHECK(r.bank == 42 && !m->writes); free(m);
		/* Selection pair succeeds. Saved snapshot and echo recheck follow;
		 * only the final pre-write pair (reads 5/6) is unstable. */
		m = residue(); m->unstable_at = CB(43) + fields[f]; m->flip_read = 6;
		r = run(m, 12); CHECK(r.bank == 43 && !r.passed && !m->writes && !m->holds);
		CHECK(m->allocations == 1 && m->releases == 1 && logged(m, "candidate changed/unstable before write")); identical(m); free(m);
	}
	/* Configured, unreferenced CB3 and CB0 still cannot become fallback banks. */
	m = residue();
	for (unsigned n = 5; n < 44; n++) m->regs[CB(n) / 4] |= 1;
	m->regs[S2CR(0) / 4] = m->regs[S2CR(1) / 4] = 2u << 16;
	r = run(m, 11); CHECK(r.bank == -1 && !m->writes);
	CHECK(logged(m, "CBAR!=0=2 CBA2R!=0=2")); free(m);
	/* Every rejected bank contributes explicit reason counts, including refs. */
	m = fresh();
	for (unsigned n = 8; n < 44; n++) m->regs[CB(n) / 4] = 1;
	m->regs[CB(43) / 4] = 0; m->regs[CBAR(43) / 4] = 1;
	m->regs[CB(42) / 4] = 0; m->regs[CBA2R(42) / 4] = 1;
	m->regs[CB(40) / 4] = 0; m->regs[(CB(40) + 0x58) / 4] = 2;
	m->regs[CB(39) / 4] = 0; m->unstable_at = CB(39); m->flip_read = 2;
	r = run(m, 11); CHECK(r.bank == -1 && !m->writes);
	CHECK(logged(m, "bank rejects: referenced=8 CBAR!=0=1 CBA2R!=0=1 M=1=32 FSR!=0=1 unstable=1")); free(m);
	/* SCTLR non-M residue is tolerable only while M remains clear. */
	m = residue(); m->restore_ignore = 1u << 29; r = run(m, 12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1);
	/* bit 29 is outside the SCTLR mask: not compared, not listed as sticky */
	CHECK(logged(m, "sticky registers: +0x10ac=0x1f300"));
	CHECK(m->regs[CB(43) / 4] == 1u << 29); identical(m); free(m);
	m = residue(); m->restore_m = true; r = run(m, 12);
	CHECK(!r.passed && !r.restored && r.retained && !m->releases && logged(m, "inert state unconfirmed")); free(m);
	m = residue(); m->restore_other_at = CB(43) + 0x38; r = run(m, 12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1);
	CHECK(logged(m, "sticky registers: +0x6b038=0x2 +0x10ac=0x1f300"));
	CHECK(m->regs[(CB(43)+0x3c)/4] == 0 && m->regs[CBA2R(43)/4] == 0); identical(m); free(m);

}

static void
claim_tests(void)
{
	struct model *m; struct mi8_smmu_result r;
	/* Configured idle is the only allowed FSR exception; every other bit stops. */
	for (unsigned bit=0;bit<32;bit++) {
		m=residue(); m->faults=1; m->fault_value=0x400 | 1u<<bit; r=run(m,12);
		CHECK(r.passed == (bit == 10));
		CHECK(m->holds == (bit == 10));
		CHECK(r.restored && !r.retained && m->releases == 1);
		if (bit != 10) CHECK(logged(m,"fault: GFSR=0 FSR="));
		free(m);
	}
	m=residue(); m->no_idle=true; r=run(m,12); CHECK(r.passed && logged(m,"FSR=0 (no fault)")); free(m);
	m=residue(); m->faults=1; m->fault_value=0x402; r=run(m,12);
	CHECK(!r.passed && !m->holds && logged(m,"fault: GFSR=0 FSR=0x402")); free(m);
	m=residue(); m->global_fault=1; r=run(m,12);
	CHECK(!r.passed && !m->holds && logged(m,"fault: GFSR=0x2 FSR=0x400")); free(m);
	/* The whole 200ms configuration is still exact, including CBAR and M. */
	const uint32_t held[]={CBAR(43), CBA2R(43), CB(43), CB(43)+0x20, CB(43)+0x24,
	    CB(43)+0x10, CB(43)+0x30, CB(43)+0x28, CB(43)+0x2c, CB(43)+0x38,
	    CB(43)+0x3c, SMR(8), S2CR(8)};
	for(unsigned i=0;i<13;i++) {
		m=residue(); m->rewrite=held[i]; r=run(m,12);
		CHECK(!r.passed && r.restored && !r.retained && m->releases==1);
		CHECK((logged(m,"readback mismatch") || logged(m,"hold readback changed")) && !logged(m,"200 ms hold: every register unchanged")); free(m);
	}
	/* Independent sticky clears all run, including ones after the ignored write. */
	const uint32_t words[]={CBA2R(43),CB(43)+0x20,CB(43)+0x24,CB(43)+0x10,CB(43)+0x30,
	    CB(43)+0x28,CB(43)+0x2c,CB(43)+0x38,CB(43)+0x3c};
	for (unsigned i=0;i<9;i++) {
		m=residue(); m->restore_other_at=words[i]; r=run(m,12);
		CHECK(r.passed && r.restored && !r.retained && m->releases == 1);
		CHECK(m->regs[words[i]/4] == 2);
		for (unsigned j=0;j<9;j++) if (i!=j) CHECK(m->regs[words[j]/4] == 0);
		CHECK(logged(m,"sticky registers:") && logged(m,"CBAR restore:"));
		identical(m); free(m);
	}
	/* An SMR that cannot be restored keeps everything reserved. A refused S2CR does not: it is sticky once the SMR is invalid
	 * (device run 20261111-audio-smmu-05), so the slot is inert, the claim stays (CBAR/S2CR are one-way) and memory is released. */
	m=residue(); m->cleanup_drop=SMR(8); r=run(m,12);
	CHECK(!r.passed && !r.restored && r.retained && !m->releases);
	CHECK(mi8_smmu_reserved(&m->claim,&r,8,~0u));
	CHECK(m->regs[(CB(43)+0x3c)/4] == 0); free(m);
	m=residue(); m->cleanup_drop=S2CR(8); r=run(m,12);
	CHECK(r.passed && r.restored && !r.retained && m->releases == 1 && logged(m, "S2CR sticky (inert: SMR invalid)"));
	CHECK(mi8_smmu_reserved(&m->claim,&r,~0u,43)); free(m); /* the bank stays claimed; slot 8 is no longer FAULT-type, so nobody picks it */
	/* Original free-bank policy still excludes configured FSR=0x400. */
	m=residue(); m->regs[(CB(43)+0x58)/4]=0x400; r=run(m,11); CHECK(r.bank==42&&!m->writes); free(m);
	m=residue(); r=run(m,12); CHECK(r.passed && m->claim.owned && m->claim.bank==43);
	unsigned first_writes=m->writes;
	CHECK(mi8_smmu_reserved(&m->claim,&r,~0u,43));
	CHECK(!mi8_smmu_reserved(&m->claim,&r,8,~0u));
	CHECK(!mi8_smmu_reserved(&m->claim,&r,~0u,44));
	m->holds=0; r=run(m,12);
	CHECK(r.passed && r.bank==43 && m->releases==2 && logged(m,"reuse claimed bank 43"));
	CHECK(m->addresses[first_writes]==CBAR(43) && m->values[first_writes]==0x1f300);
	unsigned restores=0;
	for(unsigned i=0;i<m->writes;i++) if(m->addresses[i]==CBAR(43)&&m->values[i]==0) restores++;
	CHECK(restores==2); /* Exactly one zero attempt per invocation, no coercion. */
	identical(m); free(m);
	/* Even if CBAR accepts zero, software ownership remains reserved and reused. */
	m=residue(); m->cbar_writable=true; r=run(m,12);
	CHECK(r.passed && m->regs[CBAR(43)/4]==0 && logged(m,"got 0 (restored)"));
	CHECK(mi8_smmu_reserved(&m->claim,&r,~0u,43)); m->holds=0; r=run(m,12);
	CHECK(r.passed && logged(m,"reuse claimed bank 43")); free(m);
	/* Never steal a foreign bank, reuse a live/referenced claim, or touch CB44. */
	for(unsigned kind=0;kind<5;kind++) {
		m=residue(); m->claim.owned=true; m->claim.bank=kind==4?44:43;
		m->regs[CBAR(43)/4]=0x1f300; m->regs[(CB(43)+0x58)/4]=0x400;
		if(kind==0)m->regs[CB(43)/4]|=1;
		if(kind==1)m->regs[S2CR(20)/4]=43;
		if(kind==2)m->regs[(CB(43)+0x58)/4]=0x402;
		if(kind==3){m->unstable_at=CB(43);m->flip_read=2;}
		r=run(m,12);CHECK(!r.passed && !m->writes && !m->allocations);free(m);
	}
	/* Emit one representative successful trace for offline review. */
	m=residue(); r=run(m,12); CHECK(r.passed && m->lines<38);
	for(unsigned i=0;i<m->lines;i++) printf("MODEL: %s\n",m->logs[i]);
	free(m);
}

int main(void) { overlap_tests(); flow_tests(); free_bank_tests(); claim_tests(); printf("SELFTEST PASS %u/%u\n", checks, checks); return 0; }
