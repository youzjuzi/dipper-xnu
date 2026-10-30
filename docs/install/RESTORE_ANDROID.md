# Android GPT 恢复工具

入口：[tools/restore-android-layout.py](../../tools/restore-android-layout.py)。这是 Linux 主机上的离线方案生成器，不连接 ADB、不执行设备命令。通用的是恢复逻辑，本机身份、输入摘要和 GPT 备份在 `local/`。目前只支持 dipper、sda、4096 字节扇区，以及尾部相邻 userdata/darwin 恢复为原 userdata 的布局；不是任意手机的分区修复工具。

## 目录与输入

- `tools/restore-android-layout.py`：公共工具，纳入 Git。
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

## 离线审查和生成

在仓库根目录执行，替换本机配置和新运行目录：

```sh
python3 tools/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json
python3 tools/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --output-dir work/runs/<new-run-id>
```

默认只显示方案；`--output-dir` 创建新目录，保存 `plan.json`、`inputs.json`、`restore-android-layout.sh`、来源记录 `provenance.json` 与摘要。已有目录被拒绝，避免覆盖。`inputs.json` 是配置审计副本，其中相对路径仍按原配置目录解释，不要将它当作新位置下可直接运行的配置。方案与脚本包含私人 GUID，禁止提交。

## 持有人执行及验收

审查方案后，持有人将核验过的 sgdisk 和本轮脚本放到 Recovery 的 `/tmp/sgdisk` 与 `/tmp/restore-android-layout.sh`。传输后核对摘要。设备只通过此显式命令修改 GPT：

```sh
adb -s <serial> shell sh /tmp/restore-android-layout.sh RESTORE-ANDROID-GPT
```

脚本复核身份、工具和恢复前 GPT 摘要、容量，要求 userdata/darwin 均无挂载或块设备 holder，且无活动 swap。它不自动卸载；先在 TWRP 停用 MTP 并卸载相关分区，再重新检查。不在执行期间操作 TWRP 挂载界面、启动其他存储任务或其他 mount namespace；本工具不保证并发访问安全，也未覆盖所有 Recovery 版本。旧 awk 路径不再使用。

脚本只删除 darwin 并重建目标 userdata GPT 条目，不格式化、不刷系统、不自动重启。写入中断时不要盲目重跑；重新读取主备 GPT，按备份分析。不要将 sgdisk 的成功退出直接视作恢复验收通过。

完成后先回读并校验主备 GPT，再由持有人重进 Recovery，重新捕获 GPT 和内核 userdata 字节容量。用新读数验收：

```sh
python3 tools/restore-android-layout.py --config local/devices/<alias>/android-restore-<date>.json --verify-primary <重启后主GPT> --verify-backup <重启后备GPT> --kernel-userdata-bytes <重启后容量整数>
```

旧内核容量会被拒绝。此命令只核验提供的证据，不能证明文件来源或采集时间；调用者必须保证文件和容量属于同一轮设备读取。通过后仍需单独重建数据文件系统、验证 Android 启动与容量，不能把 GPT 恢复当作系统恢复完成。

## 已验证边界

2026-10-30：17 项合成 GPT/CLI 测试通过；使用本机恢复前及重启后 GPT、已记录内核容量的离线回放通过。原一次性 v2 脚本已由持有人执行并回读通过；本通用生成器新增身份、挂载/holder 等保护后的生成脚本尚未在手机执行，不继承 v2 的全部真机验证结论。当前手机已经恢复，本次保存的配置只供历史回放，不应再次执行。

测试入口：`python3 tools/test-restore-android-layout.py`。任务进度见 [首次安装任务](../development/FIRST_INSTALL.md)。
