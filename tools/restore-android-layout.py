#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline Mi 8 GPT restoration planner. Never connects to or writes a device."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import uuid
import zlib


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def capture(base, spec):
    require(set(spec) == {'path', 'sha256'}, 'capture needs path and sha256')
    require(re.fullmatch(r'[0-9a-f]{64}', spec['sha256']), 'invalid SHA256')
    data = (base / spec['path']).read_bytes()
    require(sha(data) == spec['sha256'], 'SHA256 mismatch: ' + spec['path'])
    return data


def parse_gpt(data, sector, disk_sectors, backup=False):
    """Primary capture starts at LBA0; backup capture ends at the disk end."""
    require(len(data) % sector == 0, 'capture is not sector aligned')
    origin = disk_sectors - len(data) // sector if backup else 0
    offset = len(data) - sector if backup else sector
    require(len(data) >= 2 * sector, 'short GPT capture')
    h = data[offset:offset + sector]
    require(h[:8] == b'EFI PART', 'GPT signature missing')
    rev, size, crc, reserved = struct.unpack_from('<IIII', h, 8)
    require(rev == 0x10000 and size == 92 and reserved == 0, 'unsupported GPT header')
    check = bytearray(h[:size]); check[16:20] = b'\0' * 4
    require(zlib.crc32(check) == crc, 'GPT header CRC mismatch')
    here, other, first, last = struct.unpack_from('<QQQQ', h, 24)
    table_lba, count, entry_size, table_crc = struct.unpack_from('<QIII', h, 72)
    require((here, other) == ((disk_sectors - 1, 1) if backup else (1, disk_sectors - 1)), 'GPT disk geometry mismatch')
    require(1 <= count <= 128 and entry_size == 128, 'unsupported GPT entry table')
    table_sectors = (count * entry_size + sector - 1) // sector
    require(table_lba == (disk_sectors - 1 - table_sectors if backup else 2), 'unsupported GPT table location')
    require(2 + table_sectors <= first <= last < disk_sectors - 1 - table_sectors, 'invalid usable range')
    start = (table_lba - origin) * sector
    require(start >= 0 and start + count * entry_size <= len(data), 'GPT table not fully captured')
    table = data[start:start + count * entry_size]
    require(zlib.crc32(table) == table_crc, 'GPT table CRC mismatch')
    entries = {}; spans = []; guids = set()
    for i in range(count):
        raw = table[i * 128:(i + 1) * 128]
        if raw == bytes(128):
            continue
        require(raw[:16] != bytes(16) and raw[16:32] != bytes(16), 'malformed GPT entry')
        a, b, attr = struct.unpack_from('<QQQ', raw, 32)
        require(first <= a <= b <= last, 'partition outside usable range')
        require(raw[16:32] not in guids, 'duplicate partition GUID'); guids.add(raw[16:32])
        name = raw[56:128].decode('utf-16-le').rstrip('\0')
        entries[i + 1] = dict(start=a, end=b, attrs=attr, name=name,
                              type=str(uuid.UUID(bytes_le=raw[:16])), guid=str(uuid.UUID(bytes_le=raw[16:32])), raw=raw)
        spans.append((a, b))
    spans.sort()
    require(all(x[1] < y[0] for x, y in zip(spans, spans[1:])), 'overlapping partitions')
    return dict(entries=entries, table=table, disk_guid=h[56:72], first=first, last=last, count=count)


def pair(primary, backup, sector, sectors):
    a = parse_gpt(primary, sector, sectors)
    b = parse_gpt(backup, sector, sectors, True)
    require(a == b, 'primary/backup GPT disagree')
    return a


def validate_device_config(c):
    require(c['schema_version'] == 1 and c['device'] == 'dipper', 'only dipper schema 1 supported')
    require(c['disk'] == '/dev/block/sda' and c['sector_size'] == 4096, 'only dipper sda / 4096-byte sectors supported')
    require(type(c['disk_bytes']) is int and c['disk_bytes'] > 0 and c['disk_bytes'] % 4096 == 0, 'invalid disk size')
    for key in ('serial', 'twrp_version'):
        require(isinstance(c[key], str) and re.fullmatch(r'[A-Za-z0-9_.-]+', c[key]), 'invalid ' + key)
    require(re.fullmatch(r'[0-9a-f]{64}', c['sgdisk_sha256']), 'invalid sgdisk SHA256')


