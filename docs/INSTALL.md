# dipper-xnu：分区、写入与启动

本项目现有实机方案使用设备 UFS 上的独立 **`darwin` 分区**存放系统卷。**首次安装需要重新分区并写入存储；开发设备的分区过程清空了 Android 用户数据。** 后续通过 `fastboot boot` 临时加载 UEFI，再向 RAM 传送启动卷和内核载荷。不能把整个安装过程描述成 RAM-only。

主机环境为 Ubuntu 26.04.1 LTS x86_64，设备代号为 `dipper`。本文依据开发记录 EXP-0036/0037/0041、分区布局文档和现有启动脚本整理；没有用公开仓库新构建的产物重新执行安装验证。

先完成 [构建教程](TUTORIAL.md)。公开包的用户空间打包与设备配置仍未闭环，因此本文是安装流程及命令模板，不是可以跳过前提直接执行的一键安装脚本。所有设备操作均由设备持有人执行。

## 1. 哪些东西写入哪里

| 阶段 | 内容 | 是否持久写入 |
| --- | --- | --- |
| 首次分区 | 缩小并重建 userdata，新增 darwin，更新 GPT | 是；本方案会清空 Android 用户数据 |
| 首次写入 | 将系统卷及两个 cryptex 组合镜像写入 darwin | 是 |
| 每次启动 | 临时加载 UEFI，传送启动卷与内核载荷 | boot/stage 操作写入 RAM；系统卷从 darwin 读取 |
| 保存用户状态 | 启用专门的持久化参数后保存数据 | 是，写入 darwin 的数据区域 |

现有路线无需把 UEFI 刷入 `boot` 分区。`fastboot boot` 与 `fastboot flash` 是不同操作；前者临时加载，后者持久写入。

## 2. 安装前准备

- Bootloader 已解锁，能够进入厂商 bootloader 的 fastboot。
- 有适配 dipper 且经过验证的 recovery，可访问 root adb、GPT 工具和块设备；历史实验使用 TWRP 3.3.1，不随仓库提供。
- 已备份个人文件及设备分区，并在电脑或外置介质验证哈希。GPT 主表、备份表，以及 boot、modem、persist、modemst1/2、fsg 等恢复材料均需保留。
- 已准备适用本机的恢复手段和原系统恢复材料。历史设备有 9008 恢复条件，不能推定其他设备也有相同条件。
- 接受本次重建 userdata 会删除 Android 应用、设置和用户文件；修改 GPT 后，仅刷回原 boot 不能恢复原分区布局或用户数据。

本文不提供他人的 GPT 备份、分区唯一 GUID 或通用 EDL 写入参数。不要覆盖 modem、persist、modemst1/2、fsg 等设备身份和校准分区。

## 3. 先读取自己的布局

以下步骤要求已进入适配的 recovery，且 adb shell 具备 root 权限。`sgdisk` 需自行取得与设备架构匹配的版本，放在 recovery 的 `/tmp/sgdisk`；主机安装的 x86_64 程序不能直接在手机运行。

```sh
adb shell id
adb shell 'ls -l /dev/block/by-name/userdata /dev/block/by-name/darwin'
adb shell 'cat /proc/mounts'
```

首次安装没有 `darwin` 时，对应 `ls` 报不存在是预期现象。先确定 userdata 所在物理 LUN 对应的磁盘节点，再填入变量；不能假定所有设备都叫 `/dev/block/sda`。

```sh
# 以下仅为命令形式；将占位内容替换为本机只读核对结果。
DISK_NODE='/dev/block/替换为实际磁盘节点'
adb shell "/tmp/sgdisk --print '$DISK_NODE'"
adb shell "/tmp/sgdisk --verify '$DISK_NODE'"
```

记录逻辑扇区大小、磁盘总扇区数、最后可用 LBA、userdata 编号/起止位置/类型/唯一 GUID，以及所有其他分区。确认 userdata 位于磁盘末尾，目标区域不与任何其他分区重叠。检查 `/data`、`/sdcard` 及其他别名挂载；目标分区存在挂载或 GPT 校验异常时停止。

