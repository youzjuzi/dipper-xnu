# Device Version, TWRP, and Firmware Preparation

**English** | [简体中文](../zh-CN/docs/install/DEVICE_PREPARATION.md)

Read this page before [Partitioning and Flashing](INSTALL.md) and [Userspace Build](../build/USERLAND.md). Read-only firmware extraction does not require repartitioning or formatting Data. Firmware blobs, Recovery images, device identifiers, and raw logs must never be committed to Git.

Verify your device version in Section 1 first: if you already have Android root, use `MODE=root` in Section 3 directly without booting into TWRP solely to pull firmware. See Section 2 if you need Recovery.

## 1. Verified Device Baseline

| Item | Recorded Baseline | Evidence & Scope |
| --- | --- | --- |
| Device | Xiaomi Mi 8 (`dipper`), SDM845 / A630 | Verified target hardware |
| Android | Android 10 | Verified on device (2026-10-31) |
| MIUI | `V12.5.2.0.QEACNXM` | Tested baseline; other versions do not need forced downgrade |
| Recovery | TWRP `3.7.0_9-0` | Verified via `getprop` and `uid=0` inside Recovery |
| Target System Volume | iOS 16.5 / `20F66` | Pinned repository input; tracked separately from Android version |
| Android Root | `su` returned `uid=0` (2026-10-31) | `MODE=root` firmware extraction verified on hardware |

Record your own device versions before reusing these steps rather than assuming another phone matches the baseline device. See [Validation Log](../validation/VALIDATION.md) for full scope.

With Android booted and USB debugging authorized, check your target serial in Bash:

```sh
adb devices -l
export DEVICE_SERIAL='<your-adb-serial>'
adb -s "$DEVICE_SERIAL" shell 'getprop ro.product.device; getprop ro.build.version.release; getprop ro.build.version.incremental; getprop ro.miui.ui.version.name; getprop ro.build.fingerprint'
```

Save these outputs and distinguish the full MIUI build string from the marketing version. `getprop` values inside TWRP can come from the Recovery image itself rather than the installed Android OS. Record private device provenance under `local/devices/<alias>/` and update `local/index.json`; keep public docs scrubbed.

## 2. Obtaining and Verifying TWRP

