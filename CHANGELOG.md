# Changelog

**English** | [简体中文](docs/zh-CN/CHANGELOG.md)

Tracks changes affecting usage and builds. See [Reproduction Report](docs/validation/REPRODUCTION.md) for detailed bring-up records and [Feature Status](docs/STATUS.md) for current boundaries.

## 2026-11-19

- **Adreno 630 GMEM enablement, `fb_native=2` zero-copy DPU scanout, and batched GPU SMMU mapping (defaults updated)**:
  - Fixed `MSM_PARAM_GMEM_BASE` (`0x06`) in `bsd/dev/mi8_adreno.c` to return `0x00100000ull` instead of `0` and removed the default `caenv=FD_MESA_DEBUG=sysmem` workaround in `pexpert/arm/pe_bootargs.c`.
  - Implemented and defaulted `fb_native=2` across `MiniIOSurface.h/.cpp`, `RedwoodGPU.cpp`, and `MiniIOMobileFramebuffer.cpp`: builds a 4-slot `1125x2436` Write-Combined scanout pool (`2` splash slots `0x9deb8000`/`0x9e970000` + `2` contiguous `< 4 GB` RAM buffers, preserving Piece 0 `0x9d400000` for boot/fallback/`MiniIOFlipQuiesce()`), skips `dc civac` on WC scanout surfaces, releases `displayReaders` holds without WC CPU readback in `evictSurface()`, and uses TE-aware sleep (`MiniIOFlipWaitHintUs()`) instead of 200 us busy-polling.
  - Raised default periodic cache-flush interval (`GPU_PUSH_AGAIN_MS` / `gpu_push_ms`) from `4 ms` to `100 ms` (preserving immediate flushes on `seed` change) and added O(1) L2/L3 shadow table pointers (`keep_l2_virt`/`keep_l3_virt`), `mi8_gpu_map_range()` / `redwood_gpu_map_range()`, batched `mi8_gpu_unmap()`, and fast SMMU TLB sync polling in `bsd/dev/mi8_adreno.c`, `bsd/dev/redwood_adreno.c`, `bsd/sys/redwood_input.h`, and `iokit/Kernel/RedwoodGPU.cpp`.
  - Device-verified across 4 progressive 300 s RAM-boot rounds (`0` panics, `0` GPU/SMMU faults, clean `slumber answered` + `MiniIOFlipQuiesce`): cache flush fell from `~85 GiB / 5.56 s` (`zc-sysmem`) to `1.75–3.26 GiB / 0.14–0.29 s`, zero-copy flips reached `5698/5700` (`6.87 us` avg, `1.70 ms` max, active `59 FPS` with 95% frame intervals `< 21 ms`), `173.5 ms` WC eviction spikes dropped to `<= 14.56 ms`, `IOSurface` GPU mapping fell from `6.96–8.54 ms` to `0.12–0.18 ms`, and `gGPULock` wait max dropped from `9.44 ms` to `0.20 ms`.
- **Native Wi-Fi status bar signal bars via LQM sizing & Mach service fix**:
  - Identified why the Mi 8 home screen Wi-Fi icon showed 0 active bars despite an active link: `struct apple80211_lqm_event` in `bsd/dev/redwood_apple80211.c` was `0xc0` (192 B), pushing `KEV_MSG_HEADER_SIZE (24) + interface_name (16) + 192 = 232 B` over XNU's `MLEN (224 B)` limit so `kev_post_msg()` silently dropped every `EVENT_LQM_CHANGED (39)` with `EMSGSIZE`.
  - Shrunk `struct apple80211_lqm_event` to `0xb4` (180 B, total `220 <= 224`) with a compile-time `MLEN` `_Static_assert`, normalized RSSI via `clamp_rssi()`, added live `kev_post_msg()` error logging via `redwood_wifi_tell()`, and pre-declared `com.apple.wifi.manager` (`ResetAtClose`) in `com.apple.wifid`'s launchd plist (`userland/mkjobs.py`) to prevent `SpringBoard` startup lookup races.
  - Device-verified (`900 s` Wi-Fi run): `218` `linkQualityDidChange` events in `wifid`, `0` `kev_post_msg` failures, `0` `com.apple.wifi.manager` lookup errors, and active status bar signal bars with no UI hooks.
