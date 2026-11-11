#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the real GLINK/APR implementation against an in-memory SMEM peer."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=ROOT / 'work')
    args = parser.parse_args()
    dev = args.tree.resolve() / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev'
    with tempfile.TemporaryDirectory(prefix='mi8-audio-test-') as tmp:
        exe = Path(tmp) / 'test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                        '-DMI8_GLINK_HOST_TEST', '-I' + str(dev),
                        str(ROOT / 'tools/tests/mi8-audio-apr.c'),
                        str(dev / 'mi8_glink.c'), str(dev / 'mi8_audio.c'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
