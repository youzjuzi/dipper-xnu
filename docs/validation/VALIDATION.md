# Validation Log

**English** | [简体中文](../zh-CN/docs/validation/VALIDATION.md)

## 2026-10-27 Historical Offline Replay

Date: 2026-10-27. Host file-level verification only (no full upstream build or device boots).

- XNU recorded baseline matches Apple source + pinned HackiOS `redwood.patch`/files byte-for-byte.
- `xnu-mi8`: replay PASS; 34 changed/new/deleted text files match exported text (`loader` device GUID intentionally removed).
- `hackios-kernel`: replay PASS; 23 files match.
- `hackios-userland`: replay PASS; 7 files match.
- `edk2-sdm845`: replay PASS; 5 files match.
- `simpleinit`: replay PASS; 1 file matches.
- `unixnu`: replay PASS; 1 file matches.

71 manifest SHA-256 digests matched; Python/Bash syntax, Markdown links, UTF-8 text checks, and pattern scans passed (`SHA256SUMS` provides file integrity verification, not cryptographic signing).

## 2026-10-30 Isolated Reproduction

Completed pinned fetch, build fixes, and host outputs ([Reproduction Report](REPRODUCTION.md)):

- 6 patches replayed across 72 files in a second empty directory (`hackios-userland` expanded to 8 files).
- Kernel `build`, `ath10k`, Mesa, userspace, `xnuloader`, UEFI, and `darwin.img` succeeded; `all` continued failing on export checks and LLDB tools.
- SDK Git tree matched all 8,867 entries; mismatched SDK/IPSW digests, existing source/image paths, and UEFI `--boot` flags were rejected.

## 2026-10-30 Existing-Partition Hardware Validation

- Verified primary/backup GPT and `darwin` system span SHA-256 without repartitioning or reflashing.
- Round 1 exposed `launchd` rejecting group-writable APFS entries; fixed via `umask 022` and APFS mode checks.
- Round 2 booted SpringBoard with Settings foreground, touch, GPU rendering, and partial framebuffer capture.
- Subsequent Wi-Fi rounds fixed the 44 MiB contiguous DMA reservation timing and `firmware-5.bin` staging; owner confirmed Safari page load/refresh and clean reboot to Android. Updated manifest covered 74 files cleanly.
- Peripheral rounds fixed 32-bit DSI brightness command buffer allocation (`0` write errors) and verified brightness sliders, 3x lock/wake, haptics, torch toggle, volume UI, battery, wallpaper, widgets, and Wi-Fi ([Existing-Partition Testing](../install/EXISTING_INSTALL.md), [Device Validation Data](device-validation-20261030.json)).

## 2026-10-30 First Install: Android GPT Restore

After owner ran the restore script, primary/backup GPT CRCs/entries matched the verified historical layout; after rebooting Recovery, kernel reported `userdata` `121,425,080,320` bytes (~113.09 GiB) and no `darwin` node (before `Format Data`; [First-Install Task](../development/FIRST_INSTALL.md), `work/runs/20261030-first-install-02/`, `-03/`).

## Generic Android GPT Restore Tool Host Tests

All 17 synthetic tests passed covering CRC/hash mismatches, primary/backup mismatch, overlap/out-of-bounds, non-target entry edits, unsupported flags, shell injection, duplicate GUIDs, overwrite protection, and stale kernel capacity rejection, plus offline replay on captured device GPTs (`work/runs/20261030-restore-tool-01/`; live run of hardened generic script pending).

## Post-Format Android Verification

Owner completed `Format Data` and Android setup; ADB output showed `sys.boot_completed=1`, `/data` total `116,193,656` KiB, available `114,887,932` KiB, passing Android restoration (`work/runs/20261030-first-install-04/`).

## Post-Repartition Android Verification

Rounds 05/06 readback confirmed new primary/backup GPT matched the plan with partitions #1–#20 untouched and post-reboot nodes `userdata` `95,655,297,024` bytes / `darwin` `25,769,795,584` bytes. After `Format Data`, Round 07 ADB output showed `sys.boot_completed=1` and `/data` total `91,422,752` KiB / available `90,118,260` KiB (`work/runs/20261030-first-install-05/`..`-07/`).

