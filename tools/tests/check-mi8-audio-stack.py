#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Conservative ARM64 frame/call-graph budget for the native audio worker.

Input: the bsd/DEVELOPMENT object directory from the linked kernel build.
All mi8 objects are disassembled; local symbols are object-qualified. Direct
calls and tail branches count the complete caller frame (a conservative bound).
The bound covers these objects, not arbitrary XNU internals: external kernel
entry points are listed in the JSON, and the other 8 KiB is reserved for kernel
services, interrupts and preemption. This is not a proof of total kernel usage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def names(obj, text):
    return [obj + ':' + n for n in text.split()]


# Conservative callback unions, deliberately attached to EVERY indirect call
# in each object. These are the native tables installed by adsp_audio_handshake,
# afe_sequence, audio_amp_ops, mi8_audio_smmu_begin and tas2557_prepare[_tone].
# Host-only memory_ops are NULL in the native worker. IPCRTR port/service hooks
# are NULL in the APR raw-channel configuration; pump's receive is included.
TRANSPORT = names('mi8_rproc', 'audio_item svc_read svc_write32 audio_ring svc_sleep_us svc_now_us svc_log')
AMP = names('mi8_tas2557', 'mi8_tas2557_held mi8_tas2557_tick mi8_tas2557_stop mi8_tas2557_audible mi8_tas2557_tone_count')
# The separate clip table adds warmup/health and the mutex-protected cdev mute
# accessor. The latter is an external XNU boundary, listed explicitly below.
CLIP = names('mi8_tas2557', 'mi8_tas2557_clip_warmup mi8_tas2557_clip_audible mi8_tas2557_clip_clean')
SESSION = names('mi8_tas2557', 'mi8_tas_session_snapshot mi8_tas_session_wake mi8_tas_session_mute mi8_tas_session_zero mi8_tas_session_count mi8_tas_session_stop_request mi8_tas_session_join mi8_tas_session_held mi8_tas_session_fault')
CALLBACKS = {
    'mi8_glink': TRANSPORT + names('mi8_audio', 'receive'),
    'mi8_audio': names('mi8_rproc', 'audio_alive audio_fatal svc_now_us svc_sleep_us svc_log') + names('mi8_audio', 'native_pin_read native_pin_write') + AMP + CLIP + SESSION,
    'mi8_audio_pcm': names('mi8_audio', 'pcm_now pcm_sleep pcm_exchange pcm_send pcm_poll pcm_tell pcm_begin pcm_cache pcm_fault pcm_clear pcm_end') + AMP + CLIP + SESSION,
    'mi8_audio_smmu': names('mi8_audio_smmu', 'native_read native_write native_wait native_play_log native_allocate native_release native_cache native_table_read'),
    'mi8_tas2557': names('mi8_tas2557', 'native_read native_write native_now native_delay native_log'),
}
# commands() additionally dispatches the selected firmware validator/downloader.
EXTRA = {'mi8_tas2557:commands': names('mi8_tas2557', 'validate_command execute session_y_read'),
         'mi8_rproc:fs_dir_find': names('mi8_rproc', 'list_image_entry')}
# A nested ADSP/modem lookup must retain independent snapshots. This frame
# cannot be static. Its size is still included in every caller's budget.
ALLOW = {'mi8_rproc:item_find': '192-entry SMEM snapshot; concurrent and nested remote lookups require private storage'}


