#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 yanei
# Incremental host kernel build using the standard XNU BUILD tree; no device operations.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
K="$ROOT/work/hackios"
XNU_SRC="$K/xnu-src/xnu-8796.121.2"
DEFAULT_KERNEL="$XNU_SRC/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837"

usage() {
    cat <<'EOF'
Usage: tools/build/build-kernel.sh [-j N|--jobs N] [--with-ath10k] [--out DIR]
  -j, --jobs N     Parallel make jobs (default: nproc or 8)
  --with-ath10k    Rebuild ath10k.o via work/hackios/tools/mk-ath10k.sh first
  --out DIR        Copy built kernel.macho, kernel.sha256, and kernel-build.log to DIR
  -h, --help       Show this help
EOF
}

JOBS="$(nproc 2>/dev/null || echo 8)"
WITH_ATH10K=0
OUT_DIR=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -j|--jobs)
            [ "$#" -ge 2 ] || { echo "Missing value for $1" >&2; exit 1; }
            JOBS="$2"
            shift 2
            ;;
        -j*)
            JOBS="${1#-j}"
            shift
            ;;
        --jobs=*)
            JOBS="${1#--jobs=}"
            shift
            ;;
        --with-ath10k)
            WITH_ATH10K=1
            shift
            ;;
        --out)
            [ "$#" -ge 2 ] || { echo "Missing value for --out" >&2; exit 1; }
            OUT_DIR="$2"
            shift 2
            ;;
        --out=*)
            OUT_DIR="${1#--out=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -b|--boot)
            echo "Refusing device boot option ($1): host-only build." >&2
            exit 1
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

case "$JOBS" in
    ''|*[!0-9]*)
        echo "Invalid --jobs value: $JOBS" >&2
        exit 1
        ;;
esac
[ "$JOBS" -ge 1 ] || { echo "Invalid --jobs value: $JOBS" >&2; exit 1; }

if [ -z "${THEOS:-}" ]; then
    if [ -d "$ROOT/local/theos/toolchain/linux/iphone" ]; then
        THEOS="$ROOT/local/theos"
    elif [ -d "$ROOT/../dependencies/theos/toolchain/linux/iphone" ]; then
        THEOS="$(cd "$ROOT/../dependencies/theos" && pwd)"
    fi
fi
: "${THEOS:?Set THEOS to the verified local SDK/toolchain directory}"
export THEOS
[ -x "$THEOS/toolchain/linux/iphone/bin/ld" ] || { echo "Missing Theos linker under THEOS." >&2; exit 1; }

[ -f "$K/xnu-env.sh" ] && [ -f "$K/xnu-build.sh" ] && [ -d "$XNU_SRC" ] || {
    echo "Prepare sources first: python3 tools/prepare/prepare.py --prepare" >&2
    exit 1
}

if [ -n "$OUT_DIR" ]; then
    mkdir -p "$OUT_DIR"
    OUT_DIR="$(cd "$OUT_DIR" && pwd)"
    [ ! -e "$OUT_DIR/kernel.macho" ] || {
        echo "Refusing to overwrite existing $OUT_DIR/kernel.macho; use a new directory." >&2
        exit 1
    }
fi

if [ "$WITH_ATH10K" -eq 1 ]; then
    if [ -n "$OUT_DIR" ]; then
        (cd "$K" && bash tools/mk-ath10k.sh) 2>&1 | tee "$OUT_DIR/ath10k-build.log"
    else
        (cd "$K" && bash tools/mk-ath10k.sh)
    fi
fi

# shellcheck source=/dev/null
source "$K/xnu-env.sh"
export XNU_SRC

if [ -n "$OUT_DIR" ]; then
    bash "$K/xnu-build.sh" -j"$JOBS" build SOURCE_DIR="$XNU_SRC" 2>&1 | tee "$OUT_DIR/kernel-build.log"
else
    bash "$K/xnu-build.sh" -j"$JOBS" build SOURCE_DIR="$XNU_SRC"
fi

[ -s "$DEFAULT_KERNEL" ] || { echo "Missing or empty kernel artifact: $DEFAULT_KERNEL" >&2; exit 1; }
sha256sum "$DEFAULT_KERNEL"

if [ -n "$OUT_DIR" ]; then
    cp -a "$DEFAULT_KERNEL" "$OUT_DIR/kernel.macho"
    (cd "$OUT_DIR" && sha256sum kernel.macho > kernel.sha256)
    echo "Copied kernel to $OUT_DIR/kernel.macho"
fi
