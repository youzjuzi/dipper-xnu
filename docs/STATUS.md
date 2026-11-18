# Feature Status and Limitations

**English** | [简体中文](zh-CN/docs/STATUS.md)

Updated: 2026-11-18. Bluetooth, speaker audio, battery, haptics, and torch are enabled by default and verified in an initial hardware trial; recent stability and tooling fixes (Wi-Fi DMA barriers + `rx_confused` recovery/health + Mi 8 stop summary, Telephony Ring Switch mute-HUD fix, `/apps` `MNT_UNION` sideload settling, and live log streaming helper `tools/tests/device-log.py`) are host-built and tested, **awaiting Xiaomi Mi 8 device verification**. This does not imply re-running all historical device tests.

## Current Stage

Isolated host builds from pinned upstream sources, image packaging, and short desktop/peripheral boots on an existing `darwin` partition are complete. Subsequent first-install testing passed Android GPT restoration, repartitioning, exact `darwin.img` range readback, and owner-confirmed iOS boot; full post-repartition per-peripheral regression and clean exit to Android remain pending.

## Existing-Partition Boot Experiments

Rebuilding only the kernel and payload verified the DSI brightness DMA fix: owner confirmed Settings/Control Center dimming, lock/wake, peripherals, Wi-Fi browsing, and full reboot back to Android ([Reproduction Report](validation/REPRODUCTION.md), [Device Validation Data](validation/device-validation-20261030.json)).

## Verified Facts

| Component | Verified Behavior | Validation Boundaries |
| --- | --- | --- |
| Build & Boot | Kernel `build`, `ath10k`, Mesa, userspace, UEFI build pass; boots to SpringBoard on device | Host had pre-installed deps; initial test reused verified `darwin` span |
| Display & Input | A630 desktop rendering, touch, both brightness sliders, 3x lock/wake work | Short sessions only; long-term stability unverified |
| Wi-Fi / Safari | Driver starts, `en0` gets IP, owner confirmed web page load and refresh | Throughput, external IPv6, long runtime unverified; intermittent `SYN_SENT` stalls seen |
| Peripherals & UI | Torch toggle, haptics, volume keys/slider, battery gauge, widgets, static wallpaper work | Torch dimming steps subtle; volume UI alone does not cover audio tuning |
| Persistence (opt-in) | Under `--persist`, `/private/var` saves to `darwin` and restores icons, folders, and Settings switches on next boot with CRC match | Single save + single restore only; only saves on orderly exit; crash/periodic saving and multi-cycle store growth untested |
| Bluetooth | Default `bt=7` (also tested with `--wifi --bluetooth`): toggles in Settings (~70 s chip ready), scans classic + BLE, pairs and connects headphones (HFP + A2DP) and another phone with auto-reconnect | Single headset and single phone tested; BT audio unimplemented; pairings do not persist across reboots unless tested with `--persist`; firmware must be pulled from phone |
| Internal Speaker Audio | Default `audio=5`, 0 dB resident: iOS ringtones, clicks, and media play via ADSP + TAS2557; ~40 ms wakeup; 10 min 0 dB run passed health checks at 41–43 °C CPU; panic reset cut off verified | Activates ~1 min after boot once Wi-Fi initializes; sound quality uncalibrated; resident DSP/DMA power draw, multi-hour runtime, and charging playback untested; BT audio/mic/calls unimplemented |
| Static Wallpaper | Renders gradient or `/redwood/etc/wallpaper.jpg` cleanly under `fbscale=2` and native `still_wall=1` | User-supplied JPEG; Settings wallpaper picker has no effect; CPU impact unmeasured |

## Current Blockers and Limitations

- XNU `all` target (export symbol checks and LLDB tool generation) still fails; clean-machine Ubuntu package install unverified.
- Generic device config input and full charge/discharge cycle unverified; persistence tested once and loses unsaved state on hard power-off.
- UI stutter, power management, and GPU SMMU/modem exit recovery remain open; full reboot is required between device rounds.
- Telephony, cellular data, Bluetooth audio, microphone, camera, GPS, and unlisted hardware are not available.
- Intermittent web browsing stalls (Wi-Fi stays associated, TCP stalls on `SYN_SENT`, root cause open).
- Combined distribution terms for the Linux-derived GPU init table and APSL kernel remain unresolved ([GPU License Notes](legal/GPU_LICENSE.md)).

## Next Steps

1. Audit remaining build dependencies in a clean environment and fix XNU `all`.
2. Replace manual device-parameter edits with a reviewable config input and finish post-repartition per-item regression.
3. Verify torch dimming steps, sustained power/thermals, and remaining audio/Wi-Fi items independently.
4. Investigate Settings/Messages crashes under reduced render scale and decouple static wallpaper loading from rootfs repacking.

