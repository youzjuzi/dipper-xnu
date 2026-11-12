/* SPDX-License-Identifier: MIT */
/* Real ring and protocol integration, deterministic model plus SPSC stress. */
#include <pthread.h>
#include <stdatomic.h>
#include <sched.h>
#define MI8_RING_TEST
#include "ring-play.inc"
#undef main
#include "mi8_audio_ring.c"
static atomic_uint concurrent_checks;
#define VERIFY(x) do {atomic_fetch_add(&concurrent_checks,1);if(!(x))abort();}while(0)
static void reset_ring(void){memset(ring_samples,0,sizeof(ring_samples));memset(&ring_counts,0,sizeof(ring_counts));ring_head=ring_tail=ring_ready=ring_gate=ring_started=0;}
static unsigned rng=0x125acced;
static unsigned random_word(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void model(void){
 reset_ring();CHECK(!mi8_audio_ring_open());mi8_audio_ring_ready();
 int16_t in[2048],out[1920];for(unsigned i=0;i<2048;i++)in[i]=(int16_t)(i&1?32767:-32768);
 CHECK(mi8_audio_ring_put(in,1024)==1024);CHECK(ring_counts.outside==1024);CHECK(mi8_audio_ring_open());CHECK(!mi8_audio_ring_open());
 CHECK(!mi8_audio_ring_take(out,960));CHECK(ring_counts.underflow_frames==960);
 for(unsigned i=0;i<16;i++)CHECK(mi8_audio_ring_put(in,1024)==1024);
 CHECK(!mi8_audio_ring_put(in,1));CHECK(mi8_audio_ring_take(out,1)==1);CHECK(mi8_audio_ring_put(in,1024)==1);
 CHECK(mi8_audio_ring_close());CHECK(ring_counts.accepted==ring_counts.consumed+ring_counts.discarded);
 CHECK(mi8_audio_ring_put(in,3)==3&&ring_counts.outside==1027);
 reset_ring();mi8_audio_ring_ready();CHECK(mi8_audio_ring_open());
 uint64_t head=0,tail=0;int16_t expected[32768];
 for(unsigned op=0;op<100000;op++){
  unsigned n=1+random_word()%1024;
  if(random_word()&1){
   for(unsigned i=0;i<n;i++){in[2*i]=(int16_t)(op+i);in[2*i+1]=(int16_t)~(op+i);}
   unsigned take=n;if(take>16384-(head-tail))take=(unsigned)(16384-(head-tail));
   CHECK(mi8_audio_ring_put(in,n)==take);
   for(unsigned i=0;i<take;i++){unsigned at=(unsigned)(head+i)&16383;expected[2*at]=in[2*i];expected[2*at+1]=in[2*i+1];}head+=take;
  }else{
   n=1+random_word()%960;unsigned take=n;if(take>head-tail)take=(unsigned)(head-tail);
   CHECK(mi8_audio_ring_take(out,n)==take);
   for(unsigned i=0;i<take;i++){unsigned at=(unsigned)(tail+i)&16383;CHECK(out[2*i]==expected[2*at]&&out[2*i+1]==expected[2*at+1]);}tail+=take;
  }
  struct mi8_audio_ring_counts r;mi8_audio_ring_counts(&r);CHECK(r.accepted==r.consumed+r.queued&&r.queued==head-tail);
 }
 CHECK(mi8_audio_ring_close());CHECK(ring_counts.accepted==ring_counts.consumed+ring_counts.discarded);
 /* Deterministically stop a producer after admission, then finish publication. */
 reset_ring();mi8_audio_ring_ready();CHECK(mi8_audio_ring_open());ring_gate=3;
 CHECK(!mi8_audio_ring_close()&&ring_gate==2&&!ring_counts.discarded);
 ring_samples[0]=-32768;ring_samples[1]=32767;ring_counts.accepted=1;RSTORE(&ring_head,1);
 __atomic_fetch_and(&ring_gate,~2u,__ATOMIC_RELEASE);CHECK(mi8_audio_ring_close());CHECK(ring_counts.discarded==1);
 printf("Ring fixed-seed model: 100000 operations PASS\n");
}
#define TOTAL 2000000u
static atomic_bool producer_done;
static void *producer(void *unused){
 (void)unused;uint32_t at=0;int16_t in[2048];
 while(at<TOTAL){unsigned n=TOTAL-at;if(n>1024)n=1024;
  for(unsigned i=0;i<n;i++){in[2*i]=(int16_t)(at+i);in[2*i+1]=(int16_t)((at+i)>>16);}
  unsigned taken=mi8_audio_ring_put(in,n);VERIFY(taken<=n);at+=taken;if(!taken)sched_yield();
 }
 atomic_store(&producer_done,true);return NULL;
}
static void *consumer(void *unused){
 (void)unused;uint32_t at=0;int16_t out[1920];
 while(at<TOTAL){unsigned n=mi8_audio_ring_take(out,960);
  for(unsigned i=0;i<n;i++){uint32_t got=(uint16_t)out[2*i]|(uint32_t)(uint16_t)out[2*i+1]<<16;VERIFY(got==at++);}
  if(!n)sched_yield();
 }
 return NULL;
}
static void concurrency(void){
 reset_ring();mi8_audio_ring_ready();CHECK(mi8_audio_ring_open());pthread_t p,c;
 CHECK(!pthread_create(&p,NULL,producer,NULL));CHECK(!pthread_create(&c,NULL,consumer,NULL));
 CHECK(!pthread_join(p,NULL));CHECK(!pthread_join(c,NULL));CHECK(atomic_load(&producer_done));
 CHECK(mi8_audio_ring_close());CHECK(ring_counts.accepted==TOTAL&&ring_counts.consumed==TOTAL&&!ring_counts.discarded);
 printf("Ring SPSC: %u ordered unique frames PASS\n",TOTAL);
}
static void close_race(void){
 reset_ring();mi8_audio_ring_ready();CHECK(mi8_audio_ring_open());atomic_store(&producer_done,false);
 pthread_t p;CHECK(!pthread_create(&p,NULL,producer,NULL));int16_t out[1920];uint64_t consumed=0;
 while(consumed<100000)consumed+=mi8_audio_ring_take(out,960);
 while(!mi8_audio_ring_close())sched_yield();
 CHECK(!pthread_join(p,NULL));struct mi8_audio_ring_counts r;mi8_audio_ring_counts(&r);
 CHECK(!r.queued&&r.accepted==r.consumed+r.discarded&&r.outside>0);
 printf("Ring close concurrent with producer: conservation PASS\n");
}
static void ring_feed(void){
 int16_t data[2048];for(unsigned i=0;i<1024;i++){data[2*i]=(i&1)?32767:-32768;data[2*i+1]=(i&1)?-32768:32767;}
 (void)mi8_audio_ring_put(data,1024);
}
/* @tail_helper */
static void tail_capture(const char *text){
 char line[400];CHECK(strlen(text)<sizeof(line));strcpy(line,text);
 /* @tail_capture */
}
static void stream(void){
 struct peer p;struct play_peer m;
 for(unsigned mode=0;mode<3;mode++){
  reset_ring();mi8_audio_ring_ready();mi8_audio_set_ring(true);prepare(&p,&m);m.step=17;m.budget=mode==1?6000000:130000000;
  if(mode==2)m.drop_writes=true;
  bool okay=run_play(&p,&m);CHECK(okay==(mode==0));
  struct mi8_audio_ring_counts r;mi8_audio_ring_counts(&r);
  CHECK(!r.queued&&r.accepted==r.consumed+r.discarded&&r.accepted>0);
  CHECK(r.consumed_nonzero==r.consumed&&r.peak_l==32768&&r.peak_r==32768);
  CHECK(!m.canary_at&&m.end==1&&!m.retain&&p.closes==1);
  CHECK(saw(&m,0x10bcd)&&saw(&m,0x10d94)&&saw(&m,0x10327));
  if(!mode){CHECK(m.normal==6000&&m.writes==6000&&m.cache==6000);CHECK(p.now==120000000&&mi8_audio_play_completed());CHECK(r.underflow_frames==960);CHECK(strstr(m.log,"zero: 105 s")&&strstr(m.log,"play: 6000 periods"));}
  else CHECK(!mi8_audio_play_completed()&&p.now<m.budget);
  printf("Ring stream mode=%u zero-DMA=%u accepted=%llu consumed=%llu discarded=%llu time=%llu PASS\n",mode,m.writes,(unsigned long long)r.accepted,(unsigned long long)r.consumed,(unsigned long long)r.discarded,(unsigned long long)p.now);
 }
 mi8_audio_set_ring(false);
 worker_peer=&p;worker_memory=&m;audio_play_brief=false;m.log_length=0;m.log[0]=0;
 ring_counts.accepted=ring_counts.consumed=UINT64_MAX;ring_counts.discarded=0;
 ring_counts.dropped=ring_counts.outside=ring_counts.consumed_nonzero=UINT64_MAX;
 audio_ring_report(true,"complete");CHECK(strstr(m.log,"ring stream completed")&&strstr(m.log,"output forced zero; amp untouched (reset low)"));
 audio_tail_on=true;audio_play_thread=current_thread();audio_ring_stream=true;
 char padding[301];memset(padding,'Z',300);padding[300]=0;
 for(unsigned i=0;i<40;i++)tail_capture(padding);
 CHECK(audio_tail_len==sizeof(audio_tail)-1);
 for(const char *at=m.log;*at;){char chunk[301];unsigned n=(unsigned)strlen(at);if(n>300)n=300;memcpy(chunk,at,n);chunk[n]=0;tail_capture(chunk);at+=n;}
 CHECK(strstr(audio_tail,"ring stream completed")&&strstr(audio_tail,"amp untouched (reset low)"));
 audio_ring_stream=false;audio_play_thread=NULL;
 m.log_length=0;m.log[0]=0;ring_counts.accepted--;audio_ring_report(true,"complete");CHECK(strstr(m.log,"ring stream FAILED")&&strstr(m.log,"conservation=FAILED"));
 CHECK(audio_tail_len==strlen(m.log)&&!memcmp(audio_tail,m.log,audio_tail_len));
}
int main(void){model();concurrency();close_race();stream();printf("Ring SELFTEST PASS %u + %u concurrent checks\n",checks,atomic_load(&concurrent_checks));return 0;}
