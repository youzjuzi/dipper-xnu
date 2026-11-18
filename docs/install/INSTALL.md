# Partitioning, System Flashing, and Android Rollback

**English** | [简体中文](../zh-CN/docs/install/INSTALL.md)

This page covers persistent storage operations; [Configuration, Rebuild & Boot](STARTUP.md) covers loader, UEFI, and RAM booting. Follow Sections 1–6 for first-time installation, or Section 7 to revert to stock Android layout; if `darwin` is already partitioned and its system readback matches, skip straight to the startup guide without reflashing.

On the test device, this route passed Android layout restoration, repartitioning, byte-exact `darwin.img` readback, and owner-confirmed boot into iOS. Full per-peripheral regression and post-exit teardown checks remain tracked in [STATUS](../STATUS.md) and [VALIDATION](../validation/VALIDATION.md). Every device must verify its own GPT, GUIDs, and inputs independently.

All device modifications are executed by the device owner. Build prep is in [Build Guide](../build/BUILD.md) and existing-layout testing is in [Existing-Partition Testing](EXISTING_INSTALL.md).

## 1. What Writes Where

| Stage | Action | Persistent Write? |
| --- | --- | --- |
| First-time partitioning | Shrink/recreate `userdata`, add `darwin`, update GPT | Yes; wipes Android user data |
| First-time image write | Write composite APFS rootfs + cryptex image to `darwin` | Yes |
| Every boot | Load UEFI temporarily via `fastboot boot`, stage ramdisk + kernel payload | Writes to RAM; reads system volume from `darwin` |
| Persistent `/private/var` | Optional `--persist` / `var_store` saving | Yes, writes only `darwin` runtime region |

UEFI is **never** flashed to `boot` (`fastboot boot` loads RAM only; `fastboot flash` writes permanently).

## 2. Prerequisites

See [Device Preparation](DEVICE_PREPARATION.md) for OS baselines, TWRP downloads/checksums, and GPU firmware extraction.

