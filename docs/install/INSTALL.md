# 分区、镜像写入与 Android 回退

本页负责持久存储操作；[配置、重建与启动](STARTUP.md)负责加载器、UEFI 和 RAM 启动。首次安装按本页第 1–6 节执行，回退使用第 7 节；已有布局且镜像回读匹配时，直接进入启动教程，不重复分区或刷写。

2026-10-30 已完成 Android 布局恢复、Format Data 与容量验收，重新划出约 24 GiB darwin，再次验收 Android，核对新 GUID、重建 loader/UEFI，完成镜像准确范围回读；持有人随后确认成功进入 iOS。本轮外设逐项回归、退出后完整重启 Android 尚未确认。证据见[首次安装任务](../development/FIRST_INSTALL.md)。这是本机结果，不能套用其 GPT、GUID 或历史脚本到其他设备。

所有设备修改均由持有人执行。构建准备见[构建教程](../build/BUILD.md)，已有布局的固件及功能测试见[测试参考](EXISTING_INSTALL.md)。

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
- 有适配 dipper 且经过验证的 recovery，可访问 root adb、GPT 工具和块设备；历史实验使用 TWRP 3.3.1；本轮分区与恢复使用 TWRP 3.7.0_9-0，不随仓库提供。
- 已备份个人文件及设备分区，并在电脑或外置介质验证哈希。GPT 主表、备份表，以及 boot、modem、persist、modemst1/2、fsg 等恢复材料均需保留。
- 已准备适用本机的恢复手段和原系统恢复材料。历史设备有 9008 恢复条件，不能推定其他设备也有相同条件。
- 接受重建 userdata 会删除 Android 应用、设置和用户文件；修改 GPT 后，仅刷回原 boot 不能恢复原分区布局或用户数据。

本文不提供他人的 GPT 备份、分区唯一 GUID 或通用 EDL 写入参数。不要覆盖 modem、persist、modemst1/2、fsg 等设备身份和校准分区。

## 3. 先读取自己的布局

先用 `adb devices -l` 找到本机序列号，设置主机变量 `ANDROID_SERIAL`；进入厂商 fastboot 后用 `fastboot devices` 核对并设置 `BOOT_SERIAL`。命令一次只针对已确认的设备。

以下步骤要求已进入适配的 recovery，且 adb -s "$ANDROID_SERIAL" shell 具备 root 权限。`sgdisk` 需自行取得与设备架构匹配的版本，放在 recovery 的 `/tmp/sgdisk`；主机安装的 x86_64 程序不能直接在手机运行。

```sh
adb -s "$ANDROID_SERIAL" shell id
adb -s "$ANDROID_SERIAL" shell 'ls -l /dev/block/by-name/userdata /dev/block/by-name/darwin'
adb -s "$ANDROID_SERIAL" shell 'cat /proc/mounts'
```

首次安装没有 `darwin` 时，对应 `ls` 报不存在是预期现象。先确定 userdata 所在物理 LUN 对应的磁盘节点，再填入变量；不能假定所有设备都叫 `/dev/block/sda`。

```sh
# 以下仅为命令形式；将占位内容替换为本机只读核对结果。
DISK_NODE='/dev/block/替换为实际磁盘节点'
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --print '$DISK_NODE'"
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --verify '$DISK_NODE'"
```

记录逻辑扇区大小、磁盘总扇区数、最后可用 LBA、userdata 编号/起止位置/类型/唯一 GUID，以及所有其他分区。确认 userdata 位于磁盘末尾，目标区域不与任何其他分区重叠。检查 `/data`、`/sdcard` 及其他别名挂载；目标分区存在挂载或 GPT 校验异常时停止。

使用 sgdisk 保存当前 GPT，并从 recovery 的 RAM 拉到主机；这份文件不能代替用户文件和各分区内容备份：

```sh
adb -s "$ANDROID_SERIAL" shell "/tmp/sgdisk --backup=/tmp/dipper-gpt-before.bin '$DISK_NODE'"
adb -s "$ANDROID_SERIAL" pull /tmp/dipper-gpt-before.bin ./dipper-gpt-before.bin
sha256sum ./dipper-gpt-before.bin
```

