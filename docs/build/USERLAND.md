# Userspace Build and Host Packaging

**English** | [简体中文](../zh-CN/docs/build/USERLAND.md)

Complete source preparation, kernel dependencies, and kernel build in the [Build Guide](BUILD.md), and set `DIPPER_PROJECT_ROOT`, `DIPPER_INPUTS`, and `THEOS` first. Commands here operate on host files only; device steps are in [Existing-Partition Testing](../install/EXISTING_INSTALL.md).

## 1. Extract Verified iOS Materials

Requires 7-Zip (`7z`) version 23 or newer with APFS support. From the repository root:

```sh
python3 tools/prepare/prepare-ios.py \
  --ipsw "$DIPPER_INPUTS/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw"
```

The script verifies the full IPSW SHA-256 and `BuildManifest.plist`, then extracts three DMGs (existing DMGs are hash-checked and aborted on mismatch without overwriting). It then invokes pinned `ios165/fetch.sh` to populate `rootfs`, `cryptex`, and `dyld_shared_cache` under the current `work/` tree and records provenance in `work/hackios/ios165/input-provenance.json`. Do not symlink `ios165/rootfs` to an unrelated directory.

## 2. Build Boot Volumes (`root.apfs` & `flashboot.apfs`)

```sh
export BUILD_TIMEZONE=Asia/Tokyo   # Or your local timezone; falls back to UTC
export BUILD_JOBS=8
bash tools/build/build-userland.sh
```

The wrapper sets `GL=1 FLASHBOOT=1 CRYPTEXES=flash SKIP_SYSTEM=1 SHARE=1 REST=1 BT=1` (`BT=1` includes `bluetoothd`, `BlueTool`, injection dylib, and placeholder HCD for `bt=7`, while chip firmware from `fw-bt/` is packed into `flashboot.apfs`; `SHARE=1` omits local Wi-Fi passwords/SSH keys; `PREBUILT` is rejected). `umask 022` keeps launchd plists non-group-writable.

| Output (under `work/hackios/`) | Purpose |
| --- | --- |
| `userland/root.apfs` | Adapted binaries, dylibs, launchd plists; kernel payload `ramdisk` |
| `userland/flashboot.apfs` | Small boot volume staged via `fastboot stage` |
| `userland/obj/` | Compiled userspace binaries and libraries |
| `xnu-deps/build/mesa/out/` | Mesa build output |

If GPU firmware files are missing, compilation still completes while reporting the missing blobs—images lacking firmware are not device-ready. The APFS packer uses Python multiprocessing; restricted sandboxes must allow local IPC or fail cleanly rather than ignoring `PermissionError`.

## 3. Build Raw `darwin.img`

```sh
python3 tools/build/pack-darwin.py
```

Outputs `work/images/darwin.img` (`8,365,539,328` bytes). Refuses to overwrite existing files, checks provenance and APFS `NXSB` magic/sizes, and requires final SHA-256:

```text
9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560
```

Crucial detail: `rootfs.dmg` wraps a full GPT disk in UDIF. `pack-darwin.py` extracts only the APFS partition (`7z x -tDmg -so ... 3.apfs`) and appends `cryptex-os.dmg` and `cryptex-app.dmg`—never write the compressed DMG or full GPT disk wrapper directly. Any `.partial` file left on error must not be flashed.

## 4. Device Inputs and Hardware Testing

After host compilation, prepare device-specific inputs per [Device Preparation](../install/DEVICE_PREPARATION.md) before testing per [Existing-Partition Testing](../install/EXISTING_INSTALL.md):

- **GPU firmware**: Stage matching `a630_gmu.bin`, `a630_sqe.fw`, `a630_zap.mdt`, and `a630_zap.b02` into `work/hackios/fw-gpu/`, verify hashes, and rebuild boot volumes.
- **Wi-Fi**: Kernel reads baseband/board data from Android's `modem` partition; stage verified [WCN3990 feature file](INPUTS.md#wcn3990-wi-fi-feature-file) `firmware-5.bin` into `work/hackios/fw-wifi/` and rebuild `root.apfs`. Check your `modem` layout rather than using unrelated `wpss`/`qca6750` examples.
- **Device GPT config**: Public `loader.c` uses zero placeholder `BLOCK_DARWIN_UNIQ`; align GUID and UFS bounds to your GPT and rebuild ([Matching Sources to a New Partition](../install/STARTUP.md#1-matching-sources-to-a-new-partition)).
- **Payload packaging**: `tools/build/build-payload.py --output work/runs/desktop-01` packages a bounded RAM-boot payload (`--wifi` adds Wi-Fi, Bluetooth, and speaker audio defaults).

Inspect device state read-only first, match configs, package a run directory, and log verified findings in [Reproduction Report](../validation/REPRODUCTION.md).
