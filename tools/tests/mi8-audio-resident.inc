/* SPDX-License-Identifier: MIT */
/* Fixed arrays only; exercise the real feeder, APR/GLINK, ring and controller. */
#include <malloc.h>
#ifdef MI8_RESIDENT_ALLOC_TEST
static struct {void *p;size_t n;} resident_allocations[128];
void *__real_calloc(size_t,size_t);
void __real_free(void *);
void *__wrap_calloc(size_t n,size_t size){
 void *p=__real_calloc(n,size);if(!p)return p;
 for(unsigned i=0;i<128;i++)if(!resident_allocations[i].p){resident_allocations[i].p=p;resident_allocations[i].n=n*size;return p;}
 CHECK(false);return NULL;
}
void __wrap_free(void *p){
 for(unsigned i=0;i<128;i++)if(resident_allocations[i].p==p){resident_allocations[i].p=NULL;resident_allocations[i].n=0;break;}
 __real_free(p);
}
#endif
static size_t resident_allocation_bytes(void){
#ifdef MI8_RESIDENT_ALLOC_TEST
 size_t n=0;for(unsigned i=0;i<128;i++)n+=resident_allocations[i].n;return n;
#else
 return mallinfo2().uordblks;
#endif
}
static void resident_run(void){
 uint32_t seed=0x671245ab;uint64_t at=1000000;
 for(unsigned i=0;i<1003;i++){
  seed=seed*1664525u+1013904223u;
  uint64_t length=i<1000?200000+(seed%4800001):1260000000ull;
  resident_cues[i]=(struct resident_cue){at,at+length};
  seed=seed*1664525u+1013904223u;at+=length+31000000+(seed%20000001);
 }
 stream_seconds=(unsigned)(at/1000000+600);CHECK(stream_seconds>=14400);
 resident_mode=true;resident_index=0;reset_ring();outputs=max_peak=ticks=0;mode=0;
 CHECK(mi8_pcm_session_seconds(0));mi8_tas_session_seconds(0);
 struct peer p;struct play_peer m;prepare(&p,&m);active=&p;m.step=16;
 control_prepared=true;CHECK(session_model_prepare(0));p.now=session_model_now();stream_start=p.now;
 if(threaded){controller_delay=0;controller_clock=p.now;controller_quit=0;CHECK(!pthread_create(&controller_thread,NULL,controller_main,NULL));}
 p.extension=&m;p.extra_response=play_reply;p.reply=p.header8=p.afe_mode=true;amp_observe=observe;amp_cache_observe=NULL;
 mi8_audio_set_ring(true);mi8_audio_set_session(&session_ops);
 struct mi8_audio_pin_ops pins={pin_read,pin_write,&p};struct mi8_glink_cfg c=cfg(&p);c.log=play_log;
 struct mi8_pcm_ops memory={.ctx=&p,.begin=play_begin,.cache=play_cache,.fault=play_fault,.clear=play_clear,.end=play_end};
 size_t allocated=resident_allocation_bytes();
 bool okay=mi8_audio_run_play(&c,play_alive,&p,&pins,&memory,p.now+(uint64_t)(stream_seconds+10)*1000000,17,play_fatal);
 size_t after=resident_allocation_bytes();CHECK(resident_heap&&after<=resident_heap+4096);
 (void)join_control();m.reset=true;CHECK(mi8_audio_finish_play(true));
 struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);struct mi8_audio_ring_counts r;mi8_audio_ring_counts(&r);
 CHECK(okay&&a.done&&a.clean&&!a.reason&&a.wakes==1003&&a.mutes==1003&&a.checks==1003&&a.checks_ok==1003);
 for(unsigned i=0;i<1003;i++)CHECK(resident_seen[i]);
 CHECK(r.accepted==r.consumed+r.discarded&&!r.queued);
 CHECK(strstr(m.log,"play:")&&strstr(m.log,"asm stream close"));
 char report[512];mi8_tas_session_report(report,sizeof(report));CHECK(strstr(report," resident"));
 CHECK(m.log_length<sizeof(m.log)&&sizeof(resident_cues)==1003*sizeof(struct resident_cue));
 printf("Resident native stream PASS: %u virtual seconds, %u periods, %u wakes/mutes, %u checks; 1000 random 0.2..5s sounds and 3x21min continuous, long silence; conservation, fixed arrays, heap=%zu->%zu->%zu, bounded tail=%zu; %lu checks\n",stream_seconds,m.normal,a.wakes,a.checks_ok,allocated,resident_heap,after,m.log_length,checks+session_model_checks());
 mi8_audio_set_session(NULL);mi8_audio_set_ring(false);
}