## Generic `darwin` Partition Tool

All 14 partition tests (10 synthetic-shell guard failures) and 17 restore tests passed offline; entry tables generated from Round 05 GPT matched live Round 06 entries and kernel sizes (`work/runs/20261030-partition-tool-01/`; separate live execution of generic script pending).

## Loader/UEFI Rebuild for New Partition GUID

Round 08 updated local `loader.c` unique GUID only and rebuilt via `tools/build/build-loader-uefi.sh` (`boot-dipper.img` SHA-256 `ad209c3caf29a474b76acb841067100714667665260e7df3171c7a0a8488238e`, `loader.efi` `a5643b7e45e539f58c843d6aacaedf08feb5a44c7c0b1d114b25a726bbb96d4a`), reusing verified kernel, APFS, and `darwin.img` (`work/runs/20261030-first-install-08/`).

## New Partition Image Readback

Round 09 TWRP readback of `8,365,539,328` bytes matched `darwin.img` SHA-256 `9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560` (`work/runs/20261030-first-install-09/`).

## Round 10: iOS Boot Success on New Partition

Fastboot confirmed `product: xnuloader` running the 300 s read-only Round 08 candidate and owner confirmed clean iOS boot (`boot.log` captured `oem run OKAY` only; per-peripheral regression and post-exit Android reboot remain pending; `work/runs/20261030-first-install-10/`).

## 2026-10-31 Pre-Merge, Tools Layout & Device Prep Validation

- **Pre-merge (`test/first-install`)**: 17 restore + 14 partition tests, 151 local Markdown links/anchors, `SHA256SUMS`, and `git diff --check` passed.
- **Tools layout (`chore/tools-layout`)**: 11 scripts moved under `prepare/`, `build/`, `partition/`, and `tests/`; 17+14 unit tests, Python/Bash syntax, 6 repo-root resolutions, 6 CLI helps, 170 links/anchors, and negative checks passed (`tools/README.md`).
- **Device prep (`MODE=root`)**: On 2026-10-31 with owner authorization on `Android 10 / MIUI V12.5.2.0.QEACNXM` (`su uid=0`), all 4 A630 firmware blobs extracted with matching device before/after, host, and pinned SHA-256 digests (`work/runs/20261031-firmware-01/gpu/`; unprivileged ADB and TWRP extraction not separately tested).

## Performance Source Export and Host Rebuild

Evidence: `work/runs/20261105-export-01/` (`revision-2/`). Exported 8 XNU + 4 userspace diffs and unified patch formats for the remaining 4 components with identical replay trees (`format-equivalence.json`).

Full sweep (`sweep-after.json`) confirmed zero unexplained source diffs; clean replay, privacy scan, `32/32` `patchtool` self-tests, clean XNU `build`, `rwtouch`, and `libredwood-gl` passed (915 object text sections matched byte-for-byte after normalizing build paths/dates and dropping UBSan paths).

| Boot Arg / Switch | Default & Conditions | Behavior & Bounds |
| --- | --- | --- |
| `thermgov` | Off unless `55–69` °C | Lowers big-cluster `PERF_STATE` only; never raises frequency or alters hardware thermal protection |
| `mi8_cpufreq` / `mi8_cpufreq_big` | Existing explicit freq args | Presence of either disables `thermgov` |
| `ffix` | `1` default (kernel + userspace); single digit `0–9` | `bit0`: skips redundant static fallback hashing (default-on feature, not off-by-default profiler) |
| `ffix` bit1 (`2`) | Off | `IOSurface` wrap/cache path + wrap stats thread |
| `ffix` bit2 (`4`) | Off | Channel-swizzle shared import (`gl_osmesa` + `redwood_gl.h`) |
| `ffix` bit3 (`8`) | Off | Initial render-target GPU copy with fallback |
| `fprof` | `0` off (`200–10000` µs) | Userspace sampler & kernel surface profiler |
| `perfprof` | `0` off (`1` enables) | Kernel sampler + companion clock thread (`sched` hook still executes one atomic read/branch when off) |
| `perfprof_hz` | `1000` Hz (`100–2000`) | Active only when `perfprof=1` |
| `mi8_cpuclk` | Off standalone; `10` s companion when `perfprof=1` (`1–3600` s) | Frequency probe thread |
| `touch_lat` / `taskload` / `cpuload` | Existing defaults (`0` off) | Touch latency & load threads |
| `gpu_keep` / `surftrace` / `surf_clear` | Existing tunables `1` / `24` / `1` | Unchanged |

