/* SPDX-License-Identifier: MIT */
/* Independent submit faults against the actual PCM implementation. */
#include <assert.h>
static struct mi8_amp_snapshot guard_amp;
static unsigned guard_stops,guard_sends,guard_zeros;
static uint64_t guard_now(void *p){(void)p;return 1000000;}
static void guard_snapshot(struct mi8_amp_snapshot *o){*o=guard_amp;}
static void guard_stop(void){guard_stops++;}
static void guard_zero(void){guard_zeros++;}
static void guard_count(unsigned p,bool nz){(void)p;(void)nz;}
static void guard_mute(uint64_t n){(void)n;}
static int guard_send(void *p,const uint8_t *b,size_t n,uint64_t end){(void)p;(void)b;(void)n;(void)end;guard_sends++;return 0;}
void session_guard_tests(void){
 static uint8_t data[32768];struct mi8_pcm_ops io={.now=guard_now,.send=guard_send};
 struct mi8_pcm_session_ops ops={.snapshot=guard_snapshot,.stop=guard_stop,.zero=guard_zero,.count=guard_count,.mute=guard_mute};
 struct mi8_pcm_state s={.io=&io,.session=&ops,.zero=true,.memory={.buffer=data}};
 for(unsigned fault=0;fault<11;fault++){
  s.jobs[0].active=false;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1};
  session_pcm.periods=0;put16(data,1036);put16(data+2,1036);
  if(fault==0)put16(data,1037);
  if(fault==1)put16(data+2,1);
  if(fault==2)guard_amp.state=MI8_AMP_WARMING;
  if(fault==3)guard_amp.request=2;
  if(fault==4)guard_amp.reason=4;
  if(fault==5)guard_amp.live_total=60000000;
  if(fault==6)guard_amp.live_start=2000000;
  if(fault==7)guard_amp.wakes=21;
  if(fault==8)session_pcm.periods=1000;
  assert(!submit(&s,fault==9?8:0,fault==10?MI8_PCM_ADDRESS+32768:MI8_PCM_ADDRESS,false,2000000));
  assert(guard_stops==fault+1&&!guard_sends);
 }
 s.jobs[0].active=false;guard_amp=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1};session_pcm.periods=0;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,2000000));assert(guard_sends==1&&!guard_zeros);
 s.jobs[0].active=false;memset(data,0,sizeof(data));guard_amp.state=MI8_AMP_LATCHED_OFF;
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,2000000));assert(guard_sends==2&&guard_zeros==1);
 printf("Session submit guards PASS 11 rejection classes, legal LIVE and latched zero\n");
}
