#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native short-lock bridges, ownership and dependency policy under real contention."""
import argparse,os,runpy,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--tree',type=Path,default=ROOT/'work');ap.add_argument('--tsan',action='store_true');ap.add_argument('--sanitize',action='store_true');a=ap.parse_args()
 d=a.tree/'hackios/xnu-src/xnu-8796.121.2/bsd/dev';s=(d/'mi8_rproc.c').read_text();body=runpy.run_path(str(ROOT/'tools/tests/test-mi8-audio-smmu.py'))['body']
 functions='\n'.join(body(s,sig) for sig in ['static bool audio_route_reserved(','static bool audio_wifi_target(','struct mi8_smmu_mapping *mi8_rproc_audio_smmu_begin(','bool mi8_rproc_audio_smmu_end(','static uint64_t audio_session_stream_end(','static bool audio_session_dependency('])
 # Extract the actual dynamic Wi-Fi mapping path, substituting only its ARM cache barriers.
 mapper=body(s,'bool\nmi8_wsmmu_map(').replace('__asm__ volatile ("dc civac, %0" : : "r" (line));','(void)line;').replace('__asm__ volatile ("dsb sy");','__sync_synchronize();')
 assert 'audio_wifi_target(slot,n)' in s and 'slot == ~0u && audio_wifi_target(n,~0u)' in s
 assert 'play_session_ops?mi8_rproc_audio_smmu_begin()' in (d/'mi8_audio.c').read_text()
 assert 'play_session_ops?mi8_rproc_audio_smmu_end(safe)' in (d/'mi8_audio.c').read_text()
 # All playback claims enforce the exact resource pair before any writes.
 assert 'if (dual && (slot != 8 || bank != 43))' in (d/'mi8_audio_smmu.c').read_text()
 code=r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <assert.h>
#include <stdlib.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <stdatomic.h>
#define NSEC_PER_MSEC 1000000u
#define NSEC_PER_USEC 1000u
#define WSMMU_CB_TLBIASID 0x610u
#define WSMMU_CB_TLBSYNC 0x7f0u
#define WSMMU_CB_TLBSTATUS 0x7f4u
#define WSMMU_TABLES 1
#define WSMMU_PTE 3
static void say(const char *fmt,...){(void)fmt;}
typedef uintptr_t vm_offset_t;
static pthread_mutex_t wsmmu_lock=PTHREAD_MUTEX_INITIALIZER;
static _Thread_local bool held;
static unsigned audio_route_owner,audio_radio_state;
static uint64_t audio_lock_max_us,wifi_lock_wait_max_us,audio_return_deadline;
static bool audio_session_stream=true,audio_wait_radio,simulated,retained,fail_begin,fail_end;
static uint64_t fake_now,event_at;static unsigned event_state;
static uint64_t now_us(void){if(simulated)return fake_now;struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return (uint64_t)t.tv_sec*1000000+t.tv_nsec/1000;}
static void delay_for_interval(unsigned n,unsigned scale){if(simulated){fake_now+=(uint64_t)n*scale/1000;if(event_at&&fake_now>=event_at)__atomic_store_n(&audio_radio_state,event_state,__ATOMIC_RELEASE);}else sched_yield();}
static void lck_mtx_lock(pthread_mutex_t *m){assert(!held);struct timespec until;clock_gettime(CLOCK_REALTIME,&until);until.tv_sec+=5;assert(!pthread_mutex_timedlock(m,&until));held=true;}
static void lck_mtx_unlock(pthread_mutex_t *m){assert(held);held=false;assert(!pthread_mutex_unlock(m));}
struct mi8_smmu_mapping {unsigned slot,bank;bool active;};
static struct mi8_smmu_mapping map;
static struct mi8_smmu_mapping *mi8_audio_smmu_begin(void){assert(held);map=(struct mi8_smmu_mapping){8,43,!fail_begin};for(unsigned i=0;i<10;i++)sched_yield();return fail_begin?NULL:&map;}
static bool mi8_audio_smmu_end(bool safe){assert(held);if(!safe||fail_end){retained=true;return false;}map.active=false;retained=false;return true;}
static bool mi8_audio_smmu_reserved(unsigned slot,unsigned bank){(void)bank;assert(held);return retained&&slot==8;}
static bool wsmmu_translating=true;
static unsigned wsmmu_context=44,wsmmu_table_count=1;
static vm_offset_t wsmmu_cb=0xabc000,wsmmu_tables;
static uint64_t entries[512];
static uint64_t *wsmmu_table(unsigned n){assert(!n&&held);return entries;}
static uint64_t *wsmmu_next(uint64_t *p){assert(held&&p>=entries&&p<entries+512);return entries;}
static unsigned mmio_writes;
static void wr(vm_offset_t a,uint32_t v){(void)v;assert(held&&wsmmu_context==44&&(a==wsmmu_cb+WSMMU_CB_TLBIASID||a==wsmmu_cb+WSMMU_CB_TLBSYNC));mmio_writes++;}
static uint32_t rd(vm_offset_t a){assert(held&&a==wsmmu_cb+WSMMU_CB_TLBSTATUS);return 0;}
''' +functions+mapper+r'''
static atomic_uint wifi_maps,wifi_unmaps,play_maps,phase;
/* Native Wi-Fi maps are append-only. Model a future unmap's lock/ownership
 * contract here without adding an unmap operation to the device driver. */
