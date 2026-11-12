#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded native controller join, extracted from the actual source."""
from pathlib import Path
import argparse,runpy,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--tree',type=Path,default=root/'work');args=ap.parse_args()
body=runpy.run_path(str(root/'tools/tests/test-mi8-audio-smmu.py'))['body']
s=(args.tree/'hackios/xnu-src/xnu-8796.121.2/bsd/dev/mi8_tas2557.c').read_text()
join=body(s,'bool mi8_tas_session_join(')
code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include <pthread.h>
#include <sched.h>
#define SA(p) __atomic_load_n(&(p),__ATOMIC_ACQUIRE)
#define SP(p,v) __atomic_store_n(&(p),(v),__ATOMIC_RELEASE)
#define PIN(n) (0x03500000u+0x1000u*(n))
#define NSEC_PER_MSEC 1000000
static struct{unsigned done,clean,reset_low,expired;}session;
static bool session_started,active;
static void *session_thread;
static uint64_t clock_us,finish_at;
static unsigned reset_writes,requests,expired,deallocated,release_hung;
static void *hung_control(void *p){(void)p;while(!__atomic_load_n(&release_hung,__ATOMIC_ACQUIRE))sched_yield();return NULL;}
static void mi8_tas_session_stop_request(void){requests++;}
static uint64_t native_now(void*p){(void)p;return clock_us;}
static bool thread_is_active(void *t){assert(t==(void*)1);return active;}
static void delay_for_interval(unsigned n,unsigned scale){assert(scale==NSEC_PER_MSEC);clock_us+=n*1000;if(finish_at&&clock_us>=finish_at){session.done=session.clean=1;active=false;}}
static void mi8_tas_session_expired(void){expired++;session.expired=1;session.clean=0;}
static void native_write(void*p,unsigned a,unsigned v){(void)p;assert(a==PIN(76)+4&&!v&&expired);reset_writes++;}
static unsigned native_read(void*p,unsigned a){(void)p;assert(a==PIN(76)+4);return 0;}
static void native_log(void*p,const char*s){(void)p;(void)s;}
static void thread_deallocate(void *t){assert(t==(void*)1);deallocated++;}
'''+join+r'''
int main(void){
 assert(!mi8_tas_session_join()&&!requests&&!reset_writes);
 session_started=true;session_thread=(void*)1;active=true;finish_at=200000;
 assert(mi8_tas_session_join()&&clock_us==200000&&deallocated==1&&!reset_writes);
 pthread_t hung;assert(!pthread_create(&hung,NULL,hung_control,NULL));
 session.done=session.clean=0;session_thread=(void*)1;active=true;finish_at=0;clock_us=0;
 assert(!mi8_tas_session_join()&&clock_us==300000&&reset_writes==1&&session_thread==(void*)1&&expired==1&&!session.clean&&session.reset_low);
 /* Resource quiescence alone is not a completed thread termination. */
 assert(!mi8_tas_session_join()&&clock_us==300000&&reset_writes==1);
 session.expired=0;session.done=session.clean=1;clock_us=0;
 assert(!mi8_tas_session_join()&&clock_us==300000&&reset_writes==2&&session_thread==(void*)1);
 __atomic_store_n(&release_hung,1,__ATOMIC_RELEASE);assert(!pthread_join(hung,NULL));
 puts("Native join PASS: absent, normal, hung, done-but-active; 300 ms fallback retains thread, reset low FAILED");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'join.c').write_text(code)
 subprocess.run(['cc','-pthread','-std=c11','-Wall','-Wextra','-Werror',str(p/'join.c'),'-o',str(p/'join')],check=True)
 subprocess.run([str(p/'join')],check=True)
