# 配置、重建与临时启动

先完成[分区、镜像写入与回读](INSTALL.md)，或确认已有分区和镜像内容匹配。本页用于后续启动和开发验证；无需每次重新分区或刷写系统。2026-10-30 第 10 轮持有人确认新分区成功进入 iOS；外设逐项回归和退出后 Android 重启仍待确认。

## 1. 让源码匹配新分区

公开补丁移除了开发设备的分区唯一 GUID，目前使用全零占位符。首次编译前，需要把自己的布局同步到加载器与内核，再重编译：

| 位置（相对于 work/hackios） | 需要核对的参数 |
| --- | --- |
| `xnuloader/loader.c` | `BLOCK_DARWIN_FIRST`、`BLOCK_DARWIN_LAST`、`BLOCK_DARWIN_TYPE`、`BLOCK_DARWIN_UNIQ` |
| `xnu-src/xnu-8796.121.2/bsd/dev/redwood_ufs.c` | `UFS_DARWIN_FIRST`、`UFS_DARWIN_BLOCKS`、写入数据区域边界 |
| 如需使用上游 `tools/darwin-write.py` | 分区号、节点、GUID、扇区大小、边界和保护区；上游默认值并非 dipper 的布局 |

C 结构中的 GUID 必须按字段正确转换，不能把字符串直接粘进整数数组；整数形式的 GUID 首三字段与 GPT 原始字节序也不同。若内核边界或配置发生变化，必须重编译内核；若仅唯一 GUID 改变，重编译加载器及嵌入它的 UEFI，核验后可沿用边界匹配的内核。不要用旧 loader、上游预编译内核或取消校验来代替适配。

`source-manifest.json` 校验的是公开源码快照；设备参数应在源码准备和哈希校验完成后修改。当前还没有自动生成设备配置的公开工具，这一步需要人工审查。

## 2. 按变化范围重建并保存候选

源码仍在唯一的 `work/` 中开发。重编译前，将将被覆盖的 loader 源码、loader.efi、boot-dipper.img、BootShim/FD 和本机配置备份到 `local/backups/<run-id>/`，保存摘要与对应关系；原生构建会更新原输出位置。运行记录放 `work/runs/<run-id>/`，不复制整套源码。

| 变化 | 必须处理 |
| --- | --- |
| 仅 darwin 唯一 GUID 改变 | 更新本机 loader，重建 loader 和 UEFI |
| 分区起点、长度或内核改动 | 同步 loader/内核边界，按构建教程重建受影响内核及依赖，再重建 loader/UEFI |
| 用户态、GPU/Wi-Fi 固件或配置改变 | 按用户空间教程重建相应 APFS，再重新打包载荷 |
| 仅启动参数改变 | 新建候选目录重新打包，保留旧候选 |

在仓库根目录完成[构建环境](../build/BUILD.md)与[用户空间准备](../build/USERLAND.md)后：

```sh
bash tools/build-loader-uefi.sh
# RUN_ID 换成本轮唯一名称；候选目录必须不存在。
: "${RUN_ID:?先设置本轮名称}"
python3 tools/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 300 --wifi --peripherals
(cd "work/runs/$RUN_ID/candidate" && sha256sum -c SHA256SUMS)
```

Wi-Fi 需要已核验的对应固件；基础测试可省略 `--wifi --peripherals`。此处候选限时 300 秒，默认不启用持久存储写入或旧 var_store。具体测试矩阵见[已有分区测试](EXISTING_INSTALL.md)。

本轮第 08 轮只改 loader GUID，内核边界不变，因此未无意义地重编译内核或系统镜像。实际重建 loader/UEFI，并核对：ARM64 EFI、新 GUID、固件卷内嵌的完整 loader、boot 镜像中 BootShim+FD+USB XNUP、DTB；内核及两个启动 APFS 摘要与已验产物相同。新候选保存在该轮 candidate/，不是直接使用旧目录的散装文件。

`tools/build-loader-uefi.sh` 会嵌入 USB 引导载荷；缺少它，即使看到 UEFI 也不保证出现 xnuloader 服务。构建命令退出成功只是主机证据，设备成功须另验。

## 3. 临时启动

命令在主机 Bash 执行。先由持有人进入厂商 bootloader，使用 `fastboot devices` 识别本机序列号，再设置变量；不是 TWRP 的 adb 模式。

```sh
: "${BOOT_SERIAL:?设置厂商 fastboot 序列号}"
: "${CANDIDATE:?设置本轮 candidate 的绝对路径}"
(cd "$CANDIDATE" && sha256sum -c SHA256SUMS)
fastboot -s "$BOOT_SERIAL" getvar product
# 只有 product 为 dipper、配置与摘要核对通过后继续。
fastboot -s "$BOOT_SERIAL" boot "$CANDIDATE/boot-dipper.img"
```

这是临时加载 UEFI，不是 `fastboot flash boot`。等待设备重新出现；厂商 fastboot 序列号与 loader 阶段不同，本轮后者为 `xnuloader`。若连接多台设备，先只保留本次目标，明确确认身份。

```sh
fastboot devices
fastboot -s xnuloader getvar product
# 只有 product 确认为 xnuloader 后才逐条继续。
fastboot -s xnuloader oem ramdisk
fastboot -s xnuloader stage "$CANDIDATE/flashboot.apfs"
fastboot -s xnuloader stage "$CANDIDATE/payload.bin"
fastboot -s xnuloader oem run
```

所有文件必须来自同一候选。系统根卷从 darwin 读取，启动卷与内核载荷传到 RAM；UFS 路线使用 `ufs=2 root_apfs=ufs_darwin`。基础测试不要加入 `ufs_write=1`，持久保存须单独审查范围与恢复方法。已安装并回读匹配后，日常启动从本节开始。

## 4. 验收、日志与结束

UEFI 画面、xnuloader 身份和 fastboot OKAY 分别只证明各自阶段；真正进入 iOS 需持有人观察屏幕。记录桌面、触摸及本轮实际测试项目，结合内核根卷挂载和用户态日志，不能从“能进桌面”推定全部外设正常。

loader 可响应时取证，文件放本轮新运行目录，避免覆盖旧日志：

```sh
fastboot -s xnuloader getvar result
fastboot -s xnuloader oem log
fastboot -s xnuloader get_staged "$LOG_DIR/kernel-log.txt"
```

先设置并创建本轮 `LOG_DIR`，确认输出文件不存在。接口暂不可用不应改用刷写命令。当前 GPU SMMU/基带退出恢复尚未闭合；限时结束或失败后，由持有人完整重启再开始下一轮，不能直接连续 rerun。回到 Android 后检查启动完成与 `/data`；需要恢复分区布局时才用[Android 回退章节](INSTALL.md#7-回退恢复-android-布局)。

本轮第 10 轮：主机实时确认 xnuloader，`oem run` 日志仅有 OKAY；持有人随后明确报告“成功进入ios了 没问题”。因此记为持有人确认的 iOS 启动成功，未取得详细内核启动日志，未将本轮外设逐项回归或最终 Android 重启记为通过。
