#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual bounded clip, ring/GLINK/APR and TAS driver against independent peers."""
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
    with tempfile.TemporaryDirectory(prefix='mi8-clip-') as tmpname:
        tmp = Path(tmpname)
        (tmp/'play-fixture.c').write_text(fixture.replace('int main(void)', 'int play_legacy_main(void)'))
        ref = tmp/'expected.txt'
        ref.write_text(f'{len(selected)} {len(blocks["PROGRAM0/0"])} 92 0\n' + ''.join(' '.join(map(str, v))+'\n' for v in selected))
        # Same independent register/wire peer as the diagnostic tone. Only its
        # trigger-relative timing predicates change; ordered transactions stay.
        model = (ROOT/'tools/tests/mi8-audio-tone-model.c').read_text()
        model = model.replace('p->time>=run_time+600000 && p->time<run_time+1000000', 'p->time>=powered_at+200000')
        model = model.replace('p->time>=run_time+300000', 'p->time>=run_time')
        model = model.replace('mi8_tas2557_hold_tone(', 'mi8_tas2557_hold_clip(')
        model = model.replace('delay_us(ctx,n);*play_time=m.time;', 'if(scenario==18 && !shutting && startup_writes==6 && n==2000)n+=60000;\n delay_us(ctx,n);*play_time=m.time;')
        model += '''
void clip_model_check(bool triggered,bool played) {
 CHECK(!power && !m.pin[76] && m.cfg[85]==m.saved_cfg[85] && m.cfg[86]==m.saved_cfg[86]);
 if(!triggered)CHECK(!startup_writes&&!unmute_writes);
 if(played && scenario!=5)CHECK(startup_writes==7 && shutdown_writes==9 && health_reads==1 && unmute_writes==2 && mute_writes==2 && software_shutdown);
 if(scenario==1)CHECK(!unmute_writes);
 if(scenario==16 && played)CHECK(stopped_at-mute_begin>=40000);
}
'''
        (tmp/'model.c').write_text(model)
        actual = '\n'.join(body(source, sig) for sig in ['static void audio_clip_report(', 'static void\nsteps_audio_clip('])
        actual = actual.replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(').replace('audio_clip_ops', 'clip_ops')
        test = (ROOT/'tools/tests/mi8-audio-clip.c').read_text().replace('/* @clip_worker_helpers */', actual)
        (tmp/'test.c').write_text(test)
        (tmp/'pcm.c').write_text((dev/'mi8_audio_pcm.c').read_text()+(ROOT/'tools/tests/mi8-audio-clip-guards.inc').read_text())
        exe = tmp/'clip'
        subprocess.run(['cc', *flags, '-I'+str(tmp), str(tmp/'test.c'), str(tmp/'model.c'), str(tmp/'pcm.c'), str(dev/'mi8_tas2557.c'), str(dev/'mi8_glink.c'), str(dev/'mi8_audio.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(a.firmware), str(ref)], check=True, env=env)

if __name__ == '__main__':
    main()