`rwtouch mark` and `mem` are explicit script commands (`mem` untested on hardware).

## Nested Component Export Regression (2026-11-05)

Fixed `patchtool.py` skipping unowned diffs in child components nested inside parent trees; synthetic tests cover modify/add/delete/owned paths/ordering (`33/33` tests pass; `work/runs/20261106-bootargs-01/`).

## `dipper` Defaults and Short Payloads (2026-11-06)

Four XNU files implement centralized `dipper` platform defaults, DT matching, masked MAC bootcfg logs, and `kern.bootargs` output. Host DT-stub compilation passed `315` assertions comparing old long cmdlines vs. short profiles, worst-case prefixes, non-`dipper` isolation, and override semantics (`work/runs/20261106-bootargs-01/revision-1/`, clean `build` exit `0`). `daily` cmdline is 87 bytes; `bench` is 172 bytes (252 with 80-byte prefix, leaving 347 bytes `< 600`).

Device smoke (2026-11-09, `daily`): reached SpringBoard without panic, `kern.bootargs` matched old full profile, and Safari loaded pages (`bootcfg` not in captured loader log ring; `S-slim` bench smoke and long stability untested).

## Reduced Render Scale and Status Bar

**Crash & fix.** Bare `fbscale=2` panicked at ~14 s in `IOMobileFramebuffer::drawRows` because line buffer allocation used source width (`750`) while writing panel width (`1125`); fixed allocation to `max(src, panel)` per half.

**Screen class & status bar.** MobileGestalt returns `-1` for `750x1624 @2x` and `828x1792 @2x` (only `1125x2436 @3x` returns class `15`), causing PosterBoard black backgrounds and `rdar:45025538` red status bar. SpringBoard shim swaps `_UIStatusBarVisualProvider_Fallback` to `_UIStatusBarVisualProvider_Split1125` (35 methods + `alloc` redirect), verified removing the red bar on device.

**DPU scaling (`fb_dpu=1`).** Uses `750x1624` flip buffers (`stride=3008`) scaled via QSEED3; median copy time dropped from `6471 µs` (p90 `8551`) CPU scaling to `520 µs` (p90 `571`) on device with visibly smoother scrolling.

**Frame stats (active seconds >= 30 fps; non-matched runs with profilers on).** Native full-res (toggling wallpaper every 2 min): slow frames (>18 ms) `25.1%`, p95 `28.3 ms`, median `51 fps`; `fbscale=2` CPU scaling: `17.6%`, `24.8 ms`, `54 fps`; `fbscale=2` + DPU: `12.4%`, `21.8 ms`, `58 fps` (75 active s; black wallpaper also lowers load: `22.8%` hidden vs `30.6%` shown in native run).

**Static wallpaper & app crashes (2026-11-10).** Overlay above wallpaper window renders `/redwood/etc/wallpaper.jpg` (user-supplied `750x1624` JPEG, or gradient fallback; logged `a still picture is over the wallpaper window`). Settings crashed 5 times (`SIGBUS`/`SIGSEGV`) and Messages crashed 12 times across scaled boots; native-resolution `still_wall=1` smoke had zero crashes across Settings/Messages/Calendar/Spotlight once each (small sample), while `PosterBoard` still threw `NSInvalidArgumentException` once regardless of resolution. Full peripheral regression and crash root cause remain open.

## Persistence First Test (2026-11-10)

