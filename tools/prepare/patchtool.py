#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export manifest-owned patches, verify clean replay, and scan public content."""
import argparse
import contextlib
import fnmatch
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = {'xnu-mi8': 'hackios/xnu-src/xnu-8796.121.2',
          'hackios-kernel': 'hackios', 'hackios-userland': 'hackios',
          'edk2-sdm845': 'edk2', 'simpleinit': 'edk2/GPLDrivers/Library/SimpleInit',
          'unixnu': 'unixnu'}
# UEFI/APFS/Linux partition types, published package/file GUIDs in the port,
# and the synthetic partition test placeholder. These are not device IDs.
ALLOWED_GUIDS = {
    str(uuid.UUID(int=0)), '7c3457ef-0000-11aa-aa11-00306543ecac',
    '0fc63daf-8483-4772-8e79-3d69d8477de4',
    'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
    'db99a07e-4e35-4491-957e-ef89c3dd57a0',
    '3f6c3b0e-5a52-4f0b-9a3e-6a2f0d0c8b11',
    '25462cda-221f-47df-ac1d-259cfaa4e326',
    'd82f808b-ecca-4bb8-8e9f-9b9bafc490f5',
    # Apple CDN release asset ID from docs/build/INPUTS.md.
    '6ab0d10a-8af9-4f6c-8cf5-a1b315cabe88',
    # Locked HackiOS loader's published example, present on removed patch lines.
    'fd6854ad-24aa-4fc3-94fe-290116858d68',
}
# Fixed upstream EFI protocol and package identifiers from locked xnuloader/efi.h,
# dipper.dsc, dipper.fdf.inc and UniXNULib.inf (upstream.lock.json).
ALLOWED_GUIDS.update({
    '09576e91-6d3f-11d2-8e39-00a0c969723b',
    '1c0cffce-fc8d-4e44-8c78-9c9e5b530d36',
    '21bfb78b-02ea-4ab7-9940-b58a2ad65829',
    '25462cda-221f-47df-ac1d-259cfaa4e326',
    '26baccb1-6f42-11d4-bce7-0080c73c8881',
    '28f1a3bf-193a-47e3-a7b9-5a435eaab2ee',
    '2ea3e316-7ec4-4867-9fea-abe1d4e9dba6',
    '5bd181db-0487-4f1a-ae73-820e165611b3',
    '6edc8a6d-2663-43cd-90ff-4621ffd10df5',
    '7e374e25-8e01-4fee-87f2-390c23c606cd',
    '8cf2f62c-bc9b-4821-808d-ec9ec421a1a0',
    '9042a9de-23dc-4a38-96fb-7aded080516a',
    '964e5b21-6459-11d2-8e39-00a0c969723b',
    'a77b2472-e282-4e9f-a245-c2c0e27bbcc1',
    'd9d9ce48-44b8-4f49-8e3e-2a3b927dc6c1',
})

GUID = re.compile(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b')
C_MAC = re.compile(r'(?i)\b(?:wifi_address|bluetooth_address|\w*mac(?:_address)?)\s*\[[^\]]*\]\s*=\s*\{([^{}]+)\}')
ALLOWED_MACS = {'00:00:00:00:00:00'}
# Synthetic address defaults published in the locked upstream loader.
ALLOWED_MACS.update({
    '02:52:44:57:00:01',
    '02:52:44:57:00:02',
})

MAC = re.compile(r'(?<![\w:])(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}(?![\w:])')
C_GUID = re.compile(r'\{\s*((?:0x[0-9a-fA-F]+|\d+)\s*,\s*){3}\{[^{}]+\}\s*\}')
SERIAL = re.compile(r'''(?i)(?:serial(?:[-_ ]?number)?|udid)\s*["']?\s*[:=,]\s*["']([A-Za-z0-9-]{8,})["']''')
# Published upstream loader defaults, not values read from local configuration.
SERIAL_DEFAULTS = {'RDW00POCOX5P', 'RDW00POCOX5PMLB00', 'TESTSERIAL'}
JUNK = ('*.orig', '*.rej', '*.pyc', '*.o', '*.swp', '*.bak*', '*.d', '.DS_Store')


class Failure(Exception):
    """A value-free diagnostic safe to show in public logs."""


def git(*args, cwd):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', LC_ALL='C',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_ATTR_NOSYSTEM='1')
    p = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.autocrlf=false',
                        '-c', 'core.attributesFile=/dev/null', *args],
                       cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        # Git errors may contain source lines or local paths. Never echo them.
        raise Failure('Git operation failed: ' + args[0])
    return p.stdout


