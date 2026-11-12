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
    bool fatal,fatal_canary,fatal_close,hung,reset,no_pas,no_begin,no_end,retain,drop_writes,canary_timeout,canary_close_error,bad_map,bad_copp,ordinary_fault;
    unsigned step,after_fatal;
    unsigned canary_mode; /* 0=A CB fault, 1=B global fault, 2=neither, 3=A low FAR */
    struct mi8_smmu_fault fault;
    uint64_t last_write,budget,canary_at,close_at,adm_at;
    char log[16384];size_t log_length;
};
#ifdef MI8_AMP_TEST
static void (*amp_observe)(struct peer *,const uint8_t *);
static void (*amp_cache_observe)(struct peer *,size_t);
#endif
static int play_reply(struct peer *p,const uint8_t *q,uint8_t *b,unsigned *n) {
    struct play_peer *m=p->extension;uint32_t op=rd(q+16);
#ifdef MI8_AMP_TEST
    if(amp_observe)amp_observe(p,q);
#endif
    if(m->fatal)m->after_fatal++;
    if(q[4]!=7&&q[4]!=8)return 0;
    CHECK(m->count<200);m->ops[m->count++]=op;
    b[4]=b[8]=q[4];memcpy(b+6,q+10,2);memcpy(b+10,q+6,2);
    *n=28;wr(b+16,0x110e8);wr(b+20,op);wr(b+24,op==m->fail?m->status:0);
    if(op==0x10bcd){m->close_at=p->now;if(m->fatal_close){m->fatal=true;return -1;}}
    if(op==0x10327)m->adm_at=p->now;
    if(m->hung&&(op==0x10bcd||op==0x10327))return -1;
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
            CHECK(m->step==15||!m->last_write||p->now-m->last_write>=20000);m->last_write=p->now;m->normal++;
            unsigned at=(unsigned)(address-0x110000000ull);
            for(unsigned i=0;i<960;i++){
                int16_t left=(int16_t)(m->buffer[at+4*i]|m->buffer[at+4*i+1]<<8);
                int16_t right=(int16_t)(m->buffer[at+4*i+2]|m->buffer[at+4*i+3]<<8);
                CHECK(left==right&&left>=-1000&&left<=1000);
                if(m->step==15)CHECK(!left && !right);
                CHECK(left==(int16_t)(m->buffer[at+4*(i%48)]|m->buffer[at+4*(i%48)+1]<<8));
            }
            if(m->ordinary_fault)m->fault.fsr=2;
            if(m->drop_writes)return -1;
        }else{
            m->canary_at=p->now;
            if(address>UINT32_MAX && (m->canary_mode==0||m->canary_mode==3)){
                m->fault.fsr=0x402;m->fault.far=m->canary_mode==3?(uint32_t)address:address;
            }
            if(address<=UINT32_MAX&&m->canary_mode==1)m->fault.gfsr=2;
            if(m->fatal_canary)m->fatal=true;
            if(m->canary_timeout||m->hung||m->fatal)return -1;
        }
        *n=36;wr(b+16,0x10d99);memcpy(b+20,q+20,12);wr(b+32,canary?2:0);
    }
    if(op==0x10bcd&&m->canary_close_error)wr(b+24,1);
    return 1;
}
static bool play_begin(void *v,struct mi8_pcm_memory *out){
    struct peer*p=v;struct play_peer*m=p->extension;m->begin++;
    if(m->no_begin)return false;
    *out=(struct mi8_pcm_memory){.buffer=m->buffer,.address=MI8_PCM_ADDRESS,.slot=8,.bank=43};return true;
}
static void play_cache(void*v,size_t at,size_t n){struct play_peer*m=((struct peer*)v)->extension;CHECK(n==3840&&at+n<=32768);m->cache++;
#ifdef MI8_AMP_TEST
    if(amp_cache_observe)amp_cache_observe(v,at);
#endif
}
static bool play_fault(void*v,struct mi8_smmu_fault*f){*f=((struct play_peer*)((struct peer*)v)->extension)->fault;return true;}
static bool play_clear(void*v,uint32_t observed){struct play_peer*m=((struct peer*)v)->extension;CHECK(observed==m->fault.fsr);m->clear++;m->fault.fsr=0x400;return true;}
static bool play_end(void*v,bool safe){
    struct peer*p=v;struct play_peer*m=p->extension;m->end++;m->retain=!safe||m->no_end;
    if(p->afe_count>=5)CHECK(p->actions[p->afe_count-2]==4&&p->actions[p->afe_count-1]==5);
    else CHECK(m->reset||!safe);
    CHECK(p->pin_writes==8);for(unsigned i=0;i<4;i++)CHECK(p->pin_cfg[i]==p->saved_cfg[i]&&p->pin_io[i]==p->saved_io[i]);
    return !m->retain;
}
static void play_log(void*v,const char*fmt,...){
    struct peer*p=v;struct play_peer*m=p->extension;char line[512];va_list ap;
    va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
    log_line(v,"%s",line);size_t n=strlen(line);CHECK(m->log_length+n<sizeof(m->log));
    memcpy(m->log+m->log_length,line,n+1);m->log_length+=n;
}
static bool play_fatal(void*v){return ((struct play_peer*)((struct peer*)v)->extension)->fatal;}
static bool play_alive(void*v){return !play_fatal(v)&&alive(v);}
static bool start_play(struct peer *p,struct play_peer *m){
    p->extension=m;p->extra_response=play_reply;p->reply=p->header8=p->afe_mode=true;
    struct mi8_audio_pin_ops pins={pin_read,pin_write,p};
    struct mi8_glink_cfg c=cfg(p);c.log=play_log;
    struct mi8_pcm_ops memory={.ctx=p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
    return mi8_audio_run_play(&c,play_alive,p,&pins,&memory,p->now+(m->budget?m->budget:15000000),m->step?m->step:13,play_fatal);
}
static bool run_play(struct peer*p,struct play_peer*m){
    bool okay=start_play(p,m),deferred=mi8_audio_play_needs_finish();
    if(deferred)CHECK(!m->end&&!p->closes);
    m->reset=!m->no_pas;
    bool clean=mi8_audio_finish_play(m->reset);
    if(deferred&&!m->reset&&!m->end)m->retain=true;
    CHECK(!mi8_audio_play_needs_finish());
    return okay&&clean;
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
        CHECK(mi8_audio_play_proven()==(mode==0||mode==3));CHECK(m.normal==150&&m.writes==((mode==0||mode==3)?151u:152u)&&m.cache==150);
        CHECK(m.begin==1&&m.end==1&&!m.retain&&m.clear==((mode==0||mode==3)?2u:4u));CHECK(p.closes==1&&p.now<15000000&&p.logs<=45);
        CHECK(m.ops[0]==0x10d92&&m.ops[1]==0x10db3&&m.ops[2]==0x10326&&m.ops[3]==0x10325&&m.ops[4]==0x10d98&&m.ops[5]==0x10daa);
        CHECK(m.ops[m.count-3]==0x10bcd&&m.ops[m.count-2]==0x10d94&&m.ops[m.count-1]==0x10327);
        printf("play mode %u: %u log lines, %llu us, PROVEN=%u\n",mode,p.logs,(unsigned long long)p.now,mi8_audio_play_proven());
    }
    const uint32_t commands[]={0x10d92,0x10db3,0x10326,0x10325,0x10d98,0x10daa,0x10bcd,0x10d94,0x10327};
    for(unsigned i=0;i<9;i++)for(unsigned kind=0;kind<3;kind++){
        prepare(&p,&m);if(kind==2)m.drop=commands[i];else{m.fail=commands[i];m.status=kind==1?3:1;}
        CHECK(!run_play(&p,&m));CHECK(p.closes==1&&p.now<=15000000&&p.logs<=45);CHECK(!mi8_audio_play_proven()||i>=6);
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
    prepare(&p,&m);m.drop_writes=true;CHECK(!run_play(&p,&m));CHECK(!m.retain&&p.now<=17000000);
    prepare(&p,&m);m.ordinary_fault=true;CHECK(!run_play(&p,&m));CHECK(m.normal==1&&!m.clear);
    prepare(&p,&m);m.canary_timeout=true;m.canary_close_error=true;CHECK(!run_play(&p,&m));CHECK(!m.retain&&!saw(&m,0x10d94));
    prepare(&p,&m);m.canary_close_error=true;CHECK(!run_play(&p,&m));CHECK(!m.retain&&!saw(&m,0x10d94));
    prepare(&p,&m);m.bad_map=true;m.status=0;CHECK(!run_play(&p,&m));CHECK(!m.retain&&!m.normal);
    prepare(&p,&m);m.bad_copp=true;m.status=0xffff;CHECK(!run_play(&p,&m));CHECK(!m.normal&&!saw(&m,0x10327));
    prepare(&p,&m);m.bad_map=true;m.status=UINT32_MAX;CHECK(!run_play(&p,&m));CHECK(!m.retain&&!saw(&m,0x10d94));
    prepare(&p,&m);m.bad_copp=true;m.status=0xff;CHECK(!run_play(&p,&m));CHECK(!saw(&m,0x10327));
    prepare(&p,&m);p.amp_high=true;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin);
    prepare(&p,&m);p.legacy=true;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin);
    prepare(&p,&m);m.budget=1000000;CHECK(!run_play(&p,&m));CHECK(!p.pin_writes&&!m.begin&&p.now<=m.budget);
    prepare(&p,&m);m.budget=6000000;m.drop_writes=true;CHECK(!run_play(&p,&m));CHECK(!m.retain&&p.now<=m.budget+2500000);
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
    mi8_pcm_encode(MI8_PCM_MAP,1,0,0,b,sizeof(b),&n);CHECK(rd(b+20)==0x10003&&!rd(b+24)&&rd(b+28)==0x10000000&&rd(b+32)==1&&rd(b+36)==65536);
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