- Write run (`ufs_write=1 var_store=1 var_save_ms=120000 loader_return_after=240`): after rearranging icons, folders, and a Settings toggle, loader summarized `45 writes into darwin, 177827840 bytes, read back the same; 0 refused`.
- TWRP read-only check: Slot 0 generation `1`, `182,012,768` bytes, `16,904` entries, header + payload CRC32 valid; Slot 1 empty.
- Read-only boot (`var_store=1` only): restored `6,926` dirs, `2,851` files (`179,206,807` B), and `2` links with layout/Settings preserved (`cannot be written` expected on read-only boot).
- Caveats: only top 32 KiB kernel return log visible; single save + restore only (Slot 1 rotation, periodic saves, power-loss behavior, DB consistency, and growth untested). Host `--persist` tests passed 327 assertions.

## Bluetooth UART Link

Diagnostic driver `bsd/dev/mi8_bt.c` (`bt=N`, default off) drives Qualcomm WCN3990 over QUP UART `SE6` (`hsuart0`, GPIO 45–48) across non-persistent RAM boots:

- `bt=1/2`: `SE6` UART v10, FIFO enabled, 32-word FIFOs, DMA present.
- `bt=3`: `GPLL0_EVEN/3` (`100 MHz`), div 27 (~115740 baud), 8N1 internal TX->RX loopback 12 bytes matched.
- `bt=4`: waits `bt_delay` (default 60 s), enables 5 RPMh rails (`DONE`), switches pins to `qup6`, loopback 12 B in `1142 µs`, sends `0xFC` pulse -> `HCI Reset` (`04 0e 04 01 03 0c 00`), version HCI 8 / LMP 8 / Qualcomm (29) / subver `0x2be`.
- **`bt=5` (firmware upload, 115200 baud)**: reads SoC `0x40010214` ROM `0x201` patch `0x1`, sends `crbtfw21.tlv` (222,988 B, 918 chunks, ~20.7 s) and `crnv21.bin` (19 chunks, 438 ms, baud tag temporarily `0`), runs minimal in-band sleep (`0xFD`/`0xFC`) handshake -> `HCI Reset` OK, HCI `8->9` (BT 5.0), patch `1->2`, no panic.
- **`bt=6` (3.2 Mbaud)**: fractional M/N `128/375` (`102.4 MHz`, div 1), `0xFC48` `0x11` switch -> `crbtfw21.tlv` in `969 ms`, `crnv21.bin` (keeping baud tag `0x11`) in `20 ms`, HCI Reset & version verified at 3.2 Mbaud on 2 consecutive passes after initial run exposed tag-0 bug.

## ADSP Boot, APR Handshake, and QUAT MI2S (2026-11-11)

RAM boots (`gpu=0 fts=0 buttons=0`, 90 s timeout, ADSP read from phone `modem` partition):

- **Step 8**: TrustZone authenticated ADSP PAS image 1 (`30 MB`, 0 diffs), SMP2P up in ~13 ms, `slave-kernel` ~30 ms, stop-ack ~10 ms, TZ shutdown clean.
- **Step 9**: Bidirectional `apr_audio_svc` open (local 2 / remote 5), `q6core state=1`, parsed 8 services (`AFE=4 v0x2`, `ASM=7 v0x1`, `ADM=8 v0x2`). Fixed `FOREIGN_INTENTS` sizing (>=65 buffers offered vs 64 cap) and 8-word (32 B) DSP response header parsing.
- **Step 10**: Read-only check confirmed amp pins low (GPIO 76/87/30); switched GPIO 58–61 to `qua_mi2s`, started `1.536 MHz` clock & I2S port `0x1006` (16-bit stereo 48 kHz master) for 2 s, stopped and restored pins (`0` status, no panic after fixing `ml_io_unmap`).

Boundaries: control-plane only (no oscilloscope waveforms, no sound); 4/10 runs saw loader `hung` on exit (recoverable via reboot, logs retrievable).

## AFE Pin Mapping Cleanup

Kept static cached TLMM `ml_io_map` table without calling `ml_io_unmap` on permanent pages (`3/3` static pin checks, `72727/72727` APR tests, `101/101` rproc tests, clean replay & incremental build passed; no new device test needed).

## iOS Bluetooth (`bt=7`, 2026-11-11)

`bt=7` hands the 3.2 Mbaud UART to an H4 worker thread, `iokit/Kernel/RedwoodBT.cpp` (`AppleBTHci`, `AppleBTMgmt`, `bluetooth` DT node with `local-mac-address`), and `com.apple.uart.bluetooth` socket, paired with `BT=1` userspace (`bluetoothd`, `BlueTool`, `inject_bt.c` reporting Murata Wi-Fi vendor, placeholder HCD):

