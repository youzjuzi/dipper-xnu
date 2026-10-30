# 创建 darwin 分区：通用工具

[tools/partition/partition-darwin.py](../../tools/partition/partition-darwin.py) 将本次成功的分区步骤整理为可复用的离线方案生成器。它不连接 ADB，不执行手机命令；生成的 shell 脚本由持有人审查后执行。它只改 GPT，不写入 darwin.img、不格式化、不自动重启。

本次实际流程已通过：当前 GPT 备份 → 写入分区 → 回读 → 重进 TWRP 核对容量 → Format Data → Android 初始化与容量验收。证据与未完成的首次安装项目见 [首次安装任务](../development/FIRST_INSTALL.md)。

## 支持范围和目录

当前支持 dipper 的 `/dev/block/sda`、4096 字节扇区、末尾 userdata 且尚无 darwin 的布局。userdata 类型须为 Linux filesystem、属性为零、起点按 1 MiB 对齐，尾部空闲小于 1 MiB；至少保留 8 GiB userdata。不支持保留用户数据缩容，不是任意手机的通用分区程序。

- 公共逻辑：`tools/partition/partition-darwin.py`，共用 `tools/partition/restore-android-layout.py` 的 GPT 校验和设备保护逻辑，两者都需保留。
- 本机配置：`local/devices/<alias>/darwin-partition-<date>.json`。
- 当前 GPT 备份：`local/backups/<run-id>/`，并登记 `local/index.json`。
- 方案、实际脚本和回读记录：`work/runs/<run-id>/`，每轮新建，不覆盖。

私人配置、生成脚本、GPT、GUID 和设备日志不进入 Git。公共工具、测试和本文进入 Git。

## 1. 只读采集并核验输入

