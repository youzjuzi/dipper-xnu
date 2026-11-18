# 2026-10-30 Isolated-Directory Reproduction Report

**English** | [简体中文](../zh-CN/docs/validation/REPRODUCTION.md)

Starting commit: `e930c26c4303283d7f2f5fc87479946d46409783` on Ubuntu 26.04.1 LTS `x86_64`. Results below include fixes added to tutorials and build scripts during reproduction; the unmodified starting commit did not pass end-to-end as-is.

## Inputs and Isolation

- Cloned the public repo into a fresh directory and fetched pinned upstream commits via `upstream.lock.json`.
- Verified all 7 external archives/SDKs against official origins and SHA-256 checksums before copying ([INPUTS.md](../build/INPUTS.md)); reused no old kernels, UEFI images, payloads, userspace builds, or modified worktrees.
- `THEOS` pointed to an isolated toolchain/SDK; iOS extraction, Mesa, host tools, APFS volumes, and `darwin.img` were generated fresh inside the isolated tree.
- Host packages were pre-installed (**not** a clean-OS apt test). An interrupted initial fetch was retained and resumed cleanly before re-running the fixed `prepare.py --prepare` offline into a second empty directory (all 6 patch sets and 72 manifest hashes passed).

## Initial Host Build Results

| Stage | Result | Scope & Boundaries |
| --- | --- | --- |
| `iPhoneOS16.5.sdk` | Git tree hash matched all 8,867 files/symlinks/modes | Full tree digest, not just path check |
| XNU deps stage1 / stage2 | Exit `0` | Built on host with pre-installed packages |
| `ath10k` | Compiled cleanly | Does not verify device Wi-Fi |
| XNU `-j8 -k` default (`all`) | **Exit `2`** | Failed on export symbol check & LLDB tool generation |
| XNU `-j8 build` | **Exit `0`**, ARM64 Mach-O | Headers/compile/link pass; does not imply `all` passes |
| IPSW verify & extract | Exit `0` | Verified full SHA-256, `BuildManifest`, and 3 DMGs |
| Mesa / GL / shims / `net_test` | Built from source | `PREBUILT` rejected |
| Userspace entry point | Exit `0`, built `root.apfs` / `flashboot.apfs` | GPU firmware still missing at this stage; staged later for hardware test |
| `xnuloader` / UEFI | Exit `0` | BootShim + FD + USB XNUP matched byte-for-byte; DTB present; ARM64 EFI confirmed |
| `darwin.img` | Exit `0`, 8,365,539,328 bytes | SHA-256 matched historical system image; no device writes |
| Host APFS readback | 4/4 digests matched | Read graphics lib, `net_test`, Wi-Fi plist, and stage0 via host `apfs-tool` |

APFS packing failed initially inside a restricted sandbox without Python multiprocessing IPC permissions and succeeded once local IPC was enabled.

## Fixes Applied During Reproduction

1. Shallow-fetched only required UEFI/boot submodules per pinned gitlinks rather than cloning OpenSSL's nested test repos.
2. Added `-framework Network` for `net_test.m`.
3. Enabled `pipefail` in userspace wrapper, enforced linker check, and rejected `PREBUILT`.
4. Added Mesa venv dependency recovery on retry and `BUILD_JOBS` Ninja concurrency control.
5. Added `BUILD_TIMEZONE` / UTC fallback without `timedatectl` and skipped unused RAM-root `system.apfs`.
6. Automatically embedded USB XNUP payload in UEFI build while refusing device-boot options.
7. Added SDK tree verification, IPSW extractor, userspace/UEFI wrappers, `darwin.img` packer (extracting `3.apfs` without GPT wrapper), and tutorials.

Patches, `source-manifest.json`, and `license-inventory.json` were updated together; existing [GPU licensing constraints](../legal/GPU_LICENSE.md) remain unchanged.

## Initial Host Artifact Digests

These **initial host digests predate the Wi-Fi and brightness fixes**; see [Device Validation Data](device-validation-20261030.json) for hardware-tested artifacts. Except for the deterministic Apple composite `darwin.img`, host-built artifacts embed timestamps/paths/APFS metadata and are not proven byte-identical across machines:

