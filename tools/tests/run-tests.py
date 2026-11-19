#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 yanei
"""Unified host test runner with optional offline clean-replay tree and sanitizer modes."""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / 'tools/tests'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod


def run_step(label, cmd, env):
    print(f'==> {label}', flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    if proc.returncode != 0:
        raise SystemExit(f'FAILED ({proc.returncode}): {label}')


def find_tas_fixtures(explicit_dir):
    req = ('tas2557_uCDSP_goer.bin', 'tas2557_uCDSP_goer.txt', 'tas2557_uCDSP_goer.json')
    if explicit_dir is not None:
        d = explicit_dir.resolve()
        if all((d / name).is_file() for name in req):
            return d / req[0], d / req[1], d / req[2]
        raise SystemExit(f'Missing TAS2557 fixtures in --tas-dir: {d}')
    for candidate in sorted((ROOT / 'local/devices').glob('*/audio-android')):
        if all((candidate / name).is_file() for name in req):
            return candidate / req[0], candidate / req[1], candidate / req[2]
    return None


@contextlib.contextmanager
def clean_replay_tree(work_dir, env):
    if not (work_dir / 'hackios/.git').exists():
        raise SystemExit('Clean replay requires prepared local git objects in work/.')
    patchtool = load_module('patchtool', ROOT / 'tools/prepare/patchtool.py')
    prepare = load_module('prepare', ROOT / 'tools/prepare/prepare.py')

    exp_parent = ROOT.parent / 'experiments'
    parent_dir = exp_parent if exp_parent.is_dir() else None
    with tempfile.TemporaryDirectory(prefix='clean-replay-', dir=parent_dir) as tmp:
        dest = Path(tmp)
        trees = {}
        for source in json.loads((ROOT / 'upstream.lock.json').read_text(encoding='utf-8')):
            name = source['name']
            src = work_dir / ('hackios/xnu-src/xnu-8796.121.2' if name == 'xnu' else name)
            out = dest / name
            subprocess.run(['git', 'clone', '--shared', '--no-checkout', '-q', str(src), str(out)],
                           check=True, stdout=subprocess.DEVNULL)
            subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', '-q', source['commit']],
                           cwd=out, check=True, stdout=subprocess.DEVNULL)
            trees[name] = out
        sub = 'GPLDrivers/Library/SimpleInit'
        edk2_commit = patchtool.trees_commit(ROOT, 'edk2')
        sub_commit = patchtool.git('ls-tree', edk2_commit, '--', sub, cwd=work_dir / 'edk2').decode().split()[2]
        (trees['edk2'] / sub).rmdir()
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', '-q', str(work_dir / 'edk2' / sub),
                        str(trees['edk2'] / sub)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', '-q', sub_commit],
                       cwd=trees['edk2'] / sub, check=True, stdout=subprocess.DEVNULL)

        targets = prepare.assemble_baseline(trees)
        groups = patchtool.load_groups(ROOT)
        patchtool.apply_patches(ROOT, targets, groups)
        patchtool.verify_manifest(targets, groups)
        svc = ROOT / 'system/userland-wifi/com.redwood.wifi.plist'
        if svc.is_file():
            shutil.copy2(svc, targets['hackios-kernel'] / 'userland/com.redwood.wifi.plist')

        run_step('patchtool replay (--clean-replay)',
                 [sys.executable, '-B', str(ROOT / 'tools/prepare/patchtool.py'), 'replay', '--tree', str(dest)],
                 env)
        yield dest


