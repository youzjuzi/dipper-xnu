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
	uint64_t tables[1536], buffer[4096];
	struct mi8_smmu_memory memory;
	unsigned writes, allocations, releases, caches, lines, holds;
	unsigned mismatch_write, drop_forever, unreadable, rewrite, corrupt;
	unsigned syncs, timeout_sync, faults, cb_reads;
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
	*value = m->regs[at / 4]; return true;
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
	if (at == m->drop_forever) return true;
	if (m->restore_block && m->holds && at == CB(43) && value == 0) return true;
	m->regs[at / 4] = value;
	if (m->mismatch_write == m->writes) m->regs[at / 4] ^= 0x100;
	if (m->faults == m->writes) m->regs[(CB(43) + 0x58) / 4] = 2;
	return true;
}
static void
wait_us(void *ctx, uint32_t us)
{
	struct model *m = ctx;
	if (us != 200000) { CHECK(us == 10); return; }
	m->holds++;
	if (m->rewrite) m->regs[m->rewrite / 4] ^= 0x100;
	if (m->corrupt == 2) m->tables[1024] ^= 1ull << 2;
}
static void log_line(void *ctx, const char *text) { struct model *m = ctx; CHECK(text && strlen(text) < 320); m->lines++; }
static bool
allocate(void *ctx, struct mi8_smmu_memory *mem)
{
	struct model *m = ctx;
	m->allocations++; if (m->no_memory) return false;
	memset(m->tables, 0, sizeof(m->tables));
	mem->tables = m->tables; mem->buffer = m->buffer;
	for (unsigned n = 0; n < 3; n++) mem->table_phys[n] = 0x90000000ull + n * 0x4000;
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
	for (unsigned n = 0; n < 3; n++) if (physical >= m->memory.table_phys[n] &&
	    physical - m->memory.table_phys[n] <= 4088 && !(physical & 7)) {
		memcpy(value, (const char *)m->tables + n * 4096 + physical - m->memory.table_phys[n], 8); return true;
	}
	return false;
}
static struct model *
fresh(void)
{
	struct model *m = calloc(1, sizeof(*m)); CHECK(m);
	m->drop_forever = m->unreadable = ~0u;
	m->regs[0] = 0x250406; m->regs[0x20 / 4] = 0x4c017e4c; m->regs[0x24 / 4] = 0x5000002d;
	m->regs[0x28 / 4] = 0x1222; /* 4K / 40-bit UBS,OAS,IAS */
	for (unsigned n = 0; n < 76; n++) m->regs[S2CR(n) / 4] = 2u << 16;
	for (unsigned n = 0; n < 8; n++) { m->regs[SMR(n) / 4] = 0x80000300u + n; m->regs[S2CR(n) / 4] = n; m->regs[CB(n) / 4] = 1; }
	/* Restore must preserve dormant state too, not just zero everything. */
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
	const struct mi8_smmu_ops ops = { m, read_reg, write_reg, wait_us, log_line, allocate, release, cache, table_read };
	mi8_smmu_diagnose(&ops, step, &result);
	CHECK(m->lines <= 38 && result.lines == m->lines);
	return result;
}
static void identical(struct model *m) { CHECK(!memcmp(m->regs, m->before, sizeof(m->regs))); }

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
	m = fresh(); m->timeout_sync = 1; r = run(m, 12); CHECK(!r.passed && r.retained && !m->releases); free(m);
	m = fresh(); m->timeout_sync = 2; r = run(m, 12); CHECK(!r.passed && r.retained && !m->releases); free(m);
	m = fresh(); m->faults = 5; r = run(m, 12); CHECK(!r.passed && r.retained && !m->releases && !m->holds); free(m);
	m = fresh(); m->restore_block = true; r = run(m, 12); CHECK(!r.passed && !r.restored && r.retained && !m->releases); free(m);
	for (unsigned ubs = 0; ubs < 6; ubs++) for (unsigned oas = 0; oas < 6; oas++) {
		static const unsigned bits[] = {32,36,40,42,44,48};
		m = fresh(); m->regs[0x28 / 4] = 0x1002 | ubs << 8 | oas << 4;
		memcpy(m->before, m->regs, sizeof(m->regs)); r = run(m, 12); CHECK(r.passed); identical(m);
		CHECK(m->values[4] == (oas | 1u << 4 | 7u << 15));
		CHECK((m->values[5] & 63) == 64 - (bits[ubs] < 39 ? bits[ubs] : 39)); free(m);
	}
}

int main(void) { overlap_tests(); flow_tests(); printf("SELFTEST PASS %u/%u\n", checks, checks); return 0; }
