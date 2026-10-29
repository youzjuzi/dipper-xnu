# 第三方来源与修改记录

更新日期：2026-10-30。上游版本见 `upstream.lock.json`，适配文件及其内容摘要见 `source-manifest.json`。补丁包含 dipper 平台适配，原有第三方版权和许可声明继续适用。

| 来源 | 使用范围 | 许可证与通知 |
|---|---|---|
| [HackiOS kernel](https://github.com/oosexgang/hackios-xnu-kernel) | xnuloader、构建入口、无线 glue；XNU 基线 | 根 APSL 2.0；逐文件例外与新增文件归属待审计 |
| [Apple XNU](https://github.com/apple-oss-distributions/xnu) | XNU 8796.121.2 上的 Mi 8 增量 | APSL 2.0 及原文件其他许可 |
| [HackiOS userland](https://github.com/oosexgang/hackios-xnu-userland) | 显示、Wi-Fi、launchd 与注入适配 | 根 MIT；Mesa 派生文件保留独立归属 |
| [edk2-sdm845](https://github.com/edk2-porting/edk2-sdm845) | dipper 平台、BootShim | 根许可证已附；子模块分别遵守原许可 |
| SimpleInit（edk2 子模块） | NULL 释放保护修改 | malloc.c 适用 Intel 文件级 BSD；原通知和 EDK2 历史许可见 LICENSES/，根 LGPL 文本另保留 |
| [UniXNU](https://github.com/UniXNU/UniXNU) | 库构建补丁与 XnuLoaderDxe 派生注册器 | package 的 BSD-2-Clause-Patent 已附 |
| [Linux](https://www.kernel.org/) / ath10k | WLFW 表与无线源码获取脚本 | 文件中的 ISC 及版权头保留；不将整个 Linux 声称为 ISC |
| [Mesa](https://gitlab.freedesktop.org/mesa/mesa) / freedreno | DRM 适配与渲染构建依赖 | 本补丁修改的是 HackiOS MIT IOKit DRM 适配层；完整 Mesa 依赖仍按上游逐文件许可 |
| [FreeBSD](https://github.com/freebsd/freebsd-src) | 上游无线兼容层基础 | linux_80211.c 原 BSD-2-Clause 通知已补入 LICENSES/ |

没有把这些项目的全部源码复制到本仓库。通过脚本取得的上游内容仍受原许可证约束。提供链接和致谢不取代保留版权、提供源码或其他许可义务。

## GPU 代码的许可范围

Linux GPU 初始化表按 GPL-2.0-only 保留来源、版权及许可证全文，与 ISC ath10k 分开处理。该表由 APSL 内核驱动直接包含，组合分发条件尚未解决。Mesa/freedreno 与 Fuchsia 的宽松许可来源仅覆盖部分初始化；来源、差异和验证范围见 [GPU 许可说明](docs/GPU_LICENSE.md)。

dipper 原创修改的作者为 yanei，其原创部分采用 MIT。第三方源文件声明及作者署名保留，不属于该 MIT 授权范围。