def load_plan(path):
    c = json.loads(path.read_text()); base = path.parent
    validate_device_config(c)
    blobs = {k: capture(base, c[k]) for k in ('before_primary', 'before_backup', 'original_primary')}
    sectors = c['disk_bytes'] // 4096
    before = pair(blobs['before_primary'], blobs['before_backup'], 4096, sectors)
    target = parse_gpt(blobs['original_primary'], 4096, sectors)
    require(all(before[k] == target[k] for k in ('disk_guid', 'first', 'last', 'count')), 'original GPT geometry/identity differs')
    def named(gpt, name):
        hits = [i for i, e in gpt['entries'].items() if e['name'] == name]
        require(len(hits) == 1, 'expected one ' + name)
        return hits[0]
    u = named(before, 'userdata'); d = named(before, 'darwin')
    require(named(target, 'userdata') == u, 'userdata entry number changed')
    require(set(target['entries']) == set(before['entries']) - {d}, 'unexpected added/deleted partitions')
    require(all(e['name'] != 'darwin' for e in target['entries'].values()), 'target still contains darwin')
    require(all(before['entries'][i]['raw'] == e['raw'] for i, e in target['entries'].items() if i != u), 'unrelated partition changed')
    old, removed, new = before['entries'][u], before['entries'][d], target['entries'][u]
    require(old['start'] == new['start'] and old['end'] + 1 == removed['start'], 'userdata/darwin are not adjacent')
    require(old['end'] < new['end'] <= removed['end'], 'target does not fit former userdata+darwin range')
    require(removed['end'] == max(e['end'] for e in before['entries'].values()), 'darwin is not the last physical partition')
    require(old['type'] == new['type'] == '0fc63daf-8483-4772-8e79-3d69d8477de4', 'unsupported userdata type')
    require(old['attrs'] == new['attrs'] == 0, 'nonzero userdata attributes unsupported')
    # sgdisk recreates the name with zero padding; reject data it cannot reproduce.
    canonical = uuid.UUID(new['type']).bytes_le + uuid.UUID(new['guid']).bytes_le + struct.pack('<QQQ', new['start'], new['end'], 0) + 'userdata'.encode('utf-16-le').ljust(72, b'\0')
    require(canonical == new['raw'], 'noncanonical target userdata entry')
    plan = dict(device=c['device'], disk=c['disk'], userdata_entry=u, remove_entry=d,
                userdata_start=new['start'], userdata_end=new['end'], userdata_guid=new['guid'],
                userdata_bytes=(new['end'] - new['start'] + 1) * 4096,
                effect='Remove darwin and restore userdata GPT entry only; data filesystem and Android boot remain pending')
    return c, blobs, target, plan