def parse(text, obj):
    parts = re.split(r'^(_[^\n]+):$', text, flags=re.M)
    out = {}
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        # Sum all constant decrements, even mutually exclusive paths. Include
        # register saves with pre-index writeback, not just sub sp. Never sum
        # negative adjustments as credits: epilogues cannot hide allocations.
        frame = 0
        for line in body.splitlines():
            m = re.search(r'\bsub\s+sp, sp, #(0x[\da-f]+|\d+)(?:, lsl #(\d+))?', line)
            if m:
                frame += int(m[1], 0) << int(m[2] or '0')
            m = re.search(r'\[sp, #-(0x[\da-f]+|\d+)\]!', line)
            if m:
                frame += int(m[1], 0)
            if re.search(r'\bsub\s+sp, sp, [xw]|\b(?:mov|and)\s+sp,', line):
                raise ValueError('unbounded/dynamic SP: ' + obj + ':' + parts[i])
        out[obj + ':' + parts[i][1:]] = dict(
            frame=frame, calls=re.findall(r'\b(?:bl|b)\s+_([\w.]+)', body),
            indirect=bool(re.search(r'\b(?:blr|br)\s+x', body)))
    # Generated protocol-description objects may contain data only.
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('objects', type=Path)
    ap.add_argument('--root', action='append', default=[])
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    data, hashes = {}, {}
    for p in sorted(args.objects.glob('mi8_*.o')):
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        text = subprocess.check_output(['llvm-objdump', '--macho', '--disassemble', '--no-show-raw-insn', str(p)], text=True)
        data.update(parse(text, p.stem))
    roots = args.root or ['mi8_rproc:steps_from_five', 'mi8_rproc:steps_audio_clip', 'mi8_rproc:steps_audio_session', 'mi8_tas2557:session_control_thread']
    graph, external = {}, {}
    for key, row in data.items():
        obj = key.split(':')[0]
        graph[key], external[key] = set(), set()
        for target in row['calls']:
            local = obj + ':' + target
            choices = [local] if local in data else [k for k in data if k.endswith(':' + target)]
            if len(choices) > 1:
                raise ValueError('ambiguous external symbol: ' + target)
            if choices:
                graph[key].update(choices)
            else:
                external[key].add(target)
        if row['indirect']:
            graph[key].update(CALLBACKS.get(obj, []) + EXTRA.get(key, []))
            if obj == 'mi8_audio_pcm':
                external[key].add('redwood_audio_muted (clip ops)')
    seen, paths, memo = set(), {}, {}

    def visit(key, chain=()):
        if key in chain:
            raise ValueError('unbounded call cycle: ' + ' -> '.join(chain + (key,)))
        if key not in data:
            raise ValueError('missing callback/root symbol: ' + key)
        seen.add(key)
        if data[key]['indirect'] and key not in EXTRA and key.split(':')[0] not in CALLBACKS:
            raise ValueError('unreviewed indirect call: ' + key)
        if key in memo:
            return memo[key]
        best = max((visit(n, chain + (key,)) for n in sorted(graph[key])), default=(0, []))
        memo[key] = (data[key]['frame'] + best[0], [key] + best[1])
        return memo[key]

    for root in roots:
        paths[root] = visit(root)
    warnings = {k: dict(bytes=data[k]['frame'], reason=ALLOW.get(k, 'not allowlisted')) for k in sorted(data) if data[k]['frame'] > 1024}
    for key, row in warnings.items():
        print('FRAME WARNING', key, row)
    for root, (size, path) in paths.items():
        print(f'{root}: {size} bytes / 8192')
        print(' -> '.join(f'{k}[{data[k]["frame"]}]' for k in path))
    # Include the largest reachable suffixes, useful for auditing callback unions.
    top = sorted(((v[0], k, v[1]) for k, v in memo.items()), reverse=True)[:10]
    for size, key, path in top:
        print('PATH', size, ' -> '.join(path))
    result = dict(scope='mi8 object frames; external XNU entries listed, 8 KiB kernel-service/preemption reserve',
                  objects=hashes, roots=paths, largest_paths=top, frames={k: data[k]['frame'] for k in sorted(seen)},
                  manual_edges={k: sorted(graph[k]) for k in sorted(seen) if data[k]['indirect']},
                  external={k: sorted(external[k]) for k in sorted(seen) if external[k]}, warnings=warnings)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + '\n')
    if any(size > 8192 for size, _ in paths.values()):
        raise SystemExit('FAIL: audio worker exceeds 8 KiB')
    print('PASS: mi8 audio worker stack budget')


if __name__ == '__main__':
    main()
