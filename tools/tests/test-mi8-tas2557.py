#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise real TAS parser, SE5 FIFO and open-drain GPIO code using private firmware and prior read-only decode.

No firmware bytes, decoded register data, or hardware observations are committed.
The reference text/JSON must come from an independent decoder, not this driver.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree', type=Path, default=ROOT / 'work')
    ap.add_argument('--firmware', type=Path, required=True)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--metadata', type=Path, required=True)
    ap.add_argument('--sanitize', action='store_true')
    args = ap.parse_args()
    meta = json.loads(args.metadata.read_text())
    assert hashlib.sha256(args.firmware.read_bytes()).hexdigest() == meta['sha256']
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    normalized, blocks, current = [], {}, None
    for line in args.reference.read_text().splitlines():
        if line.startswith('BLOCK '):
            m = re.fullmatch(r'BLOCK (\S+) offset=(0x[0-9a-f]+) type=(0x[0-9a-f]+) words=(\d+) crc=\[(\d+), (\d+), (\d+), (\d+)\]', line)
            assert m, line
            label, offset, typ, words, *crc = m.groups()
            normalized.append('B ' + ' '.join(map(str, [int(offset, 16), int(typ, 16), int(words), *map(int, crc)])))
            current = blocks[label] = []
        elif ' WRITE ' in line:
            at, _, b, p, r, v = line.split()
            values = [int(x, 16) for x in (b, p, r, v)]
            normalized.append('W ' + ' '.join(map(str, [int(at[1:], 16), *values])))
            current.append(values)
        elif ' WAIT ' in line:
            at, _, ms, _ = line.split()
            normalized.append(f'D {int(at[1:], 16)} {int(ms)}')
    # The last program block ends just before the config count/name/description.
    last = meta['programs'][-1]['data']['blocks'][-1]
    raw = args.firmware.read_bytes()
    config_at = last['offset'] + 12 + last['words'] * 4 + 2 + 64
    config_index = raw.index(b'\0', config_at) + 3
    selected = blocks['PROGRAM0/0'] + blocks['PLL0'] + blocks['CONFIG0/1'] + blocks['CONFIG0/0']
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-DMI8_TAS_HOST_TEST', '-I' + str(dev)]
    env = dict(os.environ)
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    with tempfile.TemporaryDirectory(prefix='mi8-tas-test-') as tmp:
        exe, ref = Path(tmp) / 'test', Path(tmp) / 'expected.txt'
        subprocess.run(['cc', *flags, str(ROOT / 'tools/tests/mi8-tas2557.c'), str(dev / 'mi8_tas2557.c'), '-o', str(exe)], check=True)
        dump = subprocess.check_output([str(exe), str(args.firmware), '--dump'], text=True, env=env)
        assert dump.splitlines() == normalized, 'C parser differs from independent ordered script decode'
        print(f'Independent firmware decode SELFTEST PASS {len(normalized)}/{len(normalized)}', flush=True)
        ref.write_text(f"{len(selected)} {len(blocks['PROGRAM0/0'])} {meta['programs'][0]['data']['blocks'][0]['crc'][1]} {config_index}\n" +
                       ''.join(' '.join(map(str, values)) + '\n' for values in selected))
        subprocess.run([str(exe), str(args.firmware), str(ref)], check=True, env=env)
        # Regression control: compile the prior unaligned read start against the
        # same word-latch peer. It must reproduce the coefficient sum 0x10.
        original = (dev / 'mi8_tas2557.c').read_text()
        line = 'while (from>0 && ((reg+from)&3)) from--;'
        assert original.count(line) == 1
        mutant = Path(tmp) / 'unaligned.c'
        mutant.write_text(original.replace(line, '/* previous unaligned read start */'))
        subprocess.run(['cc', *flags, str(ROOT / 'tools/tests/mi8-tas2557.c'), str(mutant), '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(args.firmware), str(ref), '--unaligned'], check=True, env=env)

    # Execute the real isolated worker and init gate with synthetic partition readiness.
    body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
    source = (dev / 'mi8_rproc.c').read_text()
    worker = body(source, 'static void\naudio_amp_thread(')
    gate = body(source[source.index('void\nmi8_rproc_init('):], 'if (last == 14)')
    code = r'''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define __unused __attribute__((unused))
#define KERN_SUCCESS 0
#define NSEC_PER_MSEC 1000000
#define CHECK(x) do{checks++;if(!(x))abort();}while(0)
typedef int thread_t;typedef int wait_result_t;
static unsigned checks,reads,calls,terminated,legacy,deallocated;
static uint64_t clock_us,ready_at;
static int ready=1;
static uint64_t now_us(void){return clock_us;}
static int redwood_ufs_read_named(const char*n,unsigned a,void*p,unsigned s){CHECK(n[0]=='m'&&a==0&&s==1);(void)p;reads++;return ready && clock_us>=ready_at?0:1;}
static void delay_for_interval(unsigned n,unsigned scale){CHECK(scale==NSEC_PER_MSEC);clock_us+=n*1000;}
static int current_thread(void){return 0;}
static void thread_terminate(int t){(void)t;terminated++;}
static void mi8_tas2557_probe(uint64_t end){CHECK(end==clock_us+20000000);calls++;}
static void say(const char*s){(void)s;}
''' + worker + r'''
static int kernel_thread_start(void(*f)(void*,int),void*p,int*t){*t=1;f(p,0);return 0;}
static void thread_deallocate(int t){CHECK(t==1);deallocated++;}
static void dispatch(unsigned last){
''' + gate + r'''
legacy++;
}
int main(void){
for(unsigned i=0;i<14;i++){dispatch(i);}CHECK(legacy==14&&!calls&&!reads);
dispatch(14);CHECK(calls==1&&reads==1&&terminated==1&&deallocated==1);
ready_at=9000000;clock_us=0;dispatch(14);CHECK(calls==2&&terminated==2&&clock_us==ready_at);
ready=0;clock_us=0;dispatch(14);CHECK(calls==2&&terminated==3&&clock_us<=10000000);
printf("TAS independent worker SELFTEST PASS %u/%u\n",checks,checks);return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='mi8-tas-gate-') as tmp:
        c, exe = Path(tmp) / 'gate.c', Path(tmp) / 'gate'
        c.write_text(code)
        subprocess.run(['cc', *flags, str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True, env=env)


if __name__ == '__main__':
    main()