- [Team Win Xiaomi Mi 8 device page](https://twrp.me/xiaomi/xiaomimi8.html): confirms codename `dipper` and installation notes.
- [Official dipper download directory](https://dl.twrp.me/dipper/).
- [3.7.0_9-0 download page](https://dl.twrp.me/dipper/twrp-3.7.0_9-0-dipper.img.html): image, `.sha256`, and PGP signature link.

Verified available upstream on 2026-10-31; using "latest" without testing does not prove compatibility, and images for other Mi 8 variants must never be substituted. If a working `dipper` TWRP is already installed, do not reflash it.

Download the image and `.sha256` file into a dedicated directory under workspace `downloads/` without renaming, and verify:

```sh
sha256sum -c twrp-3.7.0_9-0-dipper.img.sha256
```

If only plain hash text is listed on the page, verify `sha256sum twrp-3.7.0_9-0-dipper.img` character-for-character against the page—stop on mismatch rather than altering the checksum file. Checking a hash from the same mirror checks transfer integrity, not independent signature trust. Record source URL, download date, SHA-256, and local path privately. Note that temporary `fastboot boot` of iOS UEFI is unrelated to TWRP installation (see [Startup Guide](STARTUP.md)).

### Already Have TWRP Installed

If TWRP is already installed and Android ADB is authorized:

```sh
: "${DEVICE_SERIAL:?Set and verify ADB serial}"
adb -s "$DEVICE_SERIAL" reboot recovery
```

If ADB is unavailable, power off and hold **Volume Up + Power**, releasing after the Mi logo appears (key combo per [LineageOS dipper specs](https://github.com/LineageOS/lineage_wiki/blob/main/_data/devices/dipper.yml)). If stock Recovery appears instead, stop—TWRP commands do not apply.

### First-Time TWRP Installation (Official Route)

Applies only when TWRP is needed on a `dipper` with an unlocked bootloader and verified recovery backups. Steps below follow Team Win's official `dipper` instructions; this project verified maintenance inside TWRP without separately re-testing initial TWRP flashing:

1. Verify the `dipper` TWRP image digest and ensure backups exist (do not unlock the bootloader just to test commands—unlocking wipes user data).
2. Reboot into vendor bootloader fastboot:

```sh
adb -s "$DEVICE_SERIAL" reboot bootloader
fastboot devices
```

3. Select the vendor fastboot serial (not `xnuloader`), verify `product` is `dipper`, and verify `recovery` exists:

```sh
: "${BOOT_SERIAL:?Set verified vendor fastboot serial}"
: "${TWRP_IMAGE:?Set verified TWRP image path}"
fastboot -s "$BOOT_SERIAL" getvar product
fastboot -s "$BOOT_SERIAL" getvar partition-size:recovery
sha256sum "$TWRP_IMAGE"
```

4. Only after checks pass, flash specifically to `recovery` (never `boot` or whole disk):

```sh
fastboot -s "$BOOT_SERIAL" flash recovery "$TWRP_IMAGE"
```

5. Hold the Recovery key combo immediately after running:

```sh
fastboot -s "$BOOT_SERIAL" reboot
```

6. Verify version and root once inside TWRP (`fastboot OKAY` alone does not verify Recovery). Do not combine TWRP setup with formatting Data or repartitioning.

### Recovery Verification

```sh
adb -s "$DEVICE_SERIAL" shell 'id; getprop ro.product.device; getprop ro.twrp.version; cat /proc/mounts'
```

Confirm `dipper`, `3.7.0_9-0`, and `uid=0`. TWRP does not bundle the verified `sgdisk` binary required for partitioning; see [Install Guide](INSTALL.md).

### TWRP vs. iOS Boot

| Task | Entry Point | Need to Reflash TWRP? |
| --- | --- | --- |
| Pull GPU firmware via Android root | Section 3 below | No |
| Repartition, `Format Data`, `darwin.img` readback | Existing TWRP + [Install Guide](INSTALL.md) | No |
| Daily iOS RAM boot | Vendor `fastboot boot boot-dipper.img` -> `xnuloader` | No ([Startup Guide](STARTUP.md)) |

## 3. GPU Firmware Manifest

Digests below come from the tested MIUI `V12.5.2.0.QEACNXM` device files (not compared byte-for-byte against stock OTA ZIPs). Stop and investigate if another ROM version differs rather than bypassing build checks:

| Phone Path | Verified SHA-256 |
| --- | --- |
| `/vendor/firmware/a630_gmu.bin` | `b07f90299ff2ae33948fcfd6ed67f53fbd287b5bf85ff2d43db11d4d32c1621f` |
| `/vendor/firmware/a630_sqe.fw` | `34edacb6fdedfbfc07ed5cd1d29b0b57a3543ef5be6ab34a43bd64686826fa1e` |
| `/vendor/firmware/a630_zap.mdt` | `f369d5614503a516a6443887f04dd8497cc7127b1ff3429c492666b26a9ab34b` |
| `/vendor/firmware/a630_zap.b02` | `519b5538809f54ee566246b0520746a8ea82ca9384ea6bddb0b0e0d3c2de520c` |

### Read Preconditions in Android and TWRP

- **Android**: Try plain ADB read first; if permission is denied, use `MODE=root` only when `su` is already installed and authorized (never unlock/wipe purely to extract).
- **TWRP**: Verify `/vendor/firmware/` comes from the phone's `vendor` partition mounted read-only (`/proc/mounts`); if unmounted, mount Vendor via TWRP's GUI rather than guessing block nodes.

In TWRP:

```sh
adb -s "$DEVICE_SERIAL" shell 'cat /proc/mounts; ls -l /vendor/firmware/a630_gmu.bin /vendor/firmware/a630_sqe.fw /vendor/firmware/a630_zap.mdt /vendor/firmware/a630_zap.b02'
```

Before Android `MODE=root`:

```sh
adb -s "$DEVICE_SERIAL" shell getprop sys.boot_completed
adb -s "$DEVICE_SERIAL" exec-out su -c id
```

Expect `1` and `uid=0`.

### Extract and Verify on Both Ends

Run from repository root in Bash with a fresh `RUN_ID` (never overwrite previous runs):

```bash
set -euo pipefail
: "${DEVICE_SERIAL:?Set target ADB serial}"
: "${RUN_ID:?Set new run directory ID}"
MODE=android  # android / root / recovery per read preconditions above
case "$MODE" in android|root|recovery) ;; *) exit 1 ;; esac
OUT="work/runs/$RUN_ID"
mkdir "$OUT"
mkdir "$OUT/gpu"
cat > "$OUT/gpu/SHA256SUMS" <<'HASHES'
b07f90299ff2ae33948fcfd6ed67f53fbd287b5bf85ff2d43db11d4d32c1621f  a630_gmu.bin
34edacb6fdedfbfc07ed5cd1d29b0b57a3543ef5be6ab34a43bd64686826fa1e  a630_sqe.fw
f369d5614503a516a6443887f04dd8497cc7127b1ff3429c492666b26a9ab34b  a630_zap.mdt
519b5538809f54ee566246b0520746a8ea82ca9384ea6bddb0b0e0d3c2de520c  a630_zap.b02
HASHES
for name in a630_gmu.bin a630_sqe.fw a630_zap.mdt a630_zap.b02; do
    remote="/vendor/firmware/$name"
    if [ "$MODE" = root ]; then
        before=$(adb -s "$DEVICE_SERIAL" exec-out su -c "sha256sum $remote")
        adb -s "$DEVICE_SERIAL" exec-out su -c "cat $remote" > "$OUT/gpu/$name"
        after=$(adb -s "$DEVICE_SERIAL" exec-out su -c "sha256sum $remote")
    else
        before=$(adb -s "$DEVICE_SERIAL" exec-out sha256sum "$remote")
        adb -s "$DEVICE_SERIAL" pull "$remote" "$OUT/gpu/$name"
        after=$(adb -s "$DEVICE_SERIAL" exec-out sha256sum "$remote")
    fi
    local_hash=$(sha256sum "$OUT/gpu/$name")
    [ "${before%% *}" = "${after%% *}" ]
    [ "${before%% *}" = "${local_hash%% *}" ]
    printf '%s\n' "$before" >> "$OUT/device-sha256.txt"
done
(cd "$OUT/gpu" && sha256sum -c SHA256SUMS)
```

Stop on any failure. Extraction passes only when before/after phone digests, host digests, and pinned digests all match.

### Stage into Build Tree

Copy verified blobs into `work/hackios/fw-gpu/` without blindly overwriting differing files:

```bash
set -euo pipefail
: "${OUT:?Set verified extraction directory}"
(cd "$OUT/gpu" && sha256sum -c SHA256SUMS)
mkdir -p work/hackios/fw-gpu
for name in a630_gmu.bin a630_sqe.fw a630_zap.mdt a630_zap.b02; do
    target="work/hackios/fw-gpu/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        cmp "$OUT/gpu/$name" "$target"
    else
        cp -n "$OUT/gpu/$name" "$target"
        cmp "$OUT/gpu/$name" "$target"
    fi
done
```

Log provenance under `local/devices/<alias>/` and update `local/index.json`; keep `work/` and `local/` private.

## 4. Wi-Fi Firmware and Subsequent Builds

Wi-Fi uses two inputs:

- MBA, modem, `wlanmdsp`, and board data from the phone's `modem` partition are read directly by the kernel at runtime (no manual `adb pull` needed; never substitute board data from other devices).
- `firmware-5.bin` (WCN3990 feature flags; origin and SHA-256 in [External Inputs](../build/INPUTS.md#wcn3990-wi-fi-feature-file)), placed at `work/hackios/fw-wifi/firmware-5.bin`.

Once inputs are staged, configure Theos/SDK per [Userspace Build](../build/USERLAND.md), run `bash tools/build/build-userland.sh`, and package a new run with `tools/build/build-payload.py` (which re-verifies firmware inside the APFS images). See [Startup Guide](STARTUP.md) for device config matching and boot sequence.

## 5. Bluetooth Firmware

WCN3990 Bluetooth firmware resides on the phone's `bluetooth` partition (FAT, mounted as `/bt_firmware` in Android) under `image/`. The Mi 8 chip uses ROM version `0x21`, requiring two files (ignore `crbtfw11/20`, `apbtfw*`, `crnv11/20`):

| File | Size (bytes) | SHA-256 (tested MIUI V12.5.2.0.QEACNXM phone) |
| --- | --- | --- |
| `crbtfw21.tlv` | 222988 | `2ce84e4dc3267f8401e2f4dbf6137c3902a734ee0011541a3b4d7385bbc07dce` |
| `crnv21.bin` | 4591 | `cf5eef9879a381d1edd0be8aedbe41c765b82ce1edb18eed96ff314c66406a2d` |

Pull via Android root or TWRP (mounting `/dev/block/by-name/bluetooth` read-only without guessing raw block nodes), compare SHA-256 on phone and host, and place them in `work/hackios/fw-bt/` (never committed to Git). `userland/build.sh` (`FLASHBOOT=1`) embeds them under `/fw/` in `flashboot.apfs`, and the kernel (`bt=5..7`) checks the chip ROM version before loading.

## Verification Scope

On 2026-10-31, `MODE=root` extraction of the four GPU firmware blobs was verified on Android 10 / MIUI `V12.5.2.0.QEACNXM` with matching phone/host/pinned SHA-256 digests and zero modification to existing build inputs.

| Path or Check | Verified Status |
| --- | --- |
| Android version, boot complete, `su` root | Verified on hardware |
| `MODE=root` extraction of 4 GPU firmware files | Passed on hardware |
| Before/after device, host, and pinned SHA-256 match | All matched |
| Unprivileged ADB / TWRP firmware extraction | Not tested separately |
| Official initial TWRP flashing instructions | Cross-checked with upstream docs; not re-tested here |
| Post-extraction copy, rebuild, and boot | Not part of this extraction test |

Details in [Validation Log](../validation/VALIDATION.md).
