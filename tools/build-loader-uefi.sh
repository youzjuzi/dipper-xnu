#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Host-only compilation. Requires tools/prepare.py --prepare first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
W="$ROOT/work"
# Keep this entry point fixed to dipper. Forwarding arbitrary upstream options
# could select another device/output or trigger fastboot via combined flags.
[ "$#" -eq 0 ] || { echo 'This is a host-only dipper build; no arguments are accepted.' >&2; exit 1; }
[ -f "$W/hackios/xnuloader/build.sh" ] || { echo 'Prepare sources first.' >&2; exit 1; }
(cd "$W/hackios/xnuloader" && bash build.sh)
# Keep generated binaries in ignored work/, not in the public source package.
mkdir -p "$W/packages/XnuLoaderPkg/Binary"
cp -a "$ROOT/bootloader/uefi/XnuLoaderPkg/." "$W/packages/XnuLoaderPkg/"
cp "$W/hackios/xnuloader/loader.efi" "$W/packages/XnuLoaderPkg/Binary/loader.efi"
# The loader starts its USB service only when the BootShim-provided XNUP
# container includes a usb entry. A bare UEFI image cannot accept stage/run.
python3 "$W/hackios/xnuloader/mkpayload.py" --usb -o "$W/packages/xnuloader-usb.bin"
export XNU_PAYLOAD="$W/packages/xnuloader-usb.bin"
link_package() {
    local target="$1" name="$2" path="$W/edk2/$2"
    if [ -e "$path" ] || [ -L "$path" ]; then
        [ -L "$path" ] && [ "$(readlink "$path")" = "$target" ] || { echo "Existing package conflict: $name" >&2; exit 1; }
    else
        ln -s "$target" "$path"
    fi
}
link_package "$W/packages/XnuLoaderPkg" XnuLoaderPkg
link_package "$W/unixnu/package/UniXNUPkg" UniXNUPkg
link_package "$W/unixnu/drivers/DarwinBoot/DarwinBootPkg" DarwinBootPkg
mkdir -p "$W/host-bin"
cp "$ROOT/tools/build/cc-gnu17/cc" "$W/host-bin/cc"
chmod +x "$W/host-bin/cc"
cp "$W/host-bin/cc" "$W/host-bin/gcc"
export MI8_ROOT="$ROOT"
export EDK2_ROOT="$W/edk2/Common/edk2"
export PATH="$W/host-bin:$PATH"
(cd "$W/edk2" && bash build.sh -d dipper)
sha256sum "$W/hackios/xnuloader/loader.efi" "$W/edk2/boot-dipper.img"
