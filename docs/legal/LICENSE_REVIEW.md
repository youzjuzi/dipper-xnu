# License Scope and Open Review Items

**English** | [简体中文](../zh-CN/docs/legal/LICENSE_REVIEW.md)

Updated: 2026-10-30.

This page explains the licensing basis for the 74 inventoried target source files in `source-manifest.json` and accompanying code/configs, based on pinned upstream commits, file-level headers, and source origins. For the per-file list see [license-inventory.json](../../license-inventory.json).

## Established License Notices

- Original modules, documentation, standalone configurations, and build scripts authored by **yanei** use MIT; third-party-derived parts retain their respective licenses.
- WLFW ISC files retain Linux Foundation / Qualcomm copyrights and are tracked separately from APSL files.
- HackiOS upstream userspace uses MIT. `redwood_drm.c` is its IOKit DRM shim; external Mesa build dependencies remain governed by their respective file licenses.
- `libs/compatible/malloc.c` in SimpleInit carries an Intel file-level BSD notice; the original notice and EDK2 historical license live in `LICENSES/`. SimpleInit's root LGPL does not override that file's notice.
- `lx_ath10k_gaps.c` references FreeBSD `linux_80211.c`; the relevant BSD-2-Clause author notice is in `LICENSES/`.
- `XnuLoaderDxe` derives from the UniXNU registrar and retains UniXNU contributors' copyright and `BSD-2-Clause-Patent` notice.

## Open Licensing Items

1. **GPU initialization tables**: Linux `v7.2.10` origin and exact correspondence of the 105 HWCG entries and 32 CP protection entries are confirmed. `mi8_a630_hw_init.inc` is marked `GPL-2.0-only` with original copyright and full GPL text preserved. Stating provenance does not resolve combined distribution terms with the APSL kernel.
2. **GPU driver integration**: `mi8_adreno.c` directly `#include`s and executes that table; permissive sources from Mesa and Fuchsia cover only subsets without an equivalent drop-in replacement. See [GPU License Notes](GPU_LICENSE.md) for gaps, source digests, and replacement criteria. Distributing sources only (no merged binaries) avoids distribution-time conflict while leaving the underlying incompatibility unresolved.
3. **APSL file notices**: XNU/HackiOS-derived edits require retaining applicable per-file notices and modification dates; some incremental patches still need those notices completed. Root license files do not substitute for file-level notices.

`Experimental / Work in Progress` denotes development status and does not alter these license requirements. This page does not certify full-system or binary distribution compliance.

## Original MIT Scope

The following original modules live in the respective patches under MIT while preserving existing third-party notices:

- `xnu-mi8 : bsd/dev/mi8_glink.c`
- `xnu-mi8 : bsd/dev/mi8_glink.h`
- `xnu-mi8 : bsd/dev/mi8_hostsvc.c`
- `xnu-mi8 : bsd/dev/mi8_hostsvc.h`
- `xnu-mi8 : bsd/dev/mi8_hostsvc_k.c`
- `xnu-mi8 : bsd/dev/mi8_wlfw_k.c`
- `xnu-mi8 : bsd/sys/mi8_lx.h`
- `hackios-kernel : tools/mk-ath10k.sh`
- `hackios-kernel : wifi/lx/include-ath10k/linux/acpi.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/clk.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/io.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/iommu.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/nvmem-consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/of.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/of_device.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/platform_device.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/property.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/pwrseq/consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/qrtr.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/regulator/consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/remoteproc/qcom_rproc.h`
- `hackios-kernel : wifi/lx/include-ath10k/lx_ath10k_prelude.h`
- `hackios-kernel : wifi/lx/include/lx_ath10k_cfg.h`
- `hackios-kernel : wifi/lx/include/lx_wlfw.h`
- `hackios-kernel : wifi/lx/src-ath10k/lx_ath10k_bus.c`
- `hackios-kernel : wifi/lx/src-ath10k/lx_ath10k_qmi.c`

Exact content digests are recorded in `source-manifest.json` and pinned upstream commits in `upstream.lock.json`. Project documentation, source-preparation/build scripts, and standalone configs/compat headers explicitly marked MIT also use MIT.
