# Third-Party Notices and Modification Summary

**English** | [简体中文](docs/zh-CN/THIRD_PARTY_NOTICES.md)

Updated: 2026-10-31. Pinned upstream revisions are recorded in `upstream.lock.json`, and patched files with content digests are listed in `source-manifest.json`. Patches contain `dipper` platform adaptations; upstream copyright and license notices continue to apply.

| Origin | Scope of Use | License and Notices |
| --- | --- | --- |
| [HackiOS kernel](https://github.com/oosexgang/hackios-xnu-kernel) | `xnuloader`, build entry points, wireless glue, XNU baseline | Root APSL 2.0; per-file exceptions and added file attribution audited individually |
| [Apple XNU](https://github.com/apple-oss-distributions/xnu) | Mi 8 deltas on XNU 8796.121.2 | APSL 2.0 and other original file licenses |
| [HackiOS userland](https://github.com/oosexgang/hackios-xnu-userland) | Display, Wi-Fi, launchd, and injection shims | Root MIT; Mesa-derived files keep separate attribution |
| [edk2-sdm845](https://github.com/edk2-porting/edk2-sdm845) | `dipper` platform, BootShim | Root license included; submodules keep their respective licenses |
| SimpleInit (edk2 submodule) | `NULL`-free guard modification | `malloc.c` carries an Intel file-level BSD notice; original notice and EDK2 history are in `LICENSES/`, while the root LGPL text is kept separately |
| [UniXNU](https://github.com/UniXNU/UniXNU) | Library build patch and `XnuLoaderDxe`-derived registrar | Package `BSD-2-Clause-Patent` included |
| [Linux](https://www.kernel.org/) / ath10k | WLFW tables and wireless source fetch script | In-file ISC notices and copyright headers retained; Linux as a whole is not claimed as ISC |
| [Mesa](https://gitlab.freedesktop.org/mesa/mesa) / freedreno | DRM adaptation and graphics build dependency | Patches modify HackiOS's MIT IOKit DRM layer; full Mesa dependencies remain under their respective upstream licenses |
| [FreeBSD](https://github.com/freebsd/freebsd-src) | Upstream wireless compatibility base | Original BSD-2-Clause notice for `linux_80211.c` added to `LICENSES/` |

Full source trees of these projects are not copied into this repository. Upstream sources fetched by scripts remain subject to their original licenses. Providing links and notices does not replace copyright retention, source availability, or other license obligations.

## External Device Maintenance Tools

[Team Win / TWRP](https://twrp.me/xiaomi/xiaomimi8.html) and the `dipper` maintainers provide the Recovery environment required for device maintenance; this project has verified version `3.7.0_9-0`. TWRP is used for partition maintenance, `Format Data`, and readback checks, and is not an iOS UEFI or kernel component. This repository only links to the official download page and instructions without bundling or mirroring TWRP binaries; its rights and license follow upstream terms.

## GPU Code License Scope

Linux-derived GPU initialization tables retain their origin, copyrights, and the full GPL-2.0-only license text, kept separate from ISC `ath10k` files. Because the table is `#include`d directly by an APSL kernel driver, combined binary distribution terms remain unresolved. Permissive sources from Mesa/freedreno and Fuchsia cover only part of the initialization; origins, gaps, and verification scope are documented in [GPU License Notes](docs/legal/GPU_LICENSE.md).

Original `dipper` modifications authored by **yanei** are licensed under MIT. Third-party file notices and author attributions are preserved and excluded from that MIT grant.
