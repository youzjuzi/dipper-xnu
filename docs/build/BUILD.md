# dipper-xnu：Ubuntu 构建教程

本教程面向 Linux x86_64 主机，开发环境为 **Ubuntu 26.04.1 LTS**。目标是从固定上游源码重建 dipper 的适配代码，逐步生成内核、加载器和 UEFI。

2026-10-30 已在独立源码目录完成内核编译/链接、ath10k、Mesa、用户空间启动卷、加载器、UEFI 和 darwin 系统镜像的主机构建。主机已装有依赖，尚未验证全新 Ubuntu 的软件包安装；随后在已有分区上完成桌面启动，未重新分区或刷写系统。具体证据及未通过项见 [复现记录](../validation/REPRODUCTION.md)；当前实机功能见 [功能状态](../STATUS.md)。

## 1. 准备环境

使用普通用户运行构建命令，工作目录路径不要包含空格。准备以下工具：

| 用途 | 工具或输入 |
| --- | --- |
| 获取源码 | Git、curl、CA 证书 |
| 编译内核 | C/C++ 构建工具、make、clang、lld、Python 3、Perl、xz、flex、bison、m4 |
| 编译 UEFI | 上述工具，以及 iasl、nasm、gettext、bc、rsync、device-tree-compiler、gcc-aarch64-linux-gnu、binutils-aarch64-linux-gnu |
| 目标平台交叉编译 | 自行准备的 Theos 工具链、iPhoneOS16.5 SDK |
| 用户空间准备 | 7-Zip ≥23、Meson、Ninja、python3-venv、autoconf、automake，以及对应系统材料和设备固件 |

先核对主机环境：

```sh
cat /etc/os-release
uname -m
command -v git python3 clang lld-link make curl xz flex bison m4 perl iasl nasm
```

预期架构为 `x86_64`。还需 UUID、zlib、OpenSSL 的开发头文件（Ubuntu 包 `uuid-dev zlib1g-dev libssl-dev`）。缺少的工具需要先安装；上面的检查不覆盖所有传递依赖。构建会保留源码、原包、提取结果和镜像，建议开始时至少预留 80 GiB；这不是经过测量的最低要求。

工具链和 SDK 的固定链接、摘要与目录设置统一见 [外部材料与校验](INPUTS.md)。先完成下面的仓库获取，再按该页准备独立输入目录。

## 2. 获取本项目

公开仓库可匿名读取：

```sh
git clone https://github.com/youzjuzi/dipper-xnu.git
cd dipper-xnu
sha256sum -c SHA256SUMS
```

后续命令使用 Bash。先记录仓库根目录，方便各步骤返回：

```sh
export DIPPER_PROJECT_ROOT="$PWD"
```

如果使用的是已下载的源码包，直接进入包含 `README.md`、`patches/` 和 `tools/` 的目录，再执行校验及变量设置即可。

校验应全部显示 `OK`。若文件缺失或摘要不一致，先确认下载内容和本地修改，不要继续应用补丁。

## 3. 准备上游源码

从仓库根目录执行：

```sh
python3 tools/prepare/prepare.py
```

这一步只显示上游仓库和固定 commit，不联网、不创建构建树。

确认后获取源码并应用补丁：

```sh
python3 tools/prepare/prepare.py --prepare
```

脚本会下载锁定版本及相关子模块，合并内核与用户空间目录，基于 Apple XNU 应用 HackiOS 基线和 dipper 补丁，再检查修改文件的 SHA256。`xnu-mi8.patch` 基于 HackiOS 基线，不能直接应用到原版 XNU。上游树可能包含 prebuilt，本流程不把这些产物作为已重建的 dipper 产物使用。

固定上游版本的获取流程已验证。子模块只取构建需要的层级，不递归拉取 OpenSSL 等依赖自己的测试仓库；每个版本仍由 gitlink 固定。网络失败时保留日志和固定 commit，不能通过切换到最新分支绕过。

主要输出目录：

```text
work/
├── hackios/             合并后的内核与用户空间构建树
│   └── xnu-src/
│       └── xnu-8796.121.2/
├── userland/            固定版本的用户空间上游副本
├── edk2/                UEFI 源码
└── unixnu/              启动组件依赖
```

成功时脚本打印 `Sources prepared and hashes checked.`。准备脚本已经建立 XNU 树，不要再运行上游 `xnu/apply.sh`。

`work/` 已存在时脚本会退出，避免覆盖修改。失败现场会保留；再次尝试前应先保存日志和需要保留的源码，再将旧目录移到其他位置。不要在同一棵失败的源码树上反复叠加补丁。

## 4. 编译内核与 Wi-Fi 驱动