- Unlocked bootloader with vendor fastboot access.
- Verified `dipper` recovery (TWRP `3.7.0_9-0` tested; not bundled) providing root ADB, GPT tools, and block access.
- Full verified backups of personal files, primary/backup GPT, and critical partitions (`boot`, `modem`, `persist`, `modemst1/2`, `fsg`, etc.) copied off-device with hashes checked.
- Device-specific recovery path ready (never assume another device's EDL/9008 tools apply).
- Acceptance that recreating `userdata` wipes all Android apps/settings/data—flashing `boot` alone will not restore GPT or data.

Never overwrite `modem`, `persist`, `modemst1/2`, or `fsg`.

## 3. Inspecting Your Current Layout

Identify your ADB serial (`ANDROID_SERIAL`) and vendor fastboot serial (`BOOT_SERIAL`) so commands never target the wrong device. Commands below require root ADB inside verified recovery with an ARM64 `sgdisk` placed at `/tmp/sgdisk` (x86_64 host binaries will not run on the phone):

```sh
adb -s "$ANDROID_SERIAL" shell id
adb -s "$ANDROID_SERIAL" shell 'ls -l /dev/block/by-name/userdata /dev/block/by-name/darwin'
adb -s "$ANDROID_SERIAL" shell 'cat /proc/mounts'
```

Absence of `darwin` before first install is expected. Confirm the physical disk node holding `userdata` rather than blindly assuming `/dev/block/sda`:

```sh
# Example placeholders; substitute your verified device node.
DISK_NODE='/dev/block/<your-userdata-disk>'
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --print '$DISK_NODE'"
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --verify '$DISK_NODE'"
```

Record logical sector size, total sectors, last usable LBA, `userdata` number/start/end/type/unique GUID, and all other entries; confirm `userdata` sits at the end with no overlap, and ensure target partitions are unmounted and GPT passes verification. Back up current GPT to host (not a substitute for user-data backups):

```sh
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --backup=/tmp/dipper-gpt-before.bin '$DISK_NODE'"
adb -s "$ANDROID_SERIAL" pull /tmp/dipper-gpt-before.bin ./dipper-gpt-before.bin
sha256sum ./dipper-gpt-before.bin
```

## 4. Creating `darwin` and Rebuilding Data

Follow [Darwin Partition Tool](PARTITION_DARWIN.md) to capture primary/backup GPTs, fill a private config, review the plan, and generate a run-specific script (only tail `userdata`/`darwin` layout supported; no data-preserving shrink).

In the verified 24 GiB reference (`darwin_size_gib: 24`, 1 MiB-aligned to 25,769,795,584 bytes, 8,192 bytes shy of 24 GiB—example only, never copy across devices):

| Partition | Start LBA (4096 B) | End LBA | Kernel Node Bytes |
| --- | --- | --- | --- |
| `userdata` | 393216 | 23746559 | 95655297024 |
| `darwin` | 23746560 | 30038013 | 25769795584 |

1. Review the plan, hashes, and scope; push verified ARM64 `sgdisk` and script to Recovery `/tmp/`, verify digests, and run `CREATE-DARWIN`.
2. Read back primary/backup GPT and verify entries match; if the kernel still reports the old table, reboot Recovery before formatting.
3. Reboot into Recovery and verify both GPTs and live kernel node byte counts via `partition-darwin.py`.
4. Run TWRP **Format Data** to rebuild `userdata`, then boot Android through setup and verify capacity (do not rely on MIUI's "System" storage bucket alone):

```sh
adb -s "$ANDROID_SERIAL" shell 'getprop sys.boot_completed; df -k /data'
```

Save the new GUID, bounds, and backups in `local/`, then match your sources to the new partition per [Matching Sources to a New Partition](STARTUP.md#1-matching-sources-to-a-new-partition) before flashing.

## 5. Preparing `darwin.img`

Uses iOS 16.5 (`20F66`, `iPhone10,3`/`iPhone10,6`) images laid out sequentially inside `darwin` (4096-byte blocks relative to `darwin` start):

| Region | Start Block | Block Count | Bytes |
| --- | --- | --- | --- |
| Root APFS container | 0 | 1374208 | 5628755968 |
| OS cryptex | 1374208 | 665600 | 2726297600 |
| App cryptex | 2039808 | 2560 | 10485760 |
| Runtime data region | 2042368 | Remaining | Managed at runtime |

The root container comes from extracting `3.apfs` inside `096-04088-077.dmg` (never flash the UDIF wrapper or `system.apfs` from RAM-only schemes). After extracting the IPSW per [Userspace Guide](../build/USERLAND.md), run from repository root:

```sh
python3 tools/build/pack-darwin.py
sha256sum work/images/darwin.img
```

Verified SHA-256 (matching 2026-10-30 build): `9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560`. Build `root.apfs` and `flashboot.apfs` per [Userspace Guide](../build/USERLAND.md).

## 6. Writing the System Image and Readback Verification

Boot into vendor fastboot with only the target phone connected and verify variables first:

```sh
fastboot -s "$BOOT_SERIAL" getvar product
fastboot -s "$BOOT_SERIAL" getvar partition-size:darwin
fastboot -s "$BOOT_SERIAL" getvar partition-type:darwin
```

`partition-size:darwin` must match your GPT and fit `darwin.img` (e.g., `0x5FFFFE000` in the reference 24 GiB layout). Once confirmed, flash **specifically** `darwin` (never `boot`, `userdata`, or whole disk):

```sh
fastboot -s "$BOOT_SERIAL" flash darwin /path/to/darwin.img
```

Reboot back into verified recovery, confirm `darwin` is unmounted with matching size, and read back the exact image byte span (`8,365,539,328` bytes = `7978 * 1 MiB`) to check SHA-256:

```sh
# Recovery shell must support pipefail; otherwise pull full span to host to hash.
adb -s "$ANDROID_SERIAL" exec-out 'set -o pipefail; dd if=/dev/block/by-name/darwin bs=1048576 count=7978 | sha256sum'
```

The digest must equal host `darwin.img` exactly (`fastboot OKAY` alone cannot guarantee sparse-transfer integrity). Stop if mismatched; if verified, proceed to [Startup Guide](STARTUP.md).

## 7. Rollback to Android Layout

Rollback removes `darwin` and restores `userdata` without preserving user files or reflashing full stock ROMs. Only run this when intentionally removing dual-partition setup.

Entry point: [tools/partition/restore-android-layout.py](../../tools/partition/restore-android-layout.py) (host-only offline planner targeting `dipper` `/dev/block/sda`, 4096 B sectors, tail `userdata`+`darwin` layout).

### Layout and Inputs

- `tools/partition/restore-android-layout.py`: tracked tool.
- `local/devices/<alias>/android-restore-<date>.json`: private config.
- `local/backups/<run-id>/`: pre-restore primary/backup GPTs and verified original GPT.
- `work/runs/<run-id>/`: plans, scripts, readback logs.

Capture fresh sector-aligned pre-restore primary/backup GPTs and provide the verified original device GPT (never copy another phone's GPT):

```json
{
  "schema_version": 1,
  "device": "dipper",
  "serial": "<ro.serialno>",
  "twrp_version": "<verified-version>",
  "disk": "/dev/block/sda",
  "sector_size": 4096,
  "disk_bytes": 0,
  "sgdisk_sha256": "<verified-64-hex-sha256>",
  "before_primary": {"path": "<pre-restore-primary>", "sha256": "<verified-sha256>"},
  "before_backup": {"path": "<pre-restore-backup>", "sha256": "<verified-sha256>"},
  "original_primary": {"path": "<original-primary>", "sha256": "<verified-sha256>"}
}
```

The planner checks input hashes, header/table CRCs, primary/backup consistency, bounds, non-overlap, unchanged other entries, unchanged `userdata` start, Linux filesystem type, and zero attributes.

### Generate and Review Offline

```sh
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --output-dir work/runs/<new-run-id>
```

Never copy `inputs.json` for re-execution (paths stay relative to original config dir), and never commit generated scripts containing private GUIDs.

### Owner Execution and Verification

After reviewing the plan and verifying transfer hashes for `/tmp/sgdisk` and `/tmp/restore-android-layout.sh` inside TWRP (MTP disabled, `userdata`/`darwin` unmounted, no active swap or concurrent mounts):

```sh
adb -s <serial> shell sh /tmp/restore-android-layout.sh RESTORE-ANDROID-GPT
```

The script removes `darwin` and restores the `userdata` GPT entry without formatting or rebooting. Read back GPT immediately, reboot into Recovery to refresh kernel nodes, and verify with live post-reboot captures:

```sh
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --verify-primary <post-reboot-primary> --verify-backup <post-reboot-backup> --kernel-userdata-bytes <post-reboot-bytes>
```

### Verification Scope

Passes all 17 synthetic GPT/CLI tests (`python3 tools/tests/test-restore-android-layout.py`) and offline replay against captured device GPTs. While the restore procedure succeeded on device, the generalized generator with hardened checks has not been separately executed on a live phone. After GPT verification passes, complete TWRP **Format Data**, Android setup, `sys.boot_completed`, and `df -k /data` verification (progress tracked in [First-Install Task](../development/FIRST_INSTALL.md)).
