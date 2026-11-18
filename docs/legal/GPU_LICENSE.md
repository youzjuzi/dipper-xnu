# GPU Source Provenance and Licensing

**English** | [简体中文](../zh-CN/docs/legal/GPU_LICENSE.md)

Updated: 2026-10-31.

Existing GPU functionality is retained. `mi8_a630_hw_init.inc` is marked `GPL-2.0-only` per its Linux-derived provenance, preserving upstream author notices and the full [GPL 2.0 text](../../LICENSES/GPL-2.0-only.txt). This provenance notice does **not** constitute permission to distribute it linked into an APSL kernel binary.

## Distribution Policy

The conflict between GPL-2.0 and APSL 2.0 arises when **distributing merged binaries** containing both (prebuilt kernels, kernelcaches, boot images, or system images containing that kernel). Therefore, since 2026-10-31, this project:

- **Distributes sources, patches, build scripts, and documentation only.** `mi8_a630_hw_init.inc` remains a separate `GPL-2.0-only` file with upstream notices while other files retain their respective licenses; no file is relicensed.
- **Does not distribute or host** any prebuilt kernel or merged binary containing that table, including file hosts, release attachments, or installer payloads.
- Requires users to compile on **their own machine** following the [Build Guide](../build/BUILD.md) for personal use only.

Notes:

1. This constrains distribution behavior rather than resolving the underlying license incompatibility. Any third party redistributing merged binaries assumes full licensing responsibility; never share merged binaries in issues, drives, or installers.
2. Providing prebuilt kernels in the future requires replacing the table with an independently verified compatible source or obtaining additional permission from rights holders.
3. This document is a provenance audit record, not legal advice.

## Verified Provenance

`mi8_adreno.c` directly `#include "mi8_a630_hw_init.inc"` and executes its tables inside the kernel rather than as a standalone document or separate process.

Comparison against exported repository patches:

| Item | Result |
| --- | --- |
| Primary init table | 180 register writes |
| HWCG table | 105 entries; symbol names and values match Linux `v7.2.10` `a630_hwcg` identically |
| CP protect table | 32 entries; encodings match Linux `v7.2.10` `a630_protect_regs` identically |
| Upstream file headers | `a6xx_gpu.c` (`GPL-2.0`), `a6xx_catalog.c` (`GPL-2.0-only`) |

This correspondence establishes derivation; individual register numbers alone do not make an extracted table, sequence, and helper code MIT-relicensable. Changing the root license, splitting into patches, downloading locally, or adding an Experimental banner does not alter upstream rights.

GNU's [license list](https://www.gnu.org/licenses/license-list.html#apsl2) explicitly classifies APSL 2.0 as GPL-incompatible. Preserving GPL notices and providing source satisfies source attribution only, not combined-binary redistribution.

## Permissive-License Candidates

### Mesa / freedreno

[a6xx.xml](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-25.0.7/src/freedreno/registers/adreno/a6xx.xml) carries the [freedreno copyright and permissive notice](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-25.0.7/src/freedreno/registers/freedreno_copyright.xml), usable for register names, offsets, and bitfields.

Register definitions alone cannot substitute for an initialization recipe: those XML files do not provide the 105 HWCG values, full CP protection policy, or execution ordering. Swapping register symbol names does not resolve Linux derivation of the sequence.

### Historical Fuchsia Adreno Driver

Pinned commit: `d05398df901609c870db41e1558eeafcbf4320b7`.

- [Device init](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/src/graphics/drivers/msd-qcom-adreno/src/msd_qcom_device.cc)
- [Register definitions](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/src/graphics/drivers/msd-qcom-adreno/src/registers.h)
- [BSD-3-Clause license](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/LICENSE)

Useful as a candidate reference for memory ranges, select core registers, ring buffers, and partial CP protection, with notable gaps:

- `HardwareInit()` calls `EnableClockGating(false)` which only succeeds if HWCG is already disabled and returns unimplemented otherwise—no HWCG table is included.
- CP protection covers 26 entries rather than the current 32, with differing protected ranges and values.
- GMU, power rails, SMMU, firmware, and entry states must still be matched to `dipper`. No drop-in replacement is proven.
- Even in later commits up to removal (`16e2530aabedcb2f8cf8eff076278e60535965f7`), that unmaintained driver did not provide a complete replacement.

Fuchsia is a partially compatible reference not yet integrated; retaining its license copy documents candidate evaluation only.

### Qualcomm KGSL

The audited [Qualcomm KGSL A6xx implementation](https://github.com/qualcomm-linux/kgsl/blob/gfx-kernel.le.0.0/adreno_a6xx.c) is likewise `GPL-2.0-only` and not a permissive replacement.

## Requirements for Any Future Replacement

Replacing the Linux-derived init sequence while keeping GPU support requires either a fully compatible source or extra rights-holder authorization, with independent hardware justification for every register, value, reserved bit, precondition, HWCG/GMU/security ordering, and non-reduced CP protection coverage, followed by cold-boot, submit-completion, display, and teardown verification on real hardware by the device owner.

Until both a complete compatible source and hardware verification exist, the licensing conflict remains open.

## Verification Record

- Preprocessor output of the init fragment remained identical before and after adding file header notices; no register values, order, or function logic changed.
- Replaying the updated XNU patch in an isolated directory matched all 34 entries in the updated `source-manifest.json`.
- Original driver and init tables in the development tree were left untouched and no device operations were run.

Exact source URLs, SHA-256 digests, and comparison results are stored in [gpu-source-audit.json](gpu-source-audit.json).