```text
01bc508afdb937cc67512c5ff9915e7b6228d0917eb7303480217b92ee656ca0  mach.development.bcm2837
914c742badf4a0ee03e6b51abadab0019ec7c9681402fc8e6703b21f107417ab  loader.efi
02abf7c8f9ad660867b79df914ad9976517499bdc14b49d8f05c5aaf7987ae1a  boot-dipper.img
7e2cd404e1604e3fb5d90241947ccdc40654f53574cde01c0dbc20a742713bb1  root.apfs
4acd7b4c34c7562a3005864afeb7d27c0c37dd228389b9b369962003d2b481c5  flashboot.apfs
9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560  darwin.img
```

## Remaining Open Items at Reproduction

- XNU `all` export check and tool generation.
- Full transitive dependency pinning and clean-OS package install validation.
- Generic device config input, fresh repartitioning, and flashing (repartition/readback verified separately in [First-Install Task](../development/FIRST_INSTALL.md)).
- Long-term stability, power, charging, and remaining unported hardware.

## Hardware Validation on Existing Partition

Attached the test `dipper` with existing GPT verified (`8,365,539,328`-byte `darwin` system span readback matched new `darwin.img` SHA-256 identically, so existing partition was reused without flashing). Staged four verified A630 GPU blobs and updated local `loader.c` GUID in the gitignored build tree.

Round 1 entered XNU, mounted rootfs, and authenticated A630 ZAP, but `launchd` rejected services (`Path had bad ownership/permissions`—`0775`/`0664` due to host umask). Fixed `umask 022` in userspace build and added strict APFS `0755`/`0644` checks in `build-payload.py`.

Round 2 launched SpringBoard cleanly (Settings foreground, touch down/up events, active GPU rendering, 0 launchd permission denials), decoded native `4608`-byte-stride framebuffer showing desktop icons (screenshot interface captured top 2107 lines at UEFI `1080x2248` out of `1125x2436`), returned cleanly after 5 min (`returned 1441823 0`), and rebooted to Android (`sys.boot_completed=1`). See [Device Validation Data](device-validation-20261030.json).

## Wi-Fi and Safari Hardware Validation

Tested Wi-Fi in 900 s RAM-boot rounds (`514`-byte bootargs with local `wifi_mac`, full reboots between rounds):

- Round 1/2 captured `lx: no 46137344 bytes of memory in one piece` / `rc=12` after `FW_READY` (userspace fragmented memory before allocation); fixed by reserving the 44 MiB pool prior to modem thread startup.
- Round 3 reached WLAN start and hit `rc=60` due to missing `firmware-5.bin`; staged verified 60-byte file ([External Inputs](../build/INPUTS.md#wcn3990-wi-fi-feature-file)) and enforced host packaging check.
- Round 4 passed: `FW_READY`, `redwood_lx_start rc=0`, `en0` associated with IPv4/IPv6 and DNS (`wifi 1 cellular 0`), and owner confirmed Safari loaded and refreshed pages before returning cleanly (`returned 1441823 0`) and rebooting to Android ([Section 5 of Existing-Partition Testing](../install/EXISTING_INSTALL.md#5-wi-fi-and-web-browsing-test)).

## Peripherals and Interactive Hardware Validation

Added `battery=1 torch=3 haptic=3` (`578`-byte bootargs, [Section 6 of Existing-Partition Testing](../install/EXISTING_INSTALL.md#6-peripherals-and-interactive-desktop-test)):

- Round 1 confirmed torch, haptics, volume keys/slider, battery, wallpaper, widgets, and lock/wake, while brightness failed because DSI command buffers landed above 4 GiB (32-bit DMA limit). Fixed `kmem_alloc_contig` under 32-bit physical bounds and freed failed allocations.
- Round 2 (kernel + payload rebuilt; other 4 artifact hashes identical) allocated a 16 KiB command page at `0xfd4fc000` (`0` out-of-range rejections/write errors); owner confirmed Settings & Control Center dimming, 3x lock/wake, torch toggle (steps visually subtle—only toggle marked passing), haptics, volume UI, battery, widgets, and Wi-Fi web refresh, with teardown logging motors/torch disabled (`0`). Volume UI does not cover speaker output; battery readout does not verify full charging ([Device Validation Data](device-validation-20261030.json)).
