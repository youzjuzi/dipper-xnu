/* SPDX-License-Identifier: MIT */
/* Independent faults against the actual submit path, with no feeder/controller. */
#include <assert.h>
#include <stdlib.h>
static struct mi8_amp_snapshot guard_amp;
static unsigned guard_stops,guard_sends,guard_zeros,guard_wakes,guard_trigger;
static void guard_wake(unsigned peak){guard_wakes++;guard_trigger=peak;}
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
 bool valid=db==-30||db==-24||db==-20||db==-12||db==-6||db==0;
 assert(mi8_pcm_session_level(db)==valid);
 unsigned limit=mi8_pcm_session_limit();assert(limit==(db==-24?2068u:db==-20?3277u:db==-12?8231u:db==-6?16423u:db==0?32767u:1036u));
 assert(!mi8_pcm_session_level(-20)&&limit==mi8_pcm_session_limit());
 static uint8_t data[32768];struct mi8_pcm_ops io={.now=guard_now,.send=guard_send};
 struct mi8_pcm_session_ops ops={.snapshot=guard_snapshot,.wake=guard_wake,.stop=guard_stop,.zero=guard_zero,.count=guard_count,.mute=guard_mute,.muted=guard_muted};
 struct mi8_pcm_state s={.io=&io,.session=&ops,.zero=true,.memory={.buffer=data}};
 for(unsigned fault=0;fault<11;fault++){
  s.jobs[0].active=false;guard_clock=1000000;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1};
  session_pcm.periods=0;put16(data,limit);put16(data+2,limit);
  if(fault==0){put16(data,limit+1);put16(data+2,limit+1);}
  if(fault==1)put16(data+2,1);
  if(fault==2)guard_amp.state=MI8_AMP_WARMING;
  if(fault==3)guard_amp.request=2;
  if(fault==4)guard_amp.reason=4;
  if(fault==5)guard_clock=guard_amp.live_start+900000000;
  if(fault==6)guard_amp.live_start=2000000;
  if(fault==7)guard_amp.wakes=201;
  if(fault==8)session_pcm.periods=45000;
  assert(!submit(&s,fault==9?8:0,fault==10?MI8_PCM_ADDRESS+32768:MI8_PCM_ADDRESS,false,200000000));
  assert(guard_stops==fault+1&&!guard_sends);
 }
 s.jobs[0].active=false;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=200,.live_start=1,.live_total=90000000};
 guard_clock=899980001;session_pcm.periods=44999;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,200000000));assert(guard_sends==1&&!guard_zeros);
 s.jobs[0].active=false;memset(data,0,sizeof(data));guard_amp.state=MI8_AMP_LATCHED_OFF;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,200000000));assert(guard_sends==2&&guard_zeros==1);
 /* Exhaust all mono input values with independent signed tie-away reference. */
 session_pcm.periods=3;
 for(int v=-32768;v<=32767;v++){
  int64_t product=(int64_t)v*limit;
  int expected=product<0?-(int)((-product+16384)/32768):(int)((product+16384)/32768);
  assert(session_sample(v,v,480,false,false)==expected);
  assert(session_sample(v,v,480,false,true)==0);
  if(v!=-32768)assert(session_sample(v,-v,480,false,false)==0);
 }
 assert(session_sample(0,0,480,false,false)==0);
 assert(session_sample(32767,32767,480,false,false)==(int)(((int64_t)32767*limit+16384)/32768));
 assert(session_sample(0,0,480,false,false)==0);
 for(unsigned i=0;i<=2400;i++){
  session_pcm.periods=i/960;
  int value=session_sample(-32768,-32768,i%960,false,false);
  int expected=i<2400?-(int)(((uint64_t)limit*i+1199)/2399):-(int)limit;
  assert(value==expected);
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
 /* Exact 1499/1500 zero-period edge; guard budgets are independent. */
 guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1};
 session_pcm.wake=1;session_pcm.periods=1;session_pcm.zero_periods=0;session_pcm.closing=false;
 for(unsigned i=0;i<1499;i++){session_fill(&s,0);assert(!session_pcm.closing);}
 session_fill(&s,0);assert(session_pcm.closing&&session_pcm.zero_periods==1500);
 guard_amp.write_trigger=true;session_pcm.heard=false;session_pcm.zero_periods=0;session_pcm.closing=false;
 for(unsigned i=0;i<499;i++){session_fill(&s,0);assert(!session_pcm.closing);}
 session_fill(&s,0);assert(session_pcm.closing&&session_pcm.zero_periods==500);
 /* A write-woken window which has emitted data uses the full 30s silence. */
 session_pcm.heard=true;session_pcm.zero_periods=1498;session_pcm.closing=false;
 session_fill(&s,0);assert(!session_pcm.closing);session_fill(&s,0);assert(session_pcm.closing);
 /* HAL resume publication is consumed even outside OFF_READY. Zero writes
  * after >1s request once; <=1s writes do not, and peak remains a trigger. */
 guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_OFF_READY};
 mi8_audio_ring_write_time(1000000);session_fill(&s,0);assert(guard_wakes==1&&!guard_trigger);
 mi8_audio_ring_write_time(2000000);session_fill(&s,0);assert(guard_wakes==1);
 mi8_audio_ring_write_time(3000001);session_fill(&s,0);assert(guard_wakes==2&&!guard_trigger);
 session_fill(&s,0);assert(guard_wakes==2);
 int16_t peak_input[2]={256,256};assert(mi8_audio_ring_put(peak_input,1)==1);session_fill(&s,0);assert(guard_wakes==3&&guard_trigger==256);
 /* Fill WARMING to capacity, then keep the newest 40ms via the sole feeder.
  * Continue producing during preheat: the retained tail becomes fresh and
  * the first LIVE take/fade precedes any audible data. */
 int16_t feed[2048];
 for(unsigned chunk=0;chunk<16;chunk++){
  for(unsigned i=0;i<1024;i++)feed[2*i]=feed[2*i+1]=(int16_t)(chunk*1024+i);
  assert(mi8_audio_ring_put(feed,1024)==1024);
 }
 guard_amp.state=MI8_AMP_WARMING;guard_amp.wakes=2;
 uint64_t before_flush=session_stats.wake_flush_frames;
 session_fill(&s,0);struct mi8_audio_ring_counts counts;mi8_audio_ring_counts(&counts);
 assert(counts.queued==1920&&session_stats.wake_flush_frames-before_flush==14464);
 for(unsigned chunk=0;chunk<10;chunk++){
  for(unsigned i=0;i<960;i++)feed[2*i]=feed[2*i+1]=(int16_t)(16384+chunk*960+i);
  assert(mi8_audio_ring_put(feed,960)==960);session_fill(&s,0);
  mi8_audio_ring_counts(&counts);assert(counts.queued==1920);
 }
 for(unsigned i=0;i<960;i++)feed[2*i]=feed[2*i+1]=(int16_t)(25984+i);
 assert(mi8_audio_ring_put(feed,960)==960);
 guard_amp.state=MI8_AMP_LIVE;session_fill(&s,0);
 mi8_audio_ring_counts(&counts);assert(counts.queued==960);
 assert(session_stats.wake_flush_frames-before_flush==25024);
 assert(counts.accepted==counts.consumed+counts.discarded+counts.queued);
 assert(!get32(data)); /* first frame of the actual DMA period is faded to zero */
 assert((int16_t)get32(data+479*4)==(int)(((int64_t)((25503*(int64_t)limit+16384)/32768)*479+1199)/2399));
 assert((int16_t)get32(data+959*4)==(int)(((int64_t)((25983*(int64_t)limit+16384)/32768)*959+1199)/2399));
 assert(mi8_audio_ring_close());mi8_audio_ring_counts(&counts);assert(counts.accepted==counts.consumed+counts.discarded);
 /* Resident mode removes quantities, preserving every property check. */
 assert(mi8_pcm_session_seconds(0));
 guard_clock=7200000001ull;session_pcm.periods=(1ull<<40)+3;
 guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=100000,.live_start=1};
 memset(data,0,sizeof(data));put16(data,limit);put16(data+2,limit);s.jobs[0].active=false;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,guard_clock+1000000));
 assert(session_sample(-32768,-32768,0,false,false)==-(int)limit); /* no late fade recurrence */
 for(unsigned fault=0;fault<9;fault++){
  s.jobs[0].active=false;guard_clock=7200000001ull;
  guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=100000,.live_start=1};
  put16(data,limit);put16(data+2,limit);
  if(fault==0){put16(data,limit+1);put16(data+2,limit+1);}
  if(fault==1)put16(data+2,1);
  if(fault==2)guard_amp.state=MI8_AMP_WARMING;
  if(fault==3)guard_amp.request=2;
  if(fault==4)guard_amp.reason=4;
  if(fault==5)guard_clock=0;
  unsigned stops=guard_stops;
  assert(!submit(&s,fault==6?8:0,fault==7?MI8_PCM_ADDRESS+32768:MI8_PCM_ADDRESS,fault==8,7201000000ull));
  assert(guard_stops==stops+1);
 }
 assert(mi8_pcm_session_seconds(120));
 printf("Session guards/scaling/statistics PASS level=%d limit=%u: 11 rejection classes, late LIVE/cumulative>60s, 200th wake, all 65536 mono inputs, fade, mute, exact LIVE underflow\n",db,limit);
}
