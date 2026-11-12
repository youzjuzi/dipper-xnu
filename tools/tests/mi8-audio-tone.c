/* SPDX-License-Identifier: MIT */
#include "mi8_tas2557.h"
void mi8_tas2557_prepare(uint64_t);
void mi8_tas2557_prepare_tone(uint64_t);
#include "play-fixture.c"
extern void amp_model_load(const char *,const char *);
extern bool amp_model_begin(uint64_t *,unsigned,bool);
extern void amp_model_event(uint32_t);
extern void amp_model_check(unsigned);
extern unsigned long amp_model_checks(void);
extern unsigned mi8_tas_guard_tests(void);
extern bool tone_model_unmuted(void);
extern void tone_pcm_tests(void);
extern void tone_budget_fault(void);
static unsigned tone_nonzero,tone_peak;
static FILE *wavefile;
static unsigned scenario;
void mi8_tas2557_prepare_tone(uint64_t until){CHECK(until>worker_peer->now);worker_peer->amp_high=amp_model_begin(&worker_peer->now,scenario,true);}
/* The actual worker body is also compiled; its legacy tests remain callable. */
void mi8_tas2557_prepare(uint64_t until){(void)until;CHECK(false);}
static void observe(struct peer *p,const uint8_t *q){
 struct play_peer *m=p->extension;uint32_t op=rd(q+16);amp_model_event(op);
 if(scenario==6 && op==0x10dab && m->normal==60)m->fatal=true;
 if(op==0x10dab) {
  CHECK(rd(q+24)==1);unsigned at=rd(q+20)-0x10000000;CHECK(at+3840<=32768);
  bool nonzero=false;for(unsigned i=0;i<960;i++) {
   int v=(int16_t)((unsigned)m->buffer[at+4*i]|(unsigned)m->buffer[at+4*i+1]<<8);unsigned mag=(unsigned)(v<0?-v:v);
   CHECK(mag<=1036);nonzero|=v!=0;if(mag>tone_peak)tone_peak=mag;
  }
  if(nonzero){CHECK(m->normal>=50&&m->normal<100&&tone_model_unmuted());tone_nonzero++;}
  if(wavefile)CHECK(fwrite(m->buffer+at,1,3840,wavefile)==3840);
 }
}
static void corrupt_cache(struct peer *p,size_t at){
 struct play_peer *m=p->extension;
 if(scenario==13&&m->cache==55)tone_budget_fault();
 if(scenario==8&&m->cache==55){m->buffer[at]=0x0d;m->buffer[at+1]=4;m->buffer[at+2]=0x0d;m->buffer[at+3]=4;}
 if(scenario==9&&m->cache==20){m->buffer[at]=m->buffer[at+2]=1;}
}
int main(int argc,char **argv){
 CHECK(argc==4);CHECK(mi8_tas_guard_tests()==2048);tone_pcm_tests();amp_model_load(argv[1],argv[2]);
 for(unsigned bus=0;bus<2;bus++)for(scenario=0;scenario<=15;scenario++){
  if(scenario==12 && !bus)continue;
  tone_nonzero=tone_peak=0;wavefile=bus==1&&scenario==0?fopen(argv[3],"wb"):NULL;
  struct peer p;struct play_peer m;prepare(&p,&m);m.step=16;
  bool held=amp_model_begin(&p.now,scenario,bus!=0);p.amp_high=held;
  p.extension=&m;p.extra_response=play_reply;p.reply=p.header8=p.afe_mode=true;
  amp_observe=observe;amp_cache_observe=corrupt_cache;
  mi8_audio_set_amp(&audio_amp_ops);
  if(scenario==10)p.fail_action=3;
  struct mi8_audio_pin_ops pins={pin_read,pin_write,&p};struct mi8_glink_cfg c=cfg(&p);c.log=play_log;
  struct mi8_pcm_ops memory={.ctx=&p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
  uint64_t until=p.now+(scenario==7?5100000:20000000);
  bool ok=mi8_audio_run_play(&c,play_alive,&p,&pins,&memory,until,16,play_fatal);
  mi8_tas2557_stop();m.reset=true;(void)mi8_audio_finish_play(true);
  mi8_tas2557_report(mi8_audio_play_cleanup());amp_model_check(scenario);
  CHECK(!mi8_audio_play_proven() && m.writes==m.normal && !m.clear);
  if(scenario==0){CHECK(ok&&m.normal==150&&tone_peak==1036&&tone_nonzero==50);}
  if(wavefile){fclose(wavefile);wavefile=NULL;}
  if(scenario==0)CHECK(ok);
  else CHECK(!ok);
  CHECK(!mi8_tas2557_held());mi8_audio_set_amp(NULL);
 }
 /* Full actual worker lifecycle, including pre-ADSP download and PAS. */
 for(scenario=0;scenario<3;scenario++) {
  struct peer p;struct play_peer m;prepare(&p,&m);m.step=16;m.budget=20000000;p.extension=&m;
  worker_peer=&p;worker_memory=&m;worker_failure=0;stop_ack=aop_off=true;
  adsp_started=false;adsp_last_stop_acked=adsp_last_aop_off=false;audio_play_locked=false;
  pas_calls=stop_calls=aop_calls=unlocks=0;amp_observe=observe;amp_cache_observe=corrupt_cache;
  steps_from_five((void*)(uintptr_t)16,0);
  amp_model_check(scenario);CHECK(pas_calls==1&&stop_calls==1&&aop_calls==1);
  CHECK(!audio_play_thread&&!audio_play_locked&&!mi8_tas2557_held());
 }
 /* Execute the actual worker's pre-start failure exits with a real held TAS.
  * A failure before AFE must still drop reset and restore the bus. */
 for(unsigned failure=1;failure<=3;failure++) {
  struct peer p;struct play_peer m;prepare(&p,&m);m.step=16;p.extension=&m;
  worker_peer=&p;worker_memory=&m;worker_failure=failure;scenario=19+failure;
  adsp_started=false;adsp_last_stop_acked=adsp_last_aop_off=false;audio_play_locked=false;
  amp_observe=NULL;amp_cache_observe=NULL;
  steps_from_five((void*)(uintptr_t)16,0);
  amp_model_check(scenario);CHECK(!mi8_tas2557_held()&&!audio_play_thread&&!m.writes);
 }
 printf("Tone integration SELFTEST PASS %lu/%lu\n",checks+amp_model_checks(),checks+amp_model_checks());return 0;
}
