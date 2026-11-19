# Configuration, Rebuild, and Temporary RAM Boot

**English** | [简体中文](../zh-CN/docs/install/STARTUP.md)

Complete [Partitioning, Flashing & Rollback](INSTALL.md) first or confirm your existing `darwin` partition and image readback match. Use this page for iterative boots and development without repartitioning or reflashing the system image each round. Verified capabilities and gaps are listed in [STATUS](../STATUS.md).

## 1. Matching Sources to a New Partition

Public patches strip the development device's unique partition GUID to an all-zero placeholder. Before building for a device, match your partition layout in loader and kernel sources:

| File (under `work/hackios/`) | Parameters to Match |
| --- | --- |
| `xnuloader/loader.c` | `BLOCK_DARWIN_FIRST`, `BLOCK_DARWIN_LAST`, `BLOCK_DARWIN_TYPE`, `BLOCK_DARWIN_UNIQ` |
| `xnu-src/xnu-8796.121.2/bsd/dev/redwood_ufs.c` | `UFS_DARWIN_FIRST`, `UFS_DARWIN_BLOCKS`, writable data region bounds |
| If using upstream `tools/darwin-write.py` | Partition number, node, GUID, sector size, bounds, protected range (upstream defaults are not `dipper`) |

Convert GUIDs into the C struct fields carefully—raw GPT byte order differs for the first three fields rather than copying string digits verbatim. Rebuild the kernel if bounds change; if only the unique partition GUID changes, rebuilding the loader and UEFI suffices. Modify device parameters in `work/` after `prepare.py` hash verification (reviewed manually until automated config input is added).

## 2. Rebuild by Change Scope and Package a Candidate

Develop inside `work/`. Back up existing loader sources/binaries, UEFI/BootShim/FD, and configs to `local/backups/<run-id>/` before overwriting, and store each test run in a fresh `work/runs/<run-id>/`:

| Change | Required Rebuild |
| --- | --- |
| `darwin` unique GUID only | Update `loader.c`, rebuild loader and UEFI |
| Partition start/size or kernel code | Sync loader/kernel bounds, rebuild kernel (`tools/build/build-kernel.sh`) and loader/UEFI |
| Userspace, GPU/Wi-Fi/BT/audio firmware, or configs | Rebuild APFS volumes (`tools/build/build-userland.sh`), then repack payload |
| Boot arguments only | Repack into a new candidate directory, preserving previous ones |

From repository root after [Build Guide](../build/BUILD.md) and [Userspace Build](../build/USERLAND.md):

```sh
bash tools/build/build-loader-uefi.sh
: "${RUN_ID:?Set a unique run ID}"
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 300 --wifi --link-inputs
(cd "work/runs/$RUN_ID/candidate" && sha256sum -c SHA256SUMS)
```

Wi-Fi requires verified firmware; omit `--wifi` for radio-off baselines, or add `--no-audio` to mute speaker audio. Candidates default to 300 s and read-only storage (`--persist` enables `/private/var` persistence below). See [Existing-Partition Testing](EXISTING_INSTALL.md) for test matrices. `build-loader-uefi.sh` embeds the USB XNUP payload so `xnuloader` exposes its fastboot service.

### Short `dipper` Boot Arguments and Defaults

Short cmdlines require a kernel carrying the `dipper` defaults table; the kernel enables these defaults strictly when device-tree `/arm-io/device_type` equals `"dipper"` (the physical platform node, distinct from the emulated iPhone root identity). Other targets keep standard behavior.

| Profile | Boot Arguments |
| --- | --- |
| `daily` | `bootcpu=7 cpus=7 ufs=2 root_apfs=ufs_darwin epoch=<UNIX_TIME> wifi_mac=<LOCAL_WIFI_MAC>` |
| `bench` extras | `loader_return_after=360 taskload=500 touch_lat=1 mi8_cpuclk=10 perfprof=1 fprof=1000` |

`epoch` comes from host time and `wifi_mac` comes from private `local/wifi-mac`. `bootcpu`, `cpus`, `ufs`, and `root_apfs` must stay explicit; a matching loader prepares battery shared memory and torch identity on `dipper` by default (`battery=0`/`torch=0` disable).

All 33 defaults live in `pexpert/arm/pe_bootargs.c`, shared by the kernel parser and userspace `kern.bootargs`:

