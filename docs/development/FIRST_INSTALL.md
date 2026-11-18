# First-Install Acceptance Task

**English** | [简体中文](../zh-CN/docs/development/FIRST_INSTALL.md)

Branch: `test/first-install`. Created: 2026-10-30. Status: Android GPT restore and post-Recovery readback passed; owner completed `Format Data` and Android setup confirming boot and `/data` capacity; subsequent repartition, `Format Data`, Android boot/capacity checks, matching loader/UEFI host build, exact `darwin.img` readback, and owner-confirmed iOS boot all passed; Stage 07 per-peripheral regression and final reboot back to Android remain pending.

## Overall Goal

Inspect the device's current partition layout and recovery material read-only, restore and verify a proven Android GPT layout, then carve out `darwin`, write and verify the locally built `darwin.img`, and validate the full first-install workflow from Android back to the iOS home screen.

"Restoring the Android layout" means restoring target GPT boundaries, rebuilding `/data`, and verifying Android boots—not restoring old user data, flashing full stock firmware, or relocking the bootloader. Layouts must match verified device/stock evidence rather than guessing boundaries or assuming deleting `darwin` alone is sufficient.

## Stages and Acceptance Criteria

| Stage | Scope & Required Evidence | Pass Criteria | Status |
| --- | --- | --- | --- |
| 01 Inventory | Read-only check of device identity, disk size, sector size, LUN/nodes, full GPT, `userdata`/`darwin` bounds, mounts, encryption, backups | Primary/backup GPT match and explainable; digests saved locally; gaps listed | Verified |
| 02 Restore Plan | Compare against original layout backup; define bounds, tools, data impact, restore steps, and backup checksums | Exact write range and wipe impact confirmed; plan reviewable | Verified for GPT restore (not full-device backup) |
| 03 Restore Android | Owner executes reviewed restore; re-read GPT and filesystem; verify Android boot and `/data` size | Target layout matches with no overlap; Android boots and reports `/data` | Passed (GPT/nodes + owner `Format Data` and ADB capacity) |
| 04 Repartition | Plan `userdata`/`darwin` for disk size; owner executes; re-read GPT and check Android | Primary/backup GPT valid, bounds accurate, Android boots | Passed (GPT/nodes + owner `Format Data` and ADB capacity) |
| 05 Match Config & Build | Match loader/kernel to new layout/GUID; rebuild as needed; verify image/UEFI/ramdisk/payload SHA-256 | Sources, device config, and artifacts align and pass packaging checks | Host passed; owner later confirmed iOS boot |
| 06 Write & Readback | Owner flashes verified image to `darwin`; read back exact `darwin.img` byte range | Readback SHA-256 matches host `darwin.img` (never rely on `fastboot OKAY` alone) | Passed (TWRP readback of 8,365,539,328 bytes matched; no fastboot log saved) |
| 07 Boot & Teardown | RAM-boot UEFI per docs; check SpringBoard, touch, GPU, Wi-Fi/Safari, brightness, peripherals; reboot to Android | Logs + owner confirmation; gaps documented; docs/validation updated | Owner confirmed iOS boot; per-item regression & Android reboot pending |

Stages 03/04 wipe Android user data (in-place shrink with data preservation is out of scope). Re-read live GPT rather than reusing historical coordinates; device writes are executed by the owner only after reviewing the plan; never use another device's GPT/GUID or overwrite identity/calibration partitions. Stop immediately on any SHA-256 mismatch.

## Completion Criteria

- Evidence recorded per stage without skipping post-restore Android checks; pre-repartition boot results do not replace first-install results.
- Written system image is verified by byte-exact readback and traced to repo commit, diffs, and local config.
- Install tutorials reflect actual steps and explicitly note verification bounds (short boot != long-term stability or full charging).
- Public content scrubbed of private backups, GUIDs, and raw logs; reviewed tools/docs merged to `main`.

## Per-Round Logging

Develop sequentially inside `work/` with per-round logs under `work/runs/YYYYMMDD-first-install-NN/` and recovery backups under `local/backups/YYYYMMDD-first-install-NN/` registered in `local/index.json`. Keep live branch/handoff state solely in [Development Handoff](DEVELOPMENT.md) and product capabilities in [STATUS](../STATUS.md).

