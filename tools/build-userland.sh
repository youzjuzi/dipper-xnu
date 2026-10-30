#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build the UFS route's host artifacts; no device operations.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K="$ROOT/work/hackios"
: "${THEOS:?Set THEOS to the verified local SDK/toolchain directory}"
[ -z "${PREBUILT:-}" ] || { echo 'PREBUILT is not allowed for source reproduction.' >&2; exit 1; }
[ -x "$THEOS/toolchain/linux/iphone/bin/ld" ] || { echo 'Missing Theos linker.' >&2; exit 1; }
[ -x "$K/xnu-deps/host/bin/ld64" ] || { echo 'Run xnu-deps/setup.sh first.' >&2; exit 1; }
for input in ios165/rootfs.slt ios165/system.manifest ios165/var.skel \
    ios165/20F66__iPhone10,3_6/dyld_shared_cache_arm64 ios165/cryptex-app.dmg; do
    [ -f "$K/$input" ] || { echo "Missing $input; run tools/prepare-ios.py first." >&2; exit 1; }
done
export LDID="$THEOS/toolchain/linux/iphone/bin/ldid"
[ -x "$LDID" ] || { echo "Missing $LDID" >&2; exit 1; }
export GL=1 FLASHBOOT=1 CRYPTEXES=flash SKIP_SYSTEM=1 SHARE=1 REST=1
export RC_JOBS="$ROOT/system/userland/rc.jobs.desktop"
export DENY_MORE="fairplayd voicemail"
# Upstream JOBS selects launchd labels, not the compilation parallelism.
unset PREBUILT JOBS
bash "$K/userland/build.sh"
sha256sum "$K/userland/root.apfs" "$K/userland/flashboot.apfs"
missing=0
for name in a630_gmu.bin a630_sqe.fw a630_zap.mdt a630_zap.b02; do
    if [ ! -f "$K/fw-gpu/$name" ]; then
        echo "Missing device firmware: fw-gpu/$name" >&2
        missing=1
    fi
done
if [ "$missing" -ne 0 ]; then
    echo 'Host compilation completed; these images lack GPU firmware and are not ready for device testing.' >&2
else
    echo 'Host compilation completed. Device layout, Wi-Fi inputs and boot arguments still need review.'
fi
