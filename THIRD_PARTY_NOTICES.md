# 第三方来源与修改记录

整理日期：2026-10-27。具体版本见 `upstream.lock.json`；具体修改文件及内容摘要见 `source-manifest.json`。本次补丁整合了已有 Mi 8 修改，并移除了加载器内本机分区唯一 GUID；保留原文件声明。

| 来源 | 本包使用范围 | 许可/核对状态 |
|---|---|---|
| [HackiOS kernel](https://github.com/oosexgang/hackios-xnu-kernel) | xnuloader、构建入口、无线 glue；XNU 基线 | 根 APSL 2.0；逐文件例外与新增文件归属待审计 |
| [Apple XNU](https://github.com/apple-oss-distributions/xnu) | XNU 8796.121.2 上的 Mi 8 增量 | APSL 2.0 及原文件其他许可 |
| [HackiOS userland](https://github.com/oosexgang/hackios-xnu-userland) | 显示、Wi-Fi、launchd 与注入适配 | 根 MIT；Mesa 派生文件保留独立归属 |
| [edk2-sdm845](https://github.com/edk2-porting/edk2-sdm845) | dipper 平台、BootShim | 根许可证已附；子模块分别遵守原许可 |
| SimpleInit（edk2 子模块） | NULL 释放保护修改 | 已附上游 LICENSE |
| [UniXNU](https://github.com/UniXNU/UniXNU) | 库构建补丁与 XnuLoaderDxe 派生注册器 | package 的 BSD-2-Clause-Patent 已附 |
| [Linux](https://www.kernel.org/) / ath10k | WLFW 表与无线源码获取脚本 | 文件中的 ISC 及版权头保留；不将整个 Linux 声称为 ISC |
| [Mesa](https://gitlab.freedesktop.org/mesa/mesa) / freedreno | DRM 适配与渲染构建依赖 | 具体派生文件许可待逐文件核对 |
| [FreeBSD](https://github.com/freebsd/freebsd-src) | 上游无线兼容层基础 | 逐文件许可证，待补完整通知 |

没有把这些项目的全部源码复制到本仓库。通过脚本取得的上游内容仍受原许可证约束。提供链接和致谢不取代保留版权、提供源码或其他许可义务。
