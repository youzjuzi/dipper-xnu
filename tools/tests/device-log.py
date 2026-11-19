#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 yanei
"""Read-only live log capture and orderly stop helper for a running xnuloader session."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

TERMINAL_RESULTS = {'returned', 'hung', 'not-started'}


def result_head(result):
    return result.split()[0] if result else ''


def is_terminal_result(result):
    return result_head(result) in TERMINAL_RESULTS


def run_fastboot(fastboot_bin, serial, args, timeout=10.0):
    cmd = [fastboot_bin]
    if serial:
        cmd.extend(['-s', serial])
    cmd.extend(args)
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


def parse_getvar(output, name):
    pattern = re.compile(rf'(?im)^\s*(?:\(bootloader\)\s*)?{re.escape(name)}\s*:\s*(.*?)\s*$')
    matches = pattern.findall(output)
    return matches[-1].strip() if matches else ''


def get_var(fastboot_bin, serial, name, timeout=5.0):
    proc = run_fastboot(fastboot_bin, serial, ['getvar', name], timeout=timeout)
    combined = (proc.stdout or '') + '\n' + (proc.stderr or '')
    return proc.returncode, parse_getvar(combined, name), combined.strip()


def require_xnuloader(fastboot_bin, serial):
    rc, product, raw = get_var(fastboot_bin, serial, 'product')
    if rc != 0 or product != 'xnuloader':
        raise RuntimeError(
            f'Refusing to continue: expected fastboot product=xnuloader for {serial!r}, '
            f'got rc={rc} product={product!r} ({raw})'
        )


def atomic_write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def compute_log_delta(prev_text, new_text):
    """Return newly appended log text, handling loader ring-buffer wrap cleanly."""
    if not prev_text:
        return new_text
    if new_text == prev_text:
        return ''
    if new_text.startswith(prev_text):
        return new_text[len(prev_text):]
    prev_lines = prev_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    for window_len in (8, 4, 2, 1):
        if len(prev_lines) < window_len:
            continue
        anchor = prev_lines[-window_len:]
        for idx in range(len(new_lines) - window_len, -1, -1):
            if new_lines[idx:idx + window_len] == anchor:
                return ''.join(new_lines[idx + window_len:])
    return '\n--- [log snapshot shifted] ---\n' + new_text


def fetch_log_bytes(fastboot_bin, serial, work_dir, live_oem=True, timeout=10.0):
    if live_oem:
        proc = run_fastboot(fastboot_bin, serial, ['oem', 'log'], timeout=timeout)
        if proc.returncode != 0:
            combined = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
            raise RuntimeError(f'oem log failed ({proc.returncode}): {combined}')
    fd, tmp_name = tempfile.mkstemp(prefix='.staged-', dir=str(work_dir))
    os.close(fd)
    staged_path = Path(tmp_name)
    try:
        proc = run_fastboot(fastboot_bin, serial, ['get_staged', str(staged_path)], timeout=timeout)
        if proc.returncode != 0:
            combined = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
            raise RuntimeError(f'get_staged failed ({proc.returncode}): {combined}')
        return staged_path.read_bytes()
    finally:
        staged_path.unlink(missing_ok=True)


def capture_once(fastboot_bin, serial, out_path, live_oem=True, timeout=10.0):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _, result, _ = get_var(fastboot_bin, serial, 'result', timeout=min(timeout, 5.0))
    # Once returned/hung/not-started, oem log recomposes from loader ring only and would
    # overwrite the full post-return kernel log already staged by xnuloader.
    use_oem = live_oem and not is_terminal_result(result)
    raw = fetch_log_bytes(fastboot_bin, serial, out_path.parent, live_oem=use_oem, timeout=timeout)
    atomic_write_bytes(out_path, raw)
    return result, raw


def emit_delta(delta_text, stream_path, to_stdout):
    if not delta_text:
        return
    if stream_path is not None:
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        with stream_path.open('a', encoding='utf-8') as stream:
            stream.write(delta_text)
    if to_stdout:
        sys.stdout.write(delta_text)
        sys.stdout.flush()


def cmd_snapshot(args):
    require_xnuloader(args.fastboot, args.serial)
    result, raw = capture_once(args.fastboot, args.serial, args.out, live_oem=True, timeout=args.timeout)
    print(f'snapshot saved: {args.out} ({len(raw)} bytes, result={result or "unknown"})')
    return 0


def cmd_watch(args):
    require_xnuloader(args.fastboot, args.serial)
    deadline = time.monotonic() + args.max_seconds if args.max_seconds > 0 else None
    prev_text = ''
    if args.stream and args.stream.exists():
        args.stream.unlink()

    while True:
        try:
            require_xnuloader(args.fastboot, args.serial)
            result, raw = capture_once(args.fastboot, args.serial, args.out, live_oem=True, timeout=args.timeout)
            text = raw.decode('utf-8', errors='replace')
            delta = compute_log_delta(prev_text, text)
            emit_delta(delta, args.stream, not args.quiet)
            prev_text = text
            if is_terminal_result(result):
                print(f'\n[device-log] session ended: result={result}, saved={args.out}', file=sys.stderr)
                return 0
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f'[device-log] poll warning: {exc}', file=sys.stderr)

        if deadline is not None and time.monotonic() >= deadline:
            print(f'[device-log] reached --max-seconds={args.max_seconds}; latest snapshot at {args.out}', file=sys.stderr)
            return 0
        time.sleep(args.interval)


def cmd_stop(args):
    require_xnuloader(args.fastboot, args.serial)
    proc = run_fastboot(args.fastboot, args.serial, ['oem', 'stop'], timeout=args.timeout)
    if proc.returncode != 0:
        combined = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
        raise RuntimeError(f'oem stop failed ({proc.returncode}): {combined}')

    deadline = time.monotonic() + args.wait_timeout
    result = ''
    while time.monotonic() < deadline:
        rc, result, _ = get_var(args.fastboot, args.serial, 'result', timeout=min(args.timeout, 5.0))
        if rc == 0 and is_terminal_result(result):
            break
        time.sleep(args.poll_interval)

    _, raw = capture_once(args.fastboot, args.serial, args.out, live_oem=True, timeout=args.timeout)
    print(f'orderly stop complete: result={result or "unknown"}, saved={args.out} ({len(raw)} bytes)')
    if not is_terminal_result(result):
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', default='xnuloader', help='fastboot serial (default: xnuloader)')
    parser.add_argument('--fastboot', default=os.environ.get('FASTBOOT', 'fastboot'),
                        help='fastboot executable path (default: $FASTBOOT or fastboot)')
    parser.add_argument('--timeout', type=float, default=10.0, help='per-command USB timeout in seconds')
    sub = parser.add_subparsers(dest='command', required=True)

    p_snap = sub.add_parser('snapshot', help='capture one full live or post-return log snapshot')
    p_snap.add_argument('--out', type=Path, required=True, help='output path for staged log')

    p_watch = sub.add_parser('watch', help='poll oem log continuously until the kernel returns')
    p_watch.add_argument('--out', type=Path, required=True, help='output path updated atomically with latest full snapshot')
    p_watch.add_argument('--stream', type=Path, help='optional path receiving appended incremental log text')
    p_watch.add_argument('--interval', type=float, default=5.0, help='poll interval in seconds (default: 5.0)')
    p_watch.add_argument('--max-seconds', type=float, default=0.0, help='optional watch time limit (0 = until return)')
    p_watch.add_argument('--quiet', action='store_true', help='do not mirror incremental lines to stdout')

    p_stop = sub.add_parser('stop', help='send oem stop, wait for kernel return, and capture final log')
    p_stop.add_argument('--out', type=Path, required=True, help='output path for final post-return log')
    p_stop.add_argument('--wait-timeout', type=float, default=25.0, help='seconds to wait for return (default: 25)')
    p_stop.add_argument('--poll-interval', type=float, default=1.0, help='result poll interval in seconds')
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command == 'snapshot':
            return cmd_snapshot(args)
        if args.command == 'watch':
            return cmd_watch(args)
        if args.command == 'stop':
            return cmd_stop(args)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
