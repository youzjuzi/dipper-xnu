#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the real GLINK/APR implementation against an in-memory SMEM peer."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def check_native_mappings(source):
    # Host compilation excludes native MMIO. Ignore comments and literals so
    # the preserved explanation of the old unmap failure is not a reference.
    code = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  ' ', source)
    assert not re.search(r'\bml_io_unmap\b', code), 'permanent pin mapping must not be unmapped'
    declarations = re.findall(r'\b(static\s+)?struct\s+native_audio_pins\s+native\b', code)
    assert declarations == ['static '] and re.search(
        r'struct\s+mi8_audio_pin_ops\s+ops\s*=\s*\{\s*native_pin_read\s*,\s*'
        r'native_pin_write\s*,\s*&native\s*\}', code), 'pin mapping table must be static and reused'
    assert re.search(r'if\s*\(\s*!p->pages\[i\]\s*\)\s*p->pages\[i\]\s*=\s*ml_io_map\s*\(',
                     code), 'each pin must map only when its cached address is empty'
    print('Native pin mappings SELFTEST PASS 3/3', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=ROOT / 'work')
    args = parser.parse_args()
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    check_native_mappings((dev / 'mi8_audio.c').read_text())
    with tempfile.TemporaryDirectory(prefix='mi8-audio-test-') as tmp:
        exe = Path(tmp) / 'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                        '-DMI8_GLINK_HOST_TEST', '-I' + str(dev),
                        str(ROOT / 'tools/tests/mi8-audio-apr.c'),
                        str(dev / 'mi8_glink.c'), str(dev / 'mi8_audio.c'), str(dev / 'mi8_audio_pcm.c'), str(dev / 'mi8_audio_ring.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
