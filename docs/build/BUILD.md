# dipper-xnu: Ubuntu Build Guide

**English** | [简体中文](../zh-CN/docs/build/BUILD.md)

This guide targets Linux `x86_64`, developed on **Ubuntu 26.04.1 LTS**. It reproduces `dipper` adaptations from pinned upstream commits to produce the kernel, loader, UEFI image, and userspace system image.

On 2026-10-30, host builds of the kernel (`build`), `ath10k`, Mesa, userspace boot volumes, loader, UEFI, and `darwin.img` completed cleanly in an isolated source tree on a host with dependencies pre-installed (clean-machine apt package installation has not yet been tested end-to-end), followed by home-screen boot on an existing partition. See [Reproduction Report](../validation/REPRODUCTION.md) for evidence and failed checks, and [STATUS](../STATUS.md) for current capabilities.

## 1. Host Prerequisites

Run builds as an unprivileged user in a path with no spaces. Required tools:

| Purpose | Tools or Inputs |
| --- | --- |
| Source checkout | `git`, `curl`, CA certificates |
| Kernel build | C/C++ toolchain, `make`, `clang`, `lld`, `python3`, `perl`, `xz`, `flex`, `bison`, `m4` |
| UEFI build | Above tools plus `iasl`, `nasm`, `gettext`, `bc`, `rsync`, `device-tree-compiler`, `gcc-aarch64-linux-gnu`, `binutils-aarch64-linux-gnu` |
| Target cross-compile | User-staged Theos toolchain and `iPhoneOS16.5.sdk` |
| Userspace prep | `7z` (>= 23), `meson`, `ninja`, `python3-venv`, `autoconf`, `automake`, IPSW, and device firmware |

Verify host tools:

```sh
cat /etc/os-release
uname -m
command -v git python3 clang lld-link make curl xz flex bison m4 perl iasl nasm
```

Expected architecture is `x86_64`. Also install development headers for UUID, zlib, and OpenSSL (`uuid-dev zlib1g-dev libssl-dev` on Ubuntu). Reserve at least ~80 GiB of disk space for upstream sources, original archives, extracted system files, and images (not a measured minimum).

Pinned URLs, checksums, and staging steps for toolchain/SDKs are in [External Inputs](INPUTS.md). Clone this repository first, then prepare inputs there.

## 2. Clone and Verify the Repository

```sh
git clone https://github.com/youzjuzi/dipper-xnu.git
cd dipper-xnu
sha256sum -c SHA256SUMS
```

Subsequent commands assume Bash:

```sh
export DIPPER_PROJECT_ROOT="$PWD"
```

Every tracked file in `SHA256SUMS` must print `OK`. Stop if any file is missing or mismatched.

## 3. Prepare Upstream Sources

From the repository root:

```sh
python3 tools/prepare/prepare.py
```

This prints pinned upstream repos and commits without network access or creating `work/`. Next, fetch sources and apply patches:

```sh
python3 tools/prepare/prepare.py --prepare
```

The script fetches pinned commits and required submodules, overlays kernel and userspace trees, applies the HackiOS baseline and `dipper` patches onto Apple XNU (`xnu-mi8.patch` applies on top of HackiOS, not stock Apple XNU), and checks patched file SHA-256 digests. Upstream `prebuilt/` directories are never treated as rebuilt `dipper` artifacts.

Submodules are fetched shallowly as needed without recursing into OpenSSL's test subrepos while keeping pinned gitlink commits. Never bypass network failures by switching to unpinned branches.

Primary output layout:

```text
work/
├── hackios/             Merged kernel and userspace build tree
│   └── xnu-src/
│       └── xnu-8796.121.2/
├── userland/            Pinned upstream userspace copy
├── edk2/                UEFI source
└── unixnu/              Boot component dependency
```

On success it prints `Sources prepared and hashes checked.`. Do **not** run upstream `xnu/apply.sh`. `prepare.py` refuses to overwrite an existing `work/` directory; preserve logs/diffs before moving a failed tree aside instead of stacking patches on top of a broken checkout.

## 4. Build Kernel and Wi-Fi Driver