- Translates local version to Broadcom `15 / 0x420e`, handles erroneous-reporting commands locally, replies status `unsupported command` + sub-opcode + `0` to `OGF 0x3f` VSCs (preventing 15 s parser crash), replies `0` locally to `0x204a` (preventing `0x0c` error), converts random addresses in scan/adv/connect to public (preventing `0x12`), and publishes services at boot while waiting up to 3 min for chip readiness.
- **Device runs**: Chip ready ~70 s -> `STACK_READY`; Settings discovers and pairs OPPO Enco Free4 (`SSP`, `AVRCP`/`A2DP`/`HFP` channels connected), handles off/on auto-reconnect across cycles, and accepts incoming SSP + encryption from another phone (`build-userland.sh` output).
- **Boundaries**: Single headset, no audio routing yet, pairings do not persist across reboot, BLE/HID/sleep unverified, Broadcom proprietary features return unsupported.

## Audio Mapping, Playback, and Amplifier

Scope (2026-11-11–12): RAM boots (`mi8rp_step=11..16`, radios off, `gpu=0 fts=0 buttons=0`):

- **Step 11/12 (apps SMMU)**: Stream `0x1821` unmapped -> claimed `SMR8` + `CB43`, passed software page walk, compare-mask checks, and 200 ms hold with `0` new faults (`CBAR`/`S2CR` sticky after claim, retained lazily; ATOS unsupported; `work/runs/20261111-audio-smmu-01/`..`-07/`).
- **Step 13 (ASM/ADM/AFE)**: Consumed `150/150` PCM blocks; mapping 32 KiB while registering 64 KiB triggered real `CB43` fault (`FSR=0x402 FAR=0x10008000`) proving ADSP DMA traverses our SMMU table (`err_qdi.c` crashed ADSP as expected, keeping canary isolated to step 13; `work/runs/20261111-audio-play-02/`..`-04/`).
- **Step 14 (`TAS2557` load)**: Switched to bit-banged I2C on `GPIO85/86` (`SE5` FIFO disabled by firmware); matched IDs (`PG2.1`), downloaded `program0`/`config0` with word-aligned `P`/`Y` readback (`5c`/`3f`, `4f`, `5d`) and zero mismatches (`work/runs/20261111-audio-amp-01/`, `-02/`).
- **Step 15 (muted power-up)**: Powered up during 150-block zero PCM (`INT1=02 INT2=00 PUF=fc`, `mute=03/07`), clean shutdown before AFE stop (`work/runs/20261111-audio-amp-04/DEVICE.md`).
- **Step 16 (first audible tone)**: 1 kHz `-30 dBFS` 1 s tone confirmed audible with moderate level, `03/01` mute readback, and pop-free shutdown (`work/runs/20261112-audio-tone-01/`, `-02/`).

## iOS Audio Count Sink and Desktop Zero Stream (2026-11-12)

Under desktop GPU defaults (radios off, 240 s):

- **`audio=1` (`ef0b864`)**: Count sink received `4,604` callbacks (`4,714,496` S16LE stereo frames @1024/call, `498,298` non-zero, max peak `-6.7 dBFS`), confirming iOS applies volume scaling to PCM samples (`work/runs/20261112-audio-sink-01/DEVICE.md`).
- **`audio=2` (`051215b`)**: Completed `3000/3000` zero DMA periods (60 s), `underflow=0`, `faults=0`, clean teardown with amp in reset (`work/runs/20261112-audio-zero-01/README.md`).

## Ring Zero-DMA Host Candidate (2026-11-12)

`audio=3` adds an SPSC ring consuming real PCM while forcing zero DMA slots; passed 100k seeded ops, 2M-frame concurrency, 6000 zero-DMA periods, conservation (`accepted 5,775,424 = consumed 5,759,040 + discarded 16,384`), ASan/UBSan, and TSan on clean replay (`work/runs/20261112-audio-ring-01/`).

## Audio Worker Stack Budget & Session Validation (2026-11-12)