先完成 [外部材料页的缓存放置](INPUTS.md#让构建脚本使用已校验的原包)，确认本 shell 已设置 `THEOS`。然后进入合并后的构建树：

```sh
cd "$DIPPER_PROJECT_ROOT/work/hackios"
```

依次准备依赖、编译 ath10k，再编译 XNU。每条命令结束后先检查输出，失败时不要直接继续下一条。

```sh
bash xnu-deps/setup.sh
bash tools/mk-ath10k.sh
bash xnu-build.sh -j8 build
```

`-j8` 为并行任务数，可按主机资源调整。依赖脚本会联网取得额外源码；ath10k 获取脚本固定 Linux 7.0.14，并检查归档 SHA256 和逐文件许可证；其他传递依赖尚未全部锁定。

预期内核产物，相对于 `work/hackios/`：

```text
xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
```

检查文件类型、时间和摘要：

```sh
file xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
stat xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
sha256sum xnu-src/xnu-8796.121.2/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837
```

文件应为 ARM64 Mach-O 内核。已验证显式 `build` 目标退出码为 0；它执行头文件准备、编译和链接。原教程不指定目标的 `-j8 -k` 会继续执行 `all` 中的导出检查与工具生成，已记录的构建因平台导出符号和 LLDB 脚本的 `python` 命令问题退出 2；这些检查尚未修复，不能宣称完整 `all` 通过。任何命令非零退出都应先检查日志。主机链接成功不代表设备可启动。

## 5. 编译加载器与 UEFI

重新分区后，先按 [设备配置匹配](../install/STARTUP.md#1-让源码匹配新分区)核对 GUID 与边界；已有构建不能直接沿用旧 GUID。若仅唯一 GUID 改变，按本节重编译 loader/UEFI；内核边界和内容不变时，可在核验后沿用既有内核。

此入口会刷新 work/ 中的原生构建输出。再次运行前，将旧 loader 源码/产物、UEFI/BootShim/FD 和本机配置复制到 local/backups/ 对应目录并校验；新候选保存到独立 work/runs/ 目录。不要复制整套源码或重新运行 prepare.py。

返回仓库根目录：

```sh
cd "$DIPPER_PROJECT_ROOT"
bash tools/build/build-loader-uefi.sh
```

脚本先编译 xnuloader，再生成含 `usb` 条目的 XNUP 引导载荷，经 `XNU_PAYLOAD` 嵌入 BootShim/UEFI，最后调用上游 dipper 构建入口。它拒绝 `-b` / `--boot`，不会连接设备。

预期输出：

| 文件 | 用途 |
| --- | --- |
| `work/hackios/xnuloader/loader.efi` | EFI 加载器 |
| `work/edk2/boot-dipper.img` | UEFI 启动镜像 |

脚本成功后会打印这两个文件的 SHA256。UEFI 镜像生成不等于已生成包含内核及用户空间的完整启动载荷。

## 6. 用户空间、打包与启动

设备端步骤单独见 **[分区、写入与回退教程](../install/INSTALL.md)**。当前实机路线需要 darwin 分区，首次重建 userdata 会清空 Android 数据；系统写入 UFS，之后临时加载 UEFI 启动。

按 [用户空间构建与主机打包](USERLAND.md) 继续：

1. `tools/prepare/prepare-ios.py` 校验 IPSW 并在本工作树提取系统材料。
2. `tools/build/build-userland.sh` 从源码生成 `root.apfs` 和 `flashboot.apfs`。
3. `tools/build/pack-darwin.py` 生成并校验 `darwin.img`。

这些主机步骤已实际完成。进入设备测试前还必须准备经核查的本设备固件、分区配置及内核启动载荷；[已有分区路线](../install/EXISTING_INSTALL.md) 已完成桌面启动验证。公开 loader 的分区 GUID 是零占位符，边界来自历史实验，必须对照本机 GPT 修改并重编译；不能删除校验强行启动。主机产物检查完成后，先补齐 [设备输入](USERLAND.md#4-设备输入与实机测试)，再进入设备测试。

## 7. 常见问题

| 问题 | 检查方向 |
| --- | --- |
| 公开仓库克隆失败 | 检查报错 URL、网络及代理配置 |
| 准备脚本提示 `work/ already exists` | 保存旧目录和失败日志后，再准备独立源码树 |
| 下载或子模块获取失败 | 检查网络和报错 URL，保留固定 commit，不要随意换成最新分支 |
| 补丁无法应用或源码哈希不一致 | 检查是否使用锁定版本、是否有本地改动；不要忽略错误继续编译 |
| 找不到 SDK 或交叉工具 | 检查 `THEOS`、SDK 版本和工具链安装位置 |
| 内核构建非零退出但存在文件 | 检查完整日志及退出码，确认是否本轮完成链接，记录所有未通过检查 |
| 已生成内核和 UEFI，但不能启动桌面 | 尚需第 6 节的用户空间、载荷与设备配置，不能仅用这两个产物代替 |

报告问题时附上本项目 commit、Ubuntu 版本、失败命令和经过脱敏的日志。贡献要求见 [贡献指南](../../CONTRIBUTING.md)。