Complete [Staging Verified Archives for Build Scripts](INPUTS.md#staging-verified-archives-for-build-scripts) and verify `THEOS` is set (or staged at `local/theos` / `../dependencies/theos` for auto-detection).

For incremental builds in the main development tree, run from the repository root (auto-detects `THEOS` and passes `SOURCE_DIR="$XNU_SRC"` explicitly):

```sh
bash tools/build/build-kernel.sh [--with-ath10k] [--out work/runs/<run-id>/kernel]
```

For initial first-time dependency setup or manual step-by-step builds inside `work/hackios`:

```sh
cd "$DIPPER_PROJECT_ROOT/work/hackios"
bash xnu-deps/setup.sh
bash tools/mk-ath10k.sh
bash xnu-build.sh -j8 build SOURCE_DIR="$PWD/xnu-src/xnu-8796.121.2"
```

Adjust `-j8` to your CPU cores. `mk-ath10k.sh` pins Linux `7.0.14` and checks archive SHA-256 and per-file licenses; remaining transitive `xnu-deps` inputs are not yet fully pinned.

Expected kernel output (relative to `work/hackios/`):

```text
xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
```

Inspect file type, mtime, and digest:

```sh
file xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
stat xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
sha256sum xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
```

The output should be an ARM64 Mach-O binary. Explicit `build` succeeds with exit code `0` (headers, compilation, linking). Default `-j8 -k` running `all` still exits `2` on platform export symbol checks and LLDB `python` script calls; host linking does not prove device boot.

## 5. Build Loader and UEFI

After repartitioning, match GPT GUIDs and boundaries first per [Matching Sources to a New Partition](../install/STARTUP.md#1-matching-sources-to-a-new-partition); existing binaries must not reuse stale GUIDs. If only the unique partition GUID changed, rebuilding loader/UEFI suffices without rebuilding the kernel.

Back up previous loader/UEFI artifacts and configs to `local/backups/` before overwriting, and store new candidates in fresh `work/runs/` subdirectories—do not duplicate the whole source tree or re-run `prepare.py`.

From the repository root:

```sh
cd "$DIPPER_PROJECT_ROOT"
bash tools/build/build-loader-uefi.sh
```

This compiles `xnuloader`, packages a `usb`-capable XNUP container into `XNU_PAYLOAD`, embeds it into BootShim/UEFI, and runs the upstream `dipper` UEFI build (refuses `-b` / `--boot` and never touches a device).

Expected outputs:

| File | Purpose |
| --- | --- |
| `work/hackios/xnuloader/loader.efi` | EFI loader |
| `work/edk2/boot-dipper.img` | UEFI boot image |

The script prints SHA-256 digests on success. Note that `boot-dipper.img` does not yet contain the XNU kernel or userspace volumes.

## 6. Userspace, Packaging, and Boot

Device-side steps are covered in **[Partitioning, Flashing & Rollback](../install/INSTALL.md)**. Creating the `darwin` partition wipes Android `userdata`; the system image lives on UFS and boots via temporary RAM-loaded UEFI.

Continue with [Userspace and Packaging](USERLAND.md):

1. `tools/prepare/prepare-ios.py` verifies the IPSW and extracts system inputs locally.
2. `tools/build/build-userland.sh` builds `root.apfs` and `flashboot.apfs` from source.
3. `tools/build/pack-darwin.py` builds and verifies `darwin.img`.

Public `loader.c` contains zero-placeholder partition GUIDs and historical experimental boundaries that must be adjusted to match your real GPT and rebuilt. After host checks pass, stage [Device Inputs and Hardware Testing](USERLAND.md#4-device-inputs-and-hardware-testing) and follow [Existing-Partition Testing](../install/EXISTING_INSTALL.md).

## 7. Troubleshooting

| Issue | Where to Check |
| --- | --- |
| Public git clone fails | Check URL, network, and proxy settings |
| `work/ already exists` | Back up logs and local diffs before moving old tree aside |
| Submodule or tarball fetch fails | Keep pinned commits; inspect URL and network instead of switching branches |
| Patch check or hash mismatch | Verify pinned inputs and local edits; never ignore errors |
| Missing SDK or cross-tools | Check `THEOS`, SDK version, and toolchain path |
| Non-zero kernel exit despite binary present | Inspect full log and exit code to verify linking completed this round |
| Kernel + UEFI built but cannot boot desktop | Complete userspace, payload packaging, firmware staging, and GPT matching in Section 6 |

Include commit hash, Ubuntu version, failing command, and scrubbed logs when reporting issues. See [Contributing](../../CONTRIBUTING.md).
