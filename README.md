# dipper-xnu

**English** | [简体中文](docs/zh-CN/README.md)

**Experimental / Work in Progress**

Experimental XNU (`8796.121.2`, Darwin `22.5.0`) and iOS `16.5` (`20F66`) port for **Xiaomi Mi 8 (`dipper`)**, Qualcomm Snapdragon 845 (`SDM845`).

Built on the [HackiOS](https://github.com/oosexgang/hackios-xnu-kernel) foundation, with `dipper`-specific bring-up for UEFI/loader boot, display, touch, Adreno 630 GPU, WCN3990 Wi-Fi & Bluetooth, and internal speaker audio. It boots to the SpringBoard home screen with GPU rendering, touch, Wi-Fi networking, Bluetooth pairing, and speaker output.

This project is still under active development and is **not** ready for daily use.

## Recent Updates · 2026-11-19

- **GPU & display smoothness**: Enabled Adreno 630 GMEM tile rendering, zero-copy DPU scanout (`fb_native=2`), and batched GPU SMMU page-table mapping by default, eliminating frame-copy and cache-flush animation stutter.
- **Native Wi-Fi & Bluetooth**: Replaced userspace Bluetooth and Wi-Fi status-bar shims with native kernel IOKit drivers (`RedwoodBT`, `RedwoodWLAN`) and fixed native SpringBoard Wi-Fi signal bar updates.
- **Dynamic frequency scaling**: Added touch- and GPU-driven dynamic CPU/DDR frequency scaling (`825 MHz` / DDR `2/16` idle under the `66 °C` thermal ceiling).
- **Speaker audio & volume HUD**: Fixed TAS2557 I2C check timing for faster wakeups, and fixed the muted volume HUD via standard HID ringer state reporting.
- **Sideload, teardown & tooling**: Added `/apps` union-mount sideloading, orderly warm teardown for resident subsystems, and read-only live logging (`tools/tests/device-log.py`).

Full change history and device test metrics: [CHANGELOG.md](CHANGELOG.md) and [VALIDATION.md](docs/validation/VALIDATION.md).

## Hardware & Boot Chain

| Component | Target |
| --- | --- |
| Device Codename | `dipper` (Xiaomi Mi 8) |
| SoC | Qualcomm Snapdragon 845 (`SDM845`) |
| GPU | Adreno 630 (`A630`) |
| Wi-Fi & Bluetooth | Qualcomm WCN3990 |
| Speaker Amp | TI TAS2557 (Quaternary MI2S + I2C) |
| Kernel | XNU `8796.121.2` (Darwin `22.5.0`) |
| Userspace | iOS `16.5` (Build `20F66`) |

Boot flow:

```text
Stock dipper bootloaders -> edk2-sdm845 UEFI -> xnuloader -> XNU -> iOS 16.5 userspace
```

## Feature Status (2026-11-19)

Most peripheral checks below were recorded on the pre-repartition test layout, with newer items (Bluetooth, speaker audio, native Wi-Fi status bar/LQM, dynamic CPU/DDR scaling, optional render scaling, persistent `/private/var`) verified separately in recent boots; full post-repartition regression and long-term stability remain to be tested.

| Feature | Status | Notes |
| --- | --- | --- |
| System boot | Works | Reaches iOS 16.5 SpringBoard home screen |
| Display & GPU | Partly | Mesa / freedreno drives A630 with GMEM tile rendering, `fb_native=2` WC zero-copy scanout (`59 FPS` active), dynamic CPU/DDR governor, and batched SMMU mapping; render-thread big-core affinity and exit recovery need work |
| Touch | Works | FTS touch input working |
| Brightness & Lock/Wake | Works | Settings / Control Center brightness and lock/wake verified |
| Volume buttons | Works | Standard HID Telephony Ring Switch (`0x0b`/`0x2e`) fixes the muted HUD overlay; buttons and slider adjust volume |
| Torch & Haptics | Works | Torch toggle and haptics work; torch brightness steps are subtle |
| Battery gauge | Partly | Battery percentage/status reported; full charge/discharge cycle unverified |
| Wi-Fi | Partly | Native status bar signal bars via kernel LQM events; DMA barriers, `rx_confused` recovery, and multi-AP fallback added; long-term stability under test |
| Safari / Web | Partly | Loads and refreshes pages over Wi-Fi; extended stability and video decoding need work |
| Bluetooth | Partly | Enabled by default via native `AppleOLYHAL` (no userspace shim); toggles, scans, pairs, and connects headphones/phones; no BT audio; pairings need `--persist` |
| Reduced render scale (`fbscale=2`) | Partly | Optional (`fbscale=2 fb_dpu=1`); smoother UI with status bar fix and static wallpaper; some apps crash |
| Static wallpaper | Works | User-supplied image (`/redwood/etc/wallpaper.jpg`); changing wallpaper in Settings has no effect |
| Internal speaker audio | Partly | Enabled by default; iOS audio plays via ADSP + TAS2557 (~31 ms warmup, ~207 ms idle coeff check); uncalibrated EQ; long-term power untested |
| Persistent `/private/var` (`--persist`) | Partly | First save/restore test verified under `--persist`; crash/periodic saving untested |
| Cellular / Mobile data | Not tested | Not yet verified working |
| Bluetooth audio / Mic / Calls | No | Not yet implemented |

Detailed status and verification boundaries are tracked in [docs/STATUS.md](docs/STATUS.md).

## Source-Only Policy & Compliance

This repository publishes **source patches, file manifests, host build/test tools, and documentation only**:

- **No prebuilt kernels or merged binaries** are hosted or distributed (see [GPU_LICENSE.md](docs/legal/GPU_LICENSE.md#distribution-policy) regarding `mi8_a630_hw_init.inc` and APSL 2.0/GPL-2.0-only boundaries).
- **No Apple binaries or IPSW contents** (no rootfs, dyld shared cache, system apps, fonts, or proprietary Apple keys/certificates) are committed.
- **No proprietary vendor firmware** is committed; device firmware (`a630_*`, `crbtfw21.tlv`/`crnv21.bin`, `tas2557_uCDSP_goer.bin`) and device-unique GPT GUIDs/MAC addresses must be obtained from your own device. Public patches keep zero/placeholder identifiers (`loader.c`).

## Building & Reproducing (Linux x86_64)

Developed on **Ubuntu 26.04.1 LTS (`x86_64`)**. Rather than tracking a full XNU fork directly, this repository reproduces the port deterministically from pinned upstream commits ([upstream.lock.json](upstream.lock.json)), component patches (`patches/`), and file checksums ([source-manifest.json](source-manifest.json)).

> **Note:** Chinese mirrors of all documentation are available under [docs/zh-CN/](docs/zh-CN/README.md).

1. **Verify repo files and prepare pinned sources**:
   ```sh
   git clone https://github.com/youzjuzi/dipper-xnu.git
   cd dipper-xnu
   sha256sum -c SHA256SUMS
   python3 -B tools/prepare/prepare.py --prepare
   ```
2. **Stage external inputs & extract IPSW** ([docs/build/INPUTS.md](docs/build/INPUTS.md), [docs/build/USERLAND.md](docs/build/USERLAND.md)):
   - Verify and place `THEOS`, `iPhoneOS16.5.sdk` (`tools/prepare/check-sdk.py`), `MacOSX13.3.sdk`, `linux-7.0.14`, `freebsd-15.1-src`, `mesa-25.0.7`, and the `iOS 16.5 (20F66)` IPSW (`tools/prepare/prepare-ios.py`).
   - Extract required device firmware from your own Xiaomi Mi 8 ([docs/install/DEVICE_PREPARATION.md](docs/install/DEVICE_PREPARATION.md)) and match your device's `darwin` partition GUID in `loader.c`.
3. **Build kernel, loader/UEFI, userspace & host images** ([docs/build/BUILD.md](docs/build/BUILD.md)):
   ```sh
   # First-time kernel dependencies & ath10k inside work/hackios:
   #   bash xnu-deps/setup.sh && bash tools/mk-ath10k.sh
   bash tools/build/build-kernel.sh
   bash tools/build/build-loader-uefi.sh
   bash tools/build/build-userland.sh
   python3 -B tools/build/pack-darwin.py
   python3 -B tools/build/build-payload.py --output work/runs/<run-id> --wifi --link-inputs
   ```
4. **Verify workspace status & host test suite** ([tools/README.md](tools/README.md)):
   ```sh
   PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py --deep
   PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite all --clean-replay --sanitize
   ```

**First-time device installation requires creating an independent `darwin` UFS partition, which wipes Android `userdata`.** The system image is written to UFS and booted via temporary RAM-loaded UEFI (`fastboot boot`), never flashing over stock Android boot permanently. Read [INSTALL.md](docs/install/INSTALL.md) and back up GPT/data before touching a phone.

### Tool Layout

| Directory | Purpose |
| --- | --- |
| `tools/prepare/` | Pinned source preparation, patch export/replay/privacy scan, workspace status & cleanup, SDK/IPSW checks |
| `tools/build/` | Incremental kernel, loader/UEFI, and userspace builds; `darwin.img` & bounded payload packaging |
| `tools/partition/` | Offline GPT partition / Android restore plan generation and readback verification |
| `tools/tests/` | Unified host test runner, clean-replay validation, synthetic GPT, and audio/workflow self-tests |

## Known Issues

- First cold app launch after boot has a brief loading delay (render-thread big-core affinity is not yet implemented; optional `fbscale=2` mode still causes some apps to crash).
- Bluetooth headphones receive no audio yet, pairings are not saved across reboots without `--persist`, and Bluetooth initializes ~70 s after boot.
- Internal speaker activates ~1 minute after boot (after Wi-Fi setup); sound quality is uncalibrated and long-term power draw is unmeasured.
- Long-term Wi-Fi stability and extended web video playback need further testing.
- Baseband `halt port modem` does not idle on warm stop; devices still require a full reboot between modem/baseband runs.
- Storage configuration targets an experimental layout (`darwin` partition) and does not yet ship as a generic one-click installer.

## Contributing

Issues, source patches, and reproducible host/device reports are welcome. Please read [DEVELOPMENT.md](docs/development/DEVELOPMENT.md) and [CONTRIBUTING.md](CONTRIBUTING.md) first. Never include personal data, device-unique GUIDs/MACs/serials, device backups, Apple system images, or proprietary firmware in patches or issues.

## Acknowledgements

This port builds on the work of many open-source projects, especially:

- **OOSEX GANG / HackiOS**: Core XNU port, `xnuloader`, userspace shims, and wireless compatibility layer.
- **Apple Open Source**: XNU and related open-source packages.
- **edk2-porting / Renegade Project, TianoCore, SimpleInit**: SDM845 UEFI and display/boot framework.
- **UniXNU / DarwinBoot**: Early boot components and reference work.
- **Linux, Mesa / freedreno, FreeBSD**: Hardware drivers, Adreno 630 graphics, and LinuxKPI base.
- **[Team Win / TWRP & dipper maintainers](https://twrp.me/xiaomi/xiaomimi8.html)**: Recovery environment for partition maintenance and image verification.
- **Theos, LLVM, and related toolchains**.

See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for details.

## License

This repository is **not** licensed under a single MIT license; each component retains its original license:

- Original build scripts, documentation, standalone headers/configurations, and inventoried original modules: **MIT** ([LICENSES/MI8-packaging-MIT.txt](LICENSES/MI8-packaging-MIT.txt)).
- XNU / HackiOS-derived kernel and loader modifications: **APSL 2.0** ([LICENSES/APSL-2.0.txt](LICENSES/APSL-2.0.txt)), keeping upstream notices.
- Third-party derivatives (`edk2-sdm845`, `SimpleInit`, `UniXNU`, `FreeBSD`, `WLFW` / `ISC`, Linux-derived `mi8_a630_hw_init.inc` under `GPL-2.0-only`): see [LICENSE.md](LICENSE.md), [LICENSES/](LICENSES), [LICENSE_REVIEW.md](docs/legal/LICENSE_REVIEW.md), [GPU_LICENSE.md](docs/legal/GPU_LICENSE.md), and [license-inventory.json](license-inventory.json).

This is an independent research project with no affiliation with device or OS vendors. Documentation index: [docs/README.md](docs/README.md).
