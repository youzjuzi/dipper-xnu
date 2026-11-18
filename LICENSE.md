# Licensing

**English** | [简体中文](docs/zh-CN/LICENSE.md)

This project uses different licenses depending on file origin and component. Original portions by **yanei** are licensed under the MIT License; pre-existing third-party code and derivatives remain governed by their respective terms.

| Scope | License and Notices |
| --- | --- |
| Original docs, packaging/build scripts, standalone config/compat headers, and inventoried original modules | [MIT](LICENSES/MI8-packaging-MIT.txt); see [License Review](docs/legal/LICENSE_REVIEW.md#original-mit-scope) for original modules inside patches |
| XNU / HackiOS-derived kernel and loader modifications | [APSL 2.0](LICENSES/APSL-2.0.txt); existing file notices continue to apply |
| WLFW ISC files | [ISC](LICENSES/ISC.txt) plus in-file Linux Foundation / Qualcomm copyrights |
| HackiOS userspace modifications | [Upstream MIT](LICENSES/HackiOS-userland-MIT.txt) |
| edk2-sdm845 platform modifications | [Platform License](LICENSES/edk2-sdm845.txt) |
| Modifications to `malloc.c` in SimpleInit | Intel file-level BSD notice; see [Original Notice](LICENSES/SimpleInit-malloc-notice.txt) and [Historical License](LICENSES/EDK2-License-History.txt) rather than the root SimpleInit LGPL |
| UniXNU-derived UEFI registrar and library config modifications | [BSD-2-Clause-Patent](LICENSES/UniXNU-package.txt) |
| FreeBSD `linux_80211.c`-derived compatibility helpers | [BSD-2-Clause Notice](LICENSES/FreeBSD-linux_80211-BSD-2-Clause.txt) |
| Linux-derived GPU initialization tables | [GPL-2.0-only](LICENSES/GPL-2.0-only.txt), **not** MIT; see [GPU License Notes](docs/legal/GPU_LICENSE.md) regarding combination with the APSL kernel |

For the per-file inventory see [license-inventory.json](license-inventory.json), and for origins and modification summaries see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). License texts, copyright headers, and required modification notices must be preserved.

The source statement and full GPL text for the GPU tables are retained; distribution compatibility when combined with the APSL kernel remains unresolved (see [GPU License Notes](docs/legal/GPU_LICENSE.md)). Additional APSL file notices are tracked in [License Review](docs/legal/LICENSE_REVIEW.md). `Experimental / Work in Progress` indicates development status and does not waive any file's license terms.
