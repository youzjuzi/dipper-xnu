# Feature Status and Limitations

**English** | [简体中文](zh-CN/docs/STATUS.md)

Updated: 2026-11-19. Stage 1 native integration and stability updates are host-built, clean-replay tested (`21/21`), and verified on the Xiaomi Mi 8: native kernel `AppleOLYHAL` (`RedwoodBT.cpp`, removing `libredwood-bt.dylib`), `"wlan"` node + early `en0` (`RedwoodWLAN.cpp`, removing SpringBoard status bar hooks), `EVENT_LQM_CHANGED` `MLEN` sizing + `com.apple.wifi.manager` pre-declaration (active native Wi-Fi signal bars), Wi-Fi DMA barriers + `rx_confused` recovery + multi-AP fallback, standard HID Telephony Ring Switch mute-HUD fix, `/apps` `MNT_UNION` sideload, dynamic CPU/DDR governor (`825 MHz` / DDR `2/16` idle) + `RedwoodGPU` flush coalescing, orderly subsystem teardown, and `TAS2557` bit-bang I2C busy-spin (`~207 ms` idle check, `~31 ms` warmup). This does not imply re-running all historical device tests.

## Current Stage

Isolated host builds from pinned upstream sources, image packaging, and short desktop/peripheral boots on an existing `darwin` partition are complete. Subsequent first-install testing passed Android GPT restoration, repartitioning, exact `darwin.img` range readback, and owner-confirmed iOS boot; full post-repartition per-peripheral regression and clean exit to Android remain pending.

## Existing-Partition Boot Experiments

Rebuilding only the kernel and payload verified the DSI brightness DMA fix: owner confirmed Settings/Control Center dimming, lock/wake, peripherals, Wi-Fi browsing, and full reboot back to Android ([Reproduction Report](validation/REPRODUCTION.md), [Device Validation Data](validation/device-validation-20261030.json)).

## Verified Facts

| Component | Verified Behavior | Validation Boundaries |
| --- | --- | --- |
| Build & Boot | Kernel `build`, `ath10k`, Mesa, userspace, UEFI build pass; boots to SpringBoard on device | Host had pre-installed deps; initial test reused verified `darwin` span |
| Display & Input | A630 GMEM desktop rendering (`caenv=FD_MESA_DEBUG=sysmem` default removed), `fb_native=2` WC zero-copy scanout (`59 FPS`, `5698/5700` zero-copy, `6.87 us` avg flip), TE-aware submit waits, batched SMMU mapping (`0.12–0.18 ms`/`IOSurface`), dynamic CPU/DDR governor, touch & brightness sliders | Bounded 300 s runs verified (`perfprof=1`); standalone zero-override boot with default `pe_bootargs.c` & render-thread big-core affinity open |
| Wi-Fi / Safari | Driver starts, `en0` gets IP, native LQM updates (`218` `linkQualityDidChange` events, active status bar bars), DMA barriers/`rx_confused` recovery, Safari page load/refresh | Throughput, external IPv6, and multi-hour runtime unverified |
| Peripherals & UI | Torch toggle, haptics, volume keys/slider, standard HID ringer switch (`0x0b`/`0x2e` HUD fix), battery gauge, `/apps` `MNT_UNION` sideload, widgets, static wallpaper | Torch dimming steps subtle; volume UI alone does not cover audio tuning |
| Persistence (opt-in) | Under `--persist`, `/private/var` saves to `darwin` and restores icons, folders, and Settings switches on next boot with CRC match | Single save + single restore only; only saves on orderly exit; crash/periodic saving and multi-cycle store growth untested |
| Bluetooth | Default `bt=7` via native kernel `AppleOLYHAL` (no userspace shim): toggles in Settings (~70 s chip ready), scans classic + BLE, pairs/connects headphones and phone with auto-reconnect | Single headset and single phone tested; BT audio unimplemented; pairings do not persist across reboots unless tested with `--persist`; firmware must be pulled from phone |
| Internal Speaker Audio | Default `audio=5`, 0 dB resident: iOS audio via ADSP + TAS2557 (~31 ms warmup, `~207–208 ms` busy-spin idle coeff check, `checks=2/2` across ringtone wake/mute/wake); 10 min 0 dB run passed; panic reset + orderly exit verified | Activates ~1 min after boot once Wi-Fi initializes; sound quality uncalibrated; resident DSP/DMA power draw, multi-hour runtime, and charging playback untested; BT audio/mic/calls unimplemented |
| Static Wallpaper | Renders gradient or `/redwood/etc/wallpaper.jpg` cleanly under `fbscale=2` and native `still_wall=1` | User-supplied JPEG; Settings wallpaper picker has no effect; CPU impact unmeasured |

## Current Blockers and Limitations

- XNU `all` target (export symbol checks and LLDB tool generation) still fails; clean-machine Ubuntu package install unverified.
- Generic device config input and full charge/discharge cycle unverified; persistence tested once and loses unsaved state on hard power-off.
- Render-thread big-core affinity, sustained power management, and modem exit recovery (`halt port modem` stays non-idle across warm stop; full reboot still required between baseband runs) remain open.
- Telephony, cellular data, Bluetooth audio, microphone, camera, GPS, and unlisted hardware are not available.
- Extended Wi-Fi runtime stability and browser video decoding remain under observation.
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