Moved scratch buffer to static storage and compressed setup frames (`6,752` B max path `< 8,192` B; feeder `7,280` B, control `3,056` B, panic hook `16` B):

- **`audio=4`**: Played ~3 s iOS ringtone once cleanly (`-30 dB`, `150` blocks, peak `269 <= 1036`, `03/01` mute, `6000/6000` periods, no pops/panics; `work/runs/20261112-audio-clip-01/DEVICE.md`).
- **`audio=5` (radios off, 120 s)**: 7 wake/mute cycles, `6/6` `0x5d` Y-checks across reset-high soft shutdowns, `6000/6000` periods (`work/runs/20261112-audio-session-01/DEVICE-22.md`).
- **Panic hook (`audio=5 audio_panic_test=1`)**: Verified emergency GPIO76 reset cut-off 1 s after first LIVE (`DEVICE-22-panic.md`).
- **Wireless coexistence (300 s, `-30 dB`)**: Coexisted with Wi-Fi (`16,032 ms` wait, `CB44`), BT, and GPU (`21.7 ms` max DONE gap, `1.76 ms` max lateness, `1.35 ms` max SMMU hold, `0` Wi-Fi lock wait, `6` wakes, `5/5` checks, peak `1007`, clean exit; `work/runs/20261112-audio-coexist-01/DEVICE.md`).
- **`-30`/`-20 dB` comparison**: Both 300 s wireless runs passed without panic (`work/runs/20261112-audio-level-01/DEVICE.md`); onset glitch traced to ~528 ms wakeup dropping buffered frames.
- **Wake trim + 6 levels + `-6 dB` device run**: Trimmed backlog to 1920 frames (40 ms) across WARMING/LIVE and raised PCM session log budget to 256 lines; `-6 dB` 300 s run passed (`15000/15000`, `dropped=0`, `wake_flush_frames=106880`, complete 32 KiB tail log, ~60 dB SPL; `work/runs/20261112-audio-louder-01/DEVICE.md`).
- **Fast wake + `0 dB` runs**: Moved `Y` verify to `OFF_READY`, added write-triggered wake (`45–48 ms` max warmup, `50 ms` fade-in, 10 s/30 s silence shutdown); both `-6 dB` and `0 dB` 300 s wireless runs passed (`101.4 s` continuous `0 dB` LIVE, `out_peak=31842`, `0` saturation; noted Safari Wi-Fi stall after long browsing; `work/runs/20261112-audio-fastwake-01/DEVICE.md`).
- **10-min `0 dB` continuous playback**: Using diagnostic `audio_test_clip=1` (user clip, not in repo), completed 5 loops (`645.8 s` LIVE, `out_peak=32767`, `0` saturation, `0` underflows, `1238/1238` health checks, CPU steady at `41–43.5 °C`, `45000/45000` periods, no panic; `work/runs/20261112-audio-long-01/DEVICE.md`).
- **Default-on peripherals & resident audio**: Expanded `dipper` defaults (`bt=7 audio=5 audio_level_db=0 audio_seconds=0 battery=1 torch=3 haptic=3`), verified 47,976 s / 1,003-wake host model, and passed zero-arg hardware trial `P28` (`~16 s` Wi-Fi wait, `41 ms` wakeup, ~128 s continuous LIVE, `INT1=02 INT2=00 PUF=fc`, Wi-Fi/BT/battery/haptics/torch/speaker all verified, CPU `46–68 °C` under video/browser load, stopped via host `oem stop` at ~600 s; early Safari `SYN_SENT` stall open; `work/runs/20261112-audio-default-01/`).

### Adreno GMEM, Zero-Copy `fb_native=2` Scanout & Batched GPU SMMU (2026-11-19)

Four 300 s RAM-boot validation runs verified zero-copy display scanout, Adreno GMEM enablement, non-blocking WC scanout eviction, TE pacing, and O(1) batched GPU SMMU mapping on `dipper` with zero panics and zero GPU/SMMU faults:

