#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 yanei
"""Inspect workspace status, diff unexported work changes, check repo hygiene, and prune runs."""
import argparse
import datetime
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]


def load_patchtool():
    spec = importlib.util.spec_from_file_location('patchtool', ROOT / 'tools/prepare/patchtool.py')
    mod = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prev
    return mod


def sha256_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run_git(*args, cwd=ROOT, check=True):
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=check)


def detect_theos():
    env = os.environ.get('THEOS')
    candidates = []
    if env:
        candidates.append(('env:THEOS', Path(env)))
    candidates.append(('local/theos', ROOT / 'local/theos'))
    candidates.append(('../dependencies/theos', ROOT.parent / 'dependencies/theos'))
    for label, path in candidates:
        ld = path / 'toolchain/linux/iphone/bin/ld'
        sdk = path / 'sdks/iPhoneOS16.5.sdk'
        if ld.is_file() and os.access(ld, os.X_OK):
            return {'label': label, 'ready': True, 'sdk_present': sdk.is_dir()}
    if env:
        return {'label': 'env:THEOS (invalid)', 'ready': False, 'sdk_present': False}
    return {'label': 'not found', 'ready': False, 'sdk_present': False}


def verify_sha256sums(repo_root):
    sums_path = repo_root / 'SHA256SUMS'
    if not sums_path.is_file():
        return {'ok': False, 'checked': 0, 'mismatches': ['SHA256SUMS missing'], 'entries': []}
    entries = []
    mismatches = []
    for raw in sums_path.read_text(encoding='utf-8').splitlines():
        if not raw.strip():
            continue
        if '  ' not in raw:
            mismatches.append(f'invalid line: {raw[:40]}')
            continue
        expected, rel = raw.split('  ', 1)
        entries.append((expected, rel))
        target = repo_root / rel
        if not target.is_file():
            mismatches.append(f'missing: {rel}')
        elif sha256_file(target) != expected:
            mismatches.append(f'mismatch: {rel}')
    return {'ok': not mismatches, 'checked': len(entries), 'mismatches': mismatches, 'entries': entries}


def public_loader_reference(pt, work):
    """Reconstruct only public xnuloader/loader.c quickly from pinned hackios commit + patch."""
    lock = json.loads((ROOT / 'upstream.lock.json').read_text(encoding='utf-8'))
    commit = next(s['commit'] for s in lock if s['name'] == 'hackios')
    repo = work / 'hackios'
    if not (repo / '.git').exists():
        return None
    raw = pt.git('show', f'{commit}:xnuloader/loader.c', cwd=repo)
    patch_bytes = (ROOT / 'patches/hackios-kernel.patch').read_bytes()
    marker = b'diff --git a/xnuloader/loader.c b/xnuloader/loader.c'
    if marker not in patch_bytes:
        return None
    idx = patch_bytes.index(marker)
    next_idx = patch_bytes.find(b'\ndiff --git ', idx + len(marker))
    hunk = patch_bytes[idx:] if next_idx == -1 else patch_bytes[idx:next_idx + 1]
    with tempfile.TemporaryDirectory(prefix='loader-ref-') as tmp:
        tdir = Path(tmp)
        pt.git('init', '-q', cwd=tdir)
        pt.put_file(tdir / 'xnuloader/loader.c', raw, '0o644')
        pfile = tdir / 'loader.patch'
        pfile.write_bytes(hunk)
        pt.git('apply', str(pfile), cwd=tdir)
        return (tdir / 'xnuloader/loader.c').read_bytes()


def is_benign_unowned(pt, work, entry):
    comp, path = entry['component'], entry['path']
    kind = entry.get('kind', '')
    if comp == 'edk2-sdm845':
        if path in {'DarwinBootPkg', 'UniXNUPkg', 'XnuLoaderPkg'} and (work / 'edk2' / path).is_symlink():
            return True
        if kind == 'submodule-revision;submodule-baseline-unavailable':
            return True
        if path.startswith('tools/Installer/'):
            return True
    if comp == 'hackios-kernel' and path == 'userland/com.redwood.wifi.plist':
        svc = ROOT / 'system/userland-wifi/com.redwood.wifi.plist'
        tgt = work / 'hackios' / path
        if svc.is_file() and tgt.is_file() and tgt.read_bytes() == svc.read_bytes():
            return True
    return False