- **2026-11-19**: Device-verified Adreno 630 GMEM (`MSM_PARAM_GMEM_BASE` `0x00100000`), `fb_native=2` WC zero-copy DPU scanout + TE-aware wait + non-copy eviction, `gpu_push_ms=100` flush reduction, and O(1) batched GPU SMMU mapping (`0.12–0.18 ms`/`IOSurface`, `0.20 ms` max `gGPULock`), plus native Wi-Fi status bar signal bars (`EVENT_LQM_CHANGED` sized to `0xb4`, `220 <= MLEN 224` + `clamp_rssi()` + `kev_post_msg()` failure logging + `com.apple.wifi.manager` pre-declaration), `TAS2557` bit-bang I2C busy-spin (`native_delay` for `<= 50 us` + `check_us`/`check_y`/`check_err` summary fields), native `AppleOLYHAL` / `RedwoodWLAN` / dynamic CPU-DDR governor / `RedwoodGPU` flush coalescing, warm subsystem teardown + `mi8_rproc_stop()`, and 2026-11-18 stability fixes.
- **2026-11-18**: Stability & tooling fixes: settled `/apps` `MNT_UNION` sideload support (`bsd/vfs/vfs_attrlist.c`, `userland/build.sh` with `APPS=1`, `userland/src/init.c`), reported standard HID Telephony Ring Switch (`0x0b`/`0x2e`, unmuted) on `Redwood buttons` (`userland/src/inject.c`), added `dsb sy` DMA barriers + 512-byte recycled slot zeroing + bounded `rx_confused` recovery + active health lines + `mi8_wifi_stop()` teardown summary, fixed `build-payload.py --link-inputs`, and added read-only `tools/tests/device-log.py`.
- **2026-11-11**: Cached permanent TLMM mappings statically in AFE diagnostics to avoid `ml_io_unmap` assertions ([AFE Cleanup](validation/VALIDATION.md#afe-pin-mapping-cleanup)).
- **2026-11-05**: Fixed `patchtool.py` nested-component unowned reporting bug (33/33 host tests).
- **2026-10-31**: Categorized tools under `prepare/`, `build/`, `partition/`, and `tests/` ([Tools Index](../tools/README.md)).

## Device Material Preparation

On 2026-10-31, `MODE=root` extraction of the four A630 firmware blobs was verified on `Android 10 / MIUI V12.5.2.0.QEACNXM` (`su uid=0`) matching phone, host, and pinned SHA-256 digests byte-for-byte ([Device Preparation](install/DEVICE_PREPARATION.md)).

## Thermals, Rendering, and Performance Diagnostics

Patches include optional `thermgov`, frame/thread profiling, and rendering/static-image optimizations (`ffix=1` default on; bit2/bit3 off). On `dipper`, `thermgov` defaults to `66 °C` while profilers stay off unless requested. Host `rwtouch` adds `mark` and `mem` (`mem` untested on hardware); see [Performance Export](validation/VALIDATION.md#performance-source-export-and-host-rebuild).

## `dipper` Boot-Arg Defaults

33 fixed platform settings live in `pexpert/arm/pe_bootargs.c` for `dipper` (including `fb_native=2` and GMEM enabled without default `caenv=FD_MESA_DEBUG=sysmem`; overridable via explicit args including `=0`) and are shared via `kern.bootargs`; host equivalence tests passed after updating defaults, while previous device validation ran `fb_native=2` explicitly ([Startup Guide](install/STARTUP.md#short-dipper-boot-arguments-and-defaults)).

## Audio Bring-Up and Session Evolution

Diagnostic steps `mi8rp_step=8..16` verified ADSP PAS boot, GLINK/APR handshake, AFE `0x1006` QUAT MI2S, apps SMMU (`CB43`/`SMR8`), ASM/ADM PCM playback + canary fault proof, manual I2C `TAS2557` download, muted power-up, and an audible 1 kHz `-30 dBFS` diagnostic tone. Desktop modes then progressed from `audio=1` (count sink), `audio=2` (60 s zero stream), `audio=3` (host-verified ring + zero DMA), and `audio=4` (~3 s iOS ringtone clip) to `audio=5` (120 s session, panic GPIO76 reset, 300 s wireless coexistence, configurable `-30..0 dB` gain levels, ~40 ms fast wake, 10 min 0 dB continuous playback at 41–43.5 °C CPU, and default resident mode). See [Audio Mapping Playback and Amplifier](validation/VALIDATION.md#audio-mapping-playback-and-amplifier) for exact test counts, constraints, and remaining unverified bounds.

## Optional Reduced Render Scale

Appending `fbscale=2 fb_dpu=1` renders at `750x1624 @2x` using DPU QSEED3 scaling (median blit 6.5 ms -> 0.5 ms), swaps the fallback status bar to iPhone X split layout (fixing the `rdar:45025538` red bar), and covers black PosterBoard output with `/redwood/etc/wallpaper.jpg` (or gradient; `still_wall=1` applies the overlay at native resolution). Kept opt-in because Settings/Messages crashed in some scaled runs ([Startup Guide](install/STARTUP.md#optional-reduced-render-scale), [Reduced Render Scale Validation](validation/VALIDATION.md#reduced-render-scale-and-status-bar)).