/* Execute the real rproc worker and PAS shutdown ordering with fake hardware.
 * The APR/GLINK/AFE/PCM stack above stays real; only the SCM boundary is fake. */
#define __unused __attribute__((unused))
#define NSEC_PER_MSEC 1000000
#define SCM_PAS_SHUTDOWN 1
#define SCM_ONE_VALUE 1
#define PAS_ADSP 1
typedef int wait_result_t;
static struct peer *worker_peer;
static struct play_peer *worker_memory;
static bool adsp_started,adsp_last_stop_acked,adsp_last_aop_off;
static bool audio_play_brief,audio_play_locked,stop_ack,aop_off;
static void *audio_play_thread;
static uint64_t audio_play_until;
static char audio_play_note[400];
static int wsmmu_lock;
static unsigned pas_calls,stop_calls,aop_calls,unlocks;
static uint64_t worker_now_us(void){return worker_peer->now;}
static int worker_say(const char *fmt,...){
    char line[512];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
    if(audio_play_brief)snprintf(audio_play_note,sizeof(audio_play_note),"%.399s",line);
    else play_log(worker_peer,"%s",line);
    return 0;
}
static bool audio_play_worker(void){return audio_play_thread!=NULL;}
static bool dsp_ask_to_stop(unsigned ms){
    CHECK(ms>0&&ms<=3000);CHECK(worker_peer->pin_writes==8);stop_calls++;
    if(!stop_ack)worker_peer->now+=(uint64_t)ms*1000;
    return stop_ack;
}
static int32_t scm(const char*why,unsigned cmd,unsigned nargs,unsigned dsp,unsigned b,unsigned c,unsigned d,uint64_t*answer){
    (void)why;CHECK(cmd==SCM_PAS_SHUTDOWN&&nargs==SCM_ONE_VALUE&&dsp==PAS_ADSP&&!b&&!c&&!d);
    CHECK(worker_memory->fatal ? worker_peer->afe_count==3 : worker_peer->afe_count==5&&worker_peer->actions[3]==4&&worker_peer->actions[4]==5);
    CHECK(worker_memory->end==((worker_memory->hung||worker_memory->fatal)?0u:1u));
    CHECK(audio_play_locked==(worker_memory->hung||worker_memory->fatal));pas_calls++;
    worker_memory->reset=!worker_memory->no_pas;*answer=worker_memory->no_pas?1:0;
    play_log(worker_peer,"PAS boundary: %s\n",*answer?"failed":"reset confirmed");
    return 0;
}
static bool qmp_send(const char*text){
    CHECK(strstr(text,"val: off"));aop_calls++;
    worker_say(aop_off?"mi8rp: qmp: the AOP has taken it\n":"mi8rp: qmp: THE AOP DOES NOT TAKE THE MESSAGE within a second; taken back\n");
    return aop_off;
}
/* @dsp_shutdown */
static int redwood_ufs_read_named(const char*n,unsigned a,void*p,unsigned b){(void)n;(void)a;(void)p;(void)b;return 0;}
static void delay_for_interval(unsigned ms,unsigned unit){(void)unit;worker_peer->now+=(uint64_t)ms*1000;}
static void step_firmware(void){worker_peer->now+=11000000;CHECK(audio_play_until==45000000);}
static void step_aop(void){}
#ifdef MI8_AMP_TEST
static unsigned worker_failure;
#endif
static bool step_header(void){
#ifdef MI8_AMP_TEST
    if(worker_failure==1)return false;
#endif
    return true;
}
static bool step_image(void){return true;}
static bool adsp_glink_prepare(void){
#ifdef MI8_AMP_TEST
    if(worker_failure==2)return false;
#endif
    return true;
}
static bool step_start(void){
#ifdef MI8_AMP_TEST
    if(worker_failure==3)return false;
#endif
    adsp_started=true;return true;
}
static bool adsp_audio_handshake(uint32_t last){
    CHECK(last==13||last==15);audio_play_locked=true;
    bool okay=start_play(worker_peer,worker_memory);
    audio_play_until=mi8_audio_play_teardown_end();
    if(!mi8_audio_play_needs_finish())audio_play_locked=false;
    return okay;
}
static void lck_mtx_unlock(int*lock){CHECK(lock==&wsmmu_lock&&audio_play_locked);unlocks++;}
static void *current_thread(void){return worker_peer;}
static void thread_terminate(void*t){CHECK(t==worker_peer);}
#ifndef MI8_AMP_TEST
static bool mi8_tas2557_held(void){CHECK(false);return false;}
static bool mi8_tas2557_tick(uint64_t a,uint64_t b){(void)a;(void)b;CHECK(false);return false;}
static void mi8_tas2557_stop(void){CHECK(false);}
static void mi8_tas2557_prepare(uint64_t end){(void)end;CHECK(false);}
static void mi8_tas2557_report(const char *s){(void)s;CHECK(false);}
#endif
static const struct mi8_pcm_amp audio_amp_ops={mi8_tas2557_held,mi8_tas2557_tick,mi8_tas2557_stop};
/* @steps_from_five */
static void log_order(const char*text,const char*const*lines,unsigned n){
    for(unsigned i=0;i<n;i++){const char*at=strstr(text,lines[i]);CHECK(at);text=at+strlen(lines[i]);}
}
static unsigned count_op(struct play_peer*m,uint32_t op){unsigned n=0;for(unsigned i=0;i<m->count;i++)n+=m->ops[i]==op;return n;}
static void lifecycle(void){
    struct peer p;struct play_peer m;
    for(unsigned scenario=0;scenario<5;scenario++){
        prepare(&p,&m);worker_peer=&p;worker_memory=&m;
        p.extension=&m;m.canary_mode=scenario?3:2;m.hung=scenario!=0;m.no_pas=scenario==2;
        if(scenario==3)p.drop_stop=p.drop_off=true;
        if(scenario==4)m.fatal_canary=true;
        stop_ack=aop_off=scenario==0;pas_calls=stop_calls=aop_calls=unlocks=0;
        steps_from_five((void*)(uintptr_t)13,0);
        CHECK(pas_calls==1&&stop_calls==1&&aop_calls==1);
        CHECK(!audio_play_locked&&!audio_play_thread&&!mi8_audio_play_needs_finish());
        CHECK(m.normal==150&&m.writes==(scenario?151u:152u));
        CHECK(mi8_audio_play_proven()==(scenario!=0));
        CHECK(count_op(&m,0x10bcd)==(scenario==4?0u:1u)&&count_op(&m,0x10327)==(scenario==4?0u:1u));
        CHECK(p.pin_writes==8&&(scenario==4?p.afe_count==3:p.actions[3]==4&&p.actions[4]==5));
        CHECK(m.end==(scenario==2?0u:1u)&&unlocks==(scenario?1u:0u));
        if(scenario==4){
            CHECK(!m.after_fatal&&mi8_audio_play_proven());
            CHECK(strstr(m.log,"ADSP fatal; APR teardown skipped, PAS shutdown required"));
            CHECK(strstr(m.log,"cleanup=Pending (AFE: DSP fatal) (stop-ack missing) (AOP off Pending)"));
            const char*const lines[]={"translation: ENGAGED","ADSP fatal; APR teardown skipped","pins restored","PAS boundary: reset confirmed","smmu: end inert","channel close local","cleanup=Pending (AFE: DSP fatal)"};
            log_order(m.log,lines,sizeof(lines)/sizeof(*lines));
        }else if(scenario){
            CHECK(m.close_at-m.canary_at<=500000&&m.adm_at-m.close_at<=500000);
            CHECK(m.adm_at-m.close_at==500000); /* No hidden drain or retry. */
            CHECK(!saw(&m,0x10d94)&&!strstr(m.log,"canary B:"));
            CHECK(strstr(m.log,"canary A: asm status=0xffffffff timeout GFSR=0 FSR=0x402 FAR=0x10008000"));
            CHECK(strstr(m.log,"translation: ENGAGED (canary A, SMMU saw FAR=0x10008000 low32)"));
            const char*const lines[]={"canary A:","translation: ENGAGED","asm stream close","adm device close",
                "afe port 0x1006 stop","afe clock off",scenario==3?"AFE FAILED; cleanup Pending":"pins restored",
                "PAS boundary:","ADSP shutdown",scenario==2?"mapping unchanged, memory retained":"memory released",
                "channel close local","Pending ADSP stop-ack","Pending AOP off","step 13: PROVEN=1 cleanup="};
            log_order(m.log,lines,sizeof(lines)/sizeof(*lines));
            CHECK(strstr(m.log,scenario==1?"cleanup=complete (stop-ack missing) (AOP off Pending)":(scenario==2?"cleanup=Pending (PAS, SMMU)":"cleanup=Pending (AFE)")));
            CHECK(strstr(m.log,"taken back"));
            if(scenario==2)CHECK(strstr(m.log,"Pending PAS shutdown"));
        }else{
            const char*const lines[]={"canary A: asm status=0x2","canary B: asm status=0x2","translation: NOT PROVEN",
                "asm stream close errno=0 status=0","asm unmap regions errno=0 status=0","adm device close errno=0 status=0",
                "afe port 0x1006 stop status=0","afe clock off status=0","smmu: end inert","pins restored",
                "channel close errno=0","ADSP shutdown ok","step 13: PROVEN=0 cleanup=complete"};
            log_order(m.log,lines,sizeof(lines)/sizeof(*lines));
        }
        printf("LIFECYCLE scenario %u BEGIN\n%sLIFECYCLE scenario %u END\n",scenario,m.log,scenario);
    }
    prepare(&p,&m);m.hung=true;m.fatal_close=true;CHECK(!run_play(&p,&m));
    CHECK(m.fatal&&!m.after_fatal&&!m.adm_at&&p.afe_count==3&&p.pin_writes==8);
    CHECK(strstr(m.log,"ADSP fatal; APR teardown skipped")&&strstr(mi8_audio_play_cleanup(),"AFE: DSP fatal"));
    for(unsigned step=14;step<=16;step++){
        prepare(&p,&m);m.step=step;CHECK(run_play(&p,&m));CHECK(m.writes==150&&!m.clear&&!mi8_audio_play_proven());
        CHECK(!strstr(m.log,"canary ")&&!strstr(m.log,"translation:"));
    }
    /* A timeout without a CB fault must still attempt B and cannot prove DMA. */
    prepare(&p,&m);m.canary_mode=2;m.canary_timeout=true;
    CHECK(run_play(&p,&m)&&!mi8_audio_play_proven()&&m.writes==152);
    CHECK(strstr(m.log,"canary A:")&&strstr(m.log,"canary B:")&&strstr(m.log,"translation: NOT PROVEN"));
    /* Proof survives a failed detach; incomplete cleanup must not erase it. */
    prepare(&p,&m);m.hung=true;m.canary_mode=3;m.no_end=true;
    CHECK(!run_play(&p,&m)&&mi8_audio_play_proven()&&m.retain&&m.end==1);
}

int main(void){layouts();events();integration();lifecycle();printf("PCM SELFTEST PASS %u/%u\n",checks,checks);return 0;}