先在 Recovery 确认设备、序列号、TWRP 版本、磁盘大小、逻辑扇区大小、挂载和 GPT 布局。完整备份主备 GPT：主捕获从 LBA 0 开始，包含 header 和全部条目；备捕获在磁盘末尾结束，也包含完整 header 和条目。捕获长度按扇区对齐，不能从其他手机复制备份。步骤见 [安装教程](INSTALL.md#3-先读取自己的布局)。

所用 ARM sgdisk 需先核对来源、SHA256 和版本；主机 x86 程序不能替代。公共工具不分发这个二进制。SHA256 不符时停止，不通过改写摘要来绕过。GPT 备份不是个人数据备份；这条路线会重建 userdata，清空 Android 数据。

本机配置使用以下字段，替换占位符和容量整数：

```json
{
  "schema_version": 1,
  "device": "dipper",
  "serial": "<ro.serialno>",
  "twrp_version": "<已核验版本>",
  "disk": "/dev/block/sda",
  "sector_size": 4096,
  "disk_bytes": 0,
  "sgdisk_sha256": "<已核验的64位摘要>",
  "before_primary": {"path": "<主GPT路径>", "sha256": "<已核验摘要>"},
  "before_backup": {"path": "<备GPT路径>", "sha256": "<已核验摘要>"},
  "darwin_size_gib": 24,
  "darwin_guid": "<本轮新生成的UUID-v4>"
}
```

路径相对于配置文件；用 `python3 -c 'import uuid; print(uuid.uuid4())'` 生成一个新 GUID 后存入本轮配置，不复制旧设备 GUID。大小单位为 GiB，只接受正整数。分区起点向上按 1 MiB 对齐，末端为 GPT 最后可用 LBA，因此实际容量可能比请求值少不到 1 MiB，方案会列出差额。本次 24 GiB 方案实际少 8192 字节。镜像是否能容纳及运行时空间是否足够，需要后续镜像验收另行核对。

## 2. 生成并审查

从仓库根目录执行：

```sh
# 只输出方案，不创建文件或接触手机
python3 tools/partition/partition-darwin.py --config local/devices/<alias>/darwin-partition-<date>.json

# 保存到新的私有运行目录，拒绝覆盖已有目录
python3 tools/partition/partition-darwin.py --config local/devices/<alias>/darwin-partition-<date>.json --output-dir work/runs/<new-run-id>
```

输出包含 `plan.json`、`create-darwin.sh`、`expected-gpt-entries.bin`、可用于后续校验的 `config.json`、工具来源摘要和 `SHA256SUMS`。expected 文件只是条目比对依据，**不能 dd 到磁盘**。配置中的输入路径会转换为绝对路径，不应直接迁移到另一台主机执行。

工具自动检查输入摘要、GPT 主备 CRC/条目一致性、边界和重叠，保留 userdata 起点/类型/GUID及其他分区条目，选择 userdata 编号之后的空闲 GPT 项创建 darwin。已有 darwin、未知布局或空间不足时拒绝生成方案。

## 3. 持有人执行

审查目标范围及清空影响，在本轮手机环境中使用经过核验的 sgdisk 做 `--pretend` 演练并回读确认未改盘。此前成功不代表换版本、换手机后可跳过演练。持有人将已核验工具放到 `/tmp/sgdisk`，脚本放到 `/tmp/create-darwin.sh`，校验传输摘要后执行：

```sh
adb -s <serial> shell sh /tmp/create-darwin.sh CREATE-DARWIN
```

脚本核对 root、设备身份、TWRP、磁盘容量、工具及恢复前 GPT 摘要。正常卸载 `/sdcard`、`/data`，不使用强制/懒卸载；剩余挂载、块设备 holder、活动 swap、已存在的目标节点都会阻止写入。执行期间关闭 MTP，不进行其他挂载或存储操作；本工具不覆盖并发挂载或其他 mount namespace 的情况。任何失败先保存输出并排查，不能删掉检查强行继续。

修改后脚本打印 GPT 并停止。此时旧文件系统可能比新 userdata 大，**不要启动 Android，不要按旧内核容量格式化**。也不要重复运行已完成的脚本。

## 4. 回读、重启与验收

先读取新的主备 GPT，校验它们是否与生成方案逐条一致：

```sh
python3 tools/partition/partition-darwin.py --config work/runs/<run-id>/config.json --verify-primary <写入后主GPT> --verify-backup <写入后备GPT>
```

通过后由持有人重进 Recovery，再读取主备 GPT 和两个新节点的字节容量，进行第二次校验：

```sh
python3 tools/partition/partition-darwin.py --config work/runs/<run-id>/config.json --verify-primary <重启后主GPT> --verify-backup <重启后备GPT> --kernel-userdata-bytes <实读字节数> --kernel-darwin-bytes <实读字节数>
```

工具不读取手机，必须提供同一轮的真实读数，不能把方案数字直接当作实读结果。旧容量、缺少一个节点容量或 GPT 条目不符都会被拒绝。

两步通过后，持有人在 TWRP **Format Data**，只重建 userdata，不格式化 darwin。回 Android 完成初始化，再检查 `sys.boot_completed` 与 `df -k /data`。MIUI 的“系统固件”可能包含非 Android 分区的空间；验收依据是 GPT、节点容量与文件系统读数，不是这个分类数字。通过后再匹配新 darwin GUID 与加载器、内核配置，准备镜像。

## 验证边界

14 项分区工具测试通过，包含 10 种 shell 保护条件的假设备拒绝子场景；共享恢复工具的 17 项测试通过。测试不会访问真实块设备。使用本次保存的分区前后 GPT 离线回放，生成条目与已经实机成功的条目完全一致，重启后的两个节点容量通过校验。

本通用生成器输出的脚本尚未在真实手机重新执行；本机一次性脚本的实机成功与通用工具的离线通过分别记录。当前手机已经分区，不需要为了测试再次分区。测试命令：

```sh
python3 tools/tests/test-restore-android-layout.py
python3 tools/tests/test-partition-darwin.py
```
