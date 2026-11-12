/* SPDX-License-Identifier: MIT */
#include "mi8_tas2557.h"
void mi8_tas2557_prepare(uint64_t);
void mi8_tas2557_prepare_tone(uint64_t);
void mi8_tas2557_prepare_clip(uint64_t);
#include "play-fixture.c"
#include "mi8_audio_ring.c"
extern void amp_model_load(const char *,const char *);
extern bool amp_model_begin(uint64_t *,unsigned,bool);
extern void amp_model_event(uint32_t);
extern void clip_model_check(bool,bool);
extern unsigned long amp_model_checks(void);
extern void clip_pcm_tests(void);
static unsigned scenario,output_blocks,output_peak;
static struct peer *active;
static bool muted(void){return scenario==4 || (scenario==5 && output_blocks>=40 && output_blocks<41);}
static const struct mi8_pcm_clip_ops clip_ops={mi8_tas2557_held,mi8_tas2557_clip_warmup,mi8_tas2557_clip_audible,muted,mi8_tas2557_stop,mi8_tas2557_clip_clean};
void mi8_tas2557_prepare(uint64_t end){(void)end;CHECK(false);}
void mi8_tas2557_prepare_tone(uint64_t end){(void)end;CHECK(false);}
void mi8_tas2557_prepare_clip(uint64_t end){CHECK(end>active->now);active->amp_high=amp_model_begin(&active->now,scenario==8?11:scenario==7?1:scenario==12?16:scenario==13?18:scenario==18?5:0,true);}
static void reset_ring(void){memset(ring_samples,0,sizeof(ring_samples));memset(&ring_counts,0,sizeof(ring_counts));ring_head=ring_tail=ring_ready=ring_gate=ring_started=0;mi8_audio_ring_ready();}
static void ring_feed(void){
 int16_t data[2048];int value=scenario==1?0:scenario==2?255:scenario==3?256:32767;
 for(unsigned i=0;i<1024;i++)data[2*i]=data[2*i+1]=(int16_t)value;
 (void)mi8_audio_ring_put(data,1024);
}
static void observe(struct peer *p,const uint8_t *q){
 struct play_peer *m=p->extension;uint32_t op=rd(q+16);amp_model_event(op);
 if(op==0x10dab){
  unsigned at=rd(q+20)-0x10000000;CHECK(rd(q+24)==1&&at+3840<=8*3840);
  bool nz=false;
  for(unsigned i=0;i<960;i++){
   int l=(int16_t)(m->buffer[at+4*i]|m->buffer[at+4*i+1]<<8),r=(int16_t)(m->buffer[at+4*i+2]|m->buffer[at+4*i+3]<<8);
   unsigned a=l<0?-l:l;CHECK(l==r&&a<=1036);if(a>output_peak)output_peak=a;nz|=a!=0;
  }
  if(nz){CHECK(mi8_tas2557_clip_audible()&&!muted());output_blocks++;}
  if(output_blocks==30){if(scenario==9)m->fatal=true;if(scenario==10)m->ordinary_fault=true;}
 }
}
static void corrupt(struct peer *p,size_t at){
 struct play_peer *m=p->extension;
 if(scenario==14 && m->cache==80){m->buffer[at]=m->buffer[at+2]=0x0d;m->buffer[at+1]=m->buffer[at+3]=4;}
 if(scenario==15 && m->cache==80){m->buffer[at]=1;m->buffer[at+2]=2;}
 if(scenario==16 && m->cache==2){m->buffer[at]=m->buffer[at+2]=1;}
 if(scenario==17 && m->cache==300){m->buffer[at]=m->buffer[at+2]=1;}
}
/* @clip_worker_helpers */
int main(int argc,char **argv){
 CHECK(argc==3);clip_pcm_tests();amp_model_load(argv[1],argv[2]);
 for(scenario=0;scenario<=18;scenario++){
  reset_ring();output_blocks=output_peak=0;struct peer p;struct play_peer m;prepare(&p,&m);active=&p;m.step=16;
  mi8_tas2557_prepare_clip(p.now+20000000);
  p.extension=&m;p.extra_response=play_reply;p.reply=p.header8=p.afe_mode=true;
  amp_observe=observe;amp_cache_observe=corrupt;
  mi8_audio_set_ring(true);mi8_audio_set_clip(&clip_ops);
  struct mi8_audio_pin_ops pins={pin_read,pin_write,&p};struct mi8_glink_cfg c=cfg(&p);c.log=play_log;
  struct mi8_pcm_ops memory={.ctx=&p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
  uint64_t until=p.now+(scenario==11?5100000:130000000);
  bool okay=mi8_audio_run_play(&c,play_alive,&p,&pins,&memory,until,17,play_fatal);
  mi8_tas2557_stop();m.reset=true;(void)mi8_audio_finish_play(true);
  const struct mi8_pcm_clip_result *r=mi8_pcm_clip_result();struct mi8_audio_ring_counts count;mi8_audio_ring_counts(&count);
  CHECK(count.accepted==count.consumed+count.discarded&&!count.queued);CHECK(output_peak<=1036&&output_blocks<=150);CHECK(!mi8_tas2557_held());
  if(scenario<=8||scenario==12||scenario==13||scenario==18){if(!okay || m.normal!=6000)fprintf(stderr,"scenario %u: %s\n",scenario,m.log);CHECK(okay&&m.normal==6000);}
  else CHECK(!okay);
  if(scenario==9||scenario==10||scenario==11)CHECK(r->failed&&output_blocks>0&&output_blocks<150);
  if(scenario==0||scenario==3||scenario==12||scenario==13){CHECK(r->periods==150&&output_blocks==150&&r->blocks==150&&!r->failed);}
  if(scenario==1||scenario==2)CHECK(!r->triggered&&!output_blocks);
  if(scenario==4)CHECK(r->triggered&&r->periods==150&&!output_blocks);
  if(scenario==7||scenario==8)CHECK(r->failed&&!output_blocks);
  if(scenario==18)CHECK(r->failed&&output_blocks==150);
  if(scenario==12||scenario==13)CHECK(r->warmup_us>=200000);
  worker_peer=&p;worker_memory=&m;audio_play_thread=current_thread();
  audio_clip_report(okay,mi8_audio_play_cleanup());
  if(okay&&!r->failed)CHECK(strstr(m.log,r->triggered?"audio=4: clip played":"audio=4: clip not triggered"));
  else CHECK(strstr(m.log,"audio=4: clip FAILED"));
  audio_play_thread=NULL;
  clip_model_check(r->triggered&&scenario!=8,output_blocks>0);
  printf("clip scenario=%u periods=%u window=%u blocks=%u peak=%u warmup=%llu accepted=%llu consumed=%llu discarded=%llu PASS\n",scenario,m.normal,r->periods,r->blocks,r->peak,(unsigned long long)r->warmup_us,(unsigned long long)count.accepted,(unsigned long long)count.consumed,(unsigned long long)count.discarded);
  mi8_audio_set_clip(NULL);mi8_audio_set_ring(false);
 }
 for(unsigned failure=0;failure<=3;failure++){
  scenario=0;reset_ring();output_blocks=output_peak=0;
  struct peer p;struct play_peer m;prepare(&p,&m);active=&p;m.step=16;m.budget=130000000;p.extension=&m;
  worker_peer=&p;worker_memory=&m;worker_failure=failure;stop_ack=aop_off=true;
  adsp_started=false;adsp_last_stop_acked=adsp_last_aop_off=false;audio_play_locked=false;
  audio_ring_stream=true;audio_tail_on=true;audio_tail_len=0;pas_calls=stop_calls=aop_calls=unlocks=0;
  amp_observe=observe;amp_cache_observe=corrupt;
  steps_audio_clip((void *)(uintptr_t)17,0);
  CHECK(!mi8_tas2557_held()&&!audio_play_thread&&!audio_play_locked);
  if(!failure){CHECK(m.normal==6000&&output_blocks==150&&pas_calls==1&&stop_calls==1&&aop_calls==1);CHECK(strstr(m.log,"audio=4: clip played")&&strstr(m.log,"conservation=ok"));}
  else {CHECK(!m.writes&&strstr(m.log,"audio=4: clip FAILED"));}
  clip_model_check(!failure,!failure);
 }
 printf("Clip integration SELFTEST PASS %lu/%lu\n",checks+amp_model_checks(),checks+amp_model_checks());return 0;
}