References: [Install Guide](../install/INSTALL.md), [Existing-Partition Testing](../install/EXISTING_INSTALL.md), [Validation Log](../validation/VALIDATION.md).

## 2026-10-30 Read-Only Check

Device held ~89.09 GiB `userdata` and ~24 GiB `darwin`. Primary/backup GPT CRCs on `sda` passed and matched; compared with pre-partition backup, only entries #21/#22 differed (historical `userdata` ~113.09 GiB). `/data` mounted RW with FBE. No writes/reboots performed; logs in `work/runs/20261030-first-install-01/` and GPT backups in `local/backups/20261030-first-install-01/`.

## 2026-10-30 Android Layout Restore and Reboot Verification

Owner confirmed discarding Android user data and keeping TWRP 3.7. Verified historical GPT SHA-256 and dry-run restore; initial script halted cleanly on TWRP `awk` crash before writing GPT, and v2 used `grep` checks executed by the owner.

After restore, primary/backup GPT matched verified backup (`userdata` 113.09 GiB, `darwin` removed); after re-entering Recovery (round 03), kernel reported `userdata` 121,425,080,320 bytes and no `darwin` node. Evidence in `work/runs/20261030-first-install-02/` and `-03/`.

## Post-Format Android Check

Owner completed TWRP `Format Data` and Android setup; ADB confirmed `sys.boot_completed=1` and `/data` total 116,193,656 KiB (~110.81 GiB), available 114,887,932 KiB (~109.57 GiB). Stage 03 passed (evidence in `work/runs/20261030-first-install-04/`).

## Stage 04: ~24 GiB `darwin` Repartitioning

Round 05 re-read live GPT matching restored Android layout and prepared a plan with ~89.09 GiB `userdata` and 1 MiB-aligned `darwin` (`25,769,795,584` bytes, 8,192 bytes shy of 24 GiB). `sgdisk --pretend` dry-run passed; host/device syntax and transfer digests checked (`work/runs/20261030-first-install-05/`, `local/backups/20261030-first-install-05/`).

### Round 05 & 06 Execution

Owner ran the partition script; readback primary/backup GPT CRCs and entries matched plan (`userdata` 95,655,297,024 bytes, `darwin` 25,769,795,584 bytes) while partitions #1–#20 and disk geometry remained intact. In Round 06 after rebooting TWRP, GPT matched byte-for-byte with updated kernel partition nodes before owner ran `Format Data` on `userdata` (`work/runs/20261030-first-install-06/`).

### Round 07: Post-Repartition Android Check

Owner confirmed `Format Data` and Android setup with `sys.boot_completed=1` and `/data` total 91,422,752 KiB (~87.19 GiB), available 90,118,260 KiB (~85.94 GiB), passing Stage 04 (`work/runs/20261030-first-install-07/`). Steps were generalized into [Darwin Partition Tool](../install/PARTITION_DARWIN.md).

## Round 08: Config Match & Loader/UEFI Build

Round 06 GPT showed identical `darwin` start/end LBAs and type GUID with a new unique partition GUID, requiring only loader/UEFI rebuild while keeping kernel UFS bounds intact. After backing up old local files, `loader.c` unique GUID was updated in gitignored `work/` and `bash tools/build-loader-uefi.sh` exited `0`, verifying the new GUID inside the embedded UEFI firmware volume (`BootShim+FD+USB XNUP`) and matching DTB. `darwin.img` (8,365,539,328 bytes) matched pinned inputs, and a 300 s candidate payload was staged under `work/runs/20261030-first-install-08/`.

## Round 09: `darwin.img` Readback Verification

Under TWRP with `darwin` matching Round 06 and unmounted, readback of the exact 8,365,539,328 bytes gave SHA-256 `9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560`, matching host `darwin.img` identically (`dd` byte count and exit codes verified; Stage 06 passed; `work/runs/20261030-first-install-09/`).

## Round 10: iOS Boot Success on New Partition

Fastboot detected `product: xnuloader` running the Round 08 300 s read-only candidate (`ufs_write` disabled), and the owner confirmed clean boot into iOS without issues (`boot.log` captured `oem run OKAY` only). Per-peripheral regression and post-exit Android reboot remain pending (`work/runs/20261030-first-install-10/`). Installation tutorials were split into [Install Guide](../install/INSTALL.md) and [Startup Guide](../install/STARTUP.md).