| Parameter | `dipper` Default |
| --- | --- |
| `fts` | `1` |
| `fts_steps` | `6` |
| `fts_raw` | `0` |
| `buttons` | `1` |
| `buttons_steps` | `5` |
| `gpu` | `1` |
| `mi8gpu_gmuclk` | `1` |
| `mi8gpu_zap_keep` | `1` |
| `fb_partial` | `0` |
| `fb_flip` | `1` |
| `fb_native` | `2` |
| `sb_fps_clamp` | `1` |
| `mi8rp_mss` | `6` |
| `mi8rp_hold` | `90` |
| `mi8rp_svc` | `1` |
| `mi8rp_servreg` | `1` |
| `mi8rp_wlfw` | `1` |
| `mi8rp_bdf` | `1` |
| `mi8rp_wsmmu` | `3` |
| `mi8rp_lx` | `1` |
| `mi8rp_lxirq` | `1` |
| `wifi_lx` | `2` |
| `wifi_station` | `1` |
| `wifi_quiet` | `1` |
| `thermgov` | `66` |
| `ffix` | `1` |
| `bt` | `7` (iOS Bluetooth; skipped if Wi-Fi side disabled) |
| `audio` | `5` (speaker session) |
| `audio_level_db` | `0` (0 dB digital gain) |
| `audio_seconds` | `0` (resident) |
| `battery` | `1` |
| `torch` | `3` |
| `haptic` | `3` |

Explicit arguments (including `=0`) take precedence (`fb_native=0`, `fb_native=1`, `thermgov=0`, `ffix=0`, `caenv=FD_MESA_DEBUG=sysmem` to force sysmem debug, etc.). Early `bootcfg:` logs label `arg` vs `def` without printing `wifi_mac` values. When `--wifi` is omitted, `build-payload.py` appends `mi8rp_mss=0 wifi_lx=0 wifi_station=0 bt=0`; `--peripherals` and `--bluetooth` remain compatibility no-ops (`--bluetooth` still requires `--wifi`); `--no-audio` appends `audio=0`.

With a 10-digit epoch and 17-char MAC, `daily` is 87 bytes and `bench` is 172 bytes (167 / 252 bytes with the conservative 80-byte loader prefix, leaving 347 additional bytes below `< 600`). Loader input remains capped at 608 bytes while the kernel holds the expanded config in a 2048-byte `kern.bootargs` buffer.

### Persistent Data Volume

Normally iOS `/private/var` (home layout, settings, app data) runs in RAM and resets every reboot. Adding `--persist` reads back saved data on boot and writes it back on clean exit:

```sh
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 300 --persist
```

- Appends `ufs_write=1 var_store=1 var_save_ms=120000`. **Writes storage**: loader and kernel restrict writes strictly to `darwin` blocks >= `2042368` (after the rootfs and both cryptexes), alternating across two 2 GiB slots starting at block `2097152` with readback verification; other partitions are refused.
- Saves only on orderly exit (`--seconds` >= 180 required) or host `oem stop`; long-pressing power or panicking preserves the previous slot untouched. Do not unplug or force-off during save (up to 120 s after timeout).
- Header is written last; reads load the latest CRC-verified slot or fall back cleanly to blank `/private/var`.
- Read-only restore without saving: pass `var_store=1` without `ufs_write=1`.
- Both slots and active `/private/var` live within 2 GiB per slot (logs/caches/temp dirs excluded).
- Clear saved state in TWRP (verify the `darwin` block node first!): `dd if=/dev/zero of=/dev/block/<darwin-node> bs=4096 seek=2097152 count=1048576` (system volume stays intact).
- Periodic saving, crash recovery, and long-term store growth are not yet tested.

### Bluetooth (Enabled by Default)

