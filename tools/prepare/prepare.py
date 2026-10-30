#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare pinned source trees; never builds or contacts a device."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)

def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd).decode().strip()

def patch(name, target):
    p = ROOT / 'patches' / (name + '.patch')
    if p.stat().st_size:
        run('git', 'apply', '--check', str(p), cwd=target)
        run('git', 'apply', str(p), cwd=target)

def prepare_submodules(edk2, unixnu):
    # Match edk2-sdm845/build.sh: the firmware uses these direct dependency
    # trees, not OpenSSL's nested test repositories (boringssl, krb5, etc.).
    # Gitlinks still select exact commits; depth only limits fetched history.
    args = ('git', 'submodule', 'update', '--init', '--depth', '1', '--jobs', '4')
    run(*args, cwd=edk2)
    for name in ('Common/edk2', 'Common/edk2-platforms',
                 'GPLDrivers/Library/SimpleInit', 'tools/Installer'):
        run(*args, cwd=edk2 / name)
    # The dipper wrapper references this package; the other UniXNU drivers
    # are not part of this HackiOS firmware build.
    run(*args, '--', 'drivers/DarwinBoot', cwd=unixnu)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='fetch sources into a new work/ directory')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'upstream.lock.json').read_text())
    if not args.prepare:
        for source in sources:
            print(source['name'], source['commit'], source['url'])
        print('Plan only. Use --prepare to fetch into work/.')
        return
    work = ROOT / 'work'
    if work.exists():
        raise SystemExit('work/ already exists; refusing to overwrite. Preserve/move it before retrying.')
    # Verify the release itself before consuming its patches.
    run('sha256sum', '-c', 'SHA256SUMS', cwd=ROOT)
    work.mkdir()
    trees = {}
    for source in sources:
        dest = work / source['name']
        run('git', 'init', '-q', str(dest))
        run('git', 'remote', 'add', 'origin', source['url'], cwd=dest)
        run('git', 'fetch', '--depth', '1', 'origin', source['commit'], cwd=dest)
        run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=dest)
        if output('git', 'rev-parse', 'HEAD', cwd=dest) != source['commit']:
            raise SystemExit('Commit mismatch: ' + source['name'])
        trees[source['name']] = dest
    k = trees['hackios']
    # Separate checkout retained for provenance; overlay only tracked userland files.
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=trees['userland']).decode().split('\0')
    for name in filter(None, names):
        if name in {'README.md', 'LICENSE', '.gitignore'} or name.startswith('prebuilt/'):
            continue
        src, dst = trees['userland'] / name, k / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)
    prepare_submodules(trees['edk2'], trees['unixnu'])
    x = k / 'xnu-src/xnu-8796.121.2'
    x.parent.mkdir(parents=True)
    shutil.move(str(trees['xnu']), str(x))
    run('git', 'apply', '--check', str(k / 'xnu/redwood.patch'), cwd=x)
    run('git', 'apply', str(k / 'xnu/redwood.patch'), cwd=x)
    shutil.copytree(k / 'xnu/files', x, dirs_exist_ok=True)
    targets = {'xnu-mi8': x, 'hackios-kernel': k, 'hackios-userland': k,
               'edk2-sdm845': trees['edk2'], 'unixnu': trees['unixnu'],
               'simpleinit': trees['edk2'] / 'GPLDrivers/Library/SimpleInit'}
    for name, target in targets.items():
        patch(name, target)
    for group in json.loads((ROOT / 'source-manifest.json').read_text()):
        for entry in group['files']:
            p = targets[group['component']] / entry['path']
            actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
            if actual != entry['sha256']:
                raise SystemExit('Source hash mismatch: ' + entry['path'])
            if p.exists():
                p.chmod(int(entry['mode'], 8))
    shutil.copy2(ROOT / 'system/userland-wifi/com.redwood.wifi.plist', k / 'userland/com.redwood.wifi.plist')
    print('Sources prepared and hashes checked. No build or device operation was performed.')

if __name__ == '__main__':
    main()
