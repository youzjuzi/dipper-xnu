# 许可证

本项目按文件与来源采用不同许可证。**yanei** 的原创部分采用 MIT 许可证；第三方原有代码及派生部分继续遵守对应条款。

| 范围 | 许可与通知 |
| --- | --- |
| 原创文档、发布脚本、独立配置/兼容头及清单中确认的原创模块 | [MIT](LICENSES/MI8-packaging-MIT.txt)，具体补丁内原创模块见 [核对记录](docs/legal/LICENSE_REVIEW.md#原创-mit-范围) |
| XNU/HackiOS 派生内核和加载器修改 | [APSL 2.0](LICENSES/APSL-2.0.txt)，原文件其他声明继续适用 |
| WLFW 的 ISC 文件 | [ISC](LICENSES/ISC.txt) 及文件内 Linux Foundation/Qualcomm 版权 |
| HackiOS 用户空间修改 | [上游 MIT](LICENSES/HackiOS-userland-MIT.txt) |
| edk2-sdm845 平台修改 | [平台许可证](LICENSES/edk2-sdm845.txt) |
| SimpleInit 中 malloc.c 的修改 | Intel 文件级 BSD 声明；见 [原通知](LICENSES/SimpleInit-malloc-notice.txt) 与 [历史许可](LICENSES/EDK2-License-History.txt)，不能仅按 SimpleInit 根 LGPL 判断 |
| UniXNU 衍生 UEFI 注册器及库配置修改 | [BSD-2-Clause-Patent](LICENSES/UniXNU-package.txt) |
| FreeBSD linux_80211.c 派生兼容函数 | [BSD-2-Clause 原通知](LICENSES/FreeBSD-linux_80211-BSD-2-Clause.txt) |
| Linux 派生的 GPU 初始化表 | [GPL-2.0-only](LICENSES/GPL-2.0-only.txt)，不属于 MIT；与 APSL 内核组合后的分发条件见 [GPU 许可说明](docs/legal/GPU_LICENSE.md) |

完整清单见 [license-inventory.json](license-inventory.json)，来源与修改说明见 [第三方清单](THIRD_PARTY_NOTICES.md)。许可证全文、版权声明与必要的修改通知需要一并保留。

GPU 表的来源声明和 GPL 全文已保留；与 APSL 内核组合的分发条件尚未解决，详见 [GPU 许可说明](docs/legal/GPU_LICENSE.md)。其他 APSL 文件通知见 [许可证说明](docs/legal/LICENSE_REVIEW.md)。`Experimental / Work in Progress` 表示项目处于开发阶段，各文件的许可证仍然适用。
