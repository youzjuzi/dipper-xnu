/* SPDX-License-Identifier: MIT */
/* Reuse the SMEM/GLINK peer, exercising the real transport and APR engine. */
#define main apr_legacy_main
#include "mi8-audio-apr.c"
#undef main
#include "mi8_audio_pcm.h"
struct play_peer {
    uint8_t buffer[32768];
    uint32_t ops[200]; unsigned count,writes,normal,cache,begin,end,clear;
    uint32_t fail,drop,status;
    bool no_begin,no_end,retain,drop_writes,canary_timeout,canary_close_error,bad_map,bad_copp,ordinary_fault;
    unsigned canary_mode; /* 0=A CB fault, 1=B global fault, 2=neither, 3=A low FAR */
    struct mi8_smmu_fault fault;
    uint64_t last_write,budget;
};
static int play_reply(struct peer *p,const uint8_t *q,uint8_t *b,unsigned *n) {
    struct play_peer *m=p->extension;uint32_t op=rd(q+16);
    if(q[4]!=7&&q[4]!=8)return 0;
    CHECK(m->count<200);m->ops[m->count++]=op;
    b[4]=b[8]=q[4];memcpy(b+6,q+10,2);memcpy(b+10,q+6,2);
    *n=28;wr(b+16,0x110e8);wr(b+20,op);wr(b+24,op==m->fail?m->status:0);
    if(op==m->drop)return -1;
    if(op==m->fail)return 1;
    if(op==0x10d92){*n=24;wr(b+16,0x10d93);wr(b+20,m->bad_map?m->status:0x42);}
    if(op==0x10326){wr(b+16,0x10329);wr(b+20,0);wr(b+24,m->bad_copp?m->status:5);}
    if(op==0x10dab){
        uint64_t address=(uint64_t)rd(q+24)<<32|rd(q+20);
        bool canary=(uint32_t)address==0x10008000;
        CHECK(rd(q+28)==0x42&&rd(q+32)==3840&&rd(q+36)==rd(q+12));
        CHECK(!rd(q+40)&&!rd(q+44)&&!rd(q+48));
        m->writes++;
        if(!canary){
            CHECK(address>=0x110000000ull&&address+3840<=0x110008000ull);
            CHECK(!m->last_write||p->now-m->last_write>=20000);m->last_write=p->now;m->normal++;
            unsigned at=(unsigned)(address-0x110000000ull);
            for(unsigned i=0;i<960;i++){
                int16_t left=(int16_t)(m->buffer[at+4*i]|m->buffer[at+4*i+1]<<8);
                int16_t right=(int16_t)(m->buffer[at+4*i+2]|m->buffer[at+4*i+3]<<8);
                CHECK(left==right&&left>=-1000&&left<=1000);
                CHECK(left==(int16_t)(m->buffer[at+4*(i%48)]|m->buffer[at+4*(i%48)+1]<<8));
            }
            if(m->ordinary_fault)m->fault.fsr=2;
            if(m->drop_writes)return -1;
        }else{
            if(address>UINT32_MAX && (m->canary_mode==0||m->canary_mode==3)){
                m->fault.fsr=0x402;m->fault.far=m->canary_mode==3?(uint32_t)address:address;
            }
            if(address<=UINT32_MAX&&m->canary_mode==1)m->fault.gfsr=2;
            if(m->canary_timeout)return -1;
        }
        *n=36;wr(b+16,0x10d99);memcpy(b+20,q+20,12);wr(b+32,canary&&m->canary_mode!=2?1:0);
    }
    if(op==0x10bcd&&m->canary_close_error)wr(b+24,1);
    return 1;
}
static bool play_begin(void *v,struct mi8_pcm_memory *out){
    struct peer*p=v;struct play_peer*m=p->extension;m->begin++;
    if(m->no_begin)return false;
    *out=(struct mi8_pcm_memory){.buffer=m->buffer,.address=MI8_PCM_ADDRESS,.slot=8,.bank=43};return true;
}
static void play_cache(void*v,size_t at,size_t n){struct play_peer*m=((struct peer*)v)->extension;CHECK(n==3840&&at+n<=32768);m->cache++;}
static bool play_fault(void*v,struct mi8_smmu_fault*f){*f=((struct play_peer*)((struct peer*)v)->extension)->fault;return true;}
static bool play_clear(void*v,uint32_t observed){struct play_peer*m=((struct peer*)v)->extension;CHECK(observed==m->fault.fsr);m->clear++;m->fault.fsr=0x400;return true;}
static bool play_end(void*v,bool safe){
    struct peer*p=v;struct play_peer*m=p->extension;m->end++;m->retain=!safe||m->no_end;
    if(p->afe_count>=5)CHECK(p->actions[p->afe_count-2]==4&&p->actions[p->afe_count-1]==5);
    else CHECK(!safe);
    CHECK(p->pin_writes==8);for(unsigned i=0;i<4;i++)CHECK(p->pin_cfg[i]==p->saved_cfg[i]&&p->pin_io[i]==p->saved_io[i]);
    return !m->retain;
}
static bool run_play(struct peer *p,struct play_peer *m){
    p->extension=m;p->extra_response=play_reply;p->reply=p->header8=p->afe_mode=true;
    struct mi8_audio_pin_ops pins={pin_read,pin_write,p};
    struct mi8_glink_cfg c=cfg(p);
    struct mi8_pcm_ops memory={.ctx=p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
    return mi8_audio_run_play(&c,alive,p,&pins,&memory,p->now+(m->budget?m->budget:15000000));
}
static void prepare(struct peer*p,struct play_peer*m){
    init(p);memset(m,0,sizeof(*m));m->fault.fsr=0x400;m->status=1;
    for(unsigned i=0;i<4;i++){p->pin_cfg[i]=p->saved_cfg[i]=0x22;p->pin_io[i]=p->saved_io[i]=0;}
}
static bool saw(struct play_peer*m,uint32_t op){for(unsigned i=0;i<m->count;i++)if(m->ops[i]==op)return true;return false;}
static void integration(void){
    struct peer p;struct play_peer m;
    for(unsigned mode=0;mode<4;mode++){
        prepare(&p,&m);m.canary_mode=mode;CHECK(run_play(&p,&m));
        CHECK(mi8_audio_play_proven()==(mode==0||mode==3));CHECK(m.normal==150&&m.writes==152&&m.cache==150);
        CHECK(m.begin==1&&m.end==1&&!m.retain&&m.clear==4);CHECK(p.closes==1&&p.now<15000000&&p.logs<=45);
        CHECK(m.ops[0]==0x10d92&&m.ops[1]==0x10db3&&m.ops[2]==0x10326&&m.ops[3]==0x10325&&m.ops[4]==0x10d98&&m.ops[5]==0x10daa);
        CHECK(m.ops[m.count-3]==0x10bcd&&m.ops[m.count-2]==0x10d94&&m.ops[m.count-1]==0x10327);
        printf("play mode %u: %u log lines, %llu us, PROVEN=%u\n",mode,p.logs,(unsigned long long)p.now,mi8_audio_play_proven());
    }
    const uint32_t commands[]={0x10d92,0x10db3,0x10326,0x10325,0x10d98,0x10daa,0x10bcd,0x10d94,0x10327};
    for(unsigned i=0;i<9;i++)for(unsigned kind=0;kind<3;kind++){
        prepare(&p,&m);if(kind==2)m.drop=commands[i];else{m.fail=commands[i];m.status=kind==1?3:1;}
        CHECK(run_play(&p,&m)==(i==6&&kind==0));CHECK(p.closes==1&&p.now<=15000000&&p.logs<=45);CHECK(!mi8_audio_play_proven()||i>=6);
        if(i<6){CHECK(m.normal==0);for(unsigned j=i+1;j<6;j++)CHECK(!saw(&m,commands[j]));}
        if(i==0&&kind!=2){CHECK(!saw(&m,0x10bcd)&&!saw(&m,0x10d94)&&!saw(&m,0x10327));CHECK(!m.retain&&!p.pending_logs);}
        if(i==1&&kind!=2){CHECK(!saw(&m,0x10bcd)&&saw(&m,0x10d94));}
        if(i==2&&kind!=2)CHECK(!saw(&m,0x10327));
        if(i>=3&&i<6)CHECK(m.ops[m.count-3]==0x10bcd&&m.ops[m.count-2]==0x10d94&&m.ops[m.count-1]==0x10327);
    }
    for(unsigned action=1;action<=5;action++)for(unsigned unsupported=0;unsupported<2;unsupported++){
        prepare(&p,&m);p.fail_action=action;p.afe_status=unsupported?3:1;CHECK(!run_play(&p,&m));CHECK(p.closes==1&&p.pin_writes==8);
        if(action<=3)CHECK(!m.begin&&!m.end&&!m.count);else CHECK(m.end==1);
    }
    prepare(&p,&m);m.no_begin=true;CHECK(!run_play(&p,&m));CHECK(!m.end&&!m.count);
    prepare(&p,&m);m.no_end=true;CHECK(!run_play(&p,&m));CHECK(m.retain&&m.end==1);
    prepare(&p,&m);m.drop_writes=true;CHECK(!run_play(&p,&m));CHECK(m.retain&&p.now<=15000000);
    prepare(&p,&m);m.ordinary_fault=true;CHECK(!run_play(&p,&m));CHECK(m.normal==1&&!m.clear);
    prepare(&p,&m);m.canary_timeout=true;m.canary_close_error=true;CHECK(!run_play(&p,&m));CHECK(m.retain&&!saw(&m,0x10d94));
    prepare(&p,&m);m.canary_close_error=true;CHECK(run_play(&p,&m));CHECK(!m.retain&&saw(&m,0x10d94));
    prepare(&p,&m);m.bad_map=true;m.status=0;CHECK(!run_play(&p,&m));CHECK(m.retain&&!m.normal);
    prepare(&p,&m);m.bad_copp=true;m.status=0xffff;CHECK(!run_play(&p,&m));CHECK(!m.normal&&!saw(&m,0x10327));
    prepare(&p,&m);m.bad_map=true;m.status=UINT32_MAX;CHECK(!run_play(&p,&m));CHECK(m.retain&&!saw(&m,0x10d94));
    prepare(&p,&m);m.bad_copp=true;m.status=0xff;CHECK(!run_play(&p,&m));CHECK(!saw(&m,0x10327));
    prepare(&p,&m);p.amp_high=true;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin);
    prepare(&p,&m);p.legacy=true;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin);
    prepare(&p,&m);m.budget=1000000;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin&&p.now<=m.budget);
    prepare(&p,&m);m.budget=6000000;m.drop_writes=true;CHECK(!run_play(&p,&m));CHECK(m.retain&&p.now<=m.budget);
    prepare(&p,&m);p.bad_afe_version=true;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin);
}
static void event_packet(uint8_t*b,unsigned token,uint64_t address,unsigned handle,unsigned status){
    memset(b,0,48);b[0]=0x81;b[2]=48;b[4]=b[8]=7;b[5]=4;b[9]=5;b[6]=b[7]=b[10]=b[11]=1;
    wr(b+12,token);wr(b+16,0x10d99);wr(b+32,(uint32_t)address);wr(b+36,(uint32_t)(address>>32));wr(b+40,handle);wr(b+44,status);
}
static void events(void){
    struct mi8_pcm_state s={0};uint8_t b[48];
    for(unsigned i=0;i<8;i++)s.jobs[i]=(struct mi8_pcm_job){MI8_PCM_ADDRESS+i*3840,100+i,0x42,~0u,true,false};
    for(unsigned k=0;k<10;k++){
        event_packet(b,100,MI8_PCM_ADDRESS,0x42,0);
        if(k==0)b[12]++;
        if(k==1)b[4]=8;
        if(k==2)b[6]=2;
        if(k==3)b[10]=2;
        if(k==4)b[5]=5;
        if(k==5)b[9]=4;
        if(k==6)b[0]=0x80;
        if(k==7)b[2]=47;
        if(k==8)b[40]++;
        if(k==9)b[32]++;
        CHECK(mi8_pcm_receive(&s,b,48));CHECK(s.jobs[0].active&&!s.result.done);
    }
    for(unsigned i=8;i--;){event_packet(b,100+i,MI8_PCM_ADDRESS+i*3840,0x42,0);CHECK(mi8_pcm_receive(&s,b,48));CHECK(!s.jobs[i].active&&s.result.done==8-i);CHECK(mi8_pcm_receive(&s,b,48));CHECK(s.result.done==8-i);}
    s.jobs[0]=(struct mi8_pcm_job){MI8_PCM_ADDRESS,200,0x42,~0u,true,false};event_packet(b,200,MI8_PCM_ADDRESS,0x42,3);
    CHECK(mi8_pcm_receive(&s,b,48)&&s.result.unsupported&&s.result.failed_opcode==0x10dab&&s.result.dsp_status==3);
    s.jobs[0]=(struct mi8_pcm_job){MI8_PCM_ADDRESS,201,0x42,~0u,true,false};event_packet(b,201,MI8_PCM_ADDRESS,0x42,1);
    CHECK(mi8_pcm_receive(&s,b,48)&&!s.jobs[0].active&&s.result.done==8);
    /* BASIC with the right token but wrong original command cannot release it. */
    s.jobs[0]=(struct mi8_pcm_job){MI8_PCM_ADDRESS,202,0x42,~0u,true,false};event_packet(b,202,MI8_PCM_ADDRESS,0x42,0);
    wr(b+16,0x110e8);b[2]=40;wr(b+32,0x10daa);wr(b+36,3);CHECK(!mi8_pcm_receive(&s,b,40)&&s.jobs[0].active);
    wr(b+32,0x10dab);CHECK(mi8_pcm_receive(&s,b,40)&&!s.jobs[0].active);
    event_packet(b,0,0,0,0);b[2]=32;wr(b+16,0x10c17);CHECK(mi8_pcm_receive(&s,b,32)&&s.result.underflow==1);
    b[6]=2;CHECK(mi8_pcm_receive(&s,b,32)&&s.result.underflow==1);
}
static void layouts(void){
    static const unsigned sizes[]={0,36,40,48,36,44,32,20,24,20};uint8_t b[68];size_t n;
    for(unsigned a=1;a<=9;a++){
        CHECK(!mi8_pcm_encode(a,9,0x42,5,b,sizeof(b),&n)&&n==sizes[a]);
        CHECK(b[0]==0x50&&b[1]==2&&b[2]==n&&rd(b+12)==9&&b[5]==5&&b[9]==4);
    }
    mi8_pcm_encode(MI8_PCM_OPEN,1,0,0,b,sizeof(b),&n);CHECK(rd(b+20)==0&&rd(b+24)==0x100000&&rd(b+28)==0x10c68&&rd(b+32)==0x10da5);
    mi8_pcm_encode(MI8_PCM_MAP,1,0,0,b,sizeof(b),&n);CHECK(rd(b+20)==0x10003&&!rd(b+24)&&rd(b+28)==0x10000000&&rd(b+32)==1&&rd(b+36)==32768);
    mi8_pcm_encode(MI8_PCM_ADM_OPEN,1,0,0,b,sizeof(b),&n);CHECK(rd(b+20)==0x10000&&rd(b+24)==0xffff1006&&rd(b+28)==0x10312&&rd(b+32)==0x100002&&rd(b+36)==48000&&rd(b+40)==0x201&&!rd(b+44));
    mi8_pcm_encode(MI8_PCM_ROUTE,1,0,5,b,sizeof(b),&n);CHECK(!rd(b+20)&&rd(b+24)==1&&rd(b+28)==0x10001&&rd(b+32)==5);
    mi8_pcm_encode(MI8_PCM_FORMAT,1,0,0,b,sizeof(b),&n);CHECK(rd(b+20)==20&&rd(b+24)==0x100002&&rd(b+28)==48000&&rd(b+32)==1&&rd(b+36)==0x201&&!rd(b+40));
    mi8_pcm_encode(MI8_PCM_ADM_CLOSE,1,0,5,b,sizeof(b),&n);CHECK(b[6]==6&&b[7]==16&&b[10]==5&&!b[11]);
    struct mi8_smmu_fault before={.fsr=0x400},after={.fsr=0x402,.far=0x110008000ull};
    CHECK(mi8_pcm_canary_verdict(0x110008000ull,&before,&after)==1);
    after.far=0x10008000;CHECK(mi8_pcm_canary_verdict(0x110008000ull,&before,&after)==1);
    after.far=7;CHECK(!mi8_pcm_canary_verdict(0x110008000ull,&before,&after));
    after.gfsr=2;CHECK(mi8_pcm_canary_verdict(0x110008000ull,&before,&after)==2);
    after=(struct mi8_smmu_fault){.fsr=0x400};CHECK(!mi8_pcm_canary_verdict(0x110008000ull,&before,&after));
}
int main(void){layouts();events();integration();printf("PCM SELFTEST PASS %u/%u\n",checks,checks);return 0;}
