# 设备版本、TWRP 与固件准备

本页是[分区与写入](INSTALL.md)、[构建与打包](../build/USERLAND.md)之前的设备材料入口。只读提取固件不需要重新分区或格式化 Data。固件、Recovery 镜像、设备标识和原始日志不提交 Git。

建议先按第 1 节确认版本，再选择提取环境：已有 Android root 可直接使用第 3 节的 `MODE=root`，无需为提取固件切到 TWRP。需要 Recovery 时再看第 2 节。

## 1. 已验证设备基线

| 项目 | 最近记录 | 证据与边界 |
| --- | --- | --- |
| 手机 | 小米 8，设备代号 dipper，SDM845 / A630 | 本机首次安装实验 |
| Android | Android 10 | 2026-10-31 Android 下 getprop 再次实读 |
| MIUI | V12.5.2.0.QEACNXM | 同次实读；不是要求其他版本强行刷成此版本 |
| Recovery | TWRP 3.7.0_9-0 | Recovery 内 getprop 与 root 身份核验 |
| 系统卷目标 | iOS 16.5 / 20F66 | 本仓库固定输入；与 Android 版本分别记录 |
| Android root | 2026-10-31 su 返回 uid=0 | 本轮 Android root 提取实测通过；不以此推定其他设备可用 |

Android 版本与 root 已于 2026-10-31 再次实读，证据在 `work/runs/20261031-firmware-01/`；Recovery 仍为历史实读。最初 Android 原始记录在 `work/runs/20261030-first-install-01/`，Recovery 在第 02 轮；当时持有人表示已刷入 TWRP，但未提供实际 flash 命令、刷入目标及镜像摘要。不能据此宣称已验证某个 TWRP 下载镜像或 boot/recovery 写入过程。

在 Android 已启动并允许 USB 调试后，选择自己的设备，在主机 Bash 执行：

```sh
adb devices -l
export DEVICE_SERIAL='替换为自己的序列号'
adb -s "$DEVICE_SERIAL" shell 'getprop ro.product.device; getprop ro.build.version.release; getprop ro.build.version.incremental; getprop ro.miui.ui.version.name; getprop ro.build.fingerprint'
```

保留这些输出，区分完整 MIUI 构建号与界面上的 MIUI 大版本。TWRP 内的 Android 属性可能来自 Recovery 自身，不能拿来证明已安装 Android 的版本。新采集记录写到 `local/devices/<alias>/`，同步本机 `local/index.json`；公开文档只写脱敏版本信息。

## 2. TWRP 获取与核验