def inspect_work_manifest(pt, work):
    groups = pt.load_groups(ROOT)
    targets = pt.paths_for(work)
    modified = []
    loader_state = 'missing'
    for group in groups:
        comp = group['component']
        tree = targets[comp]
        for entry in group['files']:
            rel = entry['path']
            fpath = tree / rel
            actual_data, actual_mode = pt.read_file(fpath)
            actual_digest = pt.digest(actual_data)
            if actual_digest == entry['sha256'] and actual_mode == entry['mode']:
                if comp == 'hackios-kernel' and rel == 'xnuloader/loader.c':
                    loader_state = 'exact-public-placeholder'
                continue
            if comp == 'hackios-kernel' and rel == 'xnuloader/loader.c' and actual_data is not None:
                pub = public_loader_reference(pt, work)
                if pub is not None:
                    try:
                        norm = pt.normalized(comp, rel, actual_data, pub)
                        if pt.digest(norm) == entry['sha256'] and actual_mode == entry['mode']:
                            loader_state = 'local-identity-configured (normalized OK)'
                            continue
                    except pt.Failure:
                        pass
                loader_state = 'modified-beyond-identity'
            if entry['sha256'] is None:
                kind = 'expected-deleted-but-exists'
            elif actual_data is None:
                kind = 'missing'
            elif actual_digest != entry['sha256']:
                kind = 'content-diff'
            else:
                kind = 'mode-diff'
            modified.append({'component': comp, 'path': rel, 'kind': kind})
    return modified, loader_state


def collect_artifacts(work):
    k_src = work / 'hackios/xnu-src/xnu-8796.121.2'
    items = {
        'kernel_macho': k_src / 'BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837',
        'loader_efi': work / 'hackios/xnuloader/loader.efi',
        'boot_dipper_img': work / 'edk2/boot-dipper.img',
        'root_apfs': work / 'hackios/userland/root.apfs',
        'flashboot_apfs': work / 'hackios/userland/flashboot.apfs',
        'darwin_img': work / 'images/darwin.img',
    }
    res = {}
    for name, path in items.items():
        if path.is_file():
            st = path.stat()
            res[name] = {
                'present': True,
                'size_mib': round(st.st_size / (1024 * 1024), 1),
                'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'sha256_prefix': sha256_file(path)[:12],
            }
        else:
            res[name] = {'present': False}
    fw = {}
    for name in ('fw-gpu', 'fw-wifi', 'fw-bt', 'fw-audio', 'apps', 'apps-off'):
        d = work / 'hackios' / name
        if d.is_dir():
            count = sum(1 for _ in d.iterdir())
            fw[name] = count
        else:
            fw[name] = None
    res['local_dirs'] = fw
    return res