static void radio_unmap(void){
 lck_mtx_lock(&wsmmu_lock);assert(audio_wifi_target(9,wsmmu_context));
 for(unsigned i=0;i<512;i++)entries[i]=0;
 atomic_fetch_add(&wifi_unmaps,1);lck_mtx_unlock(&wsmmu_lock);
}
static void *radio(void *unused){(void)unused;for(unsigned i=0;i<2000;i++){assert(mi8_wsmmu_map(0x400000,4096));atomic_fetch_add(&wifi_maps,1);if(atomic_load(&phase)==1)atomic_fetch_add(&play_maps,1);radio_unmap();sched_yield();}return NULL;}
int main(void){
 __atomic_store_n(&audio_route_owner,1,__ATOMIC_RELEASE);
 assert(audio_route_reserved(8,~0u)&&audio_route_reserved(~0u,43));
 assert(!audio_wifi_target(8,44)&&!audio_wifi_target(9,43)&&audio_wifi_target(9,44)&&!audio_wifi_target(9,42));
 wsmmu_context=43;assert(!mi8_wsmmu_map(0x400000,4096)&&!mmio_writes);wsmmu_context=44;
 fail_begin=true;retained=true;assert(!mi8_rproc_audio_smmu_begin()&&audio_route_owner==3&&!held);fail_begin=retained=false;
 pthread_t t;assert(!pthread_create(&t,NULL,radio,NULL));
 for(unsigned i=0;i<100;i++){
  assert(mi8_rproc_audio_smmu_begin()==&map&&!held&&audio_route_owner==3);
  atomic_store(&phase,1);
  /* No audio lock held across this simulated DMA period. */
  for(unsigned j=0;j<100;j++)sched_yield();
  atomic_store(&phase,0);
  assert(mi8_rproc_audio_smmu_end(true)&&!held&&audio_route_owner==1);
 }
 assert(!pthread_join(t,NULL));assert(atomic_load(&wifi_maps)==2000&&atomic_load(&wifi_unmaps)==2000&&atomic_load(&play_maps)>0);
 fail_end=true;assert(!mi8_rproc_audio_smmu_end(true)&&audio_route_owner==3);fail_end=false;
 assert(!mi8_rproc_audio_smmu_end(false)&&audio_route_owner==3);assert(mi8_rproc_audio_smmu_end(true)&&audio_route_owner==1);
 assert(wifi_lock_wait_max_us<5000000);
 simulated=true;audio_wait_radio=true;
 for(unsigned n=0;n<3;n++){fake_now=0;audio_radio_state=0;event_at=n==2?0:7000000;event_state=n+1;assert(audio_session_dependency()==(n==0));assert(fake_now==(n==2?90000000:7000000));}
 audio_wait_radio=false;assert(audio_session_dependency());
 assert(audio_session_stream_end(70000000,300,410000000)==380000000);
 assert(audio_session_stream_end(100000000,300,410000000)==410000000);
 assert(!audio_session_stream_end(100000001,300,410000000));
 assert(!audio_session_stream_end(410000000,120,410000000));
 assert(audio_session_stream_end(0,0,0)==(~(uint64_t)0>>1)&&!audio_session_stream_end(0,901,0));
 assert(audio_session_stream_end(1000000,0,10000000)==10000000);
 assert(!audio_session_stream_end(9000000,0,10000000));
 assert(audio_session_stream_end(50000000,900,1070000000)==960000000);
 printf("Coexist PASS: 100 claim/DMA/end cycles; 2000 actual Wi-Fi maps + simulated unmaps, %u maps during DMA; held=%llu us wait=%llu us; ownership/failure retention; READY/FAILED/90s timeout; 300/900s loader budget\n",atomic_load(&play_maps),(unsigned long long)audio_lock_max_us,(unsigned long long)wifi_lock_wait_max_us);
}
'''
 with tempfile.TemporaryDirectory(prefix='mi8-coexist-') as tmp:
  p=Path(tmp);(p/'test.c').write_text(code);flags=['-std=c11','-Wall','-Wextra','-Werror','-pthread'];env=dict(os.environ)
  if a.tsan:flags+=['-fsanitize=thread','-g','-no-pie'];env['TSAN_OPTIONS']='halt_on_error=1'
  if a.sanitize:flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie'];env['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
  subprocess.run(['cc',*flags,str(p/'test.c'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],env=env,check=True,timeout=30)
if __name__=='__main__':main()
