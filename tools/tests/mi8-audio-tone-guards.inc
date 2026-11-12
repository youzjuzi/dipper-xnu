/* SPDX-License-Identifier: MIT */
/* Appended only to the host translation unit, exercising the real submit gate. */
#include <assert.h>
static unsigned guard_sent, guard_stopped;
static bool guard_ready=true;
static bool guard_audible(void){return guard_ready;}
static void guard_stop(void){guard_stopped++;}
static int guard_send(void *ctx,const uint8_t *p,size_t n,uint64_t end){(void)ctx;(void)p;(void)n;(void)end;guard_sent++;return 0;}
void tone_pcm_tests(void) {
 uint8_t buffer[32768]={0};
 const struct mi8_pcm_amp amp={.stop=guard_stop,.audible=guard_audible};
 const struct mi8_pcm_ops ops={.send=guard_send};
 struct mi8_pcm_state s={.io=&ops,.memory={.buffer=buffer},.tone=true,.period=50,.amp=&amp};
 put16(buffer,1036);put16(buffer+2,1036);
 for(unsigned i=0;i<60;i++){s.jobs[0].active=false;assert(submit(&s,0,MI8_PCM_ADDRESS,false,0));}
 assert(s.tone_blocks==60 && guard_sent==60 && !guard_stopped);
 s.jobs[0].active=false;assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));assert(guard_stopped==1&&guard_sent==60);
 s.tone_blocks=0;
 const int values[]={1037,-1037,-32768};
 for(unsigned i=0;i<3;i++){put16(buffer,(uint16_t)values[i]);put16(buffer+2,(uint16_t)values[i]);assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));}
 put16(buffer,1);put16(buffer+2,1);s.period=49;assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));
 s.period=100;assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));
 s.period=50;guard_ready=false;assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));
 guard_ready=true;put16(buffer+2,2);assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));
 assert(guard_sent==60 && guard_stopped==8);
 printf("Tone submission guards SELFTEST PASS (60 allowed; block 61, amplitude, window, mute state and L/R rejected)\n");
}

#include "mi8_tas2557.h"
void tone_budget_fault(void) {
 uint8_t buffer[32768]={1,0,1,0};unsigned sent=guard_sent;
 const struct mi8_pcm_amp amp={.stop=mi8_tas2557_stop,.audible=mi8_tas2557_audible};
 const struct mi8_pcm_ops ops={.send=guard_send};
 struct mi8_pcm_state s={.io=&ops,.memory={.buffer=buffer},.tone=true,.period=55,.tone_blocks=60,.amp=&amp};
 assert(mi8_tas2557_audible());
 assert(!submit(&s,0,MI8_PCM_ADDRESS,false,0));
 assert(guard_sent==sent && !mi8_tas2557_held());
}
