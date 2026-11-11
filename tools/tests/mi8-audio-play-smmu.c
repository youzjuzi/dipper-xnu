/* SPDX-License-Identifier: MIT */
/* Reuse the register model and its exact write allowlist. */
#define main smmu_legacy_main
#include "mi8-audio-smmu.c"
#undef main
static void dual_test(unsigned scenario){
    struct model *m=fresh();struct mi8_smmu_mapping map;struct mi8_smmu_result r;
    const struct mi8_smmu_ops ops={m,read_reg,write_reg,wait_us,log_line,allocate,release,cache,table_read,&m->claim};
    if(scenario==4)m->regs[CBAR(43)/4]=1;
    bool began=mi8_smmu_begin(&ops,&map,&r,true);
    if(scenario==4){CHECK(!began&&!m->writes&&!m->allocations);free(m);return;}
    CHECK(began&&map.active&&map.mem.table_count==5&&map.slot==8&&map.bank==43);
    for(unsigned form=0;form<2;form++)for(unsigned n=0;n<=8;n++){
        uint64_t physical=0,attrs=0;
        int walk=mi8_smmu_walk(table_read,m,map.mem.table_phys[0],(form?0x110000000ull:0x10000000ull)+4096*n,&physical,&attrs);
        CHECK(n==8?walk==0:walk==1&&physical==map.mem.pages[n]&&attrs==MI8_AS_PTE);
        /* Independently index all levels and require only the two root entries. */
        if(n<8){unsigned base=form?3:1;CHECK(m->tables[form?4:0]==(map.mem.table_phys[base]|3));CHECK(m->tables[512*base+128]==(map.mem.table_phys[base+1]|3));CHECK(m->tables[512*(base+1)+n]==((0xa0000000ull+n*0x2000)|MI8_AS_PTE));}
    }
    for(unsigned i=0;i<512;i++)if(i!=0&&i!=4)CHECK(!m->tables[i]);
    struct mi8_smmu_fault f;
    CHECK(mi8_smmu_faults(&map,&f)&&f.gfsr==0&&f.fsr==0x400);
    unsigned writes=m->writes;CHECK(mi8_smmu_clear_faults(&map,0x400)&&writes==m->writes);
    m->regs[(CB(43)+0x58)/4]=0x40a;m->regs[(CB(43)+0x60)/4]=0x10008000;m->regs[(CB(43)+0x64)/4]=1;
    CHECK(mi8_smmu_faults(&map,&f)&&f.far==0x110008000ull&&f.fsr==0x40a);
    CHECK(!mi8_smmu_clear_faults(&map,2)); /* Newly observed other bit cannot be silently cleared. */
    CHECK(m->values[m->writes-1]==2&&m->regs[(CB(43)+0x58)/4]==0x408);
    CHECK(mi8_smmu_clear_faults(&map,8)&&m->values[m->writes-1]==8);
    if(scenario==1)m->drop_forever=SMR(8);
    if(scenario==2)m->tlb_stuck=true;
    CHECK(mi8_smmu_end(&map,scenario!=3)==(scenario==0));
    CHECK(r.retained==(scenario!=0));CHECK(m->releases==(scenario==0));
    CHECK(!mi8_smmu_faults(&map,&f)&&!mi8_smmu_clear_faults(&map,~0u));
    free(m);
}

#include "mi8_audio_pcm.h"
struct finish_model {struct mi8_smmu_mapping *map;unsigned calls;};
static bool finish_end(void*v,bool safe){struct finish_model*f=v;f->calls++;CHECK(safe);return mi8_smmu_end(f->map,safe);}
static void finish_log(void*v,const char*text){(void)v;CHECK(text&&strlen(text)<320);}
static void finish_paths(void){
    for(unsigned mode=0;mode<3;mode++){
        struct model*m=fresh();struct mi8_smmu_mapping map;struct mi8_smmu_result r;
        const struct mi8_smmu_ops ops={m,read_reg,write_reg,wait_us,log_line,allocate,release,cache,table_read,&m->claim};
        m->regs[S2CR(8)/4]=0x200ff;m->s2cr_locked=true;
        CHECK(mi8_smmu_begin(&ops,&map,&r,true));
        unsigned before=m->writes;
        uint32_t*registers=malloc(sizeof(m->regs));CHECK(registers);memcpy(registers,m->regs,sizeof(m->regs));
        struct finish_model f={&map,0};
        const struct mi8_pcm_ops memory={.ctx=&f,.end=finish_end,.log=finish_log};
        struct mi8_pcm_state pcm={.io=&memory,.mapped=true,.result={.dsp_safe=mode==0}};
        CHECK(mi8_pcm_finish(&pcm,mode==1)==(mode!=2));
        if(mode==2){
            CHECK(!f.calls&&!m->releases&&pcm.result.retained&&map.active&&map.allocated);
            CHECK(m->writes==before&&!memcmp(registers,m->regs,sizeof(m->regs)));
            CHECK((m->regs[CB(43)/4]&1)&&m->regs[SMR(8)/4]==0x80001821);
        }else{
            CHECK(f.calls==1&&m->releases==1&&!pcm.result.retained&&!map.allocated);
            CHECK(r.restored&&!r.retained&&m->regs[S2CR(8)/4]==0x2b&&!m->regs[SMR(8)/4]);
            CHECK(!(m->regs[CB(43)/4]&1)&&logged(m,"S2CR sticky (inert: SMR invalid)"));
        }
        unsigned writes=m->writes;
        CHECK(mi8_pcm_finish(&pcm,mode==1)==(mode!=2));CHECK(m->writes==writes); /* no duplicate end/free */
        free(registers);free(m);
    }
}

int main(void){for(unsigned n=0;n<5;n++)dual_test(n);finish_paths();printf("Dual SMMU SELFTEST PASS %u/%u\n",checks,checks);return 0;}