See [Validation Log](validation/VALIDATION.md) and [Development Backlog](development/RELEASE_CHECKLIST.md).

## First-Install Verification

Android layout restoration, ~24 GiB `darwin` creation, two `Format Data` cycles, Android `/data` checks, new-GUID loader/UEFI rebuild, exact `darwin.img` readback, and owner-confirmed iOS boot succeeded ([First-Install Task](development/FIRST_INSTALL.md)). Hardened generic partition/restore tools pass offline replay and synthetic suites, tracked separately from live execution.

## Tool Maintenance

- **2026-11-18**: Stability & tooling updates (host-built and clean-replay tested; device verification pending): settled `/apps` `MNT_UNION` sideload support (`bsd/vfs/vfs_attrlist.c`, `userland/build.sh` with `APPS=1`, `userland/src/init.c`), reported standard HID Telephony Ring Switch (`0x0b`/`0x2e`, unmuted) on `Redwood buttons` (`userland/src/inject.c`) to fix muted volume HUD reporting, added `dsb sy` DMA barriers + 512-byte recycled slot zeroing + bounded `rx_confused` recovery (`wifi_no_recover=1` to disable) + active health lines + `mi8_wifi_stop()` teardown summary (`wifi/lx/`, `bsd/dev/redwood_lx.c`, `osfmk/arm64/loader_return.c`), fixed missing `import os` in `build-payload.py --link-inputs`, and added read-only `tools/tests/device-log.py`.
- **2026-11-11**: Cached permanent TLMM mappings statically in AFE diagnostics to avoid `ml_io_unmap` assertions ([AFE Cleanup](validation/VALIDATION.md#afe-pin-mapping-cleanup)).
- **2026-11-05**: Fixed `patchtool.py` nested-component unowned reporting bug (33/33 host tests).
- **2026-10-31**: Categorized tools under `prepare/`, `build/`, `partition/`, and `tests/` ([Tools Index](../tools/README.md)).

## Device Material Preparation

On 2026-10-31, `MODE=root` extraction of the four A630 firmware blobs was verified on `Android 10 / MIUI V12.5.2.0.QEACNXM` (`su uid=0`) matching phone, host, and pinned SHA-256 digests byte-for-byte ([Device Preparation](install/DEVICE_PREPARATION.md)).

## Thermals, Rendering, and Performance Diagnostics

Patches include optional `thermgov`, frame/thread profiling, and rendering/static-image optimizations (`ffix=1` default on; bit2/bit3 off). On `dipper`, `thermgov` defaults to `66 °C` while profilers stay off unless requested. Host `rwtouch` adds `mark` and `mem` (`mem` untested on hardware); see [Performance Export](validation/VALIDATION.md#performance-source-export-and-host-rebuild).

## `dipper` Boot-Arg Defaults

34 fixed platform settings live in `pexpert/arm/pe_bootargs.c` for `dipper` (overridable via explicit args including `=0`) and are shared via `kern.bootargs`; host equivalence tests and `daily` home-screen boot verified ([Startup Guide](install/STARTUP.md#short-dipper-boot-arguments-and-defaults)).

## Audio Bring-Up and Session Evolution

Diagnostic steps `mi8rp_step=8..16` verified ADSP PAS boot, GLINK/APR handshake, AFE `0x1006` QUAT MI2S, apps SMMU (`CB43`/`SMR8`), ASM/ADM PCM playback + canary fault proof, manual I2C `TAS2557` download, muted power-up, and an audible 1 kHz `-30 dBFS` diagnostic tone. Desktop modes then progressed from `audio=1` (count sink), `audio=2` (60 s zero stream), `audio=3` (host-verified ring + zero DMA), and `audio=4` (~3 s iOS ringtone clip) to `audio=5` (120 s session, panic GPIO76 reset, 300 s wireless coexistence, configurable `-30..0 dB` gain levels, ~40 ms fast wake, 10 min 0 dB continuous playback at 41–43.5 °C CPU, and default resident mode). See [Audio Mapping Playback and Amplifier](validation/VALIDATION.md#audio-mapping-playback-and-amplifier) for exact test counts, constraints, and remaining unverified bounds.

## Optional Reduced Render Scale

Appending `fbscale=2 fb_dpu=1` renders at `750x1624 @2x` using DPU QSEED3 scaling (median blit 6.5 ms -> 0.5 ms), swaps the fallback status bar to iPhone X split layout (fixing the `rdar:45025538` red bar), and covers black PosterBoard output with `/redwood/etc/wallpaper.jpg` (or gradient; `still_wall=1` applies the overlay at native resolution). Kept opt-in because Settings/Messages crashed in some scaled runs ([Startup Guide](install/STARTUP.md#optional-reduced-render-scale), [Reduced Render Scale Validation](validation/VALIDATION.md#reduced-render-scale-and-status-bar)).
