#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package a bounded dipper desktop, Wi-Fi or peripheral run; no device access."""
import argparse
import hashlib
import json
import re
import secrets
from pathlib import Path
import shutil
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build_cmdline(seconds, epoch, wifi_mac=None, peripherals=False, persist=False, bluetooth=False):
    """Use kernel defaults; preserve the packager's opt-in radio profile."""
    cmdline = (f'loader_return_after={seconds} epoch={epoch} '
               'bootcpu=7 cpus=7 ufs=2 root_apfs=ufs_darwin')
    if wifi_mac is not None:
        cmdline += f' wifi_mac={wifi_mac}'
    else:
        cmdline += ' mi8rp_mss=0 wifi_lx=0 wifi_station=0'
    if peripherals:
        cmdline += ' battery=1 torch=3 haptic=3'
    if persist:
        # The data volume is read back at boot and saved when the run ends (darwin blocks >= 2042368 only).
        cmdline += ' ufs_write=1 var_store=1 var_save_ms=120000'
    if bluetooth:
        # WCN3990 firmware download at 3.2 Mbaud, then the AppleBTHci bridge for bluetoothd (bsd/dev/mi8_bt.c).
        cmdline += ' bt=7'
    return cmdline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory, preferably under ignored work/runs/')
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--wifi', action='store_true', help='enable Mi8 modem/ath10k station mode')
    parser.add_argument('--peripherals', action='store_true', help='enable battery reporting, iOS torch and haptics')
    parser.add_argument('--persist', action='store_true',
                        help='keep /private/var in darwin: read it back at boot, save it when the run ends (writes storage)')
    parser.add_argument('--bluetooth', action='store_true',
                        help='with --wifi: bring up the WCN3990 Bluetooth controller for iOS (bt=7)')
    args = parser.parse_args()
    if args.bluetooth and not args.wifi:
        # The chip shares its supplies with the Wi-Fi side and takes its address from wifi_mac.
        raise SystemExit('--bluetooth needs --wifi')
    if args.persist and args.seconds < 180:
        raise SystemExit('--persist needs --seconds >= 180: the desktop must come up before the run ends')
    if not 60 <= args.seconds <= 1800:
        raise SystemExit('Use a bounded run between 60 and 1800 seconds')
    k = ROOT / 'work/hackios'
    inputs = {
        'kernel.macho': k / 'xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837',
        'root.apfs': k / 'userland/root.apfs',
        'flashboot.apfs': k / 'userland/flashboot.apfs',
        'boot-dipper.img': ROOT / 'work/edk2/boot-dipper.img',
        'loader.efi': k / 'xnuloader/loader.efi',
    }
    for name, path in inputs.items():
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit('Missing input: ' + str(path))
        if name.endswith('.apfs'):
            with path.open('rb') as stream:
                stream.seek(32)
                if stream.read(4) != b'NXSB':
                    raise SystemExit('Not an APFS container: ' + str(path))
    # Verify firmware was actually packed, not merely left in a sibling folder.
    reader = k / 'apfs-work/apfs-tool'
    if not reader.is_file():
        subprocess.run(['bash', str(k / 'tools/apfs/build-tool.sh')], check=True)
    for image, paths in ((inputs['root.apfs'], ('/', '/LaunchDaemons', '/LaunchDaemons/com.apple.SpringBoard.plist')),
                         (inputs['flashboot.apfs'], ('/', '/sbin', '/sbin/launchd'))):
        for path in paths:
            metadata = subprocess.check_output([str(reader), 'stat', str(image), path], text=True)
            match = re.search(r'mode\s+([0-7]+)\s+uid\s+(\d+)\s+gid\s+(\d+)', metadata)
            if not match or int(match[1], 8) & 0o022 or int(match[2]) != 0:
                raise SystemExit('Unsafe launchd path ownership/permissions: ' + str(image) + ':' + path)
    firmware = {}
    for name in ('a630_gmu.bin', 'a630_sqe.fw', 'a630_zap.mdt', 'a630_zap.b02'):
        source = k / 'fw-gpu' / name
        expected = sha256(source)
        data = subprocess.check_output([str(reader), 'cat', str(inputs['root.apfs']), '/fw/' + name])
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit('GPU firmware missing or stale in root.apfs: ' + name)
        firmware[name] = expected
    wifi_firmware = {}
    if args.wifi:
        name = 'firmware-5.bin'
        source = k / 'fw-wifi' / name
        expected = 'fef6539e0127579536bc977be57a90d018b83f2931fedc3a8870fbe38d6c4127'
        if not source.is_file() or sha256(source) != expected:
            raise SystemExit('Missing or incorrect WCN3990 firmware-5.bin; see docs/build/INPUTS.md')
        data = subprocess.check_output([str(reader), 'cat', str(inputs['root.apfs']), '/fw/' + name])
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit('WCN3990 firmware-5.bin missing or stale in root.apfs; rebuild userland')
        wifi_firmware[name] = expected
    bt_firmware = {}
    if args.bluetooth:
        # The bring-up's firmware (pulled from the phone into fw-bt, see docs/install/DEVICE_PREPARATION.md)
        # in the boot volume, and the iOS side (userland/build.sh BT=1) in root.apfs.
        for name in ('crbtfw21.tlv', 'crnv21.bin'):
            source = k / 'fw-bt' / name
            if not source.is_file():
                raise SystemExit('Missing Bluetooth firmware fw-bt/' + name + '; see docs/install/DEVICE_PREPARATION.md')
            data = subprocess.check_output([str(reader), 'cat', str(inputs['flashboot.apfs']), '/fw/' + name])
            if hashlib.sha256(data).hexdigest() != sha256(source):
                raise SystemExit('Bluetooth firmware missing or stale in flashboot.apfs: ' + name)
            bt_firmware[name] = sha256(source)
        for path in ('/LaunchDaemons/com.apple.bluetoothd.plist', '/LaunchDaemons/com.apple.BlueTool.plist',
                     '/lib/libredwood-bt.dylib', '/etc/bluetool/BCM4357B1_placeholder.hcd'):
            if subprocess.run([str(reader), 'stat', str(inputs['root.apfs']), path],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                raise SystemExit('root.apfs has no ' + path + '; rebuild userland with BT=1')
    mac = None
    if args.wifi:
        mac_file = ROOT / 'local/wifi-mac'
        mac_file.parent.mkdir(parents=True, exist_ok=True)
        if not mac_file.exists():
            octets = bytearray(secrets.token_bytes(6))
            octets[0] = (octets[0] | 2) & 0xfe
            with mac_file.open('x') as stream:
                mac_file.chmod(0o600)
                stream.write(':'.join(f'{v:02x}' for v in octets) + '\n')
        mac = mac_file.read_text().strip()
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac) or int(mac[:2], 16) & 3 != 2:
            raise SystemExit('local/wifi-mac must contain a locally administered unicast MAC')
    cmdline = build_cmdline(args.seconds, int(time.time()), mac, args.peripherals, args.persist, args.bluetooth)
    # Maximum generated prefix for this fixed dipper profile (cpus supplied,
    # no serial UART), including the optional watchdog and battery address.
    prefix = 'debug=0x8 rd=md0 vtimer_intid=19 hv_wdt_pet=1 ufs_shared_pa=0x' + '0' * 16 + ' '
    if args.peripherals:
        prefix += 'battery_shared_pa=0x' + '0' * 16 + ' '
    # ufs_write and var_store are enabled only with --persist.
    if len(cmdline.encode()) + len(prefix) >= 608:
        raise SystemExit('Boot arguments exceed conservative loader allowance')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, path in inputs.items():
        shutil.copy2(path, out / name)
        actual = sha256(out / name)
        if actual != sha256(path):
            raise SystemExit('Copy changed: ' + name)
        records[name] = actual
    subprocess.run(['python3', str(k / 'xnuloader/mkpayload.py'), '-o', str(out / 'payload.bin'),
                    'kernel=' + str(out / 'kernel.macho'), 'ramdisk=' + str(out / 'root.apfs'),
                    '--cmdline', cmdline], check=True)
    data = (out / 'payload.bin').read_bytes()
    magic, size = struct.unpack_from('<II', data)
    if magic != 0x50554e58 or size != len(data) - 8:
        raise SystemExit('Bad payload container')
    records['payload.bin'] = sha256(out / 'payload.bin')
    (out / 'cmdline.txt').write_text(cmdline + '\n')
    (out / 'SHA256SUMS').write_text(''.join(digest + '  ' + name + '\n' for name, digest in records.items()))
    (out / 'manifest.json').write_text(json.dumps({
        'scope': 'host package, device GPT and system hash must be checked separately',
        'storage_writes': args.persist, 'restore_old_var_store': args.persist,
        'wifi_enabled': args.wifi, 'seconds': args.seconds, 'cmdline': cmdline,
        'peripherals_enabled': args.peripherals, 'bluetooth_enabled': args.bluetooth,
        'maximum_bootargs_bytes': len(cmdline.encode()) + len(prefix),
        'artifacts': records, 'gpu_firmware': firmware,
        'wifi_feature_metadata': wifi_firmware, 'bluetooth_firmware': bt_firmware,
    }, indent=2) + '\n')
    print(str(out))
    print('Host package only. Verify the device layout and installed system before RAM boot.')


if __name__ == '__main__':
    main()