还应确认该工具版本的备份格式及恢复能力，并保留原始分区表读数。不要把开发设备的布局和备份用于另一台设备。

## 4. 创建 darwin 并重建 Data

使用[离线分区工具说明](PARTITION_DARWIN.md)采集本机主备 GPT、填写私有配置、审查方案，再生成本轮脚本。工具只支持说明中限定的 dipper 尾部分区布局；不提供保留数据缩容。不要直接复用历史轮次的脚本。

配置中的 `darwin_size_gib` 表示 GiB；本轮请求 24 GiB，按 1 MiB 对齐后实际为 25769795584 字节，比精确 24 GiB 少 8192 字节。以下仅为验收参考，不能代替本机方案：

| 分区 | 起始 LBA（4096 字节） | 结束 LBA | 节点字节数 |
| --- | --- | --- | --- |
| userdata | 393216 | 23746559 | 95655297024 |
| darwin | 23746560 | 30038013 | 25769795584 |

1. 审查生成方案、输入摘要和改变范围；将核验的 ARM64 sgdisk 与脚本传入 Recovery `/tmp/`，再次核对摘要。按工具说明由持有人执行 `CREATE-DARWIN` 命令。
2. 回读主备 GPT，与本轮预期条目核对，确认其他分区未变。出现“kernel is still using the old partition table”表示内核尚未刷新，不能立即格式化或启动 Android。
3. 持有人重启进入 Recovery，重新读取 GPT、节点和字节容量，用工具验收。必须确认内核已识别新 userdata/darwin 边界。
4. 在 TWRP 使用 **Format Data（格式化 Data）**重建 userdata，然后启动 Android、初始化并检查容量。仅清缓存或修改 GPT 不会自动调整文件系统。

```sh
# Android 启动后，在主机执行；选择自己的序列号。
adb -s "$ANDROID_SERIAL" shell 'getprop sys.boot_completed; df -k /data'
```

本轮恢复完整 userdata 后 `/data` 为 116193656 KiB；划出 darwin 后为 91422752 KiB，两次均 `sys.boot_completed=1`。MIUI“系统固件”显示曾从约 9G 变成约 34G，不能仅凭这个分类判断失败；应以 GPT、节点容量和文件系统容量共同验收。文件系统总量小于分区容量是正常开销，但明显少一整块空间时须检查是否仍在使用旧文件系统。

