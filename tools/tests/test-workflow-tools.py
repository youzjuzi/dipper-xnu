#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 yanei
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
DEVICE_LOG = ROOT / 'tools/tests/device-log.py'


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

    def _make_fake_fastboot(self, directory, product='xnuloader'):
        state_file = directory / 'state.txt'
        calls_file = directory / 'calls.log'
        state_file.write_text('0\n', encoding='utf-8')
        fb = directory / 'fake-fastboot'
        fb.write_text(f"""#!/usr/bin/env python3
import sys
from pathlib import Path

state_file = Path({str(state_file)!r})
calls_file = Path({str(calls_file)!r})
args = sys.argv[1:]
if len(args) >= 2 and args[0] == '-s':
    args = args[2:]
with calls_file.open('a', encoding='utf-8') as f:
    f.write(' '.join(args) + '\\n')

n = int(state_file.read_text(encoding='utf-8').strip())
if args[:2] == ['getvar', 'product']:
    sys.stderr.write('product: {product}\\nFinished. Total time: 0.001s\\n')
    raise SystemExit(0)
if args[:2] == ['getvar', 'result']:
    res = 'returned 1456278 0' if n >= 2 else 'running'
    sys.stderr.write(f'result: {{res}}\\nFinished. Total time: 0.001s\\n')
    raise SystemExit(0)
if args[:2] == ['oem', 'stop']:
    state_file.write_text('2\\n', encoding='utf-8')
    sys.stderr.write('OKAY\\n')
    raise SystemExit(0)
if args[:2] == ['oem', 'log']:
    if n >= 2:
        # Simulate xnuloader recomposing the 32 KiB loader-only log over the staged post-return log.
        state_file.write_text('99\\n', encoding='utf-8')
    else:
        state_file.write_text(str(n + 1) + '\\n', encoding='utf-8')
    sys.stderr.write('OKAY\\n')
    raise SystemExit(0)
if len(args) >= 2 and args[0] == 'get_staged':
    out = Path(args[1])
    if n == 0:
        out.write_text('HEAD\\nline-1\\n', encoding='utf-8')
    elif n == 1:
        out.write_text('HEAD\\nline-1\\nline-2\\n', encoding='utf-8')
    elif n == 2:
        out.write_text('HEAD\\nline-2\\nline-3\\nreturned-ok\\n', encoding='utf-8')
    else:
        out.write_text('CLOBBERED-BY-OEM-LOG\\n', encoding='utf-8')
    raise SystemExit(0)
sys.stderr.write('unexpected command\\n')
raise SystemExit(1)
""", encoding='utf-8')
        fb.chmod(0o755)
        return fb, calls_file

    def test_device_log_refuses_non_xnuloader(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            fb, calls = self._make_fake_fastboot(tdir, product='dipper')
            res = run_py(DEVICE_LOG, '--fastboot', str(fb), 'snapshot', '--out', str(tdir / 'out.log'))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn('xnuloader', res.stderr)
            self.assertEqual(calls.read_text(encoding='utf-8').splitlines(), ['getvar product'])

    def test_device_log_watch_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            fb, calls = self._make_fake_fastboot(tdir, product='xnuloader')
            out_log = tdir / 'latest.log'
            stream_log = tdir / 'stream.log'
            res = run_py(
                DEVICE_LOG, '--fastboot', str(fb),
                'watch', '--interval', '0.01', '--out', str(out_log), '--stream', str(stream_log)
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(out_log.read_text(encoding='utf-8'), 'HEAD\nline-2\nline-3\nreturned-ok\n')
            self.assertEqual(stream_log.read_text(encoding='utf-8'), 'HEAD\nline-1\nline-2\nline-3\nreturned-ok\n')

            # Also test orderly stop subcommand starting from running state.
            stop_dir = tdir / 'stop'
            stop_dir.mkdir()
            fb2, calls2 = self._make_fake_fastboot(stop_dir, product='xnuloader')
            stop_out = tdir / 'stop.log'
            stop_res = run_py(
                DEVICE_LOG, '--fastboot', str(fb2),
                'stop', '--poll-interval', '0.01', '--wait-timeout', '2', '--out', str(stop_out)
            )
            self.assertEqual(stop_res.returncode, 0, stop_res.stdout + stop_res.stderr)
            self.assertIn('oem stop', calls2.read_text(encoding='utf-8'))
            self.assertNotIn('oem log', calls2.read_text(encoding='utf-8'))
            self.assertIn('returned-ok', stop_out.read_text(encoding='utf-8'))

            # Snapshot on an already-returned session must also skip oem log to preserve the staged log.
            snap_out = tdir / 'snap.log'
            snap_res = run_py(DEVICE_LOG, '--fastboot', str(fb2), 'snapshot', '--out', str(snap_out))
            self.assertEqual(snap_res.returncode, 0, snap_res.stdout + snap_res.stderr)
            self.assertNotIn('oem log', calls2.read_text(encoding='utf-8'))
            self.assertEqual(snap_out.read_text(encoding='utf-8'), 'HEAD\nline-2\nline-3\nreturned-ok\n')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowToolsTests)
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    if res.wasSuccessful():
        print(f'SELFTEST PASS {res.testsRun}/{res.testsRun}')
        raise SystemExit(0)
    raise SystemExit(1)
