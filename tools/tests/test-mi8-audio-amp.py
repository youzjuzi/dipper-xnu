#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real GLINK/APR/PCM and TAS driver together, against independent synthetic peers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree', type=Path, default=ROOT / 'work')
    for name in ['firmware', 'reference', 'metadata']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--sanitize', action='store_true')
    a = ap.parse_args()
    assert hashlib.sha256(a.firmware.read_bytes()).hexdigest() == json.loads(a.metadata.read_text())['sha256']
    blocks, current = {}, None
    for line in a.reference.read_text().splitlines():
        if line.startswith('BLOCK '):
            current = blocks[line.split()[1]] = []
        elif ' WRITE ' in line:
            current.append([int(v, 16) for v in line.split()[2:]])
    selected = blocks['PROGRAM0/0'] + blocks['PLL0'] + blocks['CONFIG0/1'] + blocks['CONFIG0/0']
    dev = a.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
    source = (dev / 'mi8_rproc.c').read_text()
    fixture = (ROOT / 'tools/tests/mi8-audio-play.c').read_text()
    for fn in ['dsp_shutdown', 'steps_from_five']:
        signature = ('static bool\n' if fn == 'dsp_shutdown' else 'static void\n') + fn + '('
        actual = body(source, signature).replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(')
        fixture = fixture.replace('/* @' + fn + ' */', actual)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread', '-DMI8_AMP_TEST', '-DMI8_GLINK_HOST_TEST', '-DMI8_TAS_HOST_TEST', '-I' + str(dev), '-I' + str(ROOT / 'tools/tests')]
    env = dict(os.environ)
    if a.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    with tempfile.TemporaryDirectory(prefix='mi8-amp-test-') as temp:
        tmp = Path(temp)
        (tmp / 'play-fixture.c').write_text(fixture.replace('int main(void)', 'int play_legacy_main(void)'))
        ref = tmp / 'expected.txt'
        ref.write_text(f'{len(selected)} {len(blocks["PROGRAM0/0"])} 92 0\n' + ''.join(' '.join(map(str, v)) + '\n' for v in selected))
        exe = tmp / 'amp'
        # Exercise private whitelist predicates without adding a kernel test API.
        guard = tmp / 'tas-guard.c'
        guard.write_text((dev / 'mi8_tas2557.c').read_text() + r'''
unsigned mi8_tas_guard_tests(void) {
 struct tas t={.book=0,.page=0,.guarded=true};
 for(unsigned v=0;v<256;v++) {
  t.book=0;t.firmware=false;
  if(allowed_write(&t,6,(uint8_t)v))return 0;
  if(allowed_write(&t,7,(uint8_t)v)!=(v==3))return 0;
  t.book=100;if(allowed_write(&t,7,(uint8_t)v)!=(v==1))return 0;
  t.book=0;t.firmware=true;if(allowed_write(&t,6,(uint8_t)v)!=(v==0x7c))return 0;
 }
 return 1024;
}
''')
        subprocess.run(['cc', *flags, '-I' + str(tmp), str(ROOT / 'tools/tests/mi8-audio-amp.c'), str(ROOT / 'tools/tests/mi8-audio-amp-model.c'), str(guard), *(str(dev / s) for s in ['mi8_glink.c', 'mi8_audio.c', 'mi8_audio_pcm.c']), '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(a.firmware), str(ref)], check=True, env=env)

if __name__ == '__main__':
    main()