- **TAS2557 bit-bang I2C busy-spin fix & coefficient-check diagnostics**:
  - Root-caused intermittent post-mute speaker lockouts (`latched=coefficient`): because `dipper` leaves `cpu_idle_latency == 0`, `native_delay()` in `bsd/dev/mi8_tas2557.c` called `delay_for_interval()` and context-switched on every `3 us` bit-bang half-clock, stretching `session_check()` (`486–1000+ ms`) past its `1000 ms` budget under load.
  - Switched `native_delay()` intervals `<= 50 us` to busy-spin (matching `bsd/dev/mi8_fts.c`) and persisted `check_us`, `check_y`, and `check_err` into `mi8_tas_session_report()`, without relaxing `Y == 0x5d` or `1000 ms` hardware protection thresholds.
  - Device-verified across multi-cycle ringtone wake/mute/wake: `session_check()` dropped to `207–208 ms` (`checks=2/2`), wakeup warmup dropped to `31 ms` (`startup=4`, `health=2`, `unmute=3 ms`), `latched=no`, `cleanup=complete`.

## 2026-11-18

- **Wi-Fi DMA hardening, `rx_confused` recovery, and Mi 8 stop summary** (hardware-verified in an 18-minute `0 panic` run alongside Volume HUD & `/apps` sideload): Added `dsb sy` barriers in `lkpi_dma_map_phys` / `lkpi_dma_unmap` / `linuxkpi_dma_sync` and 512-byte head zeroing of recycled RX pool slots in `wifi/lx/src/lx_base.c`; added bounded `rx_confused` diagnostics + timer-assisted refill recovery (`wifi_no_recover=1` to disable), 30 s active health telemetry, race-safe start/stop ordering, and `lx_station_say()` / `lx_memory_say()` stop summaries in `wifi/lx/src-ath10k/lx_ath10k_bus.c`; wired `mi8_wifi_stop()` (`bsd/dev/redwood_lx.c`) into `osfmk/arm64/loader_return.c`.
- **Standard HID ringer switch for Volume HUD**: Declared Telephony Ring Switch (`0x0b` / `0x2e`) on `Redwood buttons` (`userland/src/inject.c`) with `.copyEvent` and initial `down=true` dispatch so `backboardd` leaves silent mode without SpringBoard hooks or private offsets.
- **Sideload union mount settled & live log tooling**: Exported `bsd/vfs/vfs_attrlist.c` (`getattrlistbulk` `MNT_UNION` fall-through traversal), `userland/build.sh` (`APPS=1` default for `/apps`), and clean `/apps` union mount in `userland/src/init.c`; added read-only `tools/tests/device-log.py` (`snapshot`, `watch`, `stop`, plus terminal `returned <bytes> 0` handling) and fixed `build-payload.py --link-inputs` (`import os`).
- **Warm subsystem teardown & cross-run recovery**: Added orderly shutdown paths via `mi8_pcm_session_stop_request()` (`bsd/dev/mi8_audio_pcm.c`), `mi8_bt_stop()` (`bsd/dev/mi8_bt.c`), `mi8_rproc_stop()` (`bsd/dev/mi8_rproc.c`, skipping `WLFW` MSA host reclaim on warm stop), `mi8_gpu_quiesce()` (`bsd/dev/mi8_adreno.c` / `redwood_adreno.c`), plus Wi-Fi Beacon-rate preservation and multi-AP fallback (`wifi/lx/src/lx_80211.c`). Orderly `oem stop` exits in ~5 s (`returned <bytes> 0`), though `halt port modem` still requires cold reboot between baseband runs.
- **Native BT/Wi-Fi UI shim removal, dynamic CPU/DDR governor, and GPU flush coalescing** (hardware-verified): Replaced `libredwood-bt.dylib` with native IOKit `AppleOLYHAL` in `iokit/Kernel/RedwoodBT.cpp`; exposed `"wlan"` parent node + early `en0` in `iokit/Kernel/RedwoodWLAN.cpp` and `bsd/dev/redwood_net.c` while deleting SpringBoard Wi-Fi status bar hooks from `userland/src/inject_sb.c`; added touch- and GPU-driven dynamic CPU/DDR frequency scaling via `mi8_perf_kick()` (idling at `825 MHz` / DDR `2/16` under the `66 °C` thermal limit) and `2 ms` intra-frame `IOSurface` flush coalescing (`fSyncGen` / `pushedGen`) in `iokit/Kernel/RedwoodGPU.cpp`.

