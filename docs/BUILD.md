# dipper-xnu：Ubuntu 构建教程

本教程面向 Linux x86_64 主机，开发环境为 **Ubuntu 26.04.1 LTS**。目标是从固定上游源码重建 dipper 的适配代码，逐步生成内核、加载器和 UEFI。

目前已验证补丁可在对应源码基线上回放；本教程尚未在全新 Ubuntu 环境从头跑完。用户空间打包和设备启动的缺失环节列在第 6 节。已有桌面、GPU 和 Wi-Fi 的实机记录来自开发环境，具体见 [功能状态](STATUS.md)。

## 1. 准备环境

使用普通用户运行构建命令，工作目录路径不要包含空格。准备以下工具：

| 用途 | 工具或输入 |
| --- | --- |
| 获取源码 | Git、curl、CA 证书 |
| 编译内核 | C/C++ 构建工具、make、clang、lld、Python 3、Perl、xz、flex、bison、m4 |
| 编译 UEFI | 上述工具，以及 iasl、nasm、gettext；完整依赖以锁定上游构建说明为准 |
| 目标平台交叉编译 | 自行准备的 Theos 工具链、iPhoneOS16.5 SDK |
| 用户空间准备 | 合法获取的对应系统材料、设备固件，以及上游要求的提取和打包工具 |

先核对主机环境：

```sh
cat /etc/os-release
uname -m
command -v git python3 clang lld-link make curl xz flex bison m4 perl iasl nasm
```

预期架构为 `x86_64`。缺少的命令需要先安装；上面的检查不覆盖所有传递依赖。

将 `THEOS` 设置为自己的安装路径，例如安装在 `~/theos` 时：

```sh
export THEOS="$HOME/theos"
test -d "$THEOS/sdks/iPhoneOS16.5.sdk"
```

`test` 成功时没有输出；若失败，请检查 SDK 版本和位置。仅有 SDK 目录仍不足以编译，还需要可用的目标平台工具链。SDK 和系统材料不随本仓库发布。

## 2. 获取本项目

使用具有仓库读取权限的 GitHub 账号获取源码。

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
python3 tools/prepare.py
```

这一步只显示上游仓库和固定 commit，不联网、不创建构建树。

确认后获取源码并应用补丁：

```sh
python3 tools/prepare.py --prepare
```

脚本会下载锁定版本及相关子模块，合并内核与用户空间目录，基于 Apple XNU 应用 HackiOS 基线和 dipper 补丁，再检查修改文件的 SHA256。`xnu-mi8.patch` 基于 HackiOS 基线，不能直接应用到原版 XNU。上游树可能包含 prebuilt，本流程不把这些产物作为已重建的 dipper 产物使用。

该联网流程尚待独立验证；它可能因网络、上游可访问性或补丁问题中断。

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

进入合并后的构建树：

```sh
cd "$DIPPER_PROJECT_ROOT/work/hackios"
```

依次准备依赖、编译 ath10k，再编译 XNU。每条命令结束后先检查输出，失败时不要直接继续下一条。

```sh
bash xnu-deps/setup.sh
bash tools/mk-ath10k.sh
bash xnu-build.sh -j8 -k
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

文件应为目标架构的 Mach-O 内核。上游记录过链接完成后的导出检查错误；即使出现产物，也必须保留退出码和日志，区分编译/链接失败与链接后的检查失败。文件存在、时间更新或大小合理都不代表已经能在设备启动。

## 5. 编译加载器与 UEFI

返回仓库根目录：

```sh
cd "$DIPPER_PROJECT_ROOT"
bash tools/build-loader-uefi.sh
```

脚本先编译 xnuloader，再准备 UEFI 包和构建所需的链接，最后调用上游 dipper UEFI 构建入口。

预期输出：

| 文件 | 用途 |
| --- | --- |
| `work/hackios/xnuloader/loader.efi` | EFI 加载器 |
| `work/edk2/boot-dipper.img` | UEFI 启动镜像 |

脚本成功后会打印这两个文件的 SHA256。UEFI 镜像生成不等于已生成包含内核及用户空间的完整启动载荷。

## 6. 用户空间、打包与启动

设备端步骤单独见 **[分区、写入与启动教程](INSTALL.md)**。当前实机路线需要 darwin 分区，首次重建 userdata 会清空 Android 数据；系统写入 UFS，之后临时加载 UEFI 启动。

要进入桌面，除了上述产物，还需要以下步骤：

1. 从合法取得的对应系统材料准备系统卷。
2. 从修改后的源码编译图形、注入、网络等用户空间程序和动态库。
3. 准备启动卷及本设备所需固件，确认采用的是新编译的适配程序。
4. 组合内核、启动卷和完整启动参数，生成启动载荷。
5. 按实际设备核对存储布局及分区标识，再执行设备启动验证。

相关修改已包含在 `hackios-userland.patch`：`eagl.c`、`inject.c`、`inject_sb.c`、`net_test.m`、`mkjobs.py`、Mesa DRM 适配及构建脚本；Wi-Fi launchd 配置也包含在仓库中。需要从修改后的源码重新编译这些程序和库。

**这一部分的完整构建命令仍待补齐和验证。** 开发环境的历史打包步骤依赖已有目录、旧载荷及 `.new` 程序，不能直接作为从空目录开始的教程。

公开加载器中的开发设备分区 GUID 已替换为零占位符，分区边界仍来自历史实验布局。不要直接套用到自己的设备，也不要删除匹配和边界检查来强行启动。

因此，完成第 5 节后应停在主机构建产物检查阶段；本教程当前不提供可直接照做的设备启动命令。后续会在相应流程补齐并验证后更新本节。

## 7. 常见问题

| 问题 | 检查方向 |
| --- | --- |
| 私有仓库克隆失败 | 检查 GitHub 登录身份和仓库读取权限 |
| 准备脚本提示 `work/ already exists` | 保存旧目录和失败日志后，再准备独立源码树 |
| 下载或子模块获取失败 | 检查网络和报错 URL，保留固定 commit，不要随意换成最新分支 |
| 补丁无法应用或源码哈希不一致 | 检查是否使用锁定版本、是否有本地改动；不要忽略错误继续编译 |
| 找不到 SDK 或交叉工具 | 检查 `THEOS`、SDK 版本和工具链安装位置 |
| 内核构建非零退出但存在文件 | 检查完整日志及退出码，确认是否本轮完成链接，记录所有未通过检查 |
| 已生成内核和 UEFI，但不能启动桌面 | 尚需第 6 节的用户空间、载荷与设备配置，不能仅用这两个产物代替 |

报告问题时附上本项目 commit、Ubuntu 版本、失败命令和经过脱敏的日志。贡献要求见 [贡献指南](../CONTRIBUTING.md)。
