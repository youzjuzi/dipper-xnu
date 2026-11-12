#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real PCM/AFE/APR/GLINK paths and dual-address SMMU against synthetic peers."""
import argparse
import os
import runpy
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree', type=Path, default=ROOT / 'work')
    ap.add_argument('--sanitize', action='store_true')
    args = ap.parse_args()
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread', '-I' + str(dev)]
    env = dict(os.environ)
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    with tempfile.TemporaryDirectory(prefix='mi8-play-test-') as tmp:
        body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
        source = (dev / 'mi8_rproc.c').read_text()
        gate = (ROOT / 'tools/tests/mi8-audio-play-dispatch.c').read_text()
        for name in ['wsmmu_before_power', 'audio_smmu_thread']:
            gate = gate.replace('/* @' + name + ' */', body(source, 'static void\n' + name + '('))
        gate = gate.replace('/* @play_handshake */', body(source, 'if (last >= 13)'))
        dispatcher = source[source.index('void\nmi8_rproc_init('):]
        for number in [13, 11]:
            gate = gate.replace('/* @dispatch_' + str(number) + ' */', body(dispatcher, f'if (last >= {number})'))
        c, exe = Path(tmp) / 'dispatch.c', Path(tmp) / 'dispatch'
        c.write_text(gate)
        subprocess.run(['cc', *flags, str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True, env=env)
        for name, define, sources in [
            ('mi8-audio-play', 'MI8_GLINK_HOST_TEST', ['mi8_glink.c', 'mi8_audio.c', 'mi8_audio_pcm.c', 'mi8_audio_ring.c']),
            ('mi8-audio-play-smmu', 'MI8_SMMU_HOST_TEST', ['mi8_audio_smmu.c', 'mi8_glink.c', 'mi8_audio.c', 'mi8_audio_pcm.c', 'mi8_audio_ring.c'])]:
            exe = Path(tmp) / name
            fixture = ROOT / 'tools/tests' / (name + '.c')
            if name == 'mi8-audio-play':
                text = fixture.read_text()
                for fn in ['audio_ring_report', 'dsp_shutdown', 'steps_from_five']:
                    signature = ('static bool\n' if fn == 'dsp_shutdown' else 'static void\n') + fn + '('
                    actual = body(source, signature).replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(')
                    text = text.replace('/* @' + fn + ' */', actual)
                fixture = Path(tmp) / (name + '.c')
                fixture.write_text(text)
            subprocess.run(['cc', *flags, '-I' + str(ROOT / 'tools/tests'), '-DMI8_GLINK_HOST_TEST', '-D' + define, str(fixture),
                            *(str(dev / s) for s in sources), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True, env=env)


if __name__ == '__main__':
    main()
