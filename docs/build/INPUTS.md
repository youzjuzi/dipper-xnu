# 外部材料与校验

这些材料不随仓库分发。先从对应链接取得，或核查已有原始下载包的来源和摘要，再复制到独立目录。不要用旧内核、旧 UEFI、旧启动载荷或已修改的开发源码代替本轮构建。

在仓库根目录设置路径；已有材料可以使用别的绝对路径：

```sh
export DIPPER_PROJECT_ROOT="$PWD"
export DIPPER_INPUTS="$DIPPER_PROJECT_ROOT/local/inputs"
export THEOS="$DIPPER_PROJECT_ROOT/local/theos"
mkdir -p "$DIPPER_INPUTS" "$THEOS/sdks" "$THEOS/toolchain"
```

`local/` 与 `work/` 均不提交。`THEOS` 必须显式设置，避免构建意外引用其他项目的 `~/theos`。

## 下载来源

| 本地文件名 | 固定来源 | 用途 |
| --- | --- | --- |
| `iOSToolchain-x86_64.tar.xz` | [L1ghtmann test-210562a](https://github.com/L1ghtmann/llvm-project/releases/download/test-210562a/iOSToolchain-x86_64.tar.xz) | Theos Linux 交叉链接器及签名工具，Clang 11.1.0 |
| `iPhoneOS16.5.sdk.tar.xz` | [Theos master-146e41f](https://github.com/theos/sdks/releases/download/master-146e41f/iPhoneOS16.5.sdk.tar.xz) | iOS SDK |
| `MacOSX13.3.sdk.tar.xz` | [macosx-sdks 13.3](https://github.com/joseluisq/macosx-sdks/releases/download/13.3/MacOSX13.3.sdk.tar.xz) | XNU DriverKit 生成头文件 |
| `linux-7.0.14.tar.xz` | [kernel.org](https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.0.14.tar.xz) | ath10k 源码 |
| `freebsd-15.1-src.txz` | [FreeBSD 15.1 src.txz](https://download.freebsd.org/releases/amd64/15.1-RELEASE/src.txz) | LinuxKPI 源码；下载后按左列命名 |
| `mesa-25.0.7.tar.xz` | [Mesa archive](https://archive.mesa3d.org/mesa-25.0.7.tar.xz) | 图形库源码 |
| `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw` | [Apple CDN](https://updates.cdn-apple.com/2023SpringFCS/fullrestores/032-85130/6AB0D10A-8AF9-4F6C-8CF5-A1B315CABE88/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw) | iOS 16.5 / 20F66 系统材料 |

普通下载形式：`curl --fail --location --retry 3 '表中下载链接' -o "$DIPPER_INPUTS/表中文件名"`。保留原始包，以便复核和重建。只有按原文件名、版本和摘要核对通过，才可替代重新下载；文件名或大小相同不足以证明内容一致。

除 iPhoneOS SDK 外，在输入目录执行：

```sh
cd "$DIPPER_INPUTS"
sha256sum -c <<'SUMS'
a72a7a577e2fbe2838b6b5e9c72034fa7d114af96f0e1d4b016f18730ce4056e  iOSToolchain-x86_64.tar.xz
518e35eae6039b3f64e8025f4525c1c43786cc5cf39459d609852faf091e34be  MacOSX13.3.sdk.tar.xz
de9999b784d2293f00d39c62d8f92a08ab8a54bc4e80ffd250a0c09cb07a0f98  linux-7.0.14.tar.xz
cf5762da53fd52e1eaf0f9ceee9bf58cbe314c821031d0d9ffa76823185a89e1  freebsd-15.1-src.txz
592272df3cf01e85e7db300c449df5061092574d099da275d19e97ef0510f8a6  mesa-25.0.7.tar.xz
c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2  iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw
SUMS
```

任何一项不符即停止。工具链上游未提供 SHA-256：本轮用 GitHub 发布资产的 86,163,280 字节和 CDN Content-MD5 `7c31257bb7cca03e4130955bf00aee4e` 核对原包，再记录上述 SHA-256；它不是上游签名。其余摘要分别对照 SDK 发布记录、kernel.org、FreeBSD MANIFEST、固定上游构建脚本和 Apple CDN 的 `x-amz-meta-digest-sha256`。

## 放置工具链与 SDK

以下目标应为空；不要覆盖另一套安装。工具链压缩包内含 `linux/iphone/`：

```sh
tar -xJf "$DIPPER_INPUTS/iOSToolchain-x86_64.tar.xz" -C "$THEOS/toolchain"
tar -xJf "$DIPPER_INPUTS/iPhoneOS16.5.sdk.tar.xz" -C "$THEOS/sdks"
python3 "$DIPPER_PROJECT_ROOT/tools/check-sdk.py" "$THEOS/sdks/iPhoneOS16.5.sdk"
"$THEOS/toolchain/linux/iphone/bin/clang" --version
```

已有解包 SDK 可复制到同一位置后执行 `check-sdk.py`。校验依据是 Theos 提交 `146e41ff2c292168388929e43c9b4de2f00e36b3` 的 SDK Git tree `81466d46b666daa04ae3d2b0b9d5324f0f621359`，覆盖 8,867 个文件的内容、符号链接和可执行位。

## 让构建脚本使用已校验的原包

完成 `tools/prepare.py --prepare` 后执行：

```sh
K="$DIPPER_PROJECT_ROOT/work/hackios"
mkdir -p "$K/xnu-deps/build/ath10k" "$K/xnu-deps/build/mesa"
cp "$DIPPER_INPUTS/linux-7.0.14.tar.xz" "$DIPPER_INPUTS/freebsd-15.1-src.txz" "$K/xnu-deps/build/ath10k/"
cp "$DIPPER_INPUTS/mesa-25.0.7.tar.xz" "$K/xnu-deps/build/mesa/"
tar -xJf "$DIPPER_INPUTS/MacOSX13.3.sdk.tar.xz" -C "$K/xnu-deps" \
  --wildcards '*MacOSX13.3.sdk/System/Library/Frameworks/Kernel.framework*'
```

内核依赖脚本仍需获取固定版本的 Apple 开源库及主机工具源码；Mesa 首次构建还需在独立 venv 安装 Python 依赖。这些步骤并非完全离线。设备固件另见 [用户空间与打包](USERLAND.md)，不从其他设备的镜像猜测替换。

## WCN3990 Wi-Fi 特性描述文件

除了本机 modem 分区内的无线固件，ath10k 还需要 linux-firmware 的 [WCN3990/hw1.0/firmware-5.bin](https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/ath10k/WCN3990/hw1.0/firmware-5.bin)。2026-10-30 在线回读为 60 字节，SHA256：

```text
fef6539e0127579536bc977be57a90d018b83f2931fedc3a8870fbe38d6c4127
```

文件描述 ath10k 的特性与 WMI/HTT 接口版本，不包含可执行 DSP 固件，不能代替本机 modem、wlanmdsp 或板级数据。下载或复用已有副本时核对以上摘要，不一致即停止；文件本身不提交本仓库。

核对后放入 `work/hackios/fw-wifi/firmware-5.bin`，再运行 `tools/build-userland.sh`。构建脚本将它装入 root.apfs 的 `/fw/firmware-5.bin`；`tools/build-payload.py --wifi` 会回读并核对摘要，缺少文件则拒绝打包。此输入不依赖其他设备的 `wpss.mdt`。
