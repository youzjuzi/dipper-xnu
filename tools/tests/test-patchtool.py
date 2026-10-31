#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline synthetic patch export/replay tests; never open the development tree."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

spec = importlib.util.spec_from_file_location('patchtool', Path(__file__).resolve().parents[1] / 'prepare/patchtool.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'synthetic'
        self.base = self.root / 'baseline'
        self.patchdir = self.root / 'patches'
        self.patchdir.mkdir()
        self.mapping = patch.dict(m.LAYOUT, {'alpha': 'shared', 'beta': 'shared', 'other': 'other'}, clear=True)
        self.mapping.start()
        self.addCleanup(self.mapping.stop)
        self.groups = []
        for directory in [self.work / 'shared', self.work / 'other']:
            directory.mkdir(parents=True)
            m.git('init', '-q', cwd=directory)
        for name, rel, files in [('alpha', 'shared', ['a.c', 'b.c']), ('beta', 'shared', ['c.c']), ('other', 'other', ['d.c'])]:
            entries = []
            for filename in files:
                p = self.base / rel / filename
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'base\n')
                p.chmod(0o644)
                (self.work / rel / filename).write_bytes(b'base\n')
                (self.work / rel / filename).chmod(0o644)
                entries.append({'path': filename, 'sha256': m.digest(b'base\n'), 'mode': '0o644'})
            self.groups.append({'component': name, 'base': 'synthetic', 'files': entries})
            (self.patchdir / (name + '.patch')).write_bytes(b'')
        for directory in [self.work / 'shared', self.work / 'other']:
            m.git('add', '--all', cwd=directory)
        self.bases = {name: self.base / rel for name, rel in m.LAYOUT.items()}

    def export(self, dest='out', **kwargs):
        out = self.root / dest
        report = m.export_tree(self.root, self.work, out, self.groups, self.bases, **kwargs)
        return out, report

    def test_idempotence(self):
        (self.work / 'shared/a.c').write_bytes(b'changed\n')
        a, _ = self.export('one')
        b, _ = self.export('two')
        self.assertEqual({p.name: p.read_bytes() for p in a.iterdir()}, {p.name: p.read_bytes() for p in b.iterdir()})

    def test_independent_blocks(self):
        (self.work / 'shared/a.c').write_bytes(b'first\n')
        (self.work / 'shared/b.c').write_bytes(b'second\n')
        a, _ = self.export('one')
        (self.work / 'shared/a.c').write_bytes(b'third\n')
        b, _ = self.export('two')
        key = b'diff --git a/b.c b/b.c\n'
        self.assertEqual((a / 'alpha.patch').read_bytes().split(key)[1], (b / 'alpha.patch').read_bytes().split(key)[1])
        self.assertEqual((a / 'beta.patch').read_bytes(), (b / 'beta.patch').read_bytes())

    def test_unowned_report_only(self):
        (self.work / 'shared/new.c').write_bytes(b'new\n')
        out, report = self.export()
        self.assertEqual(report['unowned'], [{'component': 'alpha', 'path': 'new.c'}])
        self.assertNotIn(b'new.c', (out / 'alpha.patch').read_bytes())

    def test_explicit_add(self):
        (self.work / 'shared/new.c').write_bytes(b'new\n')
        out, _ = self.export(components=['alpha'], adds=['new.c'])
        self.assertIn(b'new.c', (out / 'alpha.patch').read_bytes())

    def test_shared_ownership(self):
        (self.work / 'shared/c.c').write_bytes(b'owned by beta\n')
        out, _ = self.export()
        self.assertFalse((out / 'alpha.patch').read_bytes())
        self.assertTrue((out / 'beta.patch').read_bytes())
        with self.assertRaises(m.Failure):
            self.export('two', adds=['alpha:c.c'])

    def test_deletion(self):
        (self.work / 'shared/a.c').unlink()
        out, report = self.export()
        self.assertEqual(report['deleted'], [{'component': 'alpha', 'path': 'a.c'}])
        groups = json.loads((out / 'source-manifest.json').read_text())
        self.assertIsNone(groups[0]['files'][0]['sha256'])
        m.apply_patches(self.root, self.bases, groups, out)
        m.verify_manifest(self.bases, groups)

    def test_junk(self):
        for name in ['BUILD/file.c', '__pycache__/foo.c', 'a.orig', 'a.rej', 'a.pyc', 'a.o', 'a.swp', 'a.bak1', 'generated.d', '.DS_Store']:
            p = self.work / 'shared' / name
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(b'junk\n')
        _, report = self.export()
        self.assertFalse(report['unowned'])

    def test_identity_restoration(self):
        # Construct a synthetic identity in memory; never print or persist it.
        private = ('#define BLOCK_DARWIN_UNIQ ' + '{ 1, 2, 3, ' + '{ ' + ', '.join(str(n) for n in range(4, 12)) + ' } }\n').encode()
        public = b'#define BLOCK_DARWIN_UNIQ { 0, 0, 0, { 0, 0, 0, 0, 0, 0, 0, 0 } }\n'
        result = m.normalized('hackios-kernel', 'xnuloader/loader.c', private, public)
        self.assertEqual(result, public)
        self.assertFalse(m.findings(result))
        self.assertNotIn(private, result)

    def test_unknown_identity_rejected(self):
        value = str(uuid.UUID(int=987654321))
        with self.assertRaises(m.Failure):
            m.normalized('alpha', 'a.c', value.encode(), None)

    def test_binary_rejected(self):
        with self.assertRaises(m.Failure):
            m.require_public(b'binary\0identity')

    def test_replay_success(self):
        (self.work / 'shared/a.c').write_bytes(b'changed\n')
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        m.replay_tree(self.root, self.work, groups, self.bases, out)

    def test_replay_hash_failure(self):
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        (self.work / 'shared/a.c').write_bytes(b'bad\n')
        with self.assertRaises(m.Failure):
            m.replay_tree(self.root, self.work, groups, self.bases, out)

    def test_replay_mode_failure(self):
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        (self.work / 'shared/a.c').chmod(0o755)
        with self.assertRaises(m.Failure):
            m.replay_tree(self.root, self.work, groups, self.bases, out)

    def test_replay_unexpected(self):
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        (self.work / 'shared/unexpected.c').write_bytes(b'new\n')
        with self.assertRaises(m.Failure):
            m.replay_tree(self.root, self.work, groups, self.bases, out)

    def test_scan_redaction_and_levels(self):
        value = str(uuid.UUID(int=987654321))
        secret_path = '/' + 'home/' + 'private-person/source'
        secret_mac = ':'.join(['12', '34', '56', '78', '90', 'ab'])
        data = '\n'.join([value, secret_path, secret_mac, 'TA' + 'SK-123', 'EX' + 'P-123'])
        p = self.root / 'input.txt'
        p.write_text(data)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = m.scan_paths(self.root, [p])
        self.assertEqual(status, 1)
        self.assertIn('error:guid', output.getvalue())
        self.assertIn('warning:process-id', output.getvalue())
        for secret in [value, secret_path, secret_mac]:
            self.assertNotIn(secret, output.getvalue())
        p.write_text('TA' + 'SK-123\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.scan_paths(self.root, [p]), 0)

    def test_scan_serial(self):
        data = ('serial=' + '"' + 'PRIVATE123456' + '"').encode()
        self.assertIn((1, 'error', 'serial'), m.findings(data))

    def test_allowlist(self):
        self.assertFalse(m.findings(('\n'.join(sorted(m.ALLOWED_GUIDS))).encode()))

    def test_output_refuses_overwrite(self):
        self.export()
        with self.assertRaises(m.Failure):
            self.export()

    def test_unsafe_path(self):
        for name in ['../escape', '/absolute', '.git/index', 'a/../../escape']:
            with self.assertRaises(m.Failure):
                m.safe_path(name)

    def test_symlink_parent(self):
        (self.work / 'shared/link').symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(m.Failure):
            m.source_path(self.work / 'shared', 'link/escape')

    def test_unowned_nested_submodule(self):
        parent = self.work / 'other'
        child = parent / 'nested'
        child.mkdir()
        m.git('init', '-q', cwd=child)
        (child / 'nested.c').write_bytes(b'base\n')
        m.git('add', '--all', cwd=child)
        commit_args = ('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-q', '-m', 'baseline')
        m.git(*commit_args, cwd=child)
        pinned = m.git('rev-parse', 'HEAD', cwd=child).decode().strip()
        m.git('update-index', '--add', '--cacheinfo', '160000,' + pinned + ',nested', cwd=parent)
        m.git(*commit_args, cwd=parent)
        head = m.git('rev-parse', 'HEAD', cwd=parent).decode().strip()
        (self.root / 'upstream.lock.json').write_text(json.dumps([{'name': 'other', 'commit': head}]))
        (child / 'nested.c').write_bytes(b'changed\n')
        changes = m.submodule_changes(self.root, self.work, self.groups)
        self.assertIn({'component': 'other', 'path': 'nested/nested.c'}, changes)
        # A shallow auxiliary checkout can lack the parent's pinned object.
        m.git('update-index', '--cacheinfo', '160000,' + '1' * 40 + ',nested', cwd=parent)
        m.git(*commit_args, cwd=parent)
        head = m.git('rev-parse', 'HEAD', cwd=parent).decode().strip()
        (self.root / 'upstream.lock.json').write_text(json.dumps([{'name': 'other', 'commit': head}]))
        changes = m.submodule_changes(self.root, self.work, self.groups)
        self.assertIn({'component': 'other', 'path': 'nested',
                       'kind': 'submodule-revision;submodule-baseline-unavailable'}, changes)

    def test_output_inside_release_refused(self):
        with self.assertRaises(m.Failure):
            m.export_tree(self.root, self.work, self.patchdir / 'new', self.groups, self.bases)

    def test_output_inside_source_refused(self):
        with self.assertRaises(m.Failure):
            m.export_tree(self.root, self.work, self.work / 'shared/output', self.groups, self.bases)

    def test_patch_executable_mode_mismatch(self):
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        groups[0]['files'][0]['mode'] = '0o755'
        with self.assertRaises(m.Failure):
            m.apply_patches(self.root, self.bases, groups, out)

    def test_unowned_directory_symlink(self):
        (self.work / 'shared/new-link').symlink_to(self.base, target_is_directory=True)
        _, report = self.export()
        self.assertIn({'component': 'alpha', 'path': 'new-link'}, report['unowned'])

    def test_staged_unowned_change(self):
        path = self.work / 'shared/extra.c'
        path.write_bytes(b'initial\n')
        m.git('add', '--', 'extra.c', cwd=path.parent)
        path.write_bytes(b'changed\n')
        m.git('add', '--', 'extra.c', cwd=path.parent)
        _, report = self.export()
        self.assertIn({'component': 'alpha', 'path': 'extra.c'}, report['unowned'])

    def test_staged_unowned_deletion(self):
        path = self.base / 'shared/extra.c'
        path.write_bytes(b'initial\n')
        _, report = self.export()
        self.assertIn({'component': 'alpha', 'path': 'extra.c'}, report['unowned'])

    def test_c_mac_rejected(self):
        data = b'static const uint8_t wifi_address[6] = ' + ('{ ' + ', '.join(str(n) for n in range(1, 7)) + ' };').encode()
        self.assertIn((1, 'error', 'mac-initializer'), m.findings(data))

    def test_identity_export_and_readonly(self):
        with patch.dict(m.LAYOUT, {'hackios-kernel': 'shared'}, clear=True):
            public = b'#define BLOCK_DARWIN_UNIQ { 0, 0, 0, { 0, 0, 0, 0, 0, 0, 0, 0 } }\n'
            public += b'static const uint8_t wifi_address[6] = { 0, 0, 0, 0, 0, 0 };\n'
            private = public.replace(b'{ 0, 0, 0, {', b'{ 1, 2, 3, {').replace(b'{ 0, 0, 0, 0, 0, 0 };', b'{ 1, 2, 3, 4, 5, 6 };')
            paths = [self.base / 'shared/xnuloader/loader.c', self.work / 'shared/xnuloader/loader.c']
            for path, data in zip(paths, [public, private]):
                path.parent.mkdir(parents=True)
                path.write_bytes(data)
                path.chmod(0o644)
            groups = [{'component': 'hackios-kernel', 'base': 'synthetic', 'files': [
                {'path': 'xnuloader/loader.c', 'sha256': m.digest(public), 'mode': '0o644'}]}]
            (self.patchdir / 'hackios-kernel.patch').write_bytes(b'')
            bases = {'hackios-kernel': self.base / 'shared'}
            before = paths[1].stat()
            out = self.root / 'identity-export'
            m.export_tree(self.root, self.work, out, groups, bases)
            for path in out.iterdir():
                self.assertNotIn(private, path.read_bytes())
                self.assertFalse([f for f in m.findings(path.read_bytes()) if f[1] == 'error'])
            after = paths[1].stat()
            self.assertEqual((before.st_mtime_ns, before.st_mode), (after.st_mtime_ns, after.st_mode))
            self.assertEqual(paths[1].read_bytes(), private)

    def test_prepare_dest_complete_local_flow(self):
        script = Path(__file__).resolve().parents[1] / 'prepare/prepare.py'
        spec = importlib.util.spec_from_file_location('source_prepare_test', script)
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        root = self.root / 'release'
        root.mkdir()
        (root / 'patches').mkdir()
        for component in ['xnu-mi8', 'hackios-kernel', 'hackios-userland', 'edk2-sdm845', 'simpleinit', 'unixnu']:
            (root / 'patches' / (component + '.patch')).write_bytes(b'')
        sources = []
        for name in ['hackios', 'userland', 'xnu', 'edk2', 'unixnu']:
            repo = self.root / 'upstream' / name
            repo.mkdir(parents=True)
            m.git('init', '-q', cwd=repo)
            (repo / 'fixture.c').write_bytes(b'base\n')
            if name == 'hackios':
                (repo / 'xnu/files').mkdir(parents=True)
                (repo / 'xnu/files/extra.h').write_bytes(b'overlay\n')
                (repo / 'xnu/redwood.patch').write_bytes(m.diff_file('fixture.c', (b'base\n', '0o644'), (b'hackios\n', '0o644')))
            if name == 'userland':
                (repo / 'userland').mkdir()
                (repo / 'userland/example.c').write_bytes(b'userland\n')
            m.git('add', '--all', cwd=repo)
            m.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                  'commit', '-q', '-m', 'baseline', cwd=repo)
            sources.append({'name': name, 'url': str(repo), 'commit': m.git('rev-parse', 'HEAD', cwd=repo).decode().strip()})
        (root / 'upstream.lock.json').write_text(json.dumps(sources))
        (root / 'patches/xnu-mi8.patch').write_bytes(m.diff_file('fixture.c', (b'hackios\n', '0o644'), (b'port\n', '0o644')))
        group = [{'component': 'xnu-mi8', 'files': [{'path': 'fixture.c', 'sha256': m.digest(b'port\n'), 'mode': '0o664'}]}]
        (root / 'source-manifest.json').write_text(json.dumps(group))
        service = root / 'system/userland-wifi/com.redwood.wifi.plist'
        service.parent.mkdir(parents=True)
        service.write_bytes(b'service\n')
        (root / 'SHA256SUMS').write_text(m.digest(service.read_bytes()) + '  system/userland-wifi/com.redwood.wifi.plist\n')
        dest = self.root / 'prepared'
        def quiet_run(*args, cwd=None):
            subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with patch.object(prepare, 'ROOT', root), patch.object(prepare, 'prepare_submodules'), patch.object(prepare, 'run', quiet_run):
            with patch('sys.argv', [str(script), '--prepare', '--dest', os.path.relpath(dest, root)]), contextlib.chdir(root), contextlib.redirect_stdout(io.StringIO()):
                prepare.main()
        self.assertEqual((dest / 'hackios/xnu-src/xnu-8796.121.2/fixture.c').read_bytes(), b'port\n')
        self.assertEqual((dest / 'hackios/xnu-src/xnu-8796.121.2/extra.h').read_bytes(), b'overlay\n')
        self.assertEqual((dest / 'hackios/userland/com.redwood.wifi.plist').read_bytes(), b'service\n')
        self.assertEqual((dest / 'hackios/xnu-src/xnu-8796.121.2/fixture.c').stat().st_mode & 0o777, 0o664)

    def test_prepare_dest_existing(self):
        script = Path(__file__).resolve().parents[1] / 'prepare/prepare.py'
        p = subprocess.run(['python3', str(script), '--prepare', '--dest', str(self.work)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b'refusing to overwrite', p.stderr)
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ['other', 'shared'])

    def test_executable_and_symlink_patch(self):
        (self.work / 'shared/a.c').chmod(0o755)
        (self.work / 'shared/b.c').unlink()
        (self.work / 'shared/b.c').symlink_to('a.c')
        out, _ = self.export()
        groups = json.loads((out / 'source-manifest.json').read_text())
        m.apply_patches(self.root, self.bases, groups, out)
        m.verify_manifest(self.bases, groups)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    count = result.testsRun
    passed = count - len(result.failures) - len(result.errors)
    print(f'SELFTEST {"PASS" if result.wasSuccessful() else "FAIL"} {passed}/{count}')
    raise SystemExit(0 if result.wasSuccessful() else 1)
