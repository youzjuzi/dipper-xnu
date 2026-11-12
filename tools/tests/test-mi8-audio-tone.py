#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real GLINK/APR/PCM and TAS driver together, against independent synthetic peers."""
import math
import struct
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
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread', '-DMI8_AMP_TEST', '-DMI8_TONE_TEST', '-DMI8_GLINK_HOST_TEST', '-DMI8_TAS_HOST_TEST', '-I' + str(dev), '-I' + str(ROOT / 'tools/tests')]
    env = dict(os.environ)
    if a.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    with tempfile.TemporaryDirectory(prefix='mi8-tone-test-') as temp:
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
  t.firmware=false;t.tone=true;t.unmute_window=false;
  if(allowed_write(&t,7,(uint8_t)v)!=(v==3))return 0;
  t.unmute_window=true;if(allowed_write(&t,7,(uint8_t)v)!=(v==0||v==3))return 0;
  t.book=100;if(allowed_write(&t,7,(uint8_t)v)!=(v==0||v==1))return 0;
  t.tone=false;if(allowed_write(&t,7,(uint8_t)v)!=(v==1))return 0;
  t.unmute_window=false;
 }
 return 2048;
}
''')
        pcm = tmp / 'pcm-check.c'
        pcm.write_text((dev / 'mi8_audio_pcm.c').read_text() + (ROOT / 'tools/tests/mi8-audio-tone-guards.inc').read_text())
        compile_command = ['cc', *flags, '-I' + str(tmp), str(ROOT / 'tools/tests/mi8-audio-tone.c'), str(ROOT / 'tools/tests/mi8-audio-tone-model.c'), str(guard), str(pcm), *(str(dev / s) for s in ['mi8_glink.c', 'mi8_audio.c']), '-o', str(exe)]
        subprocess.run(compile_command, check=True)
        subprocess.run([str(exe), str(a.firmware), str(ref), str(tmp / 'wave.raw')], check=True, env=env)
        frames = list(struct.iter_unpack('<hh', (tmp / 'wave.raw').read_bytes()))
        assert len(frames) == 144000
        for n, (left, right) in enumerate(frames):
            want = 0
            if 48000 <= n < 96000:
                at = n - 48000
                wave = round(1036 * math.sin(2 * math.pi * (at % 48) / 48))
                edge = min(at, 47999 - at)
                gain = round(32768 * (1 - math.cos(math.pi * edge / 479)) / 2) if edge < 480 else 32768
                want = (1 if wave >= 0 else -1) * ((abs(wave) * gain + 16384) // 32768)
            assert left == right == want, (n, left, right, want)
        assert max(abs(left) for left, _ in frames) == 1036
        print('Independent tone waveform SELFTEST PASS 144000/144000')
        # Counterfactuals use temporary translation units, never the work tree.
        for label, original, before, after, failure in [
            ('old-soft-readback', guard, 'h!=3 || s!=1', 'h!=3 || s!=7', 'software_shutdown'),
            ('old-zero-deadline', pcm, 'tone && n>=50 && n<100 && io->now', 'tone && io->now', 'ok&&m.normal==150'),
        ]:
            source = original.read_text()
            assert source.count(before) == 1
            variant = tmp / (label + '.c')
            variant.write_text(source.replace(before, after))
            negative = tmp / label
            command = [str(variant) if v == str(original) else str(negative) if v == str(exe) else v for v in compile_command]
            subprocess.run(command, check=True)
            result = subprocess.run([str(negative), str(a.firmware), str(ref), str(tmp / 'negative.raw')], env=env, capture_output=True, text=True)
            assert result.returncode == 1 and 'FAIL line ' in result.stderr and failure in result.stderr, (label, result.returncode, result.stderr)
            if label == 'old-soft-readback':
                assert 'mute read back R07=03/01' in result.stdout
            print('Counterfactual', label, 'rejected as expected; current source passes')


if __name__ == '__main__':
    main()
