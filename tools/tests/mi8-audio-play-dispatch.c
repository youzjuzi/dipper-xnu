/* SPDX-License-Identifier: MIT */
/* Marked blocks are filled with the actual rproc source by the runner. */
#include <pthread.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <errno.h>
#define CHECK(x) do{checks++;if(!(x))abort();}while(0)
static unsigned checks;
static pthread_mutex_t wsmmu_lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned locks,unlocks,play_calls,afe_calls,core_calls;
static uint64_t audio_play_until=45000000, fake_now=30000000;
/* The play budget starts after firmware loading and DSP startup. */
static uint64_t now_us(void){return fake_now;}
static int adsp_remote;
static bool audio_smmu_serial=true, audio_play_locked, defer_play;
static bool mi8_audio_play_needs_finish(void){return defer_play;}
static atomic_uint active,overlaps;
static void allocation(void){if(atomic_fetch_add(&active,1))atomic_fetch_add(&overlaps,1);sched_yield();atomic_fetch_sub(&active,1);}
static void lck_mtx_lock(pthread_mutex_t*l){pthread_mutex_lock(l);locks++;}
static void lck_mtx_unlock(pthread_mutex_t*l){unlocks++;pthread_mutex_unlock(l);}
static bool mi8_audio_run_play(void*c,void*f,void*r,void*p,void*m,uint64_t end){(void)c;(void)f;(void)r;(void)p;(void)m;CHECK(end==fake_now+15000000);play_calls++;allocation();return true;}
static uint64_t mi8_audio_play_teardown_end(void){return 15000000;}
static bool mi8_audio_run_afe(void*c,void*f,void*r,void*p){(void)c;(void)f;(void)r;(void)p;afe_calls++;return true;}
static bool mi8_audio_run(void*c,void*f,void*r){(void)c;(void)f;(void)r;core_calls++;return true;}
static void wsmmu_before_power_unserialized(void){allocation();}
#define __unused __attribute__((unused))
typedef int wait_result_t;
typedef int thread_t;
#define KERN_SUCCESS 0
static unsigned smmu_spawn,play_spawn,old_calls,deallocated;
static int current_thread(void){return 0;}
static void thread_terminate(int t){(void)t;}
static void mi8_audio_smmu_run(unsigned n){CHECK(n==11||n==12);smmu_spawn++;}
static void steps_from_five(void*p,int r){(void)r;CHECK((uintptr_t)p>=13);play_spawn++;}
/* @wsmmu_before_power */
/* @audio_smmu_thread */
static bool handshake(unsigned last){int cfg=0;void*audio_alive=NULL;
/* @play_handshake */
return last>=10?mi8_audio_run_afe(&cfg,audio_alive,&adsp_remote,NULL):mi8_audio_run(&cfg,audio_alive,&adsp_remote);}
static int kernel_thread_start(void(*f)(void*,int),void*p,int*t){*t=1;f(p,0);return 0;}
static void thread_deallocate(int t){(void)t;deallocated++;}
static void dispatch(unsigned last){/* @dispatch_13 */
/* @dispatch_11 */
old_calls++;}
static void*worker(void*p){for(unsigned i=0;i<200;i++){if(p)handshake(13);else wsmmu_before_power();}return NULL;}
int main(void){pthread_t a,b;CHECK(handshake(8)&&handshake(9)&&handshake(10));CHECK(core_calls==2&&afe_calls==1&&!locks);
CHECK(!pthread_create(&a,NULL,worker,(void*)1));CHECK(!pthread_create(&b,NULL,worker,NULL));CHECK(!pthread_join(a,NULL));CHECK(!pthread_join(b,NULL));CHECK(play_calls==200&&locks==400&&unlocks==400&&!atomic_load(&overlaps));
defer_play=true;fake_now+=17000000;CHECK(handshake(13)&&audio_play_locked);
CHECK(pthread_mutex_trylock(&wsmmu_lock)==EBUSY);lck_mtx_unlock(&wsmmu_lock);audio_play_locked=false;defer_play=false;
for(unsigned n=8;n<=13;n++) { dispatch(n); }
CHECK(old_calls==3&&smmu_spawn==2&&play_spawn==1&&deallocated==3);printf("Play allocation/dispatch SELFTEST PASS %u/%u\n",checks,checks);return 0;}
