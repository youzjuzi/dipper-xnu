# External Inputs and Verification

**English** | [简体中文](../zh-CN/docs/build/INPUTS.md)

These inputs are not distributed with the repository. Download them from their pinned URLs—or verify the origin and checksum of existing local archives—and place them in a separate directory. Never substitute old kernels, UEFI images, boot payloads, or modified development trees for a fresh build.

Set these paths from the repository root (or point them at other existing absolute directories):

```sh
export DIPPER_PROJECT_ROOT="$PWD"
export DIPPER_INPUTS="$DIPPER_PROJECT_ROOT/local/inputs"
export THEOS="$DIPPER_PROJECT_ROOT/local/theos"
mkdir -p "$DIPPER_INPUTS" "$THEOS/sdks" "$THEOS/toolchain"
```

Neither `local/` nor `work/` is tracked by Git. Set `THEOS` explicitly so builds do not pick up an unrelated toolchain directory.

## Download Sources

| Local Filename | Pinned URL | Purpose |
| --- | --- | --- |
| `iOSToolchain-x86_64.tar.xz` | [L1ghtmann test-210562a](https://github.com/L1ghtmann/llvm-project/releases/download/test-210562a/iOSToolchain-x86_64.tar.xz) | Theos Linux cross-linker and signing tools, Clang 11.1.0 |
| `iPhoneOS16.5.sdk.tar.xz` | [Theos master-146e41f](https://github.com/theos/sdks/releases/download/master-146e41f/iPhoneOS16.5.sdk.tar.xz) | iOS SDK |
| `MacOSX13.3.sdk.tar.xz` | [macosx-sdks 13.3](https://github.com/joseluisq/macosx-sdks/releases/download/13.3/MacOSX13.3.sdk.tar.xz) | macOS SDK headers for XNU DriverKit codegen |
| `linux-7.0.14.tar.xz` | [kernel.org](https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.0.14.tar.xz) | `ath10k` driver source |
| `freebsd-15.1-src.txz` | [FreeBSD 15.1 src.txz](https://download.freebsd.org/releases/amd64/15.1-RELEASE/src.txz) | LinuxKPI source; rename as shown in the first column |
| `mesa-25.0.7.tar.xz` | [Mesa archive](https://archive.mesa3d.org/mesa-25.0.7.tar.xz) | Graphics driver source |
| `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw` | [Apple CDN](https://updates.cdn-apple.com/2023SpringFCS/fullrestores/032-85130/6AB0D10A-8AF9-4F6C-8CF5-A1B315CABE88/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw) | iOS 16.5 / 20F66 system materials |

Typical download command: `curl --fail --location --retry 3 '<url>' -o "$DIPPER_INPUTS/<filename>"`. Keep the original archives for verification and rebuilds. Reused archives are valid only when filename, version, and SHA-256 match exactly—matching filenames or byte sizes alone are insufficient.

For all archives except the iPhoneOS SDK, verify in `$DIPPER_INPUTS`:

```sh
cd "$DIPPER_INPUTS"
sha256sum -c <<'SUMS'
a72a7a577e2fbe2838b6b5e9c72034fa7d114af96f0e1d4b016f18730ce4056e  iOSToolchain-x86_64.tar.xz
518e35eae6039b3f64e8025f4525c1c43786cc5cf39459d609852faf091e34be  MacOSX13.3.sdk.tar.xz
de9999b784d2293f00d39c62d8f92a08ab8a54bc4e80ffd250a0c09cb07a0f98  linux-7.0.14.tar.xz
cf5762da53fd52e1eaf0f9ceee9bf58cbe314c821031d0d9ffa76823185a89e1  freebsd-15.1-src.txz
592272df3cf01e85e7db300c449df5061092574d099da275d19e97ef0510f8a6  mesa-25.0.7.tar.xz
c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2  iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw
SUMS
```

Stop if any checksum fails. Upstream publishes no SHA-256 for the toolchain archive: this SHA-256 was recorded after checking the GitHub release asset's 86,163,280-byte size and CDN Content-MD5 `7c31257bb7cca03e4130955bf00aee4e`; it is not an upstream signature. Remaining digests match the SDK release metadata, kernel.org, FreeBSD MANIFEST, pinned upstream build scripts, and Apple CDN `x-amz-meta-digest-sha256`.

## Installing Toolchain and SDK

Target directories below must start empty; do not overwrite another installation. The toolchain archive unpacks `linux/iphone/`:

```sh
tar -xJf "$DIPPER_INPUTS/iOSToolchain-x86_64.tar.xz" -C "$THEOS/toolchain"
tar -xJf "$DIPPER_INPUTS/iPhoneOS16.5.sdk.tar.xz" -C "$THEOS/sdks"
python3 "$DIPPER_PROJECT_ROOT/tools/prepare/check-sdk.py" "$THEOS/sdks/iPhoneOS16.5.sdk"
"$THEOS/toolchain/linux/iphone/bin/clang" --version
```

An already unpacked SDK can be copied to the same location and checked with `check-sdk.py`, which verifies contents, symlinks, and executable bits for all 8,867 files against Theos commit `146e41ff2c292168388929e43c9b4de2f00e36b3` (Git tree `81466d46b666daa04ae3d2b0b9d5324f0f621359`).

## Staging Verified Archives for Build Scripts

After running `tools/prepare/prepare.py --prepare`:

```sh
K="$DIPPER_PROJECT_ROOT/work/hackios"
mkdir -p "$K/xnu-deps/build/ath10k" "$K/xnu-deps/build/mesa"
cp "$DIPPER_INPUTS/linux-7.0.14.tar.xz" "$DIPPER_INPUTS/freebsd-15.1-src.txz" "$K/xnu-deps/build/ath10k/"
cp "$DIPPER_INPUTS/mesa-25.0.7.tar.xz" "$K/xnu-deps/build/mesa/"
tar -xJf "$DIPPER_INPUTS/MacOSX13.3.sdk.tar.xz" -C "$K/xnu-deps" \
  --wildcards '*MacOSX13.3.sdk/System/Library/Frameworks/Kernel.framework*'
```

The kernel dependency setup script still fetches pinned Apple open-source libraries and host tool sources, and the first Mesa build installs Python dependencies inside an isolated venv, so those steps are not fully offline. Device firmware is covered in [Userspace and Packaging](USERLAND.md) and must never be guessed from another device model.

## WCN3990 Wi-Fi Feature File

Besides radio firmware read from the device's `modem` partition, `ath10k` requires linux-firmware's [WCN3990/hw1.0/firmware-5.bin](https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/ath10k/WCN3990/hw1.0/firmware-5.bin). Verified on 2026-10-30 as 60 bytes with SHA-256:

```text
fef6539e0127579536bc977be57a90d018b83f2931fedc3a8870fbe38d6c4127
```

This file describes `ath10k` WMI/HTT feature flags only and contains no executable DSP firmware; it does not replace device `modem`, `wlanmdsp`, or board data (`wpss.mdt` from other devices is not used). Verify the digest, copy to `work/hackios/fw-wifi/firmware-5.bin`, and rebuild userspace with `tools/build/build-userland.sh`; `tools/build/build-payload.py --wifi` reads it back from `root.apfs` and rejects missing or mismatched files.
