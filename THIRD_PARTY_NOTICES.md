# 第三方来源与修改记录

整理日期：2026-10-29。具体版本见 `upstream.lock.json`；具体修改文件及内容摘要见 `source-manifest.json`。本次补丁整合了已有 Mi 8 修改，并移除了加载器内本机分区唯一 GUID；保留原文件声明。

| 来源 | 本包使用范围 | 许可/核对状态 |
|---|---|---|
| [HackiOS kernel](https://github.com/oosexgang/hackios-xnu-kernel) | xnuloader、构建入口、无线 glue；XNU 基线 | 根 APSL 2.0；逐文件例外与新增文件归属待审计 |
| [Apple XNU](https://github.com/apple-oss-distributions/xnu) | XNU 8796.121.2 上的 Mi 8 增量 | APSL 2.0 及原文件其他许可 |
| [HackiOS userland](https://github.com/oosexgang/hackios-xnu-userland) | 显示、Wi-Fi、launchd 与注入适配 | 根 MIT；Mesa 派生文件保留独立归属 |
| [edk2-sdm845](https://github.com/edk2-porting/edk2-sdm845) | dipper 平台、BootShim | 根许可证已附；子模块分别遵守原许可 |
| SimpleInit（edk2 子模块） | NULL 释放保护修改 | 本次修改的 malloc.c 为 Intel 文件级 BSD；已补原通知和 EDK2 历史许可，根 LGPL 文本另保留 |
| [UniXNU](https://github.com/UniXNU/UniXNU) | 库构建补丁与 XnuLoaderDxe 派生注册器 | package 的 BSD-2-Clause-Patent 已附 |
| [Linux](https://www.kernel.org/) / ath10k | WLFW 表与无线源码获取脚本 | 文件中的 ISC 及版权头保留；不将整个 Linux 声称为 ISC |
| [Mesa](https://gitlab.freedesktop.org/mesa/mesa) / freedreno | DRM 适配与渲染构建依赖 | 本补丁修改的是 HackiOS MIT IOKit DRM 适配层；完整 Mesa 依赖仍按上游逐文件许可 |
| [FreeBSD](https://github.com/freebsd/freebsd-src) | 上游无线兼容层基础 | linux_80211.c 原 BSD-2-Clause 通知已补入 LICENSES/ |

没有把这些项目的全部源码复制到本仓库。通过脚本取得的上游内容仍受原许可证约束。提供链接和致谢不取代保留版权、提供源码或其他许可义务。

## 本次新增核对结果

Linux GPU 初始化表不同于 ISC ath10k：其 a6xx_gpu.c/a6xx_catalog.c 来源标为 GPL-2.0/GPL-2.0-only，组合分发许可尚未解决。该部分不能标作 MIT。详细来源、已补通知和剩余事项见 [许可证核对记录](docs/LICENSE_REVIEW.md)。

新增 dipper 修改的维护者署名为 yanei。现有源文件声明及上游作者署名保持原归属；本次用户确认的 MIT 授权只覆盖其原创部分。
