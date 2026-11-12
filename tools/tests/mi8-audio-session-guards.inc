/* SPDX-License-Identifier: MIT */
/* Independent faults against the actual submit path, with no feeder/controller. */
#include <assert.h>
#include <stdlib.h>
static struct mi8_amp_snapshot guard_amp;
static unsigned guard_stops,guard_sends,guard_zeros;
static uint64_t guard_clock=1000000;
static uint64_t guard_now(void *p){(void)p;return guard_clock;}
static void guard_snapshot(struct mi8_amp_snapshot *o){*o=guard_amp;}
static void guard_stop(void){guard_stops++;}
static void guard_zero(void){guard_zeros++;}
static void guard_count(unsigned p,bool nz){(void)p;(void)nz;}
static void guard_mute(uint64_t n){(void)n;}
static bool guard_muted(void){return false;}
static int guard_send(void *p,const uint8_t *b,size_t n,uint64_t end){(void)p;(void)b;(void)n;(void)end;guard_sends++;return 0;}
void session_guard_tests(void){
 int db=getenv("SESSION_LEVEL")?atoi(getenv("SESSION_LEVEL")):-30;
 bool valid=db==-30||db==-24||db==-20;
 assert(mi8_pcm_session_level(db)==valid);
 unsigned limit=mi8_pcm_session_limit();assert(limit==(db==-24?2068u:db==-20?3277u:1036u));
 assert(!mi8_pcm_session_level(-20)&&limit==mi8_pcm_session_limit());
 static uint8_t data[32768];struct mi8_pcm_ops io={.now=guard_now,.send=guard_send};
 struct mi8_pcm_session_ops ops={.snapshot=guard_snapshot,.stop=guard_stop,.zero=guard_zero,.count=guard_count,.mute=guard_mute,.muted=guard_muted};
 struct mi8_pcm_state s={.io=&io,.session=&ops,.zero=true,.memory={.buffer=data}};
 for(unsigned fault=0;fault<11;fault++){
  s.jobs[0].active=false;guard_clock=1000000;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1};
  session_pcm.periods=0;put16(data,limit);put16(data+2,limit);
  if(fault==0){put16(data,limit+1);put16(data+2,limit+1);}
  if(fault==1)put16(data+2,1);
  if(fault==2)guard_amp.state=MI8_AMP_WARMING;
  if(fault==3)guard_amp.request=2;
  if(fault==4)guard_amp.reason=4;
  if(fault==5)guard_clock=guard_amp.live_start+120000000;
  if(fault==6)guard_amp.live_start=2000000;
  if(fault==7)guard_amp.wakes=201;
  if(fault==8)session_pcm.periods=6000;
  assert(!submit(&s,fault==9?8:0,fault==10?MI8_PCM_ADDRESS+32768:MI8_PCM_ADDRESS,false,200000000));
  assert(guard_stops==fault+1&&!guard_sends);
 }
 s.jobs[0].active=false;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=200,.live_start=1,.live_total=90000000};
 guard_clock=119980001;session_pcm.periods=5999;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,200000000));assert(guard_sends==1&&!guard_zeros);
 s.jobs[0].active=false;memset(data,0,sizeof(data));guard_amp.state=MI8_AMP_LATCHED_OFF;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,200000000));assert(guard_sends==2&&guard_zeros==1);
 /* Exhaust all mono input values with independent signed tie-away reference. */
 session_pcm.periods=1;
 for(int v=-32768;v<=32767;v++){
  int64_t product=(int64_t)v*limit;
  int expected=product<0?-(int)((-product+16384)/32768):(int)((product+16384)/32768);
  assert(session_sample(v,v,480,false,false)==expected);
  assert(session_sample(v,v,480,false,true)==0);
  if(v!=-32768)assert(session_sample(v,-v,480,false,false)==0);
 }
 assert(session_sample(0,0,480,false,false)==0);
 assert(session_sample(32767,32767,480,false,false)==(int)limit);
 assert(session_sample(0,0,480,false,false)==0);
 session_pcm.periods=0;
 for(unsigned i=0;i<960;i++){
  int a=session_sample(-32768,-32768,i,false,false);
  assert(a>=-(int)limit&&a<=0);
  if(i==0)assert(!a);
 }
 session_pcm.periods=5999;
 assert(session_sample(-32768,-32768,479,true,false)==-(int)limit);
 assert(session_sample(-32768,-32768,959,true,false)==0);
 assert(!session_stats.saturated_samples);
 /* Empty and partially filled ring periods: only LIVE contributes. */
 mi8_audio_ring_ready();assert(mi8_audio_ring_open());
 session_stats.underflow_periods=session_stats.zero_frames=0;
 guard_amp.state=MI8_AMP_OFF_READY;session_fill(&s,0);
 assert(!session_stats.underflow_periods&&!session_stats.zero_frames);
 guard_amp.state=MI8_AMP_LIVE;guard_clock=1000000;guard_amp.wakes=1;
 session_fill(&s,0);assert(session_stats.underflow_periods==1&&session_stats.zero_frames==960);
 int16_t partial[200]={0};assert(mi8_audio_ring_put(partial,100)==100);
 session_fill(&s,0);assert(session_stats.underflow_periods==2&&session_stats.zero_frames==1820);
 guard_amp.state=MI8_AMP_MUTING;session_fill(&s,0);assert(session_stats.underflow_periods==2&&session_stats.zero_frames==1820);
 assert(mi8_audio_ring_close());
 printf("Session guards/scaling/statistics PASS level=%d limit=%u: 11 rejection classes, late LIVE/cumulative>60s, 200th wake, all 65536 mono inputs, fade, mute, exact LIVE underflow\n",db,limit);
}