def cmd_status(args):
    pt = load_patchtool()
    branch = run_git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
    head = run_git('rev-parse', '--short', 'HEAD').stdout.strip()
    dirty = [line for line in run_git('status', '--short').stdout.splitlines() if line.strip()]
    sums = verify_sha256sums(ROOT)
    theos = detect_theos()
    work = ROOT / 'work'
    report = {
        'branch': branch,
        'head': head,
        'git_dirty': dirty,
        'sha256sums': {'ok': sums['ok'], 'checked': sums['checked'], 'mismatches': sums['mismatches']},
        'theos': theos,
        'work_present': work.is_dir(),
    }

    if work.is_dir():
        modified, loader_state = inspect_work_manifest(pt, work)
        report['loader_state'] = loader_state
        report['manifest_modified'] = modified
        if args.deep:
            groups = pt.load_groups(ROOT)
            targets = pt.paths_for(work)
            with pt.baseline(ROOT, work) as bases:
                unowned = pt.unowned_changes(targets, bases, groups, ROOT, work)
            service = ROOT / 'system/userland-wifi/com.redwood.wifi.plist'
            real_unowned = []
            benign_unowned = []
            for entry in unowned:
                if entry['component'] == 'hackios-kernel' and entry['path'] == 'userland/com.redwood.wifi.plist' and service.exists():
                    tgt = targets[entry['component']] / entry['path']
                    if tgt.is_file() and tgt.read_bytes() == service.read_bytes():
                        benign_unowned.append(entry)
                        continue
                if is_benign_unowned(pt, work, entry):
                    benign_unowned.append(entry)
                else:
                    real_unowned.append(entry)
            report['unowned_source'] = real_unowned
            report['unowned_benign_count'] = len(benign_unowned)
            if args.all_unowned:
                report['unowned_benign'] = benign_unowned
        report['artifacts'] = collect_artifacts(work)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f'Git: branch={branch} head={head} tracked_changes={len(dirty)}')
    for line in dirty[:20]:
        print(f'  {line}')
    if sums['ok']:
        print(f"SHA256SUMS: OK ({sums['checked']} files)")
    else:
        print(f"SHA256SUMS: FAIL ({len(sums['mismatches'])} issues)")
        for item in sums['mismatches'][:20]:
            print(f'  ! {item}')
    print(f"THEOS: {theos['label']} (ready={theos['ready']}, sdk16.5={theos['sdk_present']})")

    if not work.is_dir():
        print('work/: not present (run tools/prepare/prepare.py --prepare to initialize)')
        return 0

    print(f"work/ loader.c: {report['loader_state']}")
    mods = report['manifest_modified']
    print(f'work/ manifest diffs (excluding normalized loader.c): {len(mods)}')
    for entry in mods:
        print(f"  * {entry['component']}:{entry['path']} ({entry['kind']})")

    if args.deep:
        real_u = report['unowned_source']
        print(f'work/ unowned source changes: {len(real_u)}')
        for entry in real_u:
            kind = f" ({entry['kind']})" if 'kind' in entry else ''
            print(f"  + {entry['component']}:{entry['path']}{kind}")
        if report['unowned_benign_count']:
            print(f"work/ benign build-links/aux-submodules hidden: {report['unowned_benign_count']} (use --all-unowned to list)")
        if args.all_unowned:
            for entry in report.get('unowned_benign', []):
                kind = f" ({entry['kind']})" if 'kind' in entry else ''
                print(f"  ~ {entry['component']}:{entry['path']}{kind}")
    else:
        print('work/ unowned scan: skipped (pass --deep to scan outside source-manifest.json)')

    arts = report['artifacts']
    print('Build artifacts:')
    for key in ('kernel_macho', 'loader_efi', 'boot_dipper_img', 'root_apfs', 'flashboot_apfs', 'darwin_img'):
        info = arts[key]
        if info['present']:
            print(f"  {key:16s}: {info['size_mib']:6.1f} MiB  {info['mtime']}  sha256:{info['sha256_prefix']}...")
        else:
            print(f'  {key:16s}: missing')
    dirs_summary = ', '.join(
        f'{k}({v})' if v is not None else f'{k}(none)' for k, v in arts['local_dirs'].items()
    )
    print(f'work/hackios local dirs: {dirs_summary}')

    if mods or report.get('unowned_source'):
        print('WARNING: work/ contains unexported changes; export or back up before switching tasks/branches.')
    return 0


