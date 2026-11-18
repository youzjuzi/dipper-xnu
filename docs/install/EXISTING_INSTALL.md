# Testing New Builds on an Existing `darwin` Partition

**English** | [简体中文](../zh-CN/docs/install/EXISTING_INSTALL.md)

This workflow verifies "source build -> boot on existing layout" without re-testing initial repartitioning. If the installed `darwin` system span already matches `darwin.img` byte-for-byte, reflashing can be skipped (never log a skipped flash as a fresh flash test).

## 1. Verify Existing Layout and System Span Read-Only

Inspect under root ADB (e.g. Magisk) or verified recovery without unlocking or formatting purely for checks:

```sh
adb devices -l
adb shell "su -c 'blockdev --getss /dev/block/sda; blockdev --getsize64 /dev/block/sda; blockdev --getsize64 /dev/block/by-name/darwin'"
adb shell 'ls -l /dev/block/by-name/darwin /dev/block/by-name/userdata'
```

Verify primary/backup GPT CRCs, bounds, type/unique GUIDs, sizes, and mounts. Note Linux sysfs `start`/`size` values use 512-byte sectors rather than 4096-byte GPT LBAs. Run verified readback per [Section 6 of Install Guide](INSTALL.md#6-writing-the-system-image-and-readback-verification) inside Recovery: the first `8,365,539,328` bytes must match host `darwin.img` (this covers the system span, not trailing runtime slots).

## 2. Stage Device GPU Firmware

Verify Android/MIUI versions and extract the four GPU blobs with device/host SHA-256 checks into `work/hackios/fw-gpu/` per [Device Preparation](DEVICE_PREPARATION.md) (baseline `Android 10 / MIUI V12.5.2.0.QEACNXM`; blobs stay out of Git).

## 3. Match Sources and Rebuild

Match GPT bounds and GUIDs per [Matching Sources to a New Partition](STARTUP.md#1-matching-sources-to-a-new-partition) (keeping real GUIDs private in `local/`):

```sh
bash tools/build/build-loader-uefi.sh
bash tools/build/build-userland.sh
python3 tools/build/build-payload.py --output work/runs/desktop-01 --seconds 300
```

`build-payload.py` verifies GPU firmware inside `root.apfs` and rejects existing output dirs. Default payload boots UFS read-only with A630 graphics, touch, and buttons without Wi-Fi or storage writes.

## 4. Temporary Boot and Log Capture

Check `sha256sum -c SHA256SUMS` inside the candidate directory, then boot via RAM per [Temporary RAM Boot](STARTUP.md#3-temporary-ram-boot) and pull logs from `xnuloader`:

```sh
fastboot getvar product  # Must return xnuloader
fastboot getvar result
fastboot oem log
fastboot get_staged kernel-log.txt
```

Verify rootfs mount, SpringBoard logs, physical display, and touch, and perform a full reboot after each run before starting another.

## 5. Wi-Fi and Web Browsing Test

After rebooting to Android, stage verified `firmware-5.bin` per [WCN3990 Wi-Fi Feature File](../build/INPUTS.md#wcn3990-wi-fi-feature-file), rebuild userspace, and package:

```sh
python3 tools/build/build-payload.py --wifi --seconds 900 --output work/runs/wifi-01
```

This enables Mi 8 MSS/GLINK/WLFW + `ath10k` station mode reading MBA/modem/wlanmdsp/bdwlan from the phone's `modem` partition (`local/wifi-mac` supplies a locally administered unicast MAC; boot args stay below 608 bytes). Enter Wi-Fi credentials manually on the phone, verify `en0` IP/routing/DNS and actual page loads/refreshes in Safari, and keep raw logs containing SSIDs/MACs/URLs inside gitignored run dirs.

Note: if Wi-Fi fails after `FW_READY` with `no 46137344 bytes of memory in one piece` / `rc=12`, the kernel patch pre-reserves contiguous DMA memory before modem startup and requires rebuilding `ath10k` + kernel rather than tweaking Wi-Fi settings. Because `xnuloader`'s log buffer is bounded, capture early init logs periodically right after `oem run` (e.g., every 2 s for the first 100 s).

## 6. Peripherals and Interactive Desktop Test

```sh
python3 tools/build/build-payload.py --wifi --peripherals --seconds 900 --output work/runs/peripherals-01
```

(`--peripherals` is now a compatibility flag since `battery=1 torch=3 haptic=3` are `dipper` defaults; Wi-Fi can be disabled by omitting `--wifi`; Mi 8 uses PMIC haptics rather than `aw8697_haptic.bin`.) Verify the 578-byte expanded cmdline fits under the 607-byte cap, boot per Section 4, and check each item with logs:

| Item | Verification Criteria |
| --- | --- |
| Display brightness | Adjust slider in Control Center and Settings and confirm physical backlight changes |
| Lock / Wake / Touch | Power-button lock and wake 3 times; verify swipe and tap after wake |
| Torch | Toggle on ~2 s and off twice; note brightness steps separately |
| Haptics | Long-press icons or Control Center controls and verify physical feedback + actuator logs |
| Volume buttons | Hardware buttons and slider respond (separate from speaker audio verification) |
| Battery gauge | Compare UI percentage against pre-boot Android/PMIC readings (does not prove charging) |
| Wallpaper & widgets | Background and widgets render cleanly (persistence tested separately under `--persist`) |
| Wi-Fi regression | Reconnect and load/refresh web pages with all peripherals enabled |

Note on the 2026-10-30 brightness fix: DSI command buffers allocated above 4 GiB broke 32-bit DMA registers; the fix constrains `kmem_alloc_contig` physical pages and properly frees buffers on error ([Device Validation Data](../validation/device-validation-20261030.json)). Torch dimming steps (subtle visually), full charging cycles, persistent store reliability, and unported sensors/cellular require separate verification.