## 2026-11-12

- **Internal speaker audio working and enabled by default**: iOS ringtones, keyboard clicks, and media audio play through the Qualcomm ADSP and TI `TAS2557` speaker amp; Bluetooth, battery gauge, haptics, and torch are also enabled by default without extra boot flags. Verified in an initial hardware trial; acoustic tuning, power draw, and extended runtime remain to be tested. Chronological details follow below.
- Added opt-in `audio=3` (default off): bounded ring consumes real iOS PCM while writing all-zero DMA slots with amp kept in reset; checks accepted/consumed/discarded frame conservation over 120 s (host tests and build passed; hardware test pending).
- Extended audio bring-up diagnostics to `mi8rp_step=11..16`: verified apps SMMU page tables and DMA translation, ASM/ADM/AFE playback, manual I2C `TAS2557` firmware load/verification, and muted power-up teardown; verified an audible 1 kHz `-30 dBFS` 1 s kernel tone on RAM boot without pops (out-of-bounds canary crashes ADSP intentionally and stays restricted to step 13).
- Added opt-in `audio=1` (count sink) and `audio=2` (60 s / 3000-period zero stream): confirmed S16LE stereo iOS PCM reaches the kernel and clean ADSP teardown under desktop GPU defaults.

### Audio Thread Stack Budget

Kept the static PCM scratch buffer fix, avoided inlining setup buffers into the playback loop, moved worker session/SMP2P snapshots to static storage, and added an 8 KiB static call-graph budget checker (`check-mi8-audio-stack.py`), verified alongside `audio=4` on hardware.

- `audio=4` verified a single ~3 s iOS ringtone clip on hardware (GPU/touch/buttons on, radios off): `-30 dB` linear scaling, peak 269 <= 1036, clean mute readback `03/01`, reset low, 6000/6000 periods, ring conservation, no pops or panics.
- `audio=5` verified a single 120 s radios-off hardware run: 7 wake/mute cycles with 6/6 read-only `Y` checks (`0x5d` retained across soft shutdown with reset high), peak 1035, 6000/6000 periods, clean teardown.
- Emergency panic amp reset (`audio=5 audio_panic_test=1`) verified in an isolated hardware run ~1 s after first LIVE: panic RAM buffer recorded reset-low marker and speaker cut off without pops.
- Wireless coexistence (`audio=5` with Wi-Fi, Bluetooth, GPU) verified in a 300 s hardware run: 16032 ms Wi-Fi wait, 21.7 ms max DONE gap, 1.76 ms max lateness, 1.35 ms max SMMU lock hold, 0 Wi-Fi wait contention, 6 wakes/5 checks, peak 1007, clean teardown.

### Configurable Digital Levels and Session Stats (`-30`/`-20` Hardware Comparison)

Added `audio_level_db=-30/-24/-20` (default `-30`), raised single-window cap to 120 s / 6000 periods and 200 wakes, removed the 60 s cumulative cap, added LIVE underflow / HAL gap / source clipping / output saturation counters, and added a 16 KiB rolling worker tail log.

Hardware `-30`/`-20 dB` 300 s runs with Wi-Fi and Bluetooth on passed without panic (`-30 dB`: 7 wakes, 116.7 s LIVE; `-20 dB`: 6 wakes, 169.2 s LIVE, ~40+ dB SPL). Brief click/noise at sound onset traced to ~0.5 s buffered zero/stale backlog skipped during ~528 ms wakeup.

### Wake Backlog Trim, Six Gain Levels, and Tail Log Fix

