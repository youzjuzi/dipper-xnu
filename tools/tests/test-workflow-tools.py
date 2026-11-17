#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline regression tests for status.py, build-kernel.sh, and build-payload.py options."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
STATUS_PY = ROOT / 'tools/prepare/status.py'
BUILD_KERNEL = ROOT / 'tools/build/build-kernel.sh'
BUILD_PAYLOAD = ROOT / 'tools/build/build-payload.py'


def run_py(script, *args, cwd=ROOT):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([sys.executable, '-B', str(script), *args], cwd=cwd, env=env,
                          text=True, capture_output=True)


class WorkflowToolsTests(unittest.TestCase):
    def test_status_check_refresh_and_fail_on_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo, check=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=repo, check=True)
            (repo / 'README.md').write_text('hello\n', encoding='utf-8')
            (repo / 'notes.txt').write_text('world\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'README.md', 'notes.txt'], cwd=repo, check=True)
            subprocess.run(['git', 'commit', '-q', '-m', 'init'], cwd=repo, check=True)

            res = run_py(STATUS_PY, 'check', '--refresh-sums', '--root', str(repo), cwd=repo)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            sums = (repo / 'SHA256SUMS').read_text(encoding='utf-8').splitlines()
            expected_readme = hashlib.sha256(b'hello\n').hexdigest() + '  README.md'
            self.assertIn(expected_readme, sums)

            (repo / 'notes.txt').write_text('tampered\n', encoding='utf-8')
            fail = run_py(STATUS_PY, 'check', '--root', str(repo), cwd=repo)
            self.assertNotEqual(fail.returncode, 0)

    def test_prune_runs_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / 'runs'
            r1 = runs / '20261101-demo-01'
            r2 = runs / '20261102-demo-01'
            obj = r1 / 'kernel/obj/DEVELOPMENT_ARM64_BCM2837'
            dsym = obj / 'mach.development.bcm2837.dSYM/Contents/Resources/DWARF'
            (r1 / 'replay-tree/hackios').mkdir(parents=True)
            (r1 / 'replay-tree/hackios/junk.c').write_bytes(b'x' * 1024)
            (r1 / 'replay-tree.json').write_text('{"ok": true}\n', encoding='utf-8')
            dsym.mkdir(parents=True)
            (dsym / 'mach.development.bcm2837').write_bytes(b'DWARF' * 256)
            (obj / 'foo.o').write_bytes(b'OBJ' * 128)
            (obj / 'mach.development.bcm2837.a').write_bytes(b'AR' * 256)
            (obj / 'mach.development.bcm2837').write_bytes(b'KERNEL')
            (r1 / 'candidate').mkdir(parents=True)
            (r2 / 'candidate').mkdir(parents=True)
            img_data = b'NXSB' * (300 * 1024)
            img1 = r1 / 'candidate/root.apfs'
            img2 = r2 / 'candidate/root.apfs'
            img1.write_bytes(img_data)
            img2.write_bytes(img_data)
            self.assertNotEqual(img1.stat().st_ino, img2.stat().st_ino)

            dry = run_py(STATUS_PY, 'prune-runs', '--runs-dir', str(runs))
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertIn('[DRY-RUN]', dry.stdout)
            self.assertTrue((r1 / 'replay-tree').exists())
            self.assertNotEqual(img1.stat().st_ino, img2.stat().st_ino)

            applied = run_py(STATUS_PY, 'prune-runs', '--apply', '--runs-dir', str(runs))
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertFalse((r1 / 'replay-tree').exists())
            self.assertTrue((r1 / 'replay-tree.json').is_file())
            self.assertFalse((obj / 'foo.o').exists())
            self.assertFalse((obj / 'mach.development.bcm2837.a').exists())
            self.assertFalse((obj / 'mach.development.bcm2837.dSYM').exists())
            self.assertTrue((obj / 'mach.development.bcm2837').is_file())
            self.assertEqual(img1.stat().st_ino, img2.stat().st_ino)
            self.assertEqual(img1.stat().st_nlink, 2)
            self.assertEqual(len(list(runs.glob('_pruned-*.tsv'))), 1)

    def test_cli_flags_and_host_only_guard(self):
        payload_help = run_py(BUILD_PAYLOAD, '--help')
        self.assertEqual(payload_help.returncode, 0)
        self.assertIn('--link-inputs', payload_help.stdout)

        k_help = subprocess.run(['bash', str(BUILD_KERNEL), '--help'], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(k_help.returncode, 0)
        self.assertIn('--with-ath10k', k_help.stdout)

        k_boot = subprocess.run(['bash', str(BUILD_KERNEL), '--boot'], cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(k_boot.returncode, 0)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowToolsTests)
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    if res.wasSuccessful():
        print(f'SELFTEST PASS {res.testsRun}/{res.testsRun}')
        raise SystemExit(0)
    raise SystemExit(1)