def build_jobs(args, tree, tas):
    jobs = []
    seen = set()

    def add(script, extra=()):
        key = (script, tuple(extra))
        if key in seen:
            return
        seen.add(key)
        cmd = [sys.executable, '-B', str(TESTS_DIR / script), *extra]
        label = script + (' ' + ' '.join(f for f in extra if not f.startswith('/')) if extra else '')
        jobs.append((label.strip(), cmd))

    xnu_dir = tree / 'hackios/xnu-src/xnu-8796.121.2'
    has_source_tree = xnu_dir.is_dir()

    if args.suite in {'fast', 'all'}:
        for script in ('test-patchtool.py', 'test-partition-darwin.py',
                       'test-restore-android-layout.py', 'test-workflow-tools.py'):
            add(script)
        if has_source_tree:
            add('test-boot-defaults.py', ('--tree', str(xnu_dir)))
            add('test-mi8-default-peripherals.py', ('--tree', str(tree)))
            add('test-mi8-rproc-state.py', ('--tree', str(tree)))
            add('test-mi8-audio-apr.py', ('--tree', str(tree)))
        else:
            print(f'Skipping source-tree fast tests (missing {xnu_dir}).', flush=True)

    if args.suite in {'audio', 'all'}:
        if not has_source_tree:
            raise SystemExit(f'Audio tests require a prepared source tree at {tree}')
        san_modes = []
        if args.sanitize:
            san_modes.append(['--sanitize'])
        if args.tsan:
            san_modes.append(['--tsan'])
        if not san_modes:
            san_modes.append([])

        for script in ('test-mi8-audio-apr.py', 'test-mi8-audio-session-join.py', 'test-mi8-audio-panic.py'):
            add(script, ('--tree', str(tree)))

        for script in ('test-mi8-audio-smmu.py', 'test-mi8-audio-play.py', 'test-mi8-audio-session-log.py'):
            if args.sanitize:
                add(script, ('--tree', str(tree), '--sanitize'))
            else:
                add(script, ('--tree', str(tree)))

        for script in ('test-mi8-audio-sink.py', 'test-mi8-audio-ring.py', 'test-mi8-audio-coexist.py'):
            for mode in san_modes:
                add(script, ('--tree', str(tree), *mode))

        if tas is not None:
            fw, ref, meta = tas
            tas_args = ('--tree', str(tree), '--firmware', str(fw), '--reference', str(ref), '--metadata', str(meta))
            for script in ('test-mi8-tas2557.py', 'test-mi8-audio-amp.py',
                           'test-mi8-audio-tone.py', 'test-mi8-audio-clip.py'):
                if args.sanitize:
                    add(script, (*tas_args, '--sanitize'))
                else:
                    add(script, tas_args)
            for mode in san_modes:
                add('test-mi8-audio-session.py', (*tas_args, *mode))
                if args.long:
                    add('test-mi8-audio-session.py', ('--long', *tas_args, *mode))
        else:
            print('Note: TAS2557 local firmware fixtures not found; skipping firmware-backed audio tests.', flush=True)

    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('fast', 'audio', 'all'), default='fast')
    parser.add_argument('--tree', type=Path, default=ROOT / 'work', help='prepared source tree root')
    parser.add_argument('--clean-replay', action='store_true',
                        help='build a disposable clean replay tree from locked objects and test against it')
    parser.add_argument('--sanitize', action='store_true', help='run ASan/UBSan where supported')
    parser.add_argument('--tsan', action='store_true', help='run TSan where supported')
    parser.add_argument('--long', action='store_true', help='include 300s session simulation')
    parser.add_argument('--tas-dir', type=Path, help='directory with tas2557_uCDSP_goer.{bin,txt,json}')
    args = parser.parse_args()

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    tas = find_tas_fixtures(args.tas_dir)
    base_tree = args.tree.resolve()

    if args.clean_replay:
        with clean_replay_tree(base_tree, env) as replay_dir:
            jobs = build_jobs(args, replay_dir, tas)
            for label, cmd in jobs:
                run_step(label, cmd, env)
    else:
        jobs = build_jobs(args, base_tree, tas)
        for label, cmd in jobs:
            run_step(label, cmd, env)

    print(f'PASS {len(jobs)}/{len(jobs)} host test runs ({args.suite}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