- [Team Win 小米 8 设备页](https://twrp.me/xiaomi/xiaomimi8.html)：确认设备代号 dipper 和安装说明。
- [dipper 官方下载列表](https://dl.twrp.me/dipper/)。
- [本轮同版本 3.7.0_9-0 下载页](https://dl.twrp.me/dipper/twrp-3.7.0_9-0-dipper.img.html)：提供镜像、SHA256 文件及 PGP 签名入口。

2026-10-31 核对官方页面时可获取该版本。这里固定本轮实测版本，不把“最新版本”当作兼容性证据。其他 Mi 8 系列机型的镜像不能按名称相近混用。已有可用 TWRP 时不必为本教程重新刷写。

将镜像和对应 SHA256 校验文件下载到工作区现有 `downloads/` 下的独立目录，保留文件名，在该目录核验：

```sh
sha256sum -c twrp-3.7.0_9-0-dipper.img.sha256
```

若下载页面实际提供的是纯摘要文本，使用 `sha256sum twrp-3.7.0_9-0-dipper.img`，与页面对应值逐字核对。失配或拿不到可信摘要就停止；不自行重写校验文件让它通过。校验同一网站的摘要能检查文件一致性，不等于已完成独立的签名认证。

把来源页面、下载日期、镜像 SHA256 与本机存放位置登记到私有设备记录。本仓库不镜像分发 TWRP，也不预填未经核对的镜像摘要。对尚未安装 Recovery 的设备，按官方 dipper 页面核实安装方案后由持有人操作；本文不将本机未知的历史刷入命令编造成已验证流程。加载 iOS UEFI 的 `fastboot boot` 与安装 TWRP 是两件事，见[启动教程](STARTUP.md)。

进入 TWRP 后核验：

```sh
adb -s "$DEVICE_SERIAL" shell 'id; getprop ro.product.device; getprop ro.twrp.version; cat /proc/mounts'
```

本轮应确认 dipper、3.7.0_9-0 和 uid=0。TWRP 不自带本项目所需的 sgdisk 保证；分区工具准备及其独立摘要要求见[分区教程](INSTALL.md)。

## 3. GPU 固件清单

以下摘要来自本机上述 MIUI 的实际文件，未与原厂 ZIP 做逐字节对照。不同版本摘要不符时停止核对来源，不能修改预期值绕过当前构建校验。

| 手机文件 | 本轮 SHA256 |
| --- | --- |
| /vendor/firmware/a630_gmu.bin | b07f90299ff2ae33948fcfd6ed67f53fbd287b5bf85ff2d43db11d4d32c1621f |
| /vendor/firmware/a630_sqe.fw | 34edacb6fdedfbfc07ed5cd1d29b0b57a3543ef5be6ab34a43bd64686826fa1e |
| /vendor/firmware/a630_zap.mdt | f369d5614503a516a6443887f04dd8497cc7127b1ff3429c492666b26a9ab34b |
| /vendor/firmware/a630_zap.b02 | 519b5538809f54ee566246b0520746a8ea82ca9384ea6bddb0b0e0d3c2de520c |

### Android 与 TWRP 的读取条件

- **Android**：先尝试普通 ADB 读取。如果权限不足，仅在已有且已授权 root 时使用下述 root 模式；本机 root 已重新核验；其他设备仍须自行核验，不为提取而解锁或清空手机。
- **TWRP**：ADB 通常为 root，选择 recovery 模式；检查 `/vendor/firmware/` 确实来自本机 vendor 分区且挂载为只读。未挂载时先按本机 Recovery 的挂载界面确认 Vendor；不要猜设备节点执行 mount，也不要格式化它。路径不存在或无法确定来源时停止。

TWRP 下先检查：

```sh
adb -s "$DEVICE_SERIAL" shell 'cat /proc/mounts; ls -l /vendor/firmware/a630_gmu.bin /vendor/firmware/a630_sqe.fw /vendor/firmware/a630_zap.mdt /vendor/firmware/a630_zap.b02'
```

使用 Android root 路线前，确认 Android 启动完成并允许本次 su 请求：

```sh
adb -s "$DEVICE_SERIAL" shell getprop sys.boot_completed
adb -s "$DEVICE_SERIAL" exec-out su -c id
```

应分别看到 `1` 和 `uid=0`；授权被拒绝或命令失败时停止，不继续提取。

### 提取到新轮次并双端校验

以下是主机 Bash 示例，从仓库根目录执行。先设置 `DEVICE_SERIAL` 和全新的 `RUN_ID`；不覆盖任何历史提取结果。选择一种 MODE，不要把 root 不可用当作成功。

```bash
set -euo pipefail
: "${DEVICE_SERIAL:?设置目标 ADB 序列号}"
: "${RUN_ID:?设置新的轮次名称，例如 20261031-firmware-01}"
MODE=android  # android / root / recovery，按上面的读取条件选择
case "$MODE" in android|root|recovery) ;; *) exit 1 ;; esac
OUT="work/runs/$RUN_ID"
mkdir "$OUT"                  # 要求 work/runs 已存在，且本轮目录不存在
mkdir "$OUT/gpu"
cat > "$OUT/gpu/SHA256SUMS" <<'HASHES'
b07f90299ff2ae33948fcfd6ed67f53fbd287b5bf85ff2d43db11d4d32c1621f  a630_gmu.bin
34edacb6fdedfbfc07ed5cd1d29b0b57a3543ef5be6ab34a43bd64686826fa1e  a630_sqe.fw
f369d5614503a516a6443887f04dd8497cc7127b1ff3429c492666b26a9ab34b  a630_zap.mdt
519b5538809f54ee566246b0520746a8ea82ca9384ea6bddb0b0e0d3c2de520c  a630_zap.b02
HASHES
for name in a630_gmu.bin a630_sqe.fw a630_zap.mdt a630_zap.b02; do
    remote="/vendor/firmware/$name"
    if [ "$MODE" = root ]; then
        before=$(adb -s "$DEVICE_SERIAL" exec-out su -c "sha256sum $remote")
        adb -s "$DEVICE_SERIAL" exec-out su -c "cat $remote" > "$OUT/gpu/$name"
        after=$(adb -s "$DEVICE_SERIAL" exec-out su -c "sha256sum $remote")
    else
        before=$(adb -s "$DEVICE_SERIAL" exec-out sha256sum "$remote")
        adb -s "$DEVICE_SERIAL" pull "$remote" "$OUT/gpu/$name"
        after=$(adb -s "$DEVICE_SERIAL" exec-out sha256sum "$remote")
    fi
    local_hash=$(sha256sum "$OUT/gpu/$name")
    [ "${before%% *}" = "${after%% *}" ]
    [ "${before%% *}" = "${local_hash%% *}" ]
    printf '%s\n' "$before" >> "$OUT/device-sha256.txt"
done
(cd "$OUT/gpu" && sha256sum -c SHA256SUMS)
```

任何命令或摘要检查失败都停止。手机端前后摘要与主机摘要一致，且匹配固定输入，才算本轮提取通过。记录实际 MODE、Android/TWRP 版本和日期；部分失败的文件保留为失败证据，重新尝试使用新轮次。

### 放入构建输入目录

核验通过后，将上述 4 个文件放入 `work/hackios/fw-gpu/`。目录已有文件时先比较，摘要相同则复用，不覆盖不同内容：

```bash
set -euo pipefail
: "${OUT:?使用刚才已通过校验的提取目录}"
(cd "$OUT/gpu" && sha256sum -c SHA256SUMS)
mkdir -p work/hackios/fw-gpu
for name in a630_gmu.bin a630_sqe.fw a630_zap.mdt a630_zap.b02; do
    target="work/hackios/fw-gpu/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        cmp "$OUT/gpu/$name" "$target"
    else
        cp -n "$OUT/gpu/$name" "$target"
        cmp "$OUT/gpu/$name" "$target"
    fi
done
```

记录来源到 `local/devices/<alias>/` 并登记本机索引。`work/` 的提取结果和 `local/` 的来源记录均保持私有；只把脱敏结论写入验证文档。

## 4. Wi-Fi 固件与后续构建

Wi-Fi 分两类输入：

- 本机 modem 分区中的 MBA、modem、wlanmdsp 和板级数据，由本项目内核运行时读取，当前路线不要求逐个 adb pull 到电脑。不要把 GPU 提取方法套到 modem 分区，也不要用其他设备的板级数据替换。
- `firmware-5.bin` 是 WCN3990 特性描述文件，来源和固定 SHA256 见[输入材料](../build/INPUTS.md#wcn3990-wi-fi-特性描述文件)，放到 `work/hackios/fw-wifi/`。它不是从本机 Android 提取的 DSP 固件。

所有输入齐备后，按[用户空间教程](../build/USERLAND.md)配置 Theos/SDK 并执行 `bash tools/build/build-userland.sh`，再在新目录用 `tools/build/build-payload.py` 打包。载荷工具会回读 APFS 内固件并检查输入；提取到磁盘上不等于旧启动镜像自动更新。设备配置和启动顺序见[启动教程](STARTUP.md)。

## 验证范围

GPU 固件文件及固定摘要来自已保存的实机基线；上述提取示例于 2026-10-31 以 MODE=root 在 Android 实机执行通过：4 个文件提取前后手机端摘要与主机摘要一致，固定 SHA256 全部通过，与现有构建输入逐字节相同。结果保存在 work/runs/20261031-firmware-01/gpu/；未覆盖原输入、未写手机分区。普通 Android 无 root 模式、TWRP 提取模式及复制到构建目录示例本轮未执行。TWRP 官方来源页面已核对；本机当时实际刷入镜像的来源、SHA256 与刷入目标仍待补证。


| 路线或检查 | 本轮结果 |
| --- | --- |
| Android 版本、启动完成、su root | 已实时确认 |
| MODE=root 提取 4 个 GPU 固件 | 实机通过 |
| 提取前后手机端、主机端、固定 SHA256 | 全部一致 |
| 与原构建输入比较 | 逐字节相同，未覆盖 |
| 普通 ADB / TWRP 提取路线 | 本轮未执行 |
| 提取后复制、重新构建与启动 | 本轮未执行；不能用提取通过替代 |