- PCM consumer trims stale backlog to the latest 1920 frames (40 ms) across WARMING and first LIVE before 10 ms fade-in; extends silence shutdown to 10 s.
- Added `-12`/`-6`/`0 dB` gain levels (limits up to 32767); raised session PCM log budget from 20 to 256 lines so `play` and `asm close` reach the final 32 KiB tail log.
- Hardware `-6 dB` 300 s run passed (`dropped=0`, `wake_flush_frames=106880`, ~60 dB SPL, tail logs complete).

### Fast Wake and Extended Silence Hold

- Moved read-only `Y` verification to `OFF_READY` after soft shutdown; added write-triggered wake (`startup` 6–11 ms, 20 ms wait, bounded 200 ms health polling, max warmup ~45–48 ms vs. 528 ms), 50 ms fade-in, and 10 s / 30 s idle shutdown.
- Hardware `-6 dB` and `0 dB` 300 s runs passed with 0 dropped frames, 0 saturation, 101.4 s continuous `0 dB` LIVE (`out_peak=31842`), and faster onset; browser Wi-Fi RX stall noted after extended browsing (under investigation).

### Long-Play Test Injection and Thermal Logging

- Added diagnostic `audio_test_clip=1` reading `Boot:/audio/test-clip.raw` (S16LE 48 kHz stereo, <= 32 MiB; test clips not distributed), raised `audio_seconds` / feeder cap to 900 s / 45000 periods, and logged 30 s thermal/health lines.
- Hardware 600 s `0 dB` continuous playback passed (5 clip loops, 645.8 s LIVE, 0 underflows, 1238/1238 health checks, CPU steady at 41–43.5 °C, 45000/45000 periods, no panic).

### Default Peripherals and Resident Speaker Session

- Expanded `dipper` defaults to enable `bt=7`, `audio=5`, `audio_level_db=0`, `audio_seconds=0` (resident), `battery=1`, `torch=3`, and `haptic=3` without extra flags (`--bluetooth` / `--peripherals` kept as compatibility no-ops; `--no-audio` added; omitting `--wifi` forces `bt=0`).
- Removed session/window/wake caps in resident mode while preserving all safety/health/amp-shutdown/panic guards; verified in a 13.3-hour / 1003-wake host model.
- Hardware zero-arg trial (P28) confirmed Wi-Fi, Bluetooth, battery, haptics, torch, and speaker playback with no autoplay at boot and no panic; early boot Safari `SYN_SENT` stall remains open.

## 2026-11-11

- Added audio diagnostics (`mi8rp_step=8..10`, default off): TrustZone ADSP boot/stop, `apr_audio_svc` GLINK + APR handshake, and AFE Quaternary MI2S port `0x1006` start/stop (control plane only; no sound yet).
- Fixed AFE diagnostic panic caused by calling `ml_io_unmap` on permanent TLMM `ml_io_map` pages; switched to a cached static pin table.
- Enabled iOS Bluetooth (`bt=7`): added `AppleBTHci` / `AppleBTMgmt` IOKit shim (`RedwoodBT.cpp`), `com.apple.uart.bluetooth` socket, Broadcom compatibility translations, `BT=1` daemons (`bluetoothd`, `BlueTool`, `inject_bt.c`, placeholder HCD). Verified toggling, scanning, pairing, and connecting headphones/another phone (~70 s chip ready time; BT audio unimplemented).

## 2026-11-10

- Added Bluetooth UART bring-up driver (`bt=1..6`, default off): power-up, WCN3990 rampatch + NVM download at 115200 or 3.2 Mbaud (`bt=6`, ~1 s upload), upgrading chip to Bluetooth 5.0 HCI.
- Added optional `/private/var` persistence (`build-payload.py --persist`): reads/writes two alternating 2 GiB slots after `darwin` block `2042368` on orderly exit; first save/restore verified.
- Added optional reduced render scale (`fbscale=2 fb_dpu=1`, `750x1624 @2x` DPU QSEED3 scaling; median blit drop from ~6.5 ms to ~0.5 ms), fixed `IOMobileFramebuffer::drawRows` buffer overflow on narrow source widths, swapped SpringBoard fallback status bar to split layout (removing `rdar:45025538` red bar), and added static wallpaper overlay (`/redwood/etc/wallpaper.jpg` or gradient; user-supplied). Kept opt-in due to app crashes seen in scaled mode.

