# Creating the `darwin` Partition: Generic Tool

**English** | [简体中文](../zh-CN/docs/install/PARTITION_DARWIN.md)

[tools/partition/partition-darwin.py](../../tools/partition/partition-darwin.py) is an offline partition-plan generator for `dipper`. It never invokes `adb` or touches a device; generated shell scripts must be reviewed and run by the device owner. It modifies the GPT only—never flashing `darwin.img`, formatting partitions, or rebooting automatically.

Verified workflow: backup current GPT -> write partition -> readback -> reboot TWRP and verify kernel partition sizes -> `Format Data` -> Android setup and `/data` capacity check. See [First-Install Task](../development/FIRST_INSTALL.md) for evidence and pending items.

## Supported Scope and Layout

Supports `dipper` `/dev/block/sda` with 4096-byte logical sectors, `userdata` at the tail of the disk (Linux filesystem type, zero attributes, 1 MiB-aligned start, < 1 MiB trailing slack), no existing `darwin` partition, and at least 8 GiB retained for `userdata`. In-place resize preserving user data is **not** supported; this is not a generic partitioner for arbitrary phones.

- Shared tool: `tools/partition/partition-darwin.py`, sharing GPT validation and device guards with `tools/partition/restore-android-layout.py` (keep both).
- Local config: `local/devices/<alias>/darwin-partition-<date>.json`.
- Pre-edit GPT backup: `local/backups/<run-id>/`, registered in `local/index.json`.
- Plan, generated script, and readback logs: fresh `work/runs/<run-id>/` (never overwrite).

Private configs, generated scripts, GPT binaries, GUIDs, and logs stay out of Git.

## 1. Collect and Verify Inputs Read-Only

Inside Recovery, verify device identity, serial, TWRP version, disk size, logical sector size, mount state, and GPT layout. Capture the full primary GPT (from LBA 0 including header and full entry table) and backup GPT (ending at the last disk sector including backup header and full entry table), sector-aligned. Never copy backups from another phone; see [Inspecting Your Current Layout](INSTALL.md#3-inspecting-your-current-layout).

Verify your ARM64 `sgdisk` binary's origin, version, and SHA-256 (x86 host binaries cannot run on the phone; never bypass a hash mismatch). A GPT backup is **not** a user-data backup—recreating `userdata` wipes all Android data.

Local config fields (`path` values relative to the config directory; capacities as integers):

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
  "before_primary": {"path": "<primary-gpt-path>", "sha256": "<verified-sha256>"},
  "before_backup": {"path": "<backup-gpt-path>", "sha256": "<verified-sha256>"},
  "darwin_size_gib": 24,
  "darwin_guid": "<freshly-generated-UUID-v4>"
}
```

Generate a fresh GUID per run with `python3 -c 'import uuid; print(uuid.uuid4())'` rather than copying an old device GUID. `darwin_size_gib` accepts positive integers only; because start LBA aligns up to 1 MiB and ends at last usable LBA, actual size can be slightly under the requested GiB (e.g., 8,192 bytes less in the verified 24 GiB layout). Ensure `darwin` fits `darwin.img` plus runtime write space.

## 2. Generate and Review Plan

From repository root:

```sh
# Print plan only without creating files or touching a device
python3 tools/partition/partition-darwin.py --config local/devices/<alias>/darwin-partition-<date>.json

# Write artifacts to a fresh private run directory (refuses existing directory)
python3 tools/partition/partition-darwin.py --config local/devices/<alias>/darwin-partition-<date>.json --output-dir work/runs/<new-run-id>
```

Outputs `plan.json`, `create-darwin.sh`, `expected-gpt-entries.bin`, `config.json`, provenance, and `SHA256SUMS`. `expected-gpt-entries.bin` is for verification only—**never `dd` it to disk**. Paths inside saved configs become absolute and are not portable across hosts.

The generator validates input digests, primary/backup GPT CRCs and consistency, bounds, and overlap; preserves `userdata` start/type/GUID and all other entries; and creates `darwin` in a free slot after `userdata`, aborting if `darwin` exists, layout differs, or space is insufficient.

## 3. Execution by Device Owner

Review the range and data-wipe impact, run an `sgdisk --pretend` dry-run on the live phone followed by readback verification, stage verified `sgdisk` to `/tmp/sgdisk` and the generated script to `/tmp/create-darwin.sh`, verify transfer SHA-256s, and execute:

```sh
adb -s <serial> shell sh /tmp/create-darwin.sh CREATE-DARWIN
```

The script re-verifies root, device identity, TWRP, disk capacity, tool hash, and pre-change GPT digests, cleanly unmounts `/sdcard` and `/data` (no lazy/forced unmount; aborts if mounts, block holders, active swap, or target nodes remain). Disable MTP and avoid concurrent mounts/storage ops during execution; stop and inspect on any failure without stripping checks.

After updating GPT, the script prints the table and exits. Because the old filesystem may exceed the new `userdata` partition, **do not boot Android or format using stale kernel bounds**, and never re-run a completed script.

## 4. Readback, Reboot, and Verification

Verify primary and backup GPT immediately after writing:

```sh
python3 tools/partition/partition-darwin.py --config work/runs/<run-id>/config.json --verify-primary <post-write-primary> --verify-backup <post-write-backup>
```

Reboot into Recovery, re-capture both GPTs plus live kernel byte sizes for `userdata` and `darwin`, and run the second check:

```sh
python3 tools/partition/partition-darwin.py --config work/runs/<run-id>/config.json --verify-primary <post-reboot-primary> --verify-backup <post-reboot-backup> --kernel-userdata-bytes <actual-bytes> --kernel-darwin-bytes <actual-bytes>
```

The tool never reads the phone itself; stale sizes, missing counts, or mismatched entries are rejected. Once both checks pass, run TWRP **Format Data** (rebuilding `userdata` only—never format `darwin`), boot Android through initial setup, verify `sys.boot_completed` and `df -k /data` (ignoring MIUI's "System" storage category), and match the new `darwin` GUID in loader/UEFI before staging images.

## Validation Boundaries

All 14 partition-tool tests (including 10 synthetic-shell guard failure modes) and 17 shared restore-tool tests pass offline without touching real block devices, and offline replay against captured real pre/post GPTs matched the live-verified entries and kernel node sizes exactly. Because the generalized generator's output script has not been re-run separately on a live phone (the live test used an earlier verified one-off script prior to adding extra guards), treat the generic tool's live execution as separately tracked.

Test commands:

```sh
python3 tools/tests/test-restore-android-layout.py
python3 tools/tests/test-partition-darwin.py
```