def cmd_diff(args):
    pt = load_patchtool()
    work = ROOT / 'work'
    if not work.is_dir():
        print('work/ is missing; nothing to diff.', file=sys.stderr)
        return 1
    groups = pt.load_groups(ROOT)
    targets = pt.paths_for(work)
    selected_comps = set(args.component) if args.component else None
    filters = set(args.paths) if args.paths else None

    def wanted(comp, rel):
        if selected_comps and comp not in selected_comps:
            return False
        if filters and rel not in filters and f'{comp}:{rel}' not in filters:
            return False
        return True

    printed = 0
    with pt.baseline(ROOT, work) as bases:
        with tempfile.TemporaryDirectory(prefix='status-diff-') as tmp:
            ref = {}
            for group in groups:
                c = group['component']
                ref[c] = Path(tmp) / c
                ref[c].mkdir()
                for entry in group['files']:
                    data, mode = pt.read_file(pt.source_path(bases[c], entry['path']))
                    if data is not None:
                        pt.put_file(pt.source_path(ref[c], entry['path']), data, mode)
            pt.apply_patches(ROOT, ref, groups)

            for group in groups:
                c = group['component']
                for entry in group['files']:
                    rel = entry['path']
                    if not wanted(c, rel):
                        continue
                    cur_data, cur_mode = pt.read_file(pt.source_path(targets[c], rel))
                    pub_data, pub_mode = pt.read_file(pt.source_path(ref[c], rel))
                    if c == 'hackios-kernel' and rel == 'xnuloader/loader.c' and cur_data is not None:
                        try:
                            cur_data = pt.normalized(c, rel, cur_data, pub_data)
                        except pt.Failure:
                            pass
                    if pt.digest(cur_data) == entry['sha256'] and cur_mode == entry['mode']:
                        continue
                    a_lines = (pub_data or b'').decode('utf-8', errors='replace').splitlines(keepends=True)
                    b_lines = (cur_data or b'').decode('utf-8', errors='replace').splitlines(keepends=True)
                    diff_text = ''.join(difflib.unified_diff(
                        a_lines, b_lines, fromfile=f'public/{c}/{rel}', tofile=f'work/{c}/{rel}'
                    ))
                    if any(sev == 'error' for _, sev, _ in pt.findings(diff_text.encode('utf-8'))):
                        print(f'[REDACTED] {c}:{rel} matched a privacy error pattern; run patchtool.py scan.')
                    else:
                        print(diff_text, end='' if diff_text.endswith('\n') else '\n')
                    printed += 1

            for entry in pt.unowned_changes(targets, bases, groups, ROOT, work):
                c, rel = entry['component'], entry['path']
                if is_benign_unowned(pt, work, entry) or not wanted(c, rel):
                    continue
                if 'kind' in entry:
                    print(f"[UNOWNED] {c}:{rel} ({entry['kind']})")
                    printed += 1
                    continue
                cur_data, _ = pt.read_file(pt.source_path(targets[c], rel))
                base_data, _ = pt.read_file(pt.source_path(bases[c], rel))
                a_lines = (base_data or b'').decode('utf-8', errors='replace').splitlines(keepends=True)
                b_lines = (cur_data or b'').decode('utf-8', errors='replace').splitlines(keepends=True)
                diff_text = ''.join(difflib.unified_diff(
                    a_lines, b_lines, fromfile=f'baseline/{c}/{rel}', tofile=f'work/{c}/{rel}'
                ))
                if any(sev == 'error' for _, sev, _ in pt.findings(diff_text.encode('utf-8'))):
                    print(f'[REDACTED] unowned {c}:{rel} matched a privacy error pattern; run patchtool.py scan.')
                else:
                    print(diff_text, end='' if diff_text.endswith('\n') else '\n')
                printed += 1

    if printed == 0:
        print('No unexported source differences (excluding normalized local loader identity).')
    return 0


def cmd_check(args):
    pt = load_patchtool()
    repo_root = args.root.resolve()
    staged = [n for n in pt.git('diff', '--cached', '--name-only', cwd=repo_root).decode('utf-8').splitlines() if n]
    bad_staged = [
        p for p in staged
        if p.startswith(('local/', 'work/', 'experiments/'))
        or '__pycache__' in Path(p).parts
        or p.endswith('.pyc')
    ]
    if bad_staged:
        print('Refused staged paths:', ', '.join(bad_staged), file=sys.stderr)
        return 1

    tracked = sorted(
        n for n in pt.git('ls-files', '-z', cwd=repo_root).decode('utf-8').split('\0')
        if n and n != 'SHA256SUMS'
    )
    bad_tracked = [p for p in tracked if p.startswith(('local/', 'work/', 'experiments/'))]
    if bad_tracked:
        print('Forbidden tracked paths:', ', '.join(bad_tracked), file=sys.stderr)
        return 1

    sums_path = repo_root / 'SHA256SUMS'
    if args.refresh_sums:
        existing_order = []
        if sums_path.is_file():
            for raw in sums_path.read_text(encoding='utf-8').splitlines():
                if '  ' in raw:
                    _, rel = raw.split('  ', 1)
                    if rel in tracked and rel not in existing_order:
                        existing_order.append(rel)
        tracked_set = set(existing_order)
        ordered = existing_order + [p for p in tracked if p not in tracked_set]
        lines = [f'{sha256_file(repo_root / p)}  {p}\n' for p in ordered]
        sums_path.write_text(''.join(lines), encoding='utf-8')

    sums = verify_sha256sums(repo_root)
    if not sums['ok']:
        print('SHA256SUMS check failed:', '; '.join(sums['mismatches'][:10]), file=sys.stderr)
        return 1

    listed = {rel for _, rel in sums['entries']}
    missing_from_sums = sorted(set(tracked) - listed)
    extra_in_sums = sorted(listed - set(tracked))
    if missing_from_sums or extra_in_sums:
        if missing_from_sums:
            print('Tracked files missing from SHA256SUMS:', ', '.join(missing_from_sums[:20]), file=sys.stderr)
        if extra_in_sums:
            print('Untracked files listed in SHA256SUMS:', ', '.join(extra_in_sums[:20]), file=sys.stderr)
        return 1

    if pt.scan_paths(repo_root, []) != 0:
        print('Privacy scan reported error-level findings.', file=sys.stderr)
        return 1

    diff_check = subprocess.run(['git', 'diff', '--check'], cwd=repo_root, text=True, capture_output=True)
    if diff_check.returncode != 0:
        print('git diff --check failed:\n' + diff_check.stdout, file=sys.stderr)
        return 1

    print(f"Repo check PASS: {sums['checked']} checksums OK, privacy scan 0 errors, git diff --check clean.")
    return 0


