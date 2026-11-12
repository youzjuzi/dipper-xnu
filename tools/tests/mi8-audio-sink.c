/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <pthread.h>
#include <sched.h>
#define __unused __attribute__((unused))
#define CHECK(x) do {atomic_fetch_add(&checks,1);if(!(x)){fprintf(stderr,"FAIL %u: %s\n",__LINE__,#x);exit(1);}} while(0)
static atomic_uint checks;
static _Thread_local bool held;
static pthread_mutex_t audio_lock=PTHREAD_MUTEX_INITIALIZER;
static void lck_mtx_lock(pthread_mutex_t *p){CHECK(!held);pthread_mutex_lock(p);held=true;}
static void lck_mtx_unlock(pthread_mutex_t *p){CHECK(held);held=false;pthread_mutex_unlock(p);}
typedef uint32_t (*redwood_audio_sink_t)(const int16_t *,uint32_t);
static redwood_audio_sink_t audio_sink;
static bool rec_fed,rec_mic,report_armed;
static uint64_t stretch_lost,stretch_first,stretch_last,stretch_frames,stretch_latest,stretch_sound;
static uint32_t stretch_peak,volume_below,volume_generation;
static bool volume_muted;
static void *report_call;
#define REDWOOD_AUDIO_CHANNELS 2
#define SILENCE 8
#define QUIET_MS 500
#define NSEC_PER_MSEC 1000000
#define NSEC_PER_SEC 1000000000
static atomic_uint_fast64_t clock_ns;
static uint64_t mach_absolute_time(void){return atomic_fetch_add(&clock_ns,1000);}
static void absolutetime_to_nanoseconds(uint64_t at,uint64_t *out){*out=at;}
static void audio_record(const int16_t *p,uint32_t n){(void)p;(void)n;CHECK(held);}
static void clock_interval_to_deadline(unsigned n,unsigned unit,uint64_t *out){*out=atomic_load(&clock_ns)+(uint64_t)n*unit;}
static void thread_call_enter_delayed(void *p,uint64_t deadline){(void)p;(void)deadline;}
static char logs[65536];static unsigned log_used;
static int capture(const char *fmt,...){CHECK(!held);va_list ap;va_start(ap,fmt);int n=vsnprintf(logs+log_used,sizeof(logs)-log_used,fmt,ap);va_end(ap);CHECK(n>=0&&(unsigned)n<sizeof(logs)-log_used);log_used+=(unsigned)n;return n;}
#define printf capture
/* @cdev */
typedef void *DTEntry;
#define kSuccess 0
static const char *platform="dipper";
static unsigned platform_size=7;
static int dt_fail;
static int SecureDTLookupEntry(void *root,const char *path,DTEntry *out){(void)root;CHECK(!strcmp(path,"/arm-io"));*out=(void*)1;return dt_fail;}
static int SecureDTGetProperty(DTEntry entry,const char *name,const void **out,unsigned *size){(void)entry;CHECK(!strcmp(name,"device_type"));*out=platform;*size=platform_size;return 0;}
static int audio_arg=-1;
static unsigned step_arg,owner_arg;
static const char *owner_name="sound";
static bool PE_parse_boot_argn(const char *name,void *value,unsigned bytes){CHECK(bytes==4);uint32_t n=0;bool found=true;if(!strcmp(name,"audio")){found=audio_arg>=0;n=(unsigned)audio_arg;}else if(!strcmp(name,"mi8rp_step"))n=step_arg;else if(!strcmp(name,owner_name))n=owner_arg;else found=false;if(found)memcpy(value,&n,4);return found;}
typedef int thread_t;
typedef int wait_result_t;
#define KERN_SUCCESS 0
static bool spawn_fail;
static unsigned spawned,terminated,deallocated,ticks,stop_tick;
static void (*worker)(void *,int);
static int kernel_thread_start(void(*fn)(void*,int),void *arg,thread_t *out){(void)arg;spawned++;worker=fn;*out=1;return spawn_fail?1:0;}
static void thread_deallocate(thread_t t){(void)t;deallocated++;}
static thread_t current_thread(void){return 1;}
static void thread_terminate(thread_t t){(void)t;terminated++;}
static void delay_for_interval(unsigned,unsigned);
#define MI8_AUDIO_SINK_HOST_TEST
/* @sink */
static void delay_for_interval(unsigned n,unsigned unit){
 CHECK(!held&&n==5&&unit==NSEC_PER_SEC);ticks++;atomic_fetch_add(&clock_ns,5000000000ull);
 if(ticks>=stop_tick){STORE(&stopping,1);return;}
 int16_t frame[2]={0,1};audio_play(frame,1);
 lck_mtx_lock(&audio_lock);volume_generation+=2;volume_below=ticks;volume_muted=ticks&1;lck_mtx_unlock(&audio_lock);
}
#define LOADER_LOG_SIZE (1536*1024)
static char loader_log[LOADER_LOG_SIZE];static uint32_t loader_log_len;
/* audio=2: the DSP worker's tail (mi8_rproc.c), controlled by the test. */
static const char *test_tail="";static unsigned test_tail_len;
static const char *mi8_rproc_audio_tail(unsigned *length){*length=test_tail_len;return test_tail;}
/* @loader */
#undef printf
static void reset(void){
 CHECK(!held);audio_sink=NULL;memset(&pcm,0,sizeof(pcm));memset(&volume,0,sizeof(volume));
 pcm_sequence=volume_sequence=installed=stopping=0;volume_below=volume_generation=0;volume_muted=false;
 session_profile=false;
 platform="dipper";platform_size=7;dt_fail=0;audio_arg=-1;step_arg=owner_arg=0;owner_name="sound";
 spawn_fail=false;spawned=deallocated=terminated=ticks=0;logs[0]=0;log_used=0;worker=NULL;
 atomic_store(&clock_ns,0);
}
static uint32_t other_sink(const int16_t *p,uint32_t n){(void)p;return n;}
static void *writer(void *opaque){
 unsigned seed=(unsigned)(uintptr_t)opaque;
 int16_t frame[2048];for(unsigned i=0;i<1024;i++){frame[2*i]=(i%2)?-32768:0;frame[2*i+1]=(i%2)?32767:0;}
 for(unsigned i=0;i<2000;i++)audio_play(frame,1+(i+seed)%1024);
 return NULL;
}
static atomic_bool read_stop;
static void *reader(void *ignored){
 (void)ignored;bool live=false;
 do {if(session_profile){live=!live;mi8_audio_ring_live(live);}
 struct pcm_counts p;struct volume_counts v;if(snapshot(&p,&v)){
 CHECK(p.frames==p.zero+p.nonzero);CHECK(!p.calls||(p.min_frames>=1&&p.max_frames<=1024&&p.first_us<=p.last_us));
 CHECK(p.peak_l<=32768&&p.peak_r<=32768);
 }}while(!atomic_load(&read_stop));if(session_profile)mi8_audio_ring_live(false);return NULL;
}
static pthread_mutex_t barrier_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t barrier_cond=PTHREAD_COND_INITIALIZER;
static bool entered,released;
static atomic_bool detached,detach_started;
static uint32_t blocking_sink(const int16_t *p,uint32_t n){(void)p;CHECK(held);pthread_mutex_lock(&barrier_lock);entered=true;pthread_cond_broadcast(&barrier_cond);while(!released)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);return n;}
static void *one_write(void *unused){(void)unused;int16_t frame[2]={0};audio_play(frame,1);return NULL;}
static void *detach(void *unused){(void)unused;atomic_store(&detach_started,true);redwood_audio_set_sink("nothing",NULL);atomic_store(&detached,true);return NULL;}
static bool audio_ring_stream,selected_ring,audio_clip_stream,audio_session_stream;
static char audio_tail[16384];static unsigned audio_tail_len;
/* @tail_append */
static void mi8_audio_set_ring(bool enabled){selected_ring=enabled;}
static unsigned dispatch_gate(unsigned audio,unsigned shared_step){
#define say capture
/* @ring_gate */
#undef say
 return audio==2?(audio_session_stream?17:shared_step):0;
}
int main(void){
 volume_muted=true;CHECK(redwood_audio_muted());volume_muted=false;CHECK(!redwood_audio_muted());
 reset();mi8_audio_sink_init();CHECK(!spawned&&!audio_sink&&!installed&&!log_used);
 audio_arg=0;mi8_audio_sink_init();CHECK(!spawned&&!log_used);
 audio_arg=1;platform="redwood";platform_size=8;mi8_audio_sink_init();CHECK(!spawned&&!log_used);
 platform="dipper-extra";platform_size=13;mi8_audio_sink_init();CHECK(!spawned);
 session_profile=false;
 platform="dipper";platform_size=6;mi8_audio_sink_init();CHECK(!spawned);
 platform_size=7;dt_fail=1;mi8_audio_sink_init();CHECK(!spawned);dt_fail=0;
 for(unsigned s=9;s<=17;s++){step_arg=s;mi8_audio_sink_init();CHECK(!spawned&&!audio_sink&&strstr(logs,"conflict"));}
 step_arg=UINT32_MAX;mi8_audio_sink_init();CHECK(!spawned);
 step_arg=0;const char *owners[]={"adsp","adsp_step","sound","virtio_sound"};
 for(unsigned i=0;i<4;i++){owner_name=owners[i];owner_arg=1;mi8_audio_sink_init();CHECK(!spawned&&!audio_sink);}
 owner_arg=0;audio_sink=other_sink;mi8_audio_sink_init();CHECK(audio_sink==other_sink&&!spawned);audio_sink=NULL;
 audio_arg=6;mi8_audio_sink_init();CHECK(!spawned);audio_arg=1;spawn_fail=true;mi8_audio_sink_init();CHECK(!audio_sink&&!installed);spawn_fail=false;
 for(unsigned s=0;s<=8;s++){reset();audio_arg=1;step_arg=s;mi8_audio_sink_init();CHECK(installed&&audio_sink==count_sink&&spawned==1&&deallocated==1);}
 mi8_audio_sink_init();CHECK(spawned==1);CHECK(strstr(logs,"count-only sink installed (no DSP, no amp)"));
 reset();audio_arg=3;CHECK(mi8_audio_ring_requested());
 CHECK(dispatch_gate(3,0)==17&&audio_ring_stream&&selected_ring);
 audio_ring_stream=selected_ring=false;step_arg=1;CHECK(!dispatch_gate(3,1)&&!selected_ring);step_arg=0;
 owner_name="mi8rp_mss";owner_arg=1;CHECK(!dispatch_gate(3,0)&&!selected_ring);
 CHECK(!dispatch_gate(2,0));owner_arg=0;CHECK(dispatch_gate(2,0)==17);
 CHECK(!dispatch_gate(0,0)&&!dispatch_gate(1,0));
 audio_arg=4;CHECK(dispatch_gate(4,0)==17&&audio_clip_stream&&selected_ring);audio_clip_stream=false;
 step_arg=1;CHECK(!dispatch_gate(4,1));step_arg=0;owner_name="mi8rp_mss";owner_arg=1;CHECK(!dispatch_gate(4,0));owner_arg=0;
 audio_arg=5;CHECK(dispatch_gate(5,0)==17&&audio_session_stream&&selected_ring);audio_session_stream=false;
 step_arg=1;CHECK(!dispatch_gate(5,1));step_arg=0;owner_name="mi8rp_mss";owner_arg=1;CHECK(dispatch_gate(5,0)==17);owner_arg=0;audio_session_stream=false;
 reset();audio_arg=5;mi8_audio_sink_init();CHECK(installed&&audio_sink==ring_sink);reset();
 audio_arg=3;
 platform="redwood";platform_size=8;CHECK(!dispatch_gate(3,0));session_profile=false;
 platform="dipper";platform_size=7;

 for(unsigned n=1;n<=18;n++){step_arg=n;CHECK(!mi8_audio_ring_requested());mi8_audio_sink_init();CHECK(!installed&&!audio_sink);}
 step_arg=0;owner_name="mi8rp_mss";owner_arg=1;CHECK(!mi8_audio_ring_requested());mi8_audio_sink_init();CHECK(!installed);
 owner_arg=0;platform="redwood";platform_size=8;CHECK(!mi8_audio_ring_requested());mi8_audio_sink_init();CHECK(!installed);
 session_profile=false;
 platform="dipper";platform_size=7;mi8_audio_sink_init();CHECK(installed&&audio_sink==ring_sink);CHECK(mi8_audio_ring_open());
 int16_t full[2048];for(unsigned i=0;i<2048;i++)full[i]=-32768;
 for(unsigned i=0;i<16;i++)audio_play(full,1024);
 uint64_t lost=stretch_lost;audio_play(full,1024);CHECK(stretch_lost==lost+1024);CHECK(mi8_audio_ring_close());
 struct mi8_audio_ring_counts rc;mi8_audio_ring_counts(&rc);CHECK(rc.accepted==16384&&rc.discarded==16384&&rc.dropped==1024);
 audio_play(full,1024);mi8_audio_ring_counts(&rc);CHECK(rc.outside==1024);
 reset();audio_arg=1;mi8_audio_sink_init();
 int16_t frames[8]={0,0,-32768,32767,32767,-32768,0,1};
 atomic_store(&clock_ns,1000000);audio_play(frames,4);atomic_store(&clock_ns,6000000);audio_play(frames,1);
 struct pcm_counts p;struct volume_counts v;CHECK(snapshot(&p,&v));
 CHECK(p.calls==2&&p.frames==5&&p.zero==2&&p.nonzero==3&&p.min_frames==1&&p.max_frames==4);
 CHECK(p.peak_l==32768&&p.peak_r==32768&&p.first_us==1000&&p.last_us==6000&&p.max_gap_us==5000);
 lck_mtx_lock(&audio_lock);CHECK(count_sink(NULL,1)==0&&count_sink(frames,0)==0&&count_sink(frames,1025)==0);lck_mtx_unlock(&audio_lock);
 CHECK(snapshot(&p,&v)&&p.invalid==3&&p.frames==5);
 volume_generation=9;volume_below=240;volume_muted=true;sample_volume();CHECK(snapshot(&p,&v)&&v.changes==9&&v.generation==9&&v.below==240&&v.muted&&v.seen);
 volume_generation=12;sample_volume();CHECK(snapshot(&p,&v)&&v.changes==12);
 STORE(&volume.generation,UINT32_MAX);volume_generation=1;sample_volume();CHECK(snapshot(&p,&v)&&v.changes==14);
 struct pcm_counts prev={0};struct volume_counts volprev={0};unsigned lines=0;
 CHECK(report_changed(&prev,&volprev,&lines));sample_volume();CHECK(!report_changed(&prev,&volprev,&lines));
 STORE(&pcm_sequence,LOAD(&pcm_sequence)+1);char out[768];CHECK(mi8_audio_sink_summary(out,sizeof(out))>0&&strstr(out,"partial"));
 CHECK(mi8_audio_sink_summary(out,0)==0);STORE(&pcm_sequence,LOAD(&pcm_sequence)+1);STORE(&stopping,0);
 reset();audio_arg=5;mi8_audio_sink_init();
 mi8_audio_ring_live(false);atomic_store(&clock_ns,1000000);audio_play(frames,4);
 CHECK(snapshot(&p,&v)&&p.clipped_samples==4&&!mi8_audio_ring_live_gap());
 mi8_audio_ring_live(true);atomic_store(&clock_ns,1000000000);audio_play(frames,4);
 atomic_store(&clock_ns,1050000000);audio_play(frames,4);
 CHECK(mi8_audio_ring_live_gap()==50000);
 mi8_audio_ring_live(false);atomic_store(&clock_ns,9000000000ull);audio_play(frames,4);
 mi8_audio_ring_live(true);atomic_store(&clock_ns,20000000000ull);audio_play(frames,4);
 atomic_store(&clock_ns,20010000000ull);audio_play(frames,4);
 CHECK(snapshot(&p,&v)&&p.clipped_samples==24&&mi8_audio_ring_live_gap()==50000);
 mi8_audio_ring_live(false);
 for(unsigned profile=1;profile<=5;profile+=4){
 reset();audio_arg=profile;mi8_audio_sink_init();pthread_t writers[4],observer;
 atomic_store(&read_stop,false);CHECK(!pthread_create(&observer,NULL,reader,NULL));
 uint64_t expected=0;for(unsigned w=0;w<4;w++){for(unsigned i=0;i<2000;i++)expected+=1+(i+w)%1024;CHECK(!pthread_create(&writers[w],NULL,writer,(void*)(uintptr_t)w));}
 for(unsigned w=0;w<4;w++){CHECK(!pthread_join(writers[w],NULL));}
 atomic_store(&read_stop,true);CHECK(!pthread_join(observer,NULL));
 CHECK(snapshot(&p,&v)&&p.calls==8000&&p.frames==expected&&p.zero+p.nonzero==expected&&p.peak_l==32768&&p.peak_r==32767);
 redwood_audio_set_sink("nothing",NULL);audio_play(frames,4);CHECK(snapshot(&p,&v)&&p.calls==8000);
 }
 reset();audio_sink=blocking_sink;pthread_t first,last;CHECK(!pthread_create(&first,NULL,one_write,NULL));
 pthread_mutex_lock(&barrier_lock);while(!entered)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);
 CHECK(!pthread_create(&last,NULL,detach,NULL));while(!atomic_load(&detach_started))sched_yield();
 CHECK(!atomic_load(&detached));CHECK(pthread_mutex_trylock(&audio_lock)!=0);
 pthread_mutex_lock(&barrier_lock);released=true;pthread_cond_broadcast(&barrier_cond);pthread_mutex_unlock(&barrier_lock);
 CHECK(!pthread_join(first,NULL)&&!pthread_join(last,NULL));CHECK(atomic_load(&detached)&&!audio_sink);
 reset();audio_arg=1;mi8_audio_sink_init();stop_tick=65;worker(NULL,0);CHECK(terminated==1&&ticks==65);
 unsigned aggregates=0;for(char *at=logs;(at=strstr(at,"audio: count snapshot="));at++)aggregates++;CHECK(aggregates==58);
 /* A final snapshot must not acquire even a held audio mutex, including a
  * half-published volume update from a parked statistics worker. */
 lck_mtx_lock(&audio_lock);STORE(&volume_sequence,LOAD(&volume_sequence)+1);
 loader_log_len=LOADER_LOG_SIZE;memset(loader_log,'x',sizeof(loader_log));memcpy(loader_log+sizeof(loader_log)-4,"TAIL",4);
 loader_audio_summary();CHECK(loader_log_len==LOADER_LOG_SIZE);
 char tail[32769];memcpy(tail,loader_log+loader_log_len-32768,32768);tail[32768]=0;
 CHECK(strstr(tail,"TAILaudio: final count-only snapshot=partial")&&strstr(tail,"calls=")&&strstr(tail,"volume_changes="));
 lck_mtx_unlock(&audio_lock);CHECK(LOAD(&stopping));
 loader_log_len=0;loader_audio_summary();CHECK(loader_log_len>0&&loader_log_len<768&&loader_log[loader_log_len-1]=='\n');
 reset();loader_log_len=42;loader_audio_summary();CHECK(loader_log_len==42);
 /* audio=2: the worker's tail first, then the sink summary, both in the last 32 KiB of a full log. */
 reset();audio_arg=2;mi8_audio_sink_init();CHECK(LOAD(&installed));
 test_tail="mi8rp: audio=2: zero stream completed cleanup=complete\n";test_tail_len=(unsigned)strlen(test_tail);
 loader_log_len=LOADER_LOG_SIZE;memset(loader_log,'x',sizeof(loader_log));
 loader_audio_summary();CHECK(loader_log_len==LOADER_LOG_SIZE);
 memcpy(tail,loader_log+loader_log_len-32768,32768);tail[32768]=0;
 {char *z=strstr(tail,"mi8rp: audio=2: zero stream completed"),*f=strstr(tail,"audio: final count-only snapshot=");CHECK(z&&f&&z<f);}
 test_tail_len=0;reset();loader_log_len=42;loader_audio_summary();CHECK(loader_log_len==42);
 /* Run actual worker tail append and loader final append with 300 s at 50 Hz. */
 reset();audio_arg=5;mi8_audio_sink_init();audio_session_stream=true;audio_ring_stream=false;audio_tail_len=0;
 for(unsigned i=0;i<15000;i++){char line[128];int n=snprintf(line,sizeof(line),"mi8rp: stream period=%u time=%u ms done=ok progress\n",i,i*20);audio_tail_append(line,(unsigned)n);}
 const char *ending="mi8rp: play completed\nmi8rp: asm close ok\nmi8rp: audio=5: cleanup=complete\n";
 audio_tail_append(ending,(unsigned)strlen(ending));test_tail=audio_tail;test_tail_len=audio_tail_len;
 loader_log_len=LOADER_LOG_SIZE;memset(loader_log,'x',sizeof(loader_log));loader_audio_summary();
 memcpy(tail,loader_log+loader_log_len-32768,32768);tail[32768]=0;
 CHECK(strstr(tail,"period=14999")&&strstr(tail,"play completed")&&strstr(tail,"asm close ok")&&strstr(tail,"cleanup=complete")&&strstr(tail,"audio: final count-only")&&strstr(tail,"LIVE HAL_max_gap_us="));
 CHECK(!strstr(tail,"period=0 time="));
 printf("Count sink SELFTEST PASS: 8000 concurrent writes per profile (count/session); exact totals, detach barrier, atomic snapshots, 58 periodic lines, full-log final tail; %u assertions\n",atomic_load(&checks));
 return 0;
}