- **`zc-sysmem`** (`work/runs/20261119-zerocopy-01/zc-sysmem-final-return.log`, `result: returned 1448477 0`): Enabled `fb_native=2` 4-slot WC scanout pool (`2` splash slots at `0x9deb8000`/`0x9e970000` + `2` contiguous `<4 GB` RAM allocations) while keeping sysmem: `8100` flips (`8085` zero-copy, `15` fallback, `13` evicted, `27` replaced), `83583 us` total / `6994 us` max; `300` frames in `5000 ms` (`59` a second, `10 us` each in driver); `33344` GPU submissions (`153517 us` ring, `5563882 us` flushing `89101760 KB` in `25029` calls).
- **`zc-gmem-prof`** (`work/runs/20261119-zerocopy-01/zc-gmem-prof-final-return.log`, `result=returned 1448206 0`): Fixed `MSM_PARAM_GMEM_BASE` (`case 0x06` -> `0x00100000ull`) and removed `FD_MESA_DEBUG=sysmem`: `3900` flips (`3894` zero-copy, `6` fallback, `4` evicted, `5` replaced), `56507 us` total / `9650 us` max; `22464` submissions (`173878 us` ring, `634301 us` flushing `7532128 KB` in `887` calls, `22478` at stop); profiling exposed `159.07–173.53 ms` `display` spikes on WC eviction and `10214 us` `IOSurfaces taken as buffers`.
- **`zc-gmem-step3`** (`work/runs/20261119-zerocopy-02/zc-gmem-step3-final-return.log`, `result=returned 1448816 0`): Added non-copy `evictSurface()` hold flags (`fScanLatchedHold`/`fScanPendingHold`), TE wait hint (`MiniIOFlipWaitHintUs`), and `gpu_push_ms=100`: `6000` flips (`5998` zero-copy, `2` fallback, `42` evicted, `7` replaced), `108016 us` total / `6437 us` max; `33024` submissions (`206733 us` ring, `144962 us` flushing `1836464 KB` in `247` calls, `33052` at stop); `pf: submit` (`83` windows, `15209` submissions) cut `display` max to `15.62 ms` (`16676` hits) and `cache` to `99.66 ms` total (`1.24 ms` max, `6.74 ms` periodic), isolating remaining `lock` (`1939.52 ms` total / `9.44 ms` max) and `other` (`2160.18 ms` total / `5.99 ms` max) around `IOSurfaces taken as buffers` (`6962–8537 us` each).
- **`zc-gmem-step4`** (`work/runs/20261119-zerocopy-03/zc-gmem-step4-final-return.log`, `result=returned 1448083 0`): Added O(1) GPU SMMU L2/L3 virtual lookup (`keep_l2_virt`/`keep_l3_virt`), batched segment `map_range`/`unmap` (`redwood_gpu_map_range`/`mi8_gpu_map_range`), `to_memory_nodsb()`, fast spin-then-sleep `keep_tlb()`, and `kRedwoodDescribe` early return: `5700` flips (`5698` zero-copy, `2` fallback, `12` evicted, `6` replaced), `39179 us` total / `1697 us` max (`6.87 us` avg); `297` frames in `5000 ms` (`59` a second, `8 us` each in driver), `95 in 100 under 21 ms`, `0` longer, `0` pauses; `33728` submissions (`262596 us` ring, `293673 us` flushing `3417408 KB` in `392` calls, `33772` at stop); `pf: submit` (`33` windows, `10756` submissions) cut `lock` to `9.88 ms` total (`0.20 ms` / `201 us` max), `other` to `64.72 ms` total (`0.73 ms` max), `display` max `14.56 ms`, `cache` `143.47 ms` total (`1.43 ms` max); `IOSurfaces taken as buffers` dropped to `103–180 us` each (`175 in 128 us`, `165 in 128 us`, `122 in 126 us`, `118 in 136 us`, `74 in 125 us`); clean `slumber answered` and `MiniIOFlipQuiesce` teardown.
- **Kernel defaults updated**: Promoted `fb_native` `"1"` -> `"2"` and removed `caenv=FD_MESA_DEBUG=sysmem` in `pexpert/arm/pe_bootargs.c` (`33` defaults; `test-boot-defaults.py` passing `512` assertions on host). Standalone zero-override default-bootargs smoke boot remains optional/pending.
