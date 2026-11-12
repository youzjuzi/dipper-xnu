/* SPDX-License-Identifier: MIT */
#include "mi8_tas2557.h"
#include <pthread.h>
#include <time.h>
#include <sched.h>
void mi8_tas2557_prepare(uint64_t);
void mi8_tas2557_prepare_tone(uint64_t);
#include "play-fixture.c"
#include "mi8_audio_ring.c"
extern void session_guard_tests(void);
extern void session_test_total(uint64_t);
extern void session_model_submit(bool);
extern void session_model_load(const char *,const char *);
extern bool session_model_prepare(unsigned);
extern void session_model_advance(uint64_t);
extern uint64_t session_model_now(void);
extern unsigned session_model_mutes(void),session_model_starts(void);
extern void session_model_check_done(void);
extern unsigned long session_model_checks(void);
static struct peer *active;
static unsigned mode,outputs,max_peak,ticks,stream_seconds=120;
static uint64_t stream_start;
static bool stop_requested,threaded,control_prepared;
static unsigned controller_quit,controller_delay;
static uint64_t controller_clock;
static pthread_t controller_thread;
static void *controller_main(void *unused){
 (void)unused;uint64_t next=0;
 while(!__atomic_load_n(&controller_quit,__ATOMIC_ACQUIRE)){
  uint64_t n=__atomic_load_n(&controller_clock,__ATOMIC_ACQUIRE);
  if(n>=next){session_model_advance(n);struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);if(!a.done)(void)mi8_tas_session_tick();next=n+controller_delay;}
  sched_yield();
 }
 mi8_tas_session_stop_request();(void)mi8_tas_session_tick();return NULL;
}
static bool muted(void){return mode==2;}
static bool join_control(void){
 if(!control_prepared)return false;
 mi8_tas_session_stop_request();
 if(threaded){
  if(controller_thread){__atomic_store_n(&controller_quit,1,__ATOMIC_RELEASE);CHECK(!pthread_join(controller_thread,NULL));controller_thread=0;}
  struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);CHECK(a.done);session_model_check_done();return a.clean;
 }
 session_model_advance(active->now);
 (void)mi8_tas_session_tick();active->now=session_model_now();
 struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);CHECK(a.done);session_model_check_done();return a.clean;
}
static void request_stop(void){stop_requested=true;mi8_tas_session_stop_request();}
static const struct mi8_pcm_session_ops session_ops={mi8_tas_session_snapshot,mi8_tas_session_wake,mi8_tas_session_mute,mi8_tas_session_zero,mi8_tas_session_count,request_stop,join_control,muted,mi8_tas_session_held,mi8_tas_session_fault,NULL};
void mi8_tas2557_prepare(uint64_t n){(void)n;CHECK(false);}
void mi8_tas2557_prepare_tone(uint64_t n){(void)n;CHECK(false);}
void mi8_tas_session_start(uint64_t end){CHECK(end>active->now);control_prepared=true;CHECK(session_model_prepare(0));active->now=session_model_now();stream_start=active->now;}
bool mi8_tas_session_join(void){return join_control();}
static void reset_ring(void){memset(ring_samples,0,sizeof(ring_samples));memset(&ring_counts,0,sizeof(ring_counts));ring_head=ring_tail=ring_ready=ring_gate=ring_started=0;mi8_audio_ring_ready();}
static void ring_feed(void){
 /* Deterministic scheduler: run one control turn at the simulated time. The
  * thread test separately exercises actual concurrent atomic publications. */
 if(threaded){
  __atomic_store_n(&controller_clock,active->now,__ATOMIC_RELEASE);
  /* A scheduler yield in the test clock, never a controller completion wait. */
  struct timespec pause={0,100000};nanosleep(&pause,NULL);
 } else {
 struct mi8_amp_snapshot before,after;mi8_tas_session_snapshot(&before);
 unsigned mutes=session_model_mutes();session_model_advance(active->now);
 if(!before.done)(void)mi8_tas_session_tick();
 active->now=session_model_now();ticks++;
 mi8_tas_session_snapshot(&after);
 if(before.request==2 && after.state==MI8_AMP_OFF_READY)CHECK(session_model_mutes()==mutes+1);
 }
 int16_t data[2048];uint64_t elapsed=active->now-stream_start;
 int value=32767;
 if(mode==1 || mode==4 || mode==7)value=(elapsed%((mode==7)?4500000:10000000))<800000?32767:0;
 if(mode==8)value=255;
 if(mode==9)value=256;
 if(mode==3 && elapsed>1000000)return;
 for(unsigned i=0;i<2048;i++)data[i]=(int16_t)value;
 (void)mi8_audio_ring_put(data,1024);
}
static void observe(struct peer *p,const uint8_t *q){
 struct play_peer *m=p->extension;uint32_t op=rd(q+16);
 if(op==0x10bcd || op==0x100e6){struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);CHECK(a.done);}
 if(op!=0x10dab)return;
 unsigned at=rd(q+20)-0x10000000;bool nz=false;CHECK(at+3840<=8*3840);
 for(unsigned i=0;i<960;i++){
  int l=(int16_t)(m->buffer[at+4*i]|m->buffer[at+4*i+1]<<8),r=(int16_t)(m->buffer[at+4*i+2]|m->buffer[at+4*i+3]<<8);
  unsigned a=l<0?-l:l;CHECK(l==r && a<=1036);if(a>max_peak)max_peak=a;nz|=a!=0;
 }
 session_model_submit(nz);
 if(nz){struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);CHECK(a.state==MI8_AMP_LIVE&&!a.request&&!a.reason&&!muted());outputs++;}
 if(mode==10 && outputs==20)m->fatal=true;
 if(mode==11 && outputs==20)m->ordinary_fault=true;
 if(mode==13 && m->writes==5)m->fatal=true;
}
static uint64_t audio_return_deadline,audio_lock_max_us,wifi_lock_wait_max_us;
static bool audio_session_dependency(void){return true;} /* Actual dependency policy tested separately. */
/* @session_worker */
int main(int argc,char **argv){
 CHECK(argc==3);session_guard_tests();threaded=getenv("SESSION_THREADS")!=NULL;if(getenv("SESSION_LONG"))stream_seconds=300;CHECK(mi8_pcm_session_seconds(stream_seconds));mi8_tas_session_seconds(stream_seconds);session_model_load(argv[1],argv[2]);
 for(mode=0;mode<=(stream_seconds==300?0u:threaded?2u:16u);mode++){
  reset_ring();outputs=max_peak=ticks=0;stop_requested=false;
  struct peer p;struct play_peer m;prepare(&p,&m);active=&p;m.step=16;
  control_prepared=true;CHECK(session_model_prepare(mode==5?1:mode==6?2:mode==12?3:mode==14?4:0)==(mode!=14));p.now=session_model_now();stream_start=p.now;
  if(mode==15 || mode==16)session_test_total(mode==15?59000001:59000000);
  if(threaded){controller_delay=mode==0?0:mode==1?50000:500000;controller_clock=p.now;controller_quit=0;CHECK(!pthread_create(&controller_thread,NULL,controller_main,NULL));}
  p.extension=&m;p.extra_response=play_reply;p.reply=p.header8=p.afe_mode=true;amp_observe=observe;amp_cache_observe=NULL;
  mi8_audio_set_ring(true);mi8_audio_set_session(&session_ops);
  struct mi8_audio_pin_ops pins={pin_read,pin_write,&p};struct mi8_glink_cfg c=cfg(&p);c.log=play_log;
  struct mi8_pcm_ops memory={.ctx=&p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
  bool ok=mi8_audio_run_play(&c,play_alive,&p,&pins,&memory,p.now+(uint64_t)(stream_seconds+10)*1000000,17,play_fatal);
  (void)join_control();m.reset=true;(void)mi8_audio_finish_play(true);
  struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);struct mi8_audio_ring_counts r;mi8_audio_ring_counts(&r);
  CHECK(a.done && stop_requested && r.accepted==r.consumed+r.discarded&&!r.queued && max_peak<=1036);
  fprintf(stderr,"debug mode=%u wakes=%u mutes=%u reason=%u clean=%u live=%llu\n",mode,a.wakes,a.mutes,a.reason,a.clean,(unsigned long long)a.live_total);
  if(threaded || (mode!=5 && mode!=6 && mode!=10 && mode!=11 && mode!=12 && mode!=13 && mode!=14)){if(!ok)fprintf(stderr,"mode %u %s\n",mode,m.log);CHECK(ok&&m.normal==stream_seconds*50);}
  if(!threaded){
  if(mode==0 || mode==9)CHECK(a.wakes>=3&&a.wakes<=4&&a.live_total<=60000000);
  if(mode==1 || mode==4)CHECK(a.wakes>=3 && a.checks==a.wakes-1 && a.checks_ok==a.checks);
  if(mode==2)CHECK(!outputs&&a.wakes==20);
  if(mode==3)CHECK(a.wakes==1&&a.mutes==1);
  if(mode==5)CHECK(a.reason==2&&a.checks>a.checks_ok);
  if(mode==6)CHECK(a.reason==4&&!outputs);
  if(mode==7)CHECK(a.wakes<=20&&a.live_total>59000000 && a.live_total<=60000000);
  if(mode==8 || mode==15)CHECK(!a.wakes&&!outputs);
  if(mode==16)CHECK(a.wakes==1&&a.live_total<=60000000);
  if(mode==10 || mode==11)CHECK(!ok&&outputs>0&&m.normal<6000);
  if(mode==12)CHECK(!ok&&a.reason==4&&outputs>0);
  if(mode==13)CHECK(!ok&&!outputs&&a.done);
  if(mode==14)CHECK(!ok&&a.reason==1&&!outputs&&m.normal==6000);
  }
  const struct mi8_pcm_session_stats *stats=mi8_pcm_session_stats();CHECK(stats->late_period<=m.normal);if(m.normal>100)CHECK(stats->done_gap_us>0);
  printf("session mode=%u periods=%u wakes=%u mutes=%u checks=%u/%u live=%llu blocks=%u peak=%u reason=%u PASS\n",mode,m.normal,a.wakes,a.mutes,a.checks_ok,a.checks,(unsigned long long)a.live_total,outputs,max_peak,a.reason);
  mi8_audio_set_session(NULL);mi8_audio_set_ring(false);
 }
 if(!threaded && stream_seconds==120)for(unsigned failure=0;failure<=3;failure++){
  mode=0;reset_ring();outputs=max_peak=ticks=0;control_prepared=false;
  struct peer p;struct play_peer m;prepare(&p,&m);active=&p;m.step=16;m.budget=130000000;p.extension=&m;
  worker_peer=&p;worker_memory=&m;worker_failure=failure;stop_ack=aop_off=true;
  adsp_started=false;adsp_last_stop_acked=adsp_last_aop_off=false;audio_play_locked=false;
  audio_ring_stream=true;audio_tail_on=true;audio_tail_len=0;pas_calls=stop_calls=aop_calls=unlocks=0;
  amp_observe=observe;amp_cache_observe=NULL;
  steps_audio_session((void *)(uintptr_t)17,0);
  CHECK(!audio_play_thread&&!audio_play_locked);
  if(!failure){CHECK(m.normal==6000&&pas_calls==1&&stop_calls==1&&aop_calls==1);CHECK(strstr(m.log,"audio=5:")&&strstr(m.log,"conservation=ok"));}
  else CHECK(!m.writes&&strstr(m.log,"FAILED"));
 }
 printf("Session integration SELFTEST PASS %lu/%lu\n",checks+session_model_checks(),checks+session_model_checks());return 0;
}