使用 sgdisk 保存当前 GPT，并从 recovery 的 RAM 拉到主机；这份文件不能代替用户文件和各分区内容备份：

```sh
adb shell "/tmp/sgdisk --backup=/tmp/dipper-gpt-before.bin '$DISK_NODE'"
adb pull /tmp/dipper-gpt-before.bin ./dipper-gpt-before.bin
sha256sum ./dipper-gpt-before.bin
```

还应确认该工具版本的备份格式及恢复能力，并保留原始分区表读数。不要把开发设备的布局和备份用于另一台设备。

## 4. 首次分区：清空数据的路线

历史开发设备为约 114.6 GiB 的 LUN0，逻辑扇区 4096 字节，原 userdata 为末尾的第 21 项。实验采用以下布局：

| 分区 | 编号 | 起始 LBA | 结束 LBA | 容量 |
| --- | --- | --- | --- | --- |
| userdata | 21 | 393216 | 23746559 | 约 89.1 GiB |
| darwin | 22 | 23746560 | 30038013 | 约 24 GiB |

这是**历史参考值，不是按型号通用的分区命令**。不同容量、已有双系统或分区改动都会影响布局。这里的做法是删除并重建 userdata 的 GPT 项，随后重建文件系统；它不是保留数据的文件系统缩容教程。

只有完成第 3 节核对、备份并确定自己的布局后，才能使用下面的命令模板。所有大写变量均需根据本机结果设置；示例没有自动代入上述历史值。

```sh
# 在主机 Bash 中设置并复核自己的参数后执行。
: "${DISK_NODE:?缺少磁盘节点}"
: "${USERDATA_NUMBER:?缺少原 userdata 分区号}"
: "${USERDATA_FIRST:?缺少原 userdata 起点}"
: "${USERDATA_LAST_NEW:?缺少新 userdata 终点}"
: "${USERDATA_TYPE_GUID:?缺少原 userdata 类型 GUID}"
: "${USERDATA_UNIQUE_GUID:?缺少原 userdata 唯一 GUID}"
: "${DARWIN_NUMBER:?缺少未占用的新分区号}"
: "${DARWIN_FIRST:?缺少 darwin 起点}"
: "${DARWIN_LAST:?缺少 darwin 终点}"

# 写 GPT：会改变 userdata，必须先卸载所有相关挂载并确认备份。
adb shell /tmp/sgdisk "$DISK_NODE" \
  --delete="$USERDATA_NUMBER" \
  --new="$USERDATA_NUMBER:$USERDATA_FIRST:$USERDATA_LAST_NEW" \
  --typecode="$USERDATA_NUMBER:$USERDATA_TYPE_GUID" \
  --partition-guid="$USERDATA_NUMBER:$USERDATA_UNIQUE_GUID" \
  --change-name="$USERDATA_NUMBER:userdata" \
  --new="$DARWIN_NUMBER:$DARWIN_FIRST:$DARWIN_LAST" \
  --typecode="$DARWIN_NUMBER:7C3457EF-0000-11AA-AA11-00306543ECAC" \
  --change-name="$DARWIN_NUMBER:darwin"
```

这组非空检查仅防止漏填变量，**不验证你填写的分区参数是否正确**。执行前需独立核对所有区间及磁盘身份。新 darwin 的唯一 GUID 由 GPT 工具生成，不复制开发者的 GUID。

执行后打印并校验 GPT，逐项比对修改前后的表，确认仅 userdata 和新 darwin 项发生预期变化：

```sh
adb shell "/tmp/sgdisk --print '$DISK_NODE'"
adb shell "/tmp/sgdisk --verify '$DISK_NODE'"
adb shell "/tmp/sgdisk --info='$DARWIN_NUMBER' '$DISK_NODE'"
```

