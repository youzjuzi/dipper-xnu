#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline dipper partition planner. Generates a holder-operated GPT script only."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import uuid

_HELPER = Path(__file__).with_name('restore-android-layout.py')
_spec = importlib.util.spec_from_file_location('dipper_gpt_restore', _HELPER)
gpt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gpt)
require = gpt.require
SECTOR = 4096
ALIGN_SECTORS = 256  # 1 MiB, matching the verified device layout.
MIN_USERDATA_BYTES = 8 * 2**30
APFS_TYPE = '7c3457ef-0000-11aa-aa11-00306543ecac'
LINUX_TYPE = '0fc63daf-8483-4772-8e79-3d69d8477de4'


def load_plan(path):
    c = json.loads(path.read_text())
    gpt.validate_device_config(c)
    require(type(c['darwin_size_gib']) is int and c['darwin_size_gib'] > 0, 'darwin_size_gib must be a positive integer')
    require(isinstance(c['darwin_guid'], str), 'darwin_guid must be a UUID string')
    ident = uuid.UUID(c['darwin_guid'])
    require(ident.version == 4 and ident.variant == uuid.RFC_4122, 'generate a fresh UUID v4 for darwin')
    c['darwin_guid'] = str(ident)
    blobs = {k: gpt.capture(path.parent, c[k]) for k in ('before_primary', 'before_backup')}
    before = gpt.pair(blobs['before_primary'], blobs['before_backup'], SECTOR, c['disk_bytes'] // SECTOR)
    entries = before['entries']
    require(not any(e['name'] == 'darwin' for e in entries.values()), 'darwin already exists; refusing to repartition')
    found = [i for i, e in entries.items() if e['name'] == 'userdata']
    require(len(found) == 1, 'expected one userdata partition')
    u = found[0]; old = entries[u]
    require(old['type'] == LINUX_TYPE and old['attrs'] == 0, 'unsupported userdata type or attributes')
    require(old['end'] == max(e['end'] for e in entries.values()), 'userdata must be the last physical partition')
    require(0 <= before['last'] - old['end'] < ALIGN_SECTORS, 'unexpected free space after userdata')
    require(old['start'] % ALIGN_SECTORS == 0, 'userdata start is not 1 MiB aligned')
    canonical = uuid.UUID(old['type']).bytes_le + uuid.UUID(old['guid']).bytes_le + struct.pack('<QQQ', old['start'], old['end'], 0) + 'userdata'.encode('utf-16-le').ljust(72, b'\0')
    require(old['raw'] == canonical, 'noncanonical userdata entry')
    require(str(ident) not in [e['guid'] for e in entries.values()], 'darwin GUID duplicates an existing partition')
    available = [i for i in range(u + 1, before['count'] + 1) if i not in entries]
    require(bool(available), 'no free GPT entry after userdata')
    d = available[0]
    requested = c['darwin_size_gib'] * 2**30
    first = ((before['last'] + 1 - requested // SECTOR + ALIGN_SECTORS - 1) // ALIGN_SECTORS) * ALIGN_SECTORS
    userdata_bytes = (first - old['start']) * SECTOR
    require(userdata_bytes >= MIN_USERDATA_BYTES, 'requested darwin leaves less than 8 GiB for userdata')
    require(first <= old['end'], 'darwin must carve space out of userdata')
    actual = (before['last'] - first + 1) * SECTOR
    require(0 <= requested - actual < ALIGN_SECTORS * SECTOR, 'invalid alignment result')
    target = bytearray(before['table'])
    raw = bytearray(old['raw']); struct.pack_into('<Q', raw, 40, first - 1)
    target[(u - 1) * 128:u * 128] = raw
    target[(d - 1) * 128:d * 128] = uuid.UUID(APFS_TYPE).bytes_le + ident.bytes_le + struct.pack('<QQQ', first, before['last'], 0) + 'darwin'.encode('utf-16-le').ljust(72, b'\0')
    plan = dict(userdata_entry=u, userdata_start=old['start'], userdata_end=first-1,
                userdata_guid=old['guid'], userdata_bytes=userdata_bytes,
                darwin_entry=d, darwin_start=first, darwin_end=before['last'],
                darwin_guid=str(ident), darwin_bytes=actual, requested_bytes=requested,
                alignment_bytes=ALIGN_SECTORS * SECTOR, alignment_shortfall_bytes=requested-actual,
                effect='Destructive GPT repartition only. Reboot Recovery and verify sizes, then Format Data before Android. No image write.')
    return c, blobs, before, bytes(target), plan


def render_script(c, blobs, plan):
    u = plan['userdata_entry']; d = plan['darwin_entry']
    lines = gpt.render_guard(c, blobs, 'CREATE-DARWIN', [f'sda{u}'],
                             absent_nodes=['by-name/darwin', f'sda{d}'], unmount_data=True)
    lines += ['/tmp/sgdisk --verify /dev/block/sda',
              f'/tmp/sgdisk --delete={u} --new={u}:{plan["userdata_start"]}:{plan["userdata_end"]} --typecode={u}:{LINUX_TYPE} --partition-guid={u}:{plan["userdata_guid"]} --change-name={u}:userdata --new={d}:{plan["darwin_start"]}:{plan["darwin_end"]} --typecode={d}:{APFS_TYPE} --partition-guid={d}:{plan["darwin_guid"]} --change-name={d}:darwin /dev/block/sda',
              '/tmp/sgdisk --print --verify /dev/block/sda',
              'echo "STOP HERE: return output and read back GPT. Do not boot Android or format with stale kernel sizes. After verification, reboot Recovery, verify new sizes, then Format Data."']
    return '\n'.join(lines) + '\n'


def verify(c, before, target, plan, primary, backup, userdata_bytes=None, darwin_bytes=None):
    actual = gpt.pair(primary, backup, SECTOR, c['disk_bytes'] // SECTOR)
    require(actual['table'] == target, 'actual GPT entries differ from the plan')
    require(all(actual[k] == before[k] for k in ('disk_guid', 'first', 'last', 'count')), 'GPT disk identity or geometry changed')
    if userdata_bytes is not None or darwin_bytes is not None:
        require(userdata_bytes == plan['userdata_bytes'] and darwin_bytes == plan['darwin_bytes'], 'kernel sizes stale, incomplete or incorrect; do not format')
        return 'PASS: GPT and supplied kernel sizes match. Format Data and Android boot still require holder verification.'
    return 'PASS: GPT matches. Reboot Recovery and verify both kernel sizes before Format Data.'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, help='new private run directory; never overwrites')
    p.add_argument('--verify-primary', type=Path)
    p.add_argument('--verify-backup', type=Path)
    p.add_argument('--kernel-userdata-bytes', type=int)
    p.add_argument('--kernel-darwin-bytes', type=int)
    a = p.parse_args()
    try:
        c, blobs, before, target, plan = load_plan(a.config)
        checking = any(x is not None for x in (a.verify_primary, a.verify_backup, a.kernel_userdata_bytes, a.kernel_darwin_bytes))
        if checking:
            require(a.output_dir is None, 'verification cannot emit a script')
            require(a.verify_primary is not None and a.verify_backup is not None, 'verification requires both GPT captures')
            print(verify(c, before, target, plan, a.verify_primary.read_bytes(), a.verify_backup.read_bytes(), a.kernel_userdata_bytes, a.kernel_darwin_bytes))
            return
        script = render_script(c, blobs, plan)
        if a.output_dir:
            a.output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            (a.output_dir / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
            (a.output_dir / 'create-darwin.sh').write_text(script)
            (a.output_dir / 'expected-gpt-entries.bin').write_bytes(target)
            # Rebase capture paths so the saved config is usable for later verification.
            for key in blobs:
                c[key]['path'] = str((a.config.parent / c[key]['path']).resolve())
            (a.output_dir / 'config.json').write_text(json.dumps(c, indent=2) + '\n')
            provenance = dict(config_source=str(a.config.resolve()), generator_sha256=gpt.sha(Path(__file__).read_bytes()), helper_sha256=gpt.sha(_HELPER.read_bytes()))
            (a.output_dir / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
            (a.output_dir / 'SHA256SUMS').write_text(''.join(gpt.sha(f.read_bytes()) + '  ' + f.name + '\n' for f in sorted(a.output_dir.iterdir())))
        print(json.dumps(plan, indent=2))
        print('Offline plan only. No device accessed. Output contains private identifiers.')
    except (ValueError, OSError, KeyError, TypeError, struct.error, UnicodeError) as e:
        p.exit(1, 'STOP: ' + str(e) + '\n')


if __name__ == '__main__':
    main()
