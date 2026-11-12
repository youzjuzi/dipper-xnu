#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the real count sink, cdev locking and final loader append on the host."""
import argparse
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=ROOT / 'work')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--tsan', action='store_true')
    a = parser.parse_args()
    x = a.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2'
    body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
    audio = (x / 'bsd/dev/redwood_audio.c').read_text()
    loader = (x / 'osfmk/arm64/loader_return.c').read_text()
    source = (x / 'bsd/dev/mi8_audio_sink.c').read_text()
    # Preserve the actual entry points, not a model of the cdev's locking.
    pieces = '\n'.join(body(audio, signature) for signature in [
        'static void\naudio_play(', 'void\nredwood_audio_set_sink(',
        'bool\nredwood_audio_claim_sink(', 'bool\nredwood_audio_volume(', 'bool\nredwood_audio_muted('])
    assert 'volume_below' not in body(audio, 'bool\nredwood_audio_muted(')
    final = body(loader, 'static void\nloader_audio_append(') + '\n' + body(loader, 'static void\nloader_audio_summary(')
    exit_path = body(loader, 'void\nloader_return(')
    assert exit_path.index('psci_smp_stop_others') < exit_path.index('loader_log_linearize')
    assert exit_path.index('loader_log_append_msgbuf') < exit_path.index('loader_audio_summary') < exit_path.index('loader_jump(0, 0)')
    assert exit_path.index('debug_buf_ptr') < exit_path.index('loader_audio_summary')
    assert 'loader_log_putc(' not in final and 'printf(' not in final
    assert 'mi8_audio_sink_init();' in body(audio, 'void\nredwood_audio_init(')
    assert 'bsd/dev/mi8_audio_sink.c\tstandard' in (x / 'bsd/conf/files').read_text()
    callback = body(source, 'static uint32_t count_sink(')
    for forbidden in ['printf(', 'redwood_audio_volume(', 'redwood_audio_set_sink(', 'lck_', 'alloc(', 'sleep', 'delay_', 'mi8_tas', 'mi8_pcm', 'mi8_smmu']:
        assert forbidden not in callback, forbidden
    assert not re.search(r'\{ "audio",', (x / 'pexpert/arm/pe_bootargs.c').read_text())
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread']
    env = dict(os.environ)
    if a.tsan:
        flags += ['-fsanitize=thread','-g','-fno-omit-frame-pointer','-no-pie']
        env['TSAN_OPTIONS']='halt_on_error=1'
    if a.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-no-pie']
        # LeakSanitizer cannot run under the host execution sandbox's ptrace.
        env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='mi8-count-') as tmp:
        d = Path(tmp)
        (d / 'sink-host.h').write_text('/* Host declarations are provided by the harness. */\n')
        code = (ROOT / 'tools/tests/mi8-audio-sink.c').read_text()
        rproc = (x / 'bsd/dev/mi8_rproc.c').read_text()
        gate = body(rproc, 'if(audio==5)') + '\n' + body(rproc, 'if (audio==4)') + '\n' + body(rproc, 'if (audio==3)') + '\n' + body(rproc, 'if (audio == 2 && shared_step == 0)')
        code = code.replace('/* @ring_gate */', gate).replace('/* @tail_append */',body(rproc,'static void audio_tail_append('))
        code = code.replace('/* @cdev */', pieces).replace('/* @sink */', source).replace('/* @loader */', final)
        (d / 'count.c').write_text(code)
        exe = d / 'count'
        subprocess.run(['cc', *flags, '-I'+str(d), '-I'+str(x / 'bsd/dev'), str(d/'count.c'), str(x / 'bsd/dev/mi8_audio_ring.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True, env=env, timeout=30)
    print('Count sink integration/static gates PASS; loader final append is last and lock-free')

if __name__ == '__main__':
    main()