重启并重新进入 recovery，让内核重新读取分区表，再核对节点、大小与挂载。**不能在内核仍使用旧表时格式化。** 使用 recovery 的“格式化 Data”功能重建 userdata；历史设备采用 ext4，但本机文件系统和加密处理应依据自己的恢复方案决定。完成后先确认 Android 能重新启动，保存改后的 GPT 备份和新 darwin 标识，再继续。

## 5. 让源码匹配新分区

公开补丁移除了开发设备的分区唯一 GUID，目前使用全零占位符。首次编译前，需要把自己的布局同步到加载器与内核，再重编译：

| 位置（相对于 work/hackios） | 需要核对的参数 |
| --- | --- |
| `xnuloader/loader.c` | `BLOCK_DARWIN_FIRST`、`BLOCK_DARWIN_LAST`、`BLOCK_DARWIN_TYPE`、`BLOCK_DARWIN_UNIQ` |
| `xnu-src/xnu-8796.121.2/bsd/dev/redwood_ufs.c` | `UFS_DARWIN_FIRST`、`UFS_DARWIN_BLOCKS`、写入数据区域边界 |
| 如需使用上游 `tools/darwin-write.py` | 分区号、节点、GUID、扇区大小、边界和保护区；上游默认值并非 dipper 的布局 |

C 结构中的 GUID 必须按字段正确转换，不能把字符串直接粘进整数数组；整数形式的 GUID 首三字段与 GPT 原始字节序也不同。配置完成后重新编译内核和加载器，并重建嵌入新 loader 的 UEFI。不要用旧 loader、上游预编译内核或取消校验来代替适配。

`source-manifest.json` 校验的是公开源码快照；设备参数应在源码准备和哈希校验完成后修改。当前还没有自动生成设备配置的公开工具，这一步需要人工审查。

## 6. 准备写入 darwin 的镜像

当前方案使用 iOS 16.5（20F66，iPhone10,3/iPhone10,6）的对应材料，按以下顺序组合。这里的块相对于 darwin 分区起点，大小均为 4096 字节：

| 部分 | 起始块 | 块数 | 字节数 |
| --- | --- | --- | --- |
| 系统根卷 APFS | 0 | 1374208 | 5628755968 |
| OS cryptex | 1374208 | 665600 | 2726297600 |
| App cryptex | 2039808 | 2560 | 10485760 |
| 运行时数据区 | 2042368 | 剩余容量 | 由运行时管理 |

系统根卷来自对应 `096-04088-077.dmg` 展开后的 APFS 容器，两个 cryptex 分别对应 `096-04666-078.dmg` 与 `096-03536-083.dmg`。不要把 UDIF 压缩封装直接作为已展开根卷写入，也不要把 RAM 方案的 `system.apfs` 与此布局混用。

本机合法取得并提取文件后，将它们整理为以下名称，再在主机组合：

```sh
# 当前目录必须是自己的输入目录，内含下列三个文件。
python3 - <<'PY'
from pathlib import Path
import shutil
parts = [('rootfs.apfs', 5628755968),
         ('os-cryptex.apfs', 2726297600),
         ('app-cryptex.apfs', 10485760)]
for name, size in parts:
    p = Path(name)
    if p.stat().st_size != size:
        raise SystemExit(f'大小不匹配: {name}')
    with p.open('rb') as f:
        f.seek(32)
        if f.read(4) != b'NXSB':
            raise SystemExit(f'缺少 APFS NXSB: {name}')
with Path('darwin.img').open('xb') as out:
    for name, _ in parts:
        with Path(name).open('rb') as src:
            shutil.copyfileobj(src, out, length=1024 * 1024)
print('darwin.img: 8365539328 bytes expected')
PY
sha256sum rootfs.apfs os-cryptex.apfs app-cryptex.apfs darwin.img
```

这些大小与魔数检查不能证明输入版本正确，必须同时核对合法输入材料的来源、版本和摘要。历史实验的组合镜像 SHA256 为 `9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560`；仅当使用完全相同的输入和组合方式时才应一致。不同版本不得沿用这套偏移。

