# 获取源码与构建

首次使用请从 [Ubuntu 26.04 构建教程](TUTORIAL.md) 开始；设备分区与写入见 [安装教程](INSTALL.md)。本页保留构建细节和当前复现范围。

## 复现范围

当前开发主机：**Ubuntu 26.04.1 LTS，x86_64，Linux**（2026-10-29 核对本机 `/etc/os-release` 与 `uname -m`）。这是开发环境记录，不是全新 Ubuntu 安装上的构建验收。构建流程按 Linux 编写，不要求使用 macOS；其他主机系统尚未验证。

| 阶段 | 当前验证情况 |
| --- | --- |
| 固定上游版本、Mi 8 补丁 | 已离线回放并核对文件哈希 |
| 通过公开脚本联网准备全部源码 | 尚未验证 |
| 在全新 Ubuntu 环境编译内核、UEFI 与用户空间 | 尚未验证 |
| 从源码生成完整启动载荷 | 用户空间与打包步骤尚未闭环 |
| 用本仓库新构建的产物在设备启动 | 尚未验证；已有实机记录来自开发环境 |

因此目前不能把本仓库视为可直接复现启动的一键构建包。正式复现需要先补齐下文的用户空间流程、按设备定义存储配置，再完成主机构建检查和独立的实机验证。

## 1. 主机与输入

使用 Linux 主机、Git、Python 3、clang/lld、make、C/C++ 编译工具、curl、xz、flex、bison、m4、Perl。UEFI 还需要 iasl、nasm、gettext 等上游依赖。完整依赖以锁定版本的上游文档为准，尚未在干净主机验证。

XNU 构建还依赖使用者合法获取的 Theos 工具链及 iPhoneOS16.5 SDK；设置 `THEOS` 指向自己的安装目录。这里不提供 SDK、专有用户空间、固件下载包或获取授权的替代办法。

## 2. 重建源代码

从本仓库根目录执行：

```sh
python3 tools/prepare.py               # 只显示固定版本，不联网
python3 tools/prepare.py --prepare     # 获取固定上游并回放补丁
```

输出在被 Git 忽略的 `work/`。脚本拒绝覆盖已有目录；失败保留现场。它只准备主机源码，不执行构建或设备命令。上游仓库自身可能带有 prebuilt 等内容，本发布包不复制、运行或重新分发这些产物。

顺序是：锁定 HackiOS 两个仓库 → 按其约定合并源码目录 → 获取 Apple XNU 指定提交 → 应用 HackiOS 基线 → 应用本包补丁。`xnu-mi8.patch` 基于重建后的 HackiOS 基线，不应直接应用到原版 Apple XNU。

## 3. XNU 和 ath10k

```sh
cd work/hackios
export THEOS=/path/to/your/theos
bash xnu-deps/setup.sh
bash tools/mk-ath10k.sh
bash xnu-build.sh -j8 -k
```

上游依赖脚本会联网下载并构建依赖；先阅读它们的许可证与版本检查。ath10k 脚本固定 Linux 7.0.14 并验证归档 SHA256，其余传递依赖尚未全部锁定。

预期内核位置：
`xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837`。

上游文档记录构建可能在链接后因导出检查退出 2；这仍是未通过的构建检查，不能仅凭文件存在宣布成功。保存完整日志，核对新产物时间、Mach-O 结构与链接结果，并明确报告所有失败。

## 4. 加载器和 UEFI

在本仓库根目录执行（若仍在上一节的 `work/hackios`，先执行 `cd ../..`）：

```sh
bash tools/build-loader-uefi.sh
```

此脚本只在主机编译。前提是已准备源码及 UEFI 依赖；它不打包用户空间，也不运行 fastboot/adb。输出留在 `work/`，不进入发布仓库。

公开补丁中的分区唯一 GUID 为零占位符，原来的严格匹配逻辑仍保留；因此本包没有可直接使用的设备存储配置。分区起止地址仍是原实验布局，仅供研究，不能照搬，也不要为了启动而取消边界或 GUID 检查。

## 5. 用户空间：尚未闭环的步骤

Mi 8 的 `eagl.c`、`inject.c`、`inject_sb.c`、`net_test.m`、`mkjobs.py`、Mesa DRM 适配和构建脚本修改已经包含在 `hackios-userland.patch` 中；Wi-Fi launchd 配置也已包含。

使用者需要合法取得对应的用户空间材料和固件，再按照锁定上游的构建说明准备输入。必须从修改后的源码重建相关程序和动态库，不能用上游旧 prebuilt 代替。

现有开发环境的默认 Wi-Fi 打包流程依赖已存在的 `root` 目录、`.new` 动态库/程序和旧载荷。它不是从空目录开始的完整构建入口，因此本包没有把它包装成一键构建，也没有复制这些输入。**用户空间从零构建、镜像组合和设备启动的完整公开流程仍待验证。**