Stage `work/hackios/fw-bt/` (`crbtfw21.tlv`, `crnv21.bin` per [Bluetooth Firmware](DEVICE_PREPARATION.md#5-bluetooth-firmware)), rebuild userspace (`BT=1`), and package with `--wifi`:

```sh
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 600 --wifi
```

Default `bt=7` requires `fw-bt/` in `flashboot.apfs` and BT daemons in `root.apfs`; skipped automatically if `mi8rp_mss=0` or `wifi_mac` is absent; `bt=0` disables explicitly. Shares power rails with Wi-Fi and derives BT address from `wifi_mac` without writing storage.

- Waits `bt_delay` seconds (default 60) after boot before uploading firmware (~70 s total readiness).
- Toggles, scanning, pairing, and headset connections work; Bluetooth audio routing is unimplemented and pairings do not persist across reboots unless tested with persistence.
- Kernel BT logs carry prefix `bt:`; rejected vendor commands log `bridge: the chip refuses`.

### Speaker Audio and Peripherals Enabled by Default

Speaker audio needs one user-extracted file: `tas2557_uCDSP_goer.bin` pulled read-only via Android root into `work/hackios/fw-audio/` before rebuilding userspace (`flashboot.apfs` `/fw/`); ADSP firmware is read by the kernel directly from the phone's `modem` partition.

Matching kernel and loader enable `audio=5`, `battery=1`, `haptic=3`, and `torch=3` by default on `dipper` (disable individually with `=0`; verified in a zero-arg device trial on 2026-11-12).

`audio_level_db` accepts `-30`/`-24`/`-20`/`-12`/`-6`/`0` (default `0` dB). `audio_seconds=0` runs residently (bounded only by `loader_return_after` if set), while `1..900` caps bounded diagnostics to 900 s / 45000 periods / 200 wakes. Resident mode keeps all LIVE, state, clock, mono/amplitude, buffer-bounds, health, and fault-latch guards active.

When `mi8rp_mss` is enabled, audio waits up to 90 s for Wi-Fi `FW_READY` before initializing. Resident mode soft-shuts-down the amp after 10 s (post-wake all-zero) or 30 s silence while ADSP/DMA continue 20 ms framing; long-term power draw and acoustic tuning remain to be verified.

### Bluetooth Chip Diagnostics (Experimental)

`bt=N` runs diagnostic bring-up up to step `N` (`bt=0` disables): `1` read-only probe, `2` UART clock enable, `3` internal loopback, `4` 5-rail RPMh power + `0xFC` pulse + HCI Reset/version, `5` rampatch+NVM download at 115200 baud (~25 s), `6` 3.2 Mbaud download (~1 s), `7` full iOS `bluetoothd` bridge. Steps 5–6 require firmware in `flashboot.apfs` and bounded `loader_return_after`; see [Bluetooth UART Link](../validation/VALIDATION.md#bluetooth-uart-link).

### Optional Reduced Render Scale

Append `fbscale=2 fb_dpu=1` to `daily` args to render iOS at `750x1624` (`@2x`, ~44% of `1125x2436` pixels):

| Parameter | Behavior |
| --- | --- |
| `fbscale=2` | Reports `750x1624 @2x` and writes scale to device tree |
| `fb_dpu=1` | Requires `fb_native=2` (default zero-copy WC scanout pool) or `fb_native=1`; keeps `750x1624` flip buffers and scales via DPU QSEED3 (zero-copy scanout under `fb_native=2`, or `~0.5 ms` CPU blit under `fb_native=1` instead of multi-ms CPU scaling) |

Requirements and caveats:

- Match kernel and userspace `root.apfs`: the SpringBoard shim swaps UIKit's fallback status bar for iPhone X split layout (fixing the `rdar:45025538` red bar).
- Because MobileGestalt has no screen class for `750x1624 @2x` (or `828x1792 @2x`), PosterBoard draws black; the SpringBoard shim overlays `/redwood/etc/wallpaper.jpg` (or a gradient fallback; Settings wallpaper changes have no effect). Add `still_wall=1` to also overlay a static image at native resolution.
- `fbscale` cannot be combined with `fbwidth`/`fbheight`. Output looks softer, and Settings / Messages crashed in some scaled boots (root cause open); full regression under scaled mode is pending ([VALIDATION](../validation/VALIDATION.md)).

## 3. Temporary RAM Boot

Daily iOS boots do not reflash or enter TWRP. From vendor bootloader fastboot (`BOOT_SERIAL`, **not** TWRP ADB), run from host Bash:

```sh
: "${BOOT_SERIAL:?Set vendor fastboot serial}"
: "${CANDIDATE:?Set absolute path to candidate dir}"
(cd "$CANDIDATE" && sha256sum -c SHA256SUMS)
fastboot -s "$BOOT_SERIAL" getvar product
# Continue only when product is dipper and hashes pass.
fastboot -s "$BOOT_SERIAL" boot "$CANDIDATE/boot-dipper.img"
```

Wait for `xnuloader` to re-enumerate over USB (ensure no other phones are connected):

```sh
fastboot devices
fastboot -s xnuloader getvar product
# Continue only after product returns xnuloader.
fastboot -s xnuloader oem ramdisk
fastboot -s xnuloader stage "$CANDIDATE/flashboot.apfs"
fastboot -s xnuloader stage "$CANDIDATE/payload.bin"
fastboot -s xnuloader oem run
```

All staged files must come from the same verified candidate (`ufs=2 root_apfs=ufs_darwin`, read-only unless `--persist` was chosen).

## 4. Verification, Logs, and Shutdown

`boot` screen, `xnuloader`, and `fastboot OKAY` only prove their respective stages—verify the actual screen, touch, kernel mounts, and logs. When `xnuloader` responds after return (or via `oem stop`), pull logs into a new run directory:

```sh
fastboot -s xnuloader getvar result
fastboot -s xnuloader oem log
fastboot -s xnuloader get_staged "$LOG_DIR/kernel-log.txt"
```

Because GPU SMMU and modem exit recovery remain incomplete, perform a full reboot between runs rather than re-running immediately. Check Android boot and `/data` upon returning; only use [Rollback to Android Layout](INSTALL.md#7-rollback-to-android-layout) if removing dual-partition setup.