def safe_path(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '.git' in p.parts or str(p) != name:
        raise Failure('Invalid relative source path')
    if any(ord(c) < 32 for c in name) or GUID.search(name) or MAC.search(name):
        raise Failure('Unsafe source filename')
    return name


def source_path(tree, name):
    path = tree / safe_path(name)
    # Never traverse symlink parents, including links to another component.
    for parent in path.parents:
        if parent == tree:
            break
        if parent.is_symlink():
            raise Failure('Symlink parent refused')
    return path


def ignored(name):
    p = PurePosixPath(name)
    return any(part in {'.git', 'BUILD', 'Build', '__pycache__'} for part in p.parts) or any(
        fnmatch.fnmatch(p.name, pattern) for pattern in JUNK)


def c_guid(text):
    nums = re.findall(r'0x[0-9a-fA-F]+|\d+', text)
    if len(nums) != 11:
        return None
    v = [int(n, 16 if n.lower().startswith('0x') else 10) for n in nums]
    try:
        return str(uuid.UUID(fields=(v[0], v[1], v[2], v[3], v[4],
                                    int.from_bytes(bytes(v[5:]), 'big'))))
    except (ValueError, OverflowError):
        return None


def findings(data):
    """Return only line numbers, severity, and category; never matched text."""
    text = data.decode('utf-8', errors='replace')
    result = []
    for n, line in enumerate(text.splitlines(), 1):
        cats = set()
        if re.search(r'/' + r'home/[^/\s<>"\']+', line):
            cats.add(('error', 'private-path'))
        if any(m.group().lower() not in ALLOWED_GUIDS for m in GUID.finditer(line)):
            cats.add(('error', 'guid'))
        for m in C_GUID.finditer(line):
            ident = c_guid(m.group())
            if ident is not None and ident not in ALLOWED_GUIDS:
                cats.add(('error', 'guid-initializer'))
        if any(m.group().lower().replace('-', ':') not in ALLOWED_MACS for m in MAC.finditer(line)):
            cats.add(('error', 'mac'))
        for match in C_MAC.finditer(line):
            nums = re.findall(r'0x[0-9a-fA-F]+|\d+', match.group(1))
            if len(nums) != 6:
                cats.add(('error', 'mac-initializer'))
            else:
                values = [int(n, 16 if n.lower().startswith('0x') else 10) for n in nums]
                if ':'.join(f'{n:02x}' for n in values) not in ALLOWED_MACS:
                    cats.add(('error', 'mac-initializer'))
        if any(m.group(1) not in SERIAL_DEFAULTS for m in SERIAL.finditer(line)):
            cats.add(('error', 'serial'))
        if re.search(r'\b(?:TASK|EXP)-\d+\b', line):
            cats.add(('warning', 'process-id'))
        if re.search(r'Co-Authored-By', line, re.I):
            cats.add(('warning', 'attribution'))
        if re.search(r'\b(?:Codex|Claude)\b', line, re.I):
            cats.add(('warning', 'assistant-name'))
        result.extend((n, severity, category) for severity, category in sorted(cats))
    return result


def require_public(data):
    if any(severity == 'error' for _, severity, _ in findings(data)):
        raise Failure('Privacy check failed; use scan for value-free locations')
    if b'\x00' in data:
        raise Failure('Binary source cannot be confirmed free of device identity')


def read_file(path):
    if not path.exists() and not path.is_symlink():
        return None, None
    if path.is_symlink():
        return os.readlink(path).encode(), '0o120000'
    if not path.is_file():
        raise Failure('Non-file source refused')
    return path.read_bytes(), oct(stat.S_IMODE(path.stat().st_mode))


def put_file(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == '0o120000':
        path.symlink_to(data.decode())
    else:
        path.write_bytes(data)
        path.chmod(int(mode, 8))


def git_mode(mode):
    if mode is None or mode == '0o120000':
        return mode
    return 'executable' if int(mode, 8) & 0o111 else 'regular'


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def load_groups(root):
    groups = json.loads((root / 'source-manifest.json').read_text())
    owned = set()
    for group in groups:
        if group['component'] not in LAYOUT:
            raise Failure('Unknown component')
        for entry in group['files']:
            key = (LAYOUT[group['component']], safe_path(entry['path']))
            if key in owned:
                raise Failure('Overlapping component ownership')
            owned.add(key)
    return groups


def archive(repo, commit, dest):
    # git archive reads objects without changing the source index, refs or tree.
    if git('rev-parse', commit + '^{commit}', cwd=repo).decode().strip() != commit:
        raise Failure('Pinned commit mismatch')
    dest.mkdir(parents=True)
    data = git('archive', '--format=tar', commit, cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest, filter='data')


@contextlib.contextmanager
def baseline(root, work):
    """Recreate pinned objects locally, sharing prepare.py's baseline overlay."""
    spec = importlib.util.spec_from_file_location('source_prepare', root / 'tools/prepare/prepare.py')
    prepare = importlib.util.module_from_spec(spec)
    bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(prepare)
    finally:
        sys.dont_write_bytecode = bytecode
    with tempfile.TemporaryDirectory(prefix='patchtool-') as tmp:
        dest = Path(tmp)
        trees = {}
        for source in json.loads((root / 'upstream.lock.json').read_text()):
            repo = work / ('hackios/xnu-src/xnu-8796.121.2' if source['name'] == 'xnu' else source['name'])
            trees[source['name']] = dest / source['name']
            archive(repo, source['commit'], trees[source['name']])
        # The only patched submodule is pinned by the parent's gitlink.
        sub = 'GPLDrivers/Library/SimpleInit'
        commit = git('ls-tree', trees_commit(root, 'edk2'), '--', sub, cwd=work / 'edk2').decode().split()[2]
        (trees['edk2'] / sub).rmdir()
        archive(work / 'edk2' / sub, commit, trees['edk2'] / sub)
        # assemble_baseline enumerates userland via Git; archive carries no index.
        git('init', '-q', cwd=trees['userland'])
        git('add', '--force', '--all', cwd=trees['userland'])
        yield prepare.assemble_baseline(trees)


def trees_commit(root, name):
    return next(s['commit'] for s in json.loads((root / 'upstream.lock.json').read_text()) if s['name'] == name)


def paths_for(work):
    return {name: work / rel for name, rel in LAYOUT.items()}


def normalized(component, name, data, public):
    if data is None:
        return data
    # Restore only named identity-bearing fields to their reviewed public values.
    # The reference is the existing release replay, never local configuration.
    if component == 'hackios-kernel' and name == 'xnuloader/loader.c':
        if public is None:
            raise Failure('Public loader reference missing')
        patterns = [rb'^#define BLOCK_DARWIN_UNIQ[^\n]*',
                    rb'^\s*static const uint8_t (?:wifi_address|bluetooth_address)\[[^\n]*',
                    rb'^\s*dt_prop_padded\([^\n]*"(?:serial-number|mlb-serial-number)"[^\n]*']
        for pattern in patterns:
            refs = re.findall(pattern, public, re.M)
            current = re.findall(pattern, data, re.M)
            if len(refs) != len(current):
                raise Failure('Loader identity field layout changed')
            refs = iter(refs)
            data = re.sub(pattern, lambda _: next(refs), data, flags=re.M)
    require_public(data)
    return data


def apply_patches(root, targets, groups, patch_dir=None):
    directory = patch_dir or root / 'patches'
    legacy = set()
    for group in groups:
        patch = directory / (group['component'] + '.patch')
        data = patch.read_bytes()
        if data and not data.startswith(b'diff --git '):
            legacy.add(group['component'])
        if data:
            target = targets[group['component']]
            git('apply', '--check', str(patch.resolve()), cwd=target)
            git('apply', str(patch.resolve()), cwd=target)
    for group in groups:
        for entry in group['files']:
            path = source_path(targets[group['component']], entry['path'])
            if entry['sha256'] is not None and path.exists() and not path.is_symlink():
                if group['component'] not in legacy and git_mode(read_file(path)[1]) != git_mode(entry['mode']):
                    raise Failure('Patch executable mode does not match manifest')
                # Legacy unified patches carry no modes; their manifest is the
                # authority. Modern Git patches must encode executable bits.
                # prepare.py also restores full non-executable permission bits.
                path.chmod(int(entry['mode'], 8))


def candidates(tree):
    # Include staged and unchanged tracked paths too: the index is not a baseline.
    # Standard ignores exclude untracked native build outputs.
    data = git('ls-files', '-z', '--cached', '--others', '--exclude-standard', cwd=tree)
    return sorted(set(n.decode() for n in data.split(b'\0') if n and not ignored(n.decode())))


def submodule_changes(root, work, groups):
    """Inspect initialized gitlinks too, without copying their unpatched trees."""
    lock = root / 'upstream.lock.json'
    if not lock.exists():
        return []
    targets = paths_for(work)
    owners = {str(targets[g['component']] / e['path']) for g in groups for e in g['files']}
    result = []

    def record(path, kind=None):
        matches = [(c, tree) for c, tree in targets.items() if path == tree or tree in path.parents]
        if not matches:
            return
        component, tree = max(matches, key=lambda item: len(item[1].parts))
        name = path.relative_to(tree).as_posix()
        if (name != '.' or kind) and not ignored(name) and str(path) not in owners:
            entry = {'component': component, 'path': safe_path(name)}
            if kind:
                entry['kind'] = kind
            existing = next((e for e in result if e['component'] == component and e['path'] == name), None)
            if existing is None:
                result.append(entry)
            elif kind and kind not in existing.get('kind', '').split(';'):
                existing['kind'] = ';'.join(filter(None, [existing.get('kind'), kind]))

    def visit(repo, commit):
        for entry in git('ls-tree', '-r', '-z', commit, cwd=repo).split(b'\0'):
            if not entry:
                continue
            metadata, name = entry.split(b'\t', 1)
            mode, _, pinned = metadata.decode().split()
            if mode != '160000':
                continue
            child = source_path(repo, os.fsdecode(name))
            if child.is_symlink():
                record(child, 'submodule-link')
                continue
            if not (child / '.git').exists():
                continue
            if git('rev-parse', 'HEAD', cwd=child).decode().strip() != pinned:
                record(child, 'submodule-revision')
            try:
                changed = git('diff', '--no-ext-diff', '--no-textconv', '--ignore-submodules=all',
                              '--name-only', '-z', pinned, '--', cwd=child)
            except Failure:
                # Unpatched, shallow auxiliary repos need not contain the pinned
                # object. Report this gap; do not fetch or include their files.
                record(child, 'submodule-baseline-unavailable')
                continue
            changed += git('ls-files', '-z', '--others', '--exclude-standard', cwd=child)
            for name in sorted(set(changed.split(b'\0')) - {b''}):
                record(source_path(child, os.fsdecode(name)))
            visit(child, pinned)

    for source in json.loads(lock.read_text()):
        repo = work / source['name']
        if repo in targets.values():
            visit(repo, source['commit'])
    return result


def unowned_changes(targets, bases, groups, root=None, work=None):
    owners = {(str(targets[g['component']]), e['path']) for g in groups for e in g['files']}
    result = []
    seen = set()
    roots = set(targets.values())
    for component, tree in targets.items():
        if tree in seen:
            continue
        seen.add(tree)
        known = {p.relative_to(bases[component]).as_posix()
                 for p in bases[component].rglob('*') if p.is_file() or p.is_symlink()}
        for name in sorted(set(candidates(tree)) | {n for n in known if not ignored(n)}):
            safe_path(name)
            if any(other != tree and other in (tree / name).parents for other in roots):
                continue
            if (str(tree), name) in owners:
                continue
            path = source_path(tree, name)
            if path.is_dir() and not path.is_symlink():
                continue
            current = read_file(path)
            expected = read_file(source_path(bases[component], name))
            if current[0] != expected[0] or git_mode(current[1]) != git_mode(expected[1]):
                result.append({'component': component, 'path': name})
    if root is not None:
        result.extend(e for e in submodule_changes(root, work, groups) if e not in result)
    return sorted(result, key=lambda e: (e['component'], e['path']))


def diff_file(name, before, after):
    """One isolated Git diff per file keeps unrelated blocks byte-stable."""
    with tempfile.TemporaryDirectory(prefix='patchtool-diff-') as tmp:
        tree = Path(tmp)
        git('init', '-q', cwd=tree)
        path = source_path(tree, name)
        if before[0] is not None:
            put_file(path, *before)
        git('add', '--all', cwd=tree)
        if path.exists() or path.is_symlink():
            path.unlink()
        if after[0] is not None:
            put_file(path, *after)
            if before[0] is None:
                git('add', '--intent-to-add', '--', name, cwd=tree)
        return git('-c', 'core.quotePath=true', '-c', 'core.fileMode=true',
                   'diff', '--no-ext-diff', '--no-textconv', '--no-renames',
                   '--binary', '--no-color', '--full-index', '--abbrev=40',
                   '--diff-algorithm=myers', '--no-indent-heuristic', '--src-prefix=a/', '--dst-prefix=b/', '--unified=3', '--', name, cwd=tree)


def export_tree(root, work, out, groups, bases, components=None, adds=()):
    if out.exists() or out.is_symlink():
        raise Failure('Output already exists; refusing to overwrite')
    if out.resolve().is_relative_to((root / 'patches').resolve()):
        raise Failure('Use a separate output directory before --write')
    if out.resolve().is_relative_to(work.resolve()) and not out.resolve().is_relative_to((work / 'runs').resolve()):
        raise Failure('Output must not be inside development sources')
    selected = set(components or [g['component'] for g in groups])
    if selected - {g['component'] for g in groups}:
        raise Failure('Unknown selected component')
    additions = {}
    for value in adds:
        # Component-qualified paths disambiguate the shared HackiOS directory.
        component, sep, name = value.partition(':')
        if not sep and len(selected) == 1:
            component, name = next(iter(selected)), value
        elif not sep or component not in selected:
            raise Failure('Use --add COMPONENT:PATH, or select exactly one component')
        additions.setdefault(component, set()).add(safe_path(name))
    targets = paths_for(work)
    report = {'unowned': unowned_changes(targets, bases, groups, root, work), 'deleted': [], 'added': []}
    # Prepare the public reference separately; bases must stay unpatched for diffing.
    with tempfile.TemporaryDirectory(prefix='patchtool-reference-') as tmp:
        reference = {}
        for group in groups:
            c = group['component']
            reference[c] = Path(tmp) / c
            reference[c].mkdir()
            for entry in group['files']:
                data, mode = read_file(source_path(bases[c], entry['path']))
                if data is not None:
                    put_file(source_path(reference[c], entry['path']), data, mode)
        apply_patches(root, reference, groups)
        generated, patches = [], {}
        for group in groups:
            c = group['component']
            if c not in selected:
                continue
            names = {e['path'] for e in group['files']}
            extra = additions.get(c, set())
            all_owners = {(str(targets[g['component']]), e['path']) for g in groups if g['component'] != c for e in g['files']}
            if any((str(targets[c]), name) in all_owners for name in extra):
                raise Failure('Added path belongs to another component')
            entries, blocks = [], []
            for name in sorted(names | extra):
                path = source_path(targets[c], name)
                data, mode = read_file(path)
                if name in extra and data is None:
                    raise Failure('Added source missing')
                public, _ = read_file(source_path(reference[c], name))
                data = normalized(c, name, data, public)
                before = read_file(source_path(bases[c], name))
                # Old public baseline content appears in removed/context lines too.
                if before[0] is not None:
                    require_public(before[0])
                block = diff_file(name, before, (data, mode))
                blocks.append(block)
                entries.append({'path': name, 'sha256': digest(data), 'mode': mode})
                if data is None:
                    report['deleted'].append({'component': c, 'path': name})
                if name in extra:
                    report['added'].append({'component': c, 'path': name})
            generated.append({'component': c, 'base': group['base'], 'files': entries})
            patches[c + '.patch'] = b''.join(blocks)
        manifest = (json.dumps(generated, ensure_ascii=False, indent=2) + '\n').encode()
        summary = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
        # Validate the complete output before creating any deliverable.
        for data in [*patches.values(), manifest, summary]:
            require_public(data)
        out.mkdir(parents=True)
        for name, data in patches.items():
            (out / name).write_bytes(data)
        (out / 'source-manifest.json').write_bytes(manifest)
        (out / 'report.json').write_bytes(summary)
    return report


def verify_manifest(targets, groups):
    errors = []
    for group in groups:
        for entry in group['files']:
            actual, mode = read_file(source_path(targets[group['component']], entry['path']))
            if digest(actual) != entry['sha256'] or mode != entry['mode']:
                errors.append(group['component'] + '/' + entry['path'] + ': hash/mode mismatch')
    if errors:
        raise Failure('\n'.join(errors[:49]))


def replay_tree(root, tree, groups, bases, patch_dir=None):
    targets = paths_for(tree)
    verify_manifest(targets, groups)
    # Perform --check and actual application on the reconstructed baseline. The
    # supplied prepare output already has port patches; do not apply them twice.
    apply_patches(root, bases, groups, patch_dir)
    verify_manifest(bases, groups)
    extra = unowned_changes(targets, bases, groups, root, tree)
    # prepare.py deliberately adds this single packaged service file.
    service = root / 'system/userland-wifi/com.redwood.wifi.plist'
    extra = [e for e in extra if not (e['component'] == 'hackios-kernel' and
             e['path'] == 'userland/com.redwood.wifi.plist' and service.exists() and
             read_file(targets[e['component']] / e['path'])[0] == service.read_bytes())]
    if extra:
        raise Failure('\n'.join(e['component'] + '/' + e['path'] + ': unexpected file' for e in extra[:49]))


def scan_paths(root, paths):
    if not paths:
        paths = [root / os.fsdecode(n) for n in git('ls-files', '-z', cwd=root).split(b'\0') if n]
        paths += list((root / 'patches').glob('*.patch'))
    files = set()
    for p in paths:
        if p.is_dir() and not p.is_symlink():
            files.update(f for f in p.rglob('*') if f.is_file() and not f.is_symlink() and '.git' not in f.parts)
        elif p.is_file() and not p.is_symlink():
            files.add(p)
        else:
            raise Failure('Scan path missing or symlink refused')
    errors = 0
    for path in sorted(files):
        try:
            label = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            label = path.name
        # Sanitize filenames as well as matching lines.
        if findings(label.encode()):
            label = '<redacted-filename>'
        for line, severity, category in findings(path.read_bytes()):
            print(f'{label}:{line} {severity}:{category}')
            errors += severity == 'error'
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    ex = sub.add_parser('export')
    ex.add_argument('--out', type=Path, required=True)
    ex.add_argument('--component', action='append')
    ex.add_argument('--add', action='append', default=[], metavar='COMPONENT:PATH')
    ex.add_argument('--write', action='store_true', help='also replace selected release patches and manifest')
    rp = sub.add_parser('replay')
    rp.add_argument('--tree', type=Path, required=True)
    rp.add_argument('--patch-dir', type=Path, help='export directory containing patches and manifest')
    sc = sub.add_parser('scan')
    sc.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'scan':
            return scan_paths(ROOT, args.paths)
        groups = load_groups(ROOT)
        if args.command == 'export':
            if args.out.resolve().is_relative_to((ROOT / 'patches').resolve()):
                raise Failure('Use a separate output directory before --write')
            with baseline(ROOT, ROOT / 'work') as bases:
                report = export_tree(ROOT, ROOT / 'work', args.out, groups, bases, args.component, args.add)
            if args.write:
                exported = json.loads((args.out / 'source-manifest.json').read_text())
                by_name = {g['component']: g for g in exported}
                for name in by_name:
                    shutil.copyfile(args.out / (name + '.patch'), ROOT / 'patches' / (name + '.patch'))
                (ROOT / 'source-manifest.json').write_text(json.dumps(
                    [by_name.get(g['component'], g) for g in groups], ensure_ascii=False, indent=2) + '\n')
            print('Export complete; unowned:', len(report['unowned']), 'deleted:', len(report['deleted']))
        else:
            if args.tree.resolve() == (ROOT / 'work').resolve():
                raise Failure('Replay requires a separate prepared tree')
            if args.patch_dir:
                groups = json.loads((args.patch_dir / 'source-manifest.json').read_text())
            with baseline(ROOT, args.tree) as bases:
                replay_tree(ROOT, args.tree, groups, bases, args.patch_dir)
            print('Replay passed: patches, source hashes, modes and unexpected files checked.')
        return 0
    except (Failure, OSError, ValueError, KeyError) as error:
        # Only Failure messages are authored here; OS/parser errors can leak paths.
        message = str(error) if isinstance(error, Failure) else 'Invalid or unavailable input'
        print('\n'.join(message.splitlines()[:50]))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