def _clear_ro_onerror(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IRWXU)
        func(path)
    except OSError:
        raise


def cmd_prune_runs(args):
    runs_dir = args.runs_dir.resolve()
    if not runs_dir.is_dir():
        print(f'Runs directory not found: {runs_dir}', file=sys.stderr)
        return 1

    replay_dirs = []
    for cur, dirs, _ in os.walk(runs_dir):
        cur_p = Path(cur)
        for d in list(dirs):
            p = cur_p / d
            if not p.is_symlink() and (d == 'replay-tree' or d.startswith('replay-tree-')):
                replay_dirs.append(p)
                dirs.remove(d)

    delete_files = []
    delete_dirs = list(replay_dirs)

    for rdir in replay_dirs:
        for p in rdir.rglob('*'):
            if p.is_file() and not p.is_symlink():
                delete_files.append((p.stat().st_size, p))

    build_roots = []
    for cur, dirs, _ in os.walk(runs_dir):
        cur_p = Path(cur)
        for d in list(dirs):
            p = cur_p / d
            if p.is_symlink():
                continue
            if d == 'replay-tree' or d.startswith('replay-tree-'):
                dirs.remove(d)
                continue
            if d in {'obj', 'sym', 'dst'}:
                build_roots.append(p)
                dirs.remove(d)

    for broot in build_roots:
        in_sym_or_dst = broot.name in {'sym', 'dst'}
        for cur, dirs, files in os.walk(broot):
            cur_p = Path(cur)
            for d in list(dirs):
                if d.endswith('.dSYM'):
                    dsym_dir = cur_p / d
                    delete_dirs.append(dsym_dir)
                    for p in dsym_dir.rglob('*'):
                        if p.is_file() and not p.is_symlink():
                            delete_files.append((p.stat().st_size, p))
                    dirs.remove(d)
            for fname in files:
                fp = cur_p / fname
                if fp.is_symlink():
                    continue
                if fname in {'mach.development.bcm2837', 'kernel.macho'}:
                    continue
                is_intermediate = (
                    in_sym_or_dst
                    or fp.suffix in {'.o', '.cpo', '.d', '.a', '.tmp', '.bc'}
                    or '.unstripped' in fname
                )
                if is_intermediate:
                    delete_files.append((fp.stat().st_size, fp))

    deleted_set = {p for _, p in delete_files}
    deleted_dir_set = set(delete_dirs)

    def under_deleted_dir(path):
        return any(parent in deleted_dir_set for parent in path.parents)

    image_exts = {'.apfs', '.img', '.macho', '.efi'}
    by_size_dev = {}
    for p in runs_dir.rglob('*'):
        if p in deleted_set or under_deleted_dir(p):
            continue
        if p.is_symlink() or not p.is_file():
            continue
        if p.name.startswith('_pruned-'):
            continue
        if p.suffix not in image_exts and not p.name.startswith(('root.apfs', 'flashboot.apfs')):
            continue
        st = p.stat()
        if st.st_size < 1024 * 1024:
            continue
        by_size_dev.setdefault((st.st_size, st.st_dev), []).append((p, st))

    hardlink_plans = []
    saved_link_bytes = 0
    for (_sz, _dev), items in by_size_dev.items():
        if len(items) < 2:
            continue
        by_hash_mode = {}
        for p, st in items:
            key = (sha256_file(p), stat.S_IMODE(st.st_mode))
            by_hash_mode.setdefault(key, []).append((p, st))
        for _key, group in by_hash_mode.items():
            inodes = {st.st_ino for _, st in group}
            if len(inodes) < 2:
                continue
            group.sort(key=lambda item: (item[1].st_mtime, str(item[0])))
            master_path, master_st = group[0]
            seen_victim_inodes = {master_st.st_ino}
            for victim_path, victim_st in group[1:]:
                if victim_st.st_ino == master_st.st_ino:
                    continue
                hardlink_plans.append((master_path, victim_path, victim_st.st_size))
                if victim_st.st_ino not in seen_victim_inodes:
                    seen_victim_inodes.add(victim_st.st_ino)
                    saved_link_bytes += victim_st.st_size

    prune_bytes = sum(sz for sz, _ in delete_files)
    total_saved = prune_bytes + saved_link_bytes
    mode_tag = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'[{mode_tag}] runs dir: {runs_dir}')
    print(f'  replay-tree dirs to remove : {len(replay_dirs)}')
    print(f'  build/replay files to prune: {len(delete_files)} ({prune_bytes / (1024 ** 2):.1f} MiB)')
    print(f'  duplicate images to link   : {len(hardlink_plans)} ({saved_link_bytes / (1024 ** 2):.1f} MiB)')
    print(f'  estimated space reclaimed  : {total_saved / (1024 ** 2):.1f} MiB')

    if not args.apply:
        print('Dry-run only. Re-run with --apply to modify files.')
        return 0

    pruned_records = []
    for sz, fp in delete_files:
        if any(parent in deleted_dir_set for parent in fp.parents):
            continue
        if fp.exists():
            fp.unlink()
            pruned_records.append((sz, fp.relative_to(runs_dir).as_posix()))

    for d in sorted(delete_dirs, key=lambda p: len(p.parts), reverse=True):
        if d.exists():
            for p in d.rglob('*'):
                if p.is_file() and not p.is_symlink():
                    pruned_records.append((p.stat().st_size, p.relative_to(runs_dir).as_posix()))
            shutil.rmtree(d, onerror=_clear_ro_onerror)

    for broot in build_roots:
        if not broot.exists():
            continue
        for cur, dirs, files in os.walk(broot, topdown=False):
            if not dirs and not files:
                try:
                    Path(cur).rmdir()
                except OSError:
                    pass

    for idx, (master_path, victim_path, _sz) in enumerate(hardlink_plans):
        tmp_link = victim_path.with_name(f'.prune-link-{os.getpid()}-{idx}')
        try:
            os.link(master_path, tmp_link)
            os.replace(tmp_link, victim_path)
        finally:
            if tmp_link.exists():
                tmp_link.unlink()

    if pruned_records:
        tsv = runs_dir / f"_pruned-{datetime.date.today().strftime('%Y%m%d')}.tsv"
        with tsv.open('a', encoding='utf-8') as stream:
            for sz, rel in sorted(pruned_records, key=lambda x: x[1]):
                stream.write(f'{sz}\t{rel}\n')
        print(f'Appended {len(pruned_records)} records to {tsv.name}')

    print('Prune complete.')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    st = sub.add_parser('status', help='show git branch, SHA256SUMS, work/ diffs and build artifacts')
    st.add_argument('--deep', action='store_true', help='also scan work/ for unowned changes')
    st.add_argument('--all-unowned', action='store_true', help='show benign build links and auxiliary submodules too')
    st.add_argument('--json', action='store_true', help='output JSON report')

    df = sub.add_parser('diff', help='show unified diff of unexported changes in work/')
    df.add_argument('--component', action='append', help='filter by manifest component')
    df.add_argument('paths', nargs='*', help='optional relative paths or COMPONENT:PATH filters')

    ck = sub.add_parser('check', help='verify SHA256SUMS, privacy scan, staged paths and git diff --check')
    ck.add_argument('--refresh-sums', action='store_true', help='update SHA256SUMS from tracked files')
    ck.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)

    pr = sub.add_parser('prune-runs', help='prune build intermediates/replay trees and deduplicate images in runs/')
    pr.add_argument('--apply', action='store_true', help='apply deletions and hard-links (default is dry-run)')
    pr.add_argument('--runs-dir', type=Path, default=ROOT / 'work/runs', help='target runs directory')
    return parser


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    commands = {'status', 'diff', 'check', 'prune-runs'}
    if not raw or (raw[0] not in commands and raw[0] not in {'-h', '--help'}):
        raw = ['status', *raw]
    args = build_parser().parse_args(raw)
    if args.command == 'status':
        return cmd_status(args)
    if args.command == 'diff':
        return cmd_diff(args)
    if args.command == 'check':
        return cmd_check(args)
    if args.command == 'prune-runs':
        return cmd_prune_runs(args)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
