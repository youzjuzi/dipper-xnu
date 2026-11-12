#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual session feeder, ring/GLINK/APR and TAS controller against independent peers."""
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
    ap.add_argument('--tsan', action='store_true')
    ap.add_argument('--threads', action='store_true')
    a = ap.parse_args()
    assert hashlib.sha256(a.firmware.read_bytes()).hexdigest() == json.loads(a.metadata.read_text())['sha256']
    subprocess.run(['python3',str(ROOT/'tools/tests/test-mi8-audio-session-join.py'),'--tree',str(a.tree)],check=True)
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
    for fn in ['audio_ring_report', 'dsp_shutdown', 'steps_from_five']:
        sig = ('static bool\n' if fn == 'dsp_shutdown' else 'static void\n') + fn + '('
        actual = body(source, sig).replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(')
        fixture = fixture.replace('/* @' + fn + ' */', actual)
    fixture = fixture.replace('audio_play_until==45000000', 'audio_play_until==90000000').replace('CHECK(last==13||last==15||last==16)', 'CHECK(last==13||last==15||last==16||last==17)').replace('m->step?m->step:13,play_fatal', '17,play_fatal')
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread', '-DMI8_AMP_TEST', '-DMI8_TONE_TEST', '-DMI8_RING_TEST', '-DMI8_GLINK_HOST_TEST', '-DMI8_TAS_HOST_TEST', '-I'+str(dev), '-I'+str(ROOT/'tools/tests')]
    env = dict(os.environ)
    if a.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    if a.tsan:
        flags += ['-fsanitize=thread', '-g', '-fno-omit-frame-pointer', '-no-pie']
        env['TSAN_OPTIONS'] = 'halt_on_error=1'
    if a.tsan or a.threads:
        env['SESSION_THREADS'] = '1'
    with tempfile.TemporaryDirectory(prefix='mi8-session-') as tmpname:
        tmp = Path(tmpname)
        (tmp/'play-fixture.c').write_text(fixture.replace('int main(void)', 'int play_legacy_main(void)'))
        ref = tmp/'expected.txt'
        ref.write_text(f'{len(selected)} {len(blocks["PROGRAM0/0"])} 92 0\n' + ''.join(' '.join(map(str, v))+'\n' for v in selected))
        (tmp/'model.c').write_text((ROOT/'tools/tests/mi8-audio-session-model.c').read_text())
        actual = '\n'.join(body(source,sig) for sig in ['static void audio_session_report(', 'static void\nsteps_audio_session('])
        actual=actual.replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(').replace('audio_session_ops','session_ops')
        (tmp/'test.c').write_text((ROOT/'tools/tests/mi8-audio-session.c').read_text().replace('/* @session_worker */',actual))
        (tmp/'pcm.c').write_text((dev/'mi8_audio_pcm.c').read_text()+(ROOT/'tools/tests/mi8-audio-session-guards.inc').read_text())
        (tmp/'tas.c').write_text((dev/'mi8_tas2557.c').read_text()+'\nvoid session_test_reset(void){memset(&session,0,sizeof(session));}\n')
        exe = tmp/'clip'
        subprocess.run(['cc', *flags, '-I'+str(tmp), str(tmp/'test.c'), str(tmp/'model.c'), str(tmp/'pcm.c'), str(tmp/'tas.c'), str(dev/'mi8_glink.c'), str(dev/'mi8_audio.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(a.firmware), str(ref)], check=True, env=env)

if __name__ == '__main__':
    main()