## 2026-11-06

- Consolidated fixed `dipper` boot arguments into code defaults (`pexpert/arm/pe_bootargs.c`) with explicit override support (`=0` allowed) while keeping `redwood`/QEMU unchanged.
- Added shared kernel/userspace `kern.bootargs` expansion, masked MAC bootcfg logs, and compact payload profiles verified by host tests and clean kernel build.

## 2026-11-05

- Fixed `patchtool.py` omitting unowned diffs in child components nested inside a parent component path and added regression coverage.
- Exported optional thermal governor (`thermgov`), frame/thread profiling, and render import/static-image optimizations (`ffix=1` default; experimental bit2/bit3 off).
- Exported `rwtouch` `mark` and `mem` steps (`mem` untested on hardware) and completed clean replay/build parity checks.

## 2026-10-31

Summarizes the 2026-10-30 first-install experiment and repository reorganization (no full re-run on 10-31).

### Distribution Policy

- Switched strictly to source/patch/build-script distribution only; users compile locally and no prebuilt kernels or merged binaries containing the GPL GPU init table and APSL kernel are hosted ([GPU_LICENSE.md](docs/legal/GPU_LICENSE.md)).

### First-Install Progress

- Restored Android GPT, ran `Format Data`, and verified Android boot and full `/data` capacity.
- Carved ~24 GiB `darwin` partition, ran `Format Data`, and verified Android boot and resized `/data` capacity.
- Matched new partition GUID in `loader.c` and rebuilt loader/UEFI; readback of the first `8,365,539,328` bytes of `darwin` matched `darwin.img` SHA-256 and owner confirmed iOS boot (`xnuloader` verified via fastboot).

### Tools Reorganization

- Categorized 11 tools into `tools/prepare/`, `tools/build/`, `tools/partition/`, and `tools/tests/` (31 regression tests passing); see [Tools Index](tools/README.md).

### Docs & Handoff

- Scrubbed private experiment paths from public guides; added Team Win / TWRP acknowledgements and [Device Preparation Guide](docs/install/DEVICE_PREPARATION.md) (verified `Android 10 / MIUI V12.5.2.0.QEACNXM` root GPU firmware extraction).
- Split installation tutorials into [Install Guide](docs/install/INSTALL.md) and [Startup Guide](docs/install/STARTUP.md).
- Pending items: per-item post-repartition peripheral regression, post-exit Android reboot verification, live test of hardened generic partition/restore scripts, long-term stability, XNU `all` target, and clean-host build test.

## 2026-10-30

### Fixed

- **Wi-Fi bring-up failure**: Pre-reserved the 44 MiB contiguous DMA memory pool before modem startup and added verified `firmware-5.bin` packaging + negative payload checks.
- **Display brightness slider ineffective**: Restricted DSI command buffer allocations under 4 GiB for 32-bit DMA and freed failed allocations.
- **Desktop launchd service rejection**: Pinned `umask 022` during userspace packaging and added APFS ownership/mode checks in `build-payload.py`.
- **Build link and silent-failure fixes**: Added `-framework Network` for `net_test.m`, `pipefail`, Mesa venv recovery, and `BUILD_TIMEZONE` fallback.

### Added

- Offline `darwin` partition and Android GPT restore plan generators (`tools/partition/`) with dry-run, hash, mount, and post-reboot readback verification.
- SDK tree check (`check-sdk.py`), IPSW extraction (`prepare-ios.py`), userspace build, `darwin.img` packer (`pack-darwin.py`), and payload packager (`build-payload.py`).
- Hardware verification on existing layout covering Wi-Fi/Safari page load & refresh, Settings/Control Center brightness, lock/wake, haptics, torch toggle, volume UI, battery gauge, and widgets.

### Changed & Known Limits

- Shallow-fetched only required UEFI/boot submodules; UEFI build embeds USB XNUP payload automatically; userspace build forbids `PREBUILT`.
- Known limits: XNU `all` fails; clean Ubuntu build untested; torch dimming steps subtle; desktop stutter, power, exit recovery, cellular, and full audio tuning remain open; [GPU licensing](docs/legal/GPU_LICENSE.md) remains open.