def render_guard(c, blobs, confirmation, nodes, absent_nodes=(), unmount_data=False):
    q = shlex.quote
    lines = ['#!/sbin/sh', '# Generated for one reviewed snapshot; not a universal flash script.',
             'set -eu', 'stop() { echo "STOP: $*" >&2; exit 1; }',
             f'[ "${{1:-}}" = {q(confirmation)} ] || stop "explicit {confirmation} argument required"',
             '[ "$(id -u)" = 0 ] || stop "root required"']
    for prop, value in [('ro.product.device', c['device']), ('ro.serialno', c['serial']), ('ro.twrp.version', c['twrp_version'])]:
        lines.append(f'[ "$(getprop {prop})" = {q(value)} ] || stop "{prop} mismatch"')
    lines += [f'[ "$(blockdev --getss /dev/block/sda)" = 4096 ] || stop "sector size mismatch"',
              f'[ "$(blockdev --getsize64 /dev/block/sda)" = {c["disk_bytes"]} ] || stop "disk size mismatch"',
              'toolhash=$(sha256sum /tmp/sgdisk) || stop "cannot hash sgdisk"',
              f'[ "${{toolhash%% *}}" = {c["sgdisk_sha256"]} ] || stop "sgdisk SHA256 mismatch"',
              'tmp=$(mktemp -d /tmp/restore-check.XXXXXX) || stop "cannot create RAM temporary directory"',
              'trap \'rm -rf "$tmp"\' EXIT HUP INT TERM']
    for name, skip in [('before_primary', 0), ('before_backup', c['disk_bytes'] // 4096 - len(blobs['before_backup']) // 4096)]:
        lines += [f'dd if=/dev/block/sda of="$tmp/{name}" bs=4096 skip={skip} count={len(blobs[name]) // 4096} || stop "GPT read failed"',
                  f'digest=$(sha256sum "$tmp/{name}") || stop "GPT hash failed"',
                  f'[ "${{digest%% *}}" = {sha(blobs[name])} ] || stop "{name} changed; regenerate plan"']
    lines += ['# Check all remaining mounts and device-mapper holders before writing.',
              'check_unused() {', '  node=$1',
              '  dev=$(cat "/sys/class/block/$node/dev") || stop "missing block node"',
              '  [ -d "/sys/class/block/$node/holders" ] || stop "missing holders directory"',
              '  for holder in /sys/class/block/"$node"/holders/*; do',
              '    [ ! -e "$holder" ] || stop "$node has a block-device holder"', '  done',
              '  [ -r /proc/self/mountinfo ] || stop "mountinfo unavailable"',
              '  while read -r mid parent mounted rest; do',
              '    [ "$mounted" != "$dev" ] || stop "$node remains mounted"',
              '  done < /proc/self/mountinfo', '}',
              '# Any active swap is outside the supported recovery environment.',
              '[ -r /proc/swaps ] || stop "swap state unavailable"',
              'while read -r filename rest; do',
              '  [ "$filename" = Filename ] || stop "active swap unsupported"',
              'done < /proc/swaps']
    for node in absent_nodes:
        lines.append(f'[ ! -e /dev/block/{node} ] || stop "{node} already exists"')
    if unmount_data:
        lines += ['sync', 'for mountpoint in /sdcard /data; do',
                  '  if grep -q " $mountpoint " /proc/mounts; then',
                  '    umount "$mountpoint" || stop "cannot unmount $mountpoint"',
                  '  else', '    rc=$?',
                  '    [ "$rc" -eq 1 ] || stop "mount check failed"',
                  '  fi', 'done']
    lines.extend(f'check_unused {node}' for node in nodes)
    return lines


def render_script(c, blobs, plan):
    u, d = plan['userdata_entry'], plan['remove_entry']
    lines = render_guard(c, blobs, 'RESTORE-ANDROID-GPT', [f'sda{u}', f'sda{d}'])
    lines += [
              '/tmp/sgdisk --verify /dev/block/sda',
              f'/tmp/sgdisk --delete={d} --delete={u} --new={u}:{plan["userdata_start"]}:{plan["userdata_end"]} --typecode={u}:0FC63DAF-8483-4772-8E79-3D69D8477DE4 --partition-guid={u}:{plan["userdata_guid"]} --change-name={u}:userdata /dev/block/sda',
              '/tmp/sgdisk --print --verify /dev/block/sda',
              'echo "STOP HERE: read back GPT, reboot Recovery, verify kernel capacity before rebuilding data filesystem."']
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True, help='private JSON; capture paths relative to this file')
    p.add_argument('--output-dir', type=Path, help='new private run directory: emit plan + user-operated script')
    p.add_argument('--verify-primary', type=Path, help='post-restoration primary capture')
    p.add_argument('--verify-backup', type=Path, help='post-restoration backup capture')
    p.add_argument('--kernel-userdata-bytes', type=int, help='fresh read after Recovery reboot')
    a = p.parse_args()
    try:
        c, blobs, target, plan = load_plan(a.config)
        verify = any(x is not None for x in (a.verify_primary, a.verify_backup, a.kernel_userdata_bytes))
        if verify:
            require(all(x is not None for x in (a.verify_primary, a.verify_backup, a.kernel_userdata_bytes)), 'verification needs both GPT captures and kernel capacity')
            require(a.output_dir is None, 'verification cannot emit an execution script')
            actual = pair(a.verify_primary.read_bytes(), a.verify_backup.read_bytes(), 4096, c['disk_bytes'] // 4096)
            require(actual == target, 'restored GPT differs from verified original')
            require(a.kernel_userdata_bytes == plan['userdata_bytes'], 'kernel capacity stale or incorrect; do not format')
            print('PASS: restored GPT and supplied kernel capacity match; filesystem and Android boot not verified')
        else:
            if a.output_dir:
                a.output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
                (a.output_dir / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
                (a.output_dir / 'restore-android-layout.sh').write_text(render_script(c, blobs, plan))
                (a.output_dir / 'inputs.json').write_text(json.dumps(c, indent=2) + '\n')
                (a.output_dir / 'provenance.json').write_text(json.dumps(dict(config_path=str(a.config.resolve()), generator_sha256=sha(Path(__file__).read_bytes())), indent=2) + '\n')
                (a.output_dir / 'SHA256SUMS').write_text(''.join(sha(f.read_bytes()) + '  ' + f.name + '\n' for f in sorted(a.output_dir.iterdir())))
            print(json.dumps(plan, indent=2))
            print('Offline plan only. No device accessed. Generated scripts and plans are private.')
    except (ValueError, OSError, KeyError, TypeError, struct.error, UnicodeError) as e:
        p.exit(1, 'STOP: ' + str(e) + '\n')


if __name__ == '__main__':
    main()
