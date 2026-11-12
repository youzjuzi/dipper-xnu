#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real SPSC ring, forced-zero DMA stream and bounded teardown against synthetic peers."""
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
    ap.add_argument('--tsan', action='store_true')
    args = ap.parse_args()
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    flags = ['-std=c11', '-D_POSIX_C_SOURCE=200809L', '-Wall', '-Wextra', '-Werror', '-pthread', '-I' + str(dev)]
    env = dict(os.environ)
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        env['ASAN_OPTIONS'] = env.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
    if args.tsan:
        assert not args.sanitize
        flags += ['-fsanitize=thread', '-g', '-no-pie']
        env['TSAN_OPTIONS'] = 'halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='mi8-ring-test-') as tmp:
        body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
        source = (dev / 'mi8_rproc.c').read_text()
        ring = (dev / 'mi8_audio_ring.c').read_text()
        callback = body(ring, 'uint32_t mi8_audio_ring_put(')
        for forbidden in ['sleep', 'printf', 'lck_', 'alloc(', 'mi8_pcm', 'mi8_tas', 'APR']:
            assert forbidden not in callback
        pcm = body((dev / 'mi8_audio_pcm.c').read_text(), 'bool\nmi8_pcm_run_ring(')
        assert 'memset((uint8_t *)s->memory.buffer+slot*MI8_PCM_PERIOD,0,MI8_PCM_PERIOD);' in pcm
        assert 'mi8_audio_ring_take(scratch,960)' in pcm and 'fill_period(' not in pcm
        assert 'canaries(' not in pcm and 'amp->' not in pcm
        assert pcm.index('mi8_audio_ring_close()') < pcm.index('command(s,MI8_PCM_CLOSE,true)')
        for name, define, sources in [('mi8-audio-ring', 'MI8_GLINK_HOST_TEST', ['mi8_glink.c', 'mi8_audio.c', 'mi8_audio_pcm.c'])]:
            exe = Path(tmp) / name
            fixture = Path(tmp) / (name + '.c')
            fixture.write_text((ROOT / 'tools/tests' / (name + '.c')).read_text().replace('/* @tail_capture */', body(source, 'if (audio_tail_on && audio_play_worker())')))
            if True:
                text = (ROOT / 'tools/tests/mi8-audio-play.c').read_text()
                for fn in ['audio_ring_report', 'dsp_shutdown', 'steps_from_five']:
                    signature = ('static bool\n' if fn == 'dsp_shutdown' else 'static void\n') + fn + '('
                    actual = body(source, signature).replace('now_us(', 'worker_now_us(').replace('say(', 'worker_say(')
                    text = text.replace('/* @' + fn + ' */', actual)
                (Path(tmp) / 'ring-play.inc').write_text(text.replace('int main(void){', 'int play_legacy_main(void){'))
            subprocess.run(['cc', *flags, '-I' + str(ROOT / 'tools/tests'), '-I'+str(tmp), '-DMI8_GLINK_HOST_TEST', '-D' + define, str(fixture),
                            *(str(dev / s) for s in sources), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True, env=env)


if __name__ == '__main__':
    main()
