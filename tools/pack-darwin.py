#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a verified darwin.img on the host. Never opens a device or runs adb/fastboot."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ios = ROOT / 'work/hackios/ios165'
    out = ROOT / 'work/images'
    provenance = json.loads((ios / 'input-provenance.json').read_text())
    if provenance['ipsw_sha256'] != 'c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2':
        raise SystemExit('Run prepare-ios.py with the supported IPSW first')
    for entry in provenance['images']:
        # The names are a fixed allowlist; do not treat JSON as an arbitrary path.
        if entry['file'] not in ('rootfs.dmg', 'cryptex-os.dmg', 'cryptex-app.dmg'):
            raise SystemExit('Unexpected input name')
        if sha256(ios / entry['file']) != entry['sha256']:
            raise SystemExit('Input SHA256 changed: ' + entry['file'])
    if {e['file'] for e in provenance['images']} != {'rootfs.dmg', 'cryptex-os.dmg', 'cryptex-app.dmg'}:
        raise SystemExit('Incomplete input provenance')
    out.mkdir(exist_ok=True)
    image = out / 'darwin.img'
    partial = out / 'darwin.img.partial'
    if image.exists() or image.is_symlink() or partial.exists() or partial.is_symlink():
        raise SystemExit('Output already exists; preserve it before retrying')
    # The UDIF holds an entire GPT disk. Extract only its APFS partition, not
    # the GPT headers or the compressed UDIF wrapper.
    raw = out / 'rootfs.apfs'
    if raw.is_symlink():
        raise SystemExit('Refusing rootfs.apfs symlink')
    if not raw.exists():
        temporary = out / 'rootfs.apfs.partial'
        with temporary.open('xb') as stream, (out / 'rootfs-extraction.log').open('w') as log:
            subprocess.run(['7z', 'x', '-tDmg', '-so', str(ios / 'rootfs.dmg'), '3.apfs'],
                           stdout=stream, stderr=log, check=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.rename(raw)
    parts = [(raw, 5628755968), (ios / 'cryptex-os.dmg', 2726297600),
             (ios / 'cryptex-app.dmg', 10485760)]
    for path, size in parts:
        if path.stat().st_size != size:
            raise SystemExit('Wrong APFS size: ' + str(path))
        with path.open('rb') as stream:
            stream.seek(32)
            if stream.read(4) != b'NXSB':
                raise SystemExit('Missing APFS NXSB: ' + str(path))
    digest = hashlib.sha256()
    with partial.open('xb') as stream:
        for path, _ in parts:
            with path.open('rb') as source:
                while data := source.read(8 * 1024 * 1024):
                    digest.update(data)
                    stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if digest.hexdigest() != EXPECTED or sha256(partial) != EXPECTED:
        raise SystemExit('Combined SHA256 mismatch; retained .partial, do not flash it')
    partial.rename(image)
    (out / 'SHA256SUMS').write_text(EXPECTED + '  darwin.img\n')
    print(str(image) + ': 8365539328 bytes, SHA256 ' + EXPECTED)


if __name__ == '__main__':
    main()
