/* SPDX-License-Identifier: MIT */
/* Appended to actual PCM translation unit: independent arithmetic and guards. */
#include <assert.h>
static unsigned clip_sent,clip_stopped;
static bool clip_ready=true;
static uint64_t clip_now(void *p){(void)p;return 100000;}
static bool clip_clean(void){return true;}
static bool clip_audible(void){return clip_ready;}
static void clip_shutdown(void){clip_stopped++;}
static int clip_send(void *p,const uint8_t *b,size_t n,uint64_t end){(void)p;(void)b;(void)n;(void)end;clip_sent++;return 0;}
void clip_pcm_tests(void){
 unsigned checks=0;
 for(int v=-32768;v<=32767;v++){
  int expected=(int)(((int64_t)(v<0?-v:v)*1036+16384)/32768);if(v<0)expected=-expected;
  assert(clip_sample(v,v,960,false)==expected);assert(clip_sample(v,v,960,true)==0);checks+=2;
  if(v!=-32768)assert(clip_sample(v,-v,960,false)==0);
  assert(clip_sample(v,v,0,false)==0&&clip_sample(v,v,143999,false)==0);checks+=2;
 }
 uint32_t rng=0x73512891;
 for(unsigned n=0;n<100000;n++){
  rng=rng*1664525u+1013904223u;int16_t l=(int16_t)rng;
  rng=rng*1664525u+1013904223u;int16_t r=(int16_t)rng;unsigned frame=(rng>>3)%144000;
  int64_t mono=((int32_t)l+(int32_t)r)/2;
  int64_t v=(mono<0?-1:1)*(((mono<0?-mono:mono)*1036+16384)/32768);
  unsigned edge=frame<480?frame:frame>=143520?143999-frame:479;
  v=(v<0?-1:1)*(((v<0?-v:v)*edge+239)/479);
  assert(clip_sample(l,r,frame,false)==v);assert(clip_sample(l,r,frame,true)==0);checks+=2;
 }
 int previous=0;
 for(unsigned i=0;i<480;i++){int a=clip_sample(32767,32767,i,false);assert(a>=previous&&a<=1036);assert(a==clip_sample(32767,32767,143999-i,false));previous=a;checks+=3;}
 assert(previous==1036&&clip_sample(-32768,-32768,479,false)==-1036);
 uint8_t data[32768]={0};struct mi8_pcm_clip_ops amp={.stop=clip_shutdown,.audible=clip_audible,.clean=clip_clean};struct mi8_pcm_ops io={.now=clip_now,.send=clip_send};
 struct mi8_pcm_state s={.io=&io,.clip=&amp,.memory={.buffer=data}};
 for(unsigned fault=0;fault<8;fault++){
  s.jobs[0].active=false;clip_result=(struct mi8_pcm_clip_result){.triggered=true,.live=true,.first_us=1};clip_ready=true;
  put16(data,1);put16(data+2,1);
  if(fault==0)put16(data,1037);
  if(fault==1)put16(data,-32768);
  if(fault==2)put16(data+2,2);
  if(fault==3)clip_result.live=false;
  if(fault==4)clip_ready=false;
  if(fault==5)clip_result.periods=150;
  if(fault==6)clip_result.first_us=200000;
  assert(!submit(&s,0,fault==7?MI8_PCM_ADDRESS+32768:MI8_PCM_ADDRESS,false,200000));
  assert(clip_stopped==fault+1&&clip_sent==0&&clip_result.failed);
 }
 s.jobs[0].active=false;clip_result=(struct mi8_pcm_clip_result){.triggered=true,.live=true,.first_us=1};clip_ready=true;put16(data,1036);put16(data+2,1036);
 assert(submit(&s,0,MI8_PCM_ADDRESS,false,200000));assert(clip_sent==1&&clip_result.blocks==1);
 printf("Clip arithmetic/guard SELFTEST PASS %u arithmetic checks + 8 rejection classes\n",checks);
}