保存新 GUID、边界和备份到本机 `local/`。按[启动教程的配置与重建步骤](STARTUP.md#1-让源码匹配新分区)准备匹配产物，再继续镜像写入。

## 5. 准备写入 darwin 的镜像

当前方案使用 iOS 16.5（20F66，iPhone10,3/iPhone10,6）的对应材料，按以下顺序组合。这里的块相对于 darwin 分区起点，大小均为 4096 字节：

| 部分 | 起始块 | 块数 | 字节数 |
| --- | --- | --- | --- |
| 系统根卷 APFS | 0 | 1374208 | 5628755968 |
| OS cryptex | 1374208 | 665600 | 2726297600 |
| App cryptex | 2039808 | 2560 | 10485760 |
| 运行时数据区 | 2042368 | 剩余容量 | 由运行时管理 |

系统根卷来自对应 `096-04088-077.dmg` 展开后的 APFS 容器，两个 cryptex 分别对应 `096-04666-078.dmg` 与 `096-03536-083.dmg`。不要把 UDIF 压缩封装直接作为已展开根卷写入，也不要把 RAM 方案的 `system.apfs` 与此布局混用。

按 [用户空间教程](../build/USERLAND.md) 先验证并提取 IPSW，再在仓库根目录执行：

```sh
python3 tools/build/pack-darwin.py
sha256sum work/images/darwin.img
```

该入口只取 UDIF 内的 `3.apfs` 分区，不包含 GPT 包装；校验输入来源、大小、魔数和完整输出摘要，拒绝覆盖已有输出。2026-10-30 新构建组合镜像的 SHA256 与历史值一致：`9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560`。不同版本不得沿用这套偏移。

`root.apfs` 与 `flashboot.apfs` 的源码构建命令已见 [用户空间教程](../build/USERLAND.md)。完整内核载荷仍需本机设备配置和启动参数。仓库不附带任何系统镜像。

## 6. 写入系统并回读校验

进入厂商 bootloader 的 fastboot，连接并明确选择目标设备。下列 `fastboot` 命令都针对这一台设备，不应在连接多台设备时直接执行。

```sh
fastboot -s "$BOOT_SERIAL" getvar product
fastboot -s "$BOOT_SERIAL" getvar partition-size:darwin
fastboot -s "$BOOT_SERIAL" getvar partition-type:darwin
```

分区字节数必须与你自己的 GPT 记录一致，且不小于镜像。历史 24 GiB 布局返回大小 `0x5FFFFE000`，它不是其他布局的验收值。确认分区身份、输入镜像哈希和恢复条件后，由设备持有人执行：

```sh
# 持久写入 darwin；将路径替换为第 5 节生成并校验的镜像。
fastboot -s "$BOOT_SERIAL" flash darwin /path/to/darwin.img
```

不要改成写入 `boot`、`userdata` 或整盘节点。若 fastboot 不识别分区或身份/大小不符，停止排查，不尝试把分区名替换成猜测的节点。

写入完成后重新进入适配 recovery，确认 darwin 未挂载且节点/容量正确。对上述固定长度的原始组合镜像，读取相同字节数计算 SHA256：

```sh
# Recovery shell 必须支持 pipefail；不支持则停止并改为完整读出到主机校验。
adb -s "$ANDROID_SERIAL" exec-out 'set -o pipefail; dd if=/dev/block/by-name/darwin bs=1048576 count=7978 | sha256sum'
```

结果必须等于主机 `darwin.img` 的 SHA256。fastboot 的 OKAY 不能替代回读验证；稀疏传输可能跳过区域，不能只根据传输成功推断实际数据完整。回读不一致时不进入启动步骤，也不要清除其他分区。


检查 dd 实际计数为 8365539328 字节，并同时确认命令退出成功、摘要匹配；不同镜像必须重新计算读取长度，不能沿用此 count。第 09 轮已对该范围完成实时回读，与主机摘要一致。通过后进入[启动教程](STARTUP.md)。

## 7. 回退：恢复 Android 布局

回退会删除 darwin 并重建 Android 数据区，不恢复旧个人数据，也不等于刷全套原厂固件。临时启动失败通常先完整重启、保存证据，不必因此重分区。只有明确需要撤销双系统布局时才执行本节。

入口：[tools/partition/restore-android-layout.py](../../tools/partition/restore-android-layout.py)。这是 Linux 主机上的离线方案生成器，不连接 ADB、不执行设备命令。通用的是恢复逻辑，本机身份、输入摘要和 GPT 备份在 `local/`。目前只支持 dipper、sda、4096 字节扇区，以及尾部相邻 userdata/darwin 恢复为原 userdata 的布局；不是任意手机的分区修复工具。

### 目录与输入

- `tools/partition/restore-android-layout.py`：公共工具，纳入 Git。
- `local/devices/<alias>/android-restore-<date>.json`：本机配置，不提交。
- `local/backups/<run-id>/`：恢复前主备 GPT 与已核验的原始 GPT，不提交。
- `work/runs/<run-id>/`：每次方案、生成脚本、回读结果与日志，不提交。

每次先只读采集设备身份、TWRP 版本、sda 字节容量与扇区大小、挂载状态以及完整 GPT。主 GPT 捕获必须从 LBA 0 开始，包含 header 和整个 entry table；备 GPT 捕获必须以磁盘最后一个扇区结束，包含备 header 和整个 entry table。捕获长度以逻辑扇区为单位。备份 SHA256 应来自此前核验记录；不要为通过检查而刷新不符的摘要。原始 GPT 必须属于本机，不能使用其他手机的备份。

配置字段如下，尖括号均为需核验后填写的占位符，不可直接运行。`path` 相对于配置文件所在目录；容量填整数，不能填写字符串。

```json
{
  "schema_version": 1,
  "device": "dipper",
  "serial": "<ro.serialno>",
  "twrp_version": "<已验证的版本>",
  "disk": "/dev/block/sda",
  "sector_size": 4096,
  "disk_bytes": 0,
  "sgdisk_sha256": "<已核验工具的64位摘要>",
  "before_primary": {"path": "<恢复前主GPT>", "sha256": "<已核验摘要>"},
  "before_backup": {"path": "<恢复前备GPT>", "sha256": "<已核验摘要>"},
  "original_primary": {"path": "<原始主GPT>", "sha256": "<已核验摘要>"}
}
```

工具检查输入 SHA256、GPT header/table CRC、主备一致、磁盘身份和可用区间、分区无重叠，并要求其他分区条目完全不变。userdata 起点不变，恢复范围不能超出原 userdata + darwin；目标 userdata 属性须为零且类型为 Linux filesystem。失败即停止，不猜测或修改参数。

### 离线审查和生成

在仓库根目录执行，替换本机配置和新运行目录：

```sh
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --output-dir work/runs/<new-run-id>
```

默认只显示方案；`--output-dir` 创建新目录，保存 `plan.json`、`inputs.json`、`restore-android-layout.sh`、来源记录 `provenance.json` 与摘要。已有目录被拒绝，避免覆盖。`inputs.json` 是配置审计副本，其中相对路径仍按原配置目录解释，不要将它当作新位置下可直接运行的配置。方案与脚本包含私人 GUID，禁止提交。

### 持有人执行及验收

审查方案后，持有人将核验过的 sgdisk 和本轮脚本放到 Recovery 的 `/tmp/sgdisk` 与 `/tmp/restore-android-layout.sh`。传输后核对摘要。设备只通过此显式命令修改 GPT：

```sh
adb -s <serial> shell sh /tmp/restore-android-layout.sh RESTORE-ANDROID-GPT
```

脚本复核身份、工具和恢复前 GPT 摘要、容量，要求 userdata/darwin 均无挂载或块设备 holder，且无活动 swap。它不自动卸载；先在 TWRP 停用 MTP 并卸载相关分区，再重新检查。不在执行期间操作 TWRP 挂载界面、启动其他存储任务或其他 mount namespace；本工具不保证并发访问安全，也未覆盖所有 Recovery 版本。旧 awk 路径不再使用。

脚本只删除 darwin 并重建目标 userdata GPT 条目，不格式化、不刷系统、不自动重启。写入中断时不要盲目重跑；重新读取主备 GPT，按备份分析。不要将 sgdisk 的成功退出直接视作恢复验收通过。

完成后先回读并校验主备 GPT，再由持有人重进 Recovery，重新捕获 GPT 和内核 userdata 字节容量。用新读数验收：

```sh
python3 tools/partition/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --verify-primary <重启后主GPT> --verify-backup <重启后备GPT> --kernel-userdata-bytes <重启后容量整数>
```

旧内核容量会被拒绝。此命令只核验提供的证据，不能证明文件来源或采集时间；调用者必须保证文件和容量属于同一轮设备读取。通过后仍需单独重建数据文件系统、验证 Android 启动与容量，不能把 GPT 恢复当作系统恢复完成。

### 已验证边界

2026-10-30：17 项合成 GPT/CLI 测试通过；使用本机恢复前及重启后 GPT、已记录内核容量的离线回放通过。原一次性 v2 脚本已由持有人执行并回读通过；本通用生成器新增身份、挂载/holder 等保护后的生成脚本尚未在手机执行，不继承 v2 的全部真机验证结论。本机后来已重新分区并进入 iOS；本次保存的恢复配置仅对应当时状态，只供历史回放。再次回退必须重新采集当前 GPT，生成新方案。

测试入口：`python3 tools/tests/test-restore-android-layout.py`。任务进度见 [首次安装任务](../development/FIRST_INSTALL.md)。

恢复 GPT 和重启后容量核验通过之后，持有人仍须 Format Data、初始化 Android，再检查 `sys.boot_completed` 和 `df -k /data`。本轮先恢复 GPT 未格式化时，文件系统仍只有旧容量；格式化后才完成恢复验收。无法进入 Recovery/fastboot 时，使用事先验证的本机恢复手段，不能猜测 EDL 参数。
