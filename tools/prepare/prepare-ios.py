#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the supported IPSW and prepare local userland inputs; no device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
IPSW_SHA256 = 'c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2'
PARTS = (
    ('096-04088-077.dmg', 'rootfs.dmg', 4728546953),
    ('096-04666-078.dmg', 'cryptex-os.dmg', 2726297600),
    ('096-03536-083.dmg', 'cryptex-app.dmg', 10485760),
)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(ipsw):
    kernel = ROOT / 'work/hackios'
    dest = kernel / 'ios165'
    if not (dest / 'fetch.sh').is_file():
        raise SystemExit('Prepare sources first: python3 tools/prepare/prepare.py --prepare')
    print('Checking the complete IPSW SHA256...', flush=True)
    if digest(ipsw) != IPSW_SHA256:
        raise SystemExit('IPSW SHA256 mismatch; no inputs extracted. See docs/build/INPUTS.md.')
    records = []
    with zipfile.ZipFile(ipsw) as archive:
        manifest = plistlib.loads(archive.read('BuildManifest.plist'))
        if (manifest.get('ProductVersion') != '16.5' or
                manifest.get('ProductBuildVersion') != '20F66' or
                set(manifest.get('SupportedProductTypes', [])) != {'iPhone10,3', 'iPhone10,6'}):
            raise SystemExit('Unexpected BuildManifest identity')
        for member, name, size in PARTS:
            if archive.getinfo(member).file_size != size:
                raise SystemExit('Unexpected image size: ' + member)
            target = dest / name
            if target.is_symlink():
                raise SystemExit('Refusing an input symlink: ' + str(target))
            partial = target.with_name(target.name + '.extracting')
            existing = target.exists()
            output = None if existing else partial.open('xb')
            sha = hashlib.sha256()
            try:
                with archive.open(member) as stream:
                    while chunk := stream.read(8 * 1024 * 1024):
                        sha.update(chunk)
                        if output is not None:
                            output.write(chunk)
                if output is not None:
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                if output is not None:
                    output.close()
            checked = target if existing else partial
            if checked.stat().st_size != size or digest(checked) != sha.hexdigest():
                raise SystemExit('Image content mismatch; retained for inspection: ' + str(checked))
            if not existing:
                partial.rename(target)
            records.append({'member': member, 'file': name, 'size': size, 'sha256': sha.hexdigest()})
            print('Verified ' + name, flush=True)
    (dest / 'input-provenance.json').write_text(json.dumps(
        {'ipsw_sha256': IPSW_SHA256, 'images': records}, indent=2) + '\n')
    # All three images now exist, so the upstream script need not fetch them.
    subprocess.run(['bash', 'ios165/fetch.sh'], cwd=kernel,
                   env={**os.environ, 'KEEP': '1'}, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ipsw', type=Path, required=True)
    prepare(parser.parse_args().ipsw)
