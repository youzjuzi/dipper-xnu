#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the actual bounded SMMU diagnostic against synthetic registers/RAM."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def body(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def check_shared_allocation(source, tmp, cflags, run_env):
    # Execute the real conditional-lock wrappers and early dispatcher branch.
    wrappers = '\n'.join(body(source, 'static void\n' + name + '(')
                         for name in ('wsmmu_before_power', 'audio_smmu_thread'))
    branch = body(source, 'if (last >= 11)')
    code = r'''
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#define __unused __attribute__((unused))
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"gate FAIL %u: %s\n",__LINE__,#x);exit(1);}} while(0)
typedef int wait_result_t;
typedef int thread_t;
#define KERN_SUCCESS 0
static unsigned checks, old_calls, spawned, deallocated;
static bool audio_smmu_serial, spawn_fail;
static pthread_mutex_t wsmmu_lock=PTHREAD_MUTEX_INITIALIZER;
static atomic_uint locks,unlocks,active,overlaps,terminated;
static void lck_mtx_lock(pthread_mutex_t*p){pthread_mutex_lock(p);atomic_fetch_add(&locks,1);}
static void lck_mtx_unlock(pthread_mutex_t*p){atomic_fetch_add(&unlocks,1);pthread_mutex_unlock(p);}
static void allocation(void){if(atomic_fetch_add(&active,1))atomic_fetch_add(&overlaps,1);for(unsigned n=0;n<10;n++)sched_yield();atomic_fetch_sub(&active,1);}
static void wsmmu_before_power_unserialized(void){allocation();}
static void mi8_audio_smmu_run(unsigned step){if(step<11)abort();allocation();}
static int current_thread(void){return 0;}
static void thread_terminate(int t){(void)t;atomic_fetch_add(&terminated,1);}
''' + wrappers + r'''
static int kernel_thread_start(void(*fn)(void*,int),void*arg,thread_t*out){spawned++;if(spawn_fail)return 1;*out=1;fn(arg,0);return 0;}
static void thread_deallocate(thread_t thread){(void)thread;deallocated++;}
static void dispatch(unsigned last){
''' + branch + r'''
 old_calls++;
}
static void *worker(void*arg){for(unsigned n=0;n<200;n++){if(arg)audio_smmu_thread((void*)12,0);else wsmmu_before_power();}return NULL;}
int main(void){
 pthread_t a,b;
 audio_smmu_serial=false;wsmmu_before_power();audio_smmu_thread((void*)11,0);
 CHECK(!atomic_load(&locks)&&!atomic_load(&unlocks));
 audio_smmu_serial=true;
 CHECK(!pthread_create(&a,NULL,worker,(void*)1));CHECK(!pthread_create(&b,NULL,worker,NULL));
 CHECK(!pthread_join(a,NULL));CHECK(!pthread_join(b,NULL));
 CHECK(!atomic_load(&overlaps)&&!atomic_load(&active));
 CHECK(atomic_load(&locks)==400&&atomic_load(&unlocks)==400);
 dispatch(11);dispatch(12);CHECK(old_calls==0&&spawned==2&&deallocated==2);
 dispatch(8);dispatch(9);dispatch(10);CHECK(old_calls==3&&spawned==2);
 spawn_fail=true;dispatch(12);CHECK(old_calls==3&&spawned==3&&deallocated==2);
 printf("Shared SMMU allocation/dispatch SELFTEST PASS %u/%u\n",checks,checks);return 0;
}
'''
    c, exe = Path(tmp) / 'allocation.c', Path(tmp) / 'allocation'
    c.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread', *cflags, str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], env=run_env, check=True)


def check_native_claim(engine, dev, tmp, cflags, run_env):
    # Compile the real native reservation bridge, not a hand-written surrogate.
    bridge = body(engine, 'bool\nmi8_audio_smmu_reserved(')
    native_run = body(engine, 'void\nmi8_audio_smmu_run(')
    assert 'native_table_read, &native_claim' in native_run
    assert 'if (native_result.retained)' in native_run
    code = r'''
#include "mi8_audio_smmu.h"
#include <stdio.h>
#include <stdlib.h>
static struct mi8_smmu_claim native_claim;
static struct mi8_smmu_result native_result;
static unsigned checks;
#define CHECK(x) do {checks++; if(!(x)) abort();} while(0)
''' + bridge + r'''
int main(void) {
 CHECK(!mi8_audio_smmu_reserved(~0u,43));
 native_claim.owned=true; native_claim.bank=43;
 CHECK(mi8_audio_smmu_reserved(~0u,43));
 CHECK(!mi8_audio_smmu_reserved(8,~0u));
 CHECK(!mi8_audio_smmu_reserved(~0u,44));
 native_result.retained=true; native_result.slot=8; native_result.bank=43;
 CHECK(mi8_audio_smmu_reserved(8,~0u));
 CHECK(mi8_audio_smmu_reserved(~0u,43));
 native_result.retained=false;
 CHECK(!mi8_audio_smmu_reserved(8,~0u));
 CHECK(mi8_audio_smmu_reserved(~0u,43));
 printf("Native SMMU claim bridge SELFTEST PASS %u/%u\n",checks,checks);
 return 0;
}
'''
    c, exe = Path(tmp) / 'claim.c', Path(tmp) / 'claim'
    c.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', *cflags,
                    '-DMI8_SMMU_HOST_TEST', '-I' + str(dev), str(c),
                    str(dev / 'mi8_audio_smmu.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], env=run_env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=ROOT / 'work')
    parser.add_argument('--sanitize', action='store_true', help='run ASan/UBSan; leak detection is unavailable under ptrace')
    args = parser.parse_args()
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    cflags, run_env = [], None
    if args.sanitize:
        cflags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all']
        run_env = dict(os.environ)
        run_env['ASAN_OPTIONS'] = run_env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    with tempfile.TemporaryDirectory(prefix='mi8-smmu-test-') as tmp:
        exe = Path(tmp) / 'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                        *cflags, '-DMI8_SMMU_HOST_TEST', '-I' + str(dev),
                        str(ROOT / 'tools/tests/mi8-audio-smmu.c'),
                        str(dev / 'mi8_audio_smmu.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], env=run_env, check=True)
        source = (dev / 'mi8_rproc.c').read_text()
        assert source.index('if (last >= 11)') < source.index('if (last >= 1)', source.index('if (last >= 11)'))
        assert 'audio_smmu_serial = shared_step >= 12;' in source
        assert 'mi8_audio_smmu_reserved(n, ~0u)' in source and 'mi8_audio_smmu_reserved(~0u, n)' in source
        check_native_claim((dev / 'mi8_audio_smmu.c').read_text(), dev, tmp, cflags, run_env)
        check_shared_allocation(source, tmp, cflags, run_env)


if __name__ == '__main__':
    main()