还需要从修改后的用户空间源码生成小启动卷和内核载荷（见 [构建教程第 6 节](TUTORIAL.md#6-用户空间打包与启动)）；其从零构建命令仍待补齐。仓库不附带这里的任何系统镜像。

## 7. 写入系统并回读校验

进入厂商 bootloader 的 fastboot，连接并明确选择目标设备。下列 `fastboot` 命令都针对这一台设备，不应在连接多台设备时直接执行。

```sh
fastboot getvar product
fastboot getvar partition-size:darwin
fastboot getvar partition-type:darwin
```

分区字节数必须与你自己的 GPT 记录一致，且不小于镜像。历史 24 GiB 布局返回大小 `0x5FFFFE000`，它不是其他布局的验收值。确认分区身份、输入镜像哈希和恢复条件后，由设备持有人执行：

```sh
# 持久写入 darwin；将路径替换为第 6 节生成并校验的镜像。
fastboot flash darwin /path/to/darwin.img
```

不要改成写入 `boot`、`userdata` 或整盘节点。若 fastboot 不识别分区或身份/大小不符，停止排查，不尝试把分区名替换成猜测的节点。

写入完成后重新进入适配 recovery，确认 darwin 未挂载且节点/容量正确。对上述固定长度的原始组合镜像，读取相同字节数计算 SHA256：

```sh
adb shell 'dd if=/dev/block/by-name/darwin bs=4096 count=2042368 2>/dev/null | sha256sum'
```

结果必须等于主机 `darwin.img` 的 SHA256。fastboot 的 OKAY 不能替代回读验证；稀疏传输可能跳过区域，不能只根据传输成功推断实际数据完整。回读不一致时不进入启动步骤，也不要清除其他分区。

## 8. 日常启动

前提：第 5 节的设备配置已匹配，darwin 回读通过，且已生成互相匹配的 UEFI、`flashboot.apfs` 和内核载荷。UEFI 必须按项目要求嵌入进入 USB 服务模式的引导载荷；现有公开 UEFI 构建脚本还未自动完成这一步。仅生成一个 UEFI 镜像，并不保证出现 xnuloader fastboot 服务。

以下是开发启动脚本使用的协议顺序，不是当前公开包已验证的一键命令：

```sh
# 临时加载自己构建且配置匹配的 UEFI。
fastboot boot /path/to/boot-dipper.img
# 等设备重新出现，然后确认加载器身份为 xnuloader。
fastboot getvar product
# 只有上一条确认为 xnuloader 才继续。
fastboot oem ramdisk
fastboot stage /path/to/flashboot.apfs
fastboot stage /path/to/payload.bin
fastboot oem run
```

载荷中的 UFS 读取路线使用 `ufs=2 root_apfs=ufs_darwin`。小启动卷与内核/图形/Wi-Fi 参数必须按对应构建配置生成；不要把其他设备的命令行直接套用。基础 run 路线不要加入 `ufs_write=1`；保存状态属于另一条持久写入路线，需要独立确认写入范围和恢复方式。

启动验收应同时检查内核日志中系统根卷挂载、用户空间启动及实际桌面响应。看到 UEFI、loader 或单纯 fastboot OKAY 都不等于进入桌面。现有实机记录不能代替这次新构建的启动验收。

## 9. 失败与恢复

- 临时启动失败时按设备已验证的方法完整重启，重新核对设备状态；GPU SMMU/基带恢复存在未解决问题，勿直接反复 rerun。
- darwin 内容错误且分区身份正常时，保留日志和回读结果，修正输入后只重写该分区。
- GPT 或 userdata 异常时，使用**本机**改动前备份和已验证的恢复流程。恢复 GPT 不会恢复已格式化的 userdata；也不要在新文件系统仍挂载时改回旧表。
- 无法进入 fastboot 时，需要设备持有人使用事先验证的 recovery/EDL 恢复手段，不能假定通用 9008 工具或授权条件成立。

目前没有经过公开包复现验证的自动分区、恢复或完整启动脚本。本文把实际安装方式与未完成环节写明；正式对外宣称“照教程可安装”之前，仍需完成一次独立构建和设备验收。
