# 配置、重建与临时启动

先完成[分区、镜像写入与回读](INSTALL.md)，或确认已有分区和镜像内容匹配。本页用于后续启动和开发验证，无需每次重新分区或刷写系统。已验证结果与未覆盖项目见[功能状态](../STATUS.md)。

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

源码仍在唯一的 `work/` 中开发。重编译前，将会被覆盖的 loader 源码、loader.efi、boot-dipper.img、BootShim/FD 和本机配置备份到 `local/backups/<run-id>/`，保存摘要与对应关系；原生构建会更新原输出位置。运行记录放 `work/runs/<run-id>/`，不复制整套源码。

| 变化 | 必须处理 |
| --- | --- |
| 仅 darwin 唯一 GUID 改变 | 更新本机 loader，重建 loader 和 UEFI |
| 分区起点、长度或内核改动 | 同步 loader/内核边界，按构建教程重建受影响内核及依赖，再重建 loader/UEFI |
| 用户态、GPU/Wi-Fi 固件或配置改变 | 按用户空间教程重建相应 APFS，再重新打包载荷 |
| 仅启动参数改变 | 新建候选目录重新打包，保留旧候选 |

在仓库根目录完成[构建环境](../build/BUILD.md)与[用户空间准备](../build/USERLAND.md)后：

```sh
bash tools/build/build-loader-uefi.sh
# RUN_ID 换成本轮唯一名称；候选目录必须不存在。
: "${RUN_ID:?先设置本轮名称}"
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 300 --wifi
(cd "work/runs/$RUN_ID/candidate" && sha256sum -c SHA256SUMS)
```

Wi-Fi 需要已核验的对应固件；无线关闭的对照可省略 `--wifi`，需要关闭扬声器时另加 `--no-audio`。此处候选限时 300 秒，默认不启用持久存储写入或 var_store；要保留 `/private/var` 见下面的[持久保存](#持久保存可选)。具体测试矩阵见[已有分区测试](EXISTING_INSTALL.md)。

重建后核对新 GUID、ARM64 EFI、UEFI 内嵌的 loader，以及 boot 镜像中的 BootShim、FD、USB 引导载荷与 DTB。沿用的内核和用户态产物也要核对摘要；在新的 candidate/ 中保存完整的一组启动文件。

`tools/build/build-loader-uefi.sh` 会嵌入 USB 引导载荷；缺少它，即使看到 UEFI 也不保证出现 xnuloader 服务。构建命令退出成功只是主机证据，设备成功须另验。

## dipper 短启动参数与默认值

以下短参数需配套包含平台默认值表的新内核；旧内核仍需完整参数，不能只替换 cmdline。内核在读取设备树后依据 `/arm-io/device_type` 精确等于 `dipper` 启用默认值；这是现有 loader 的物理平台字段，与模拟的 iPhone 根节点身份不同。redwood、QEMU 和缺少该字段的目标保持原参数行为。

| 载荷 | 参数 |
| --- | --- |
| daily | `bootcpu=7 cpus=7 ufs=2 root_apfs=ufs_darwin epoch=<UNIX_TIME> wifi_mac=<LOCAL_WIFI_MAC>` |
| bench 追加 | `loader_return_after=360 taskload=500 touch_lat=1 mi8_cpuclk=10 perfprof=1 fprof=1000` |

`epoch` 按运行时间提供；`wifi_mac` 仍来自本机私有配置，不能固化进代码。daily 不含测量开关和自动返回期限，并不表示长期稳定性已验证。`bootcpu`、`cpus` 由 loader 在内核启动前消费，必须保留；存储选择 `ufs`、`root_apfs` 也保留。电量缓存与手电身份也由配套的新 loader 在 dipper 上缺省准备，显式 battery=0/torch=0 关闭；其他 loader 功能仍按需显式传参。

默认值集中在 `pexpert/arm/pe_bootargs.c`，内核解析器与用户态 `kern.bootargs` 共用展开后的配置：

| 参数 | dipper 缺省值 |
| --- | --- |
| `fts` | `1` |
| `fts_steps` | `6` |
| `fts_raw` | `0` |
| `buttons` | `1` |
| `buttons_steps` | `5` |
| `gpu` | `1` |
| `mi8gpu_gmuclk` | `1` |
| `mi8gpu_zap_keep` | `1` |
| `caenv` | `FD_MESA_DEBUG=sysmem` |
| `fb_partial` | `0` |
| `fb_flip` | `1` |
| `fb_native` | `1` |
| `sb_fps_clamp` | `1` |
| `mi8rp_mss` | `6` |
| `mi8rp_hold` | `90` |
| `mi8rp_svc` | `1` |
| `mi8rp_servreg` | `1` |
| `mi8rp_wlfw` | `1` |
| `mi8rp_bdf` | `1` |
| `mi8rp_wsmmu` | `3` |
| `mi8rp_lx` | `1` |
| `mi8rp_lxirq` | `1` |
| `wifi_lx` | `2` |
| `wifi_station` | `1` |
| `wifi_quiet` | `1` |
| `thermgov` | `66` |
| `ffix` | `1` |
| `bt` | `7`（iOS 蓝牙，缺省启动依赖 Wi-Fi 侧） |
| `audio` | `5`（扬声器会话） |
| `audio_level_db` | `0`（0 dB 数字增益档） |
| `audio_seconds` | `0`（常驻） |
| `battery` | `1` |
| `torch` | `3` |
| `haptic` | `3` |

显式参数优先，包括 `0`。例如 `fb_native=0`、`thermgov=0`、`ffix=0` 分别关闭对应功能，`caenv=0` 阻止注入默认环境变量；其他显式值沿用原消费者的解析和约束。启动时 `bootcfg:` 行按 `arg`/`def` 标记来源；MAC 只显示 `wifi_mac=set(arg)`，不输出其值。

默认 Wi-Fi 配置需要匹配固件和私有 MAC。通用打包工具仍保留 `--wifi` 的显式选择：不带该选项时，短参数中增加 `mi8rp_mss=0 wifi_lx=0 wifi_station=0 bt=0` 以关闭其无线启动路径。`--peripherals` 与 `--bluetooth` 是兼容空操作，不再追加对应参数；`--bluetooth` 仍要求 `--wifi`。有 `--wifi` 时打包器同时核对蓝牙固件与用户态文件。`--no-audio` 追加 `audio=0`；缺省 cmdline 无 bt/audio 参数，采用内核默认表。

以 10 位 epoch、17 字符 MAC 计，daily 为 87 字节，bench 为 172 字节（均不含换行）；加 80 字节保守 loader 前缀分别为 167、252 字节。bench 距 600 字节边界为 348 字节，保持严格小于 600 时最多再加 347 字节。默认电量缓存使 loader 还会增加 battery_shared_pa 前缀；打包器按含该地址的完整前缀另行检查。loader 的 608 字节输入结构不变；内核另用 2048 字节缓存保存展开配置，`kern.bootargs` 可返回展开值。该缓存不放宽载荷输入长度限制。

原27项短参数设备冒烟已有记录；当前34项默认组合和常驻音频完成主机验证，组合设备验收仍待持有人执行。


## 持久保存（可选）

iOS 的 `/private/var`（主屏布局、设置、应用数据）平时是内存盘，每次启动都是空的。加 `--persist` 后，启动时从 darwin 读回上次的内容，运行结束时把它整体存回去：

```sh
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 300 --persist
```

- 它在启动参数里追加 `ufs_write=1 var_store=1 var_save_ms=120000`。**这会写设备存储**：loader 和内核只允许写 darwin 块 2042368 之后的区域（系统卷和两个 cryptex 在其之前），存档放在块 2097152 起的两个 2 GiB 槽里，每次写入读回比对，其他分区一律拒绝。
- 只在有序结束时保存：限时到期（`--persist` 要求 `--seconds` 不少于 180）或主机 stop。长按电源、断电、崩溃不保存，上一次存档保持不变。保存期间（限时到期后最长约 120 秒）不要拔线或长按电源。
- 双槽交替写，头最后写；读回取校验通过的最新一槽，存档损坏时 `/private/var` 保持空白启动，不会阻止开机。
- 只读读回：只加 `var_store=1`（不加 `ufs_write=1`），读回但不保存。日常开发和对比测试不加这两个参数，就和以前一样是干净状态、不写盘。
- 存档和 `/private/var` 一起放在内存里，每槽上限 2 GiB；日志目录、临时目录和运行时目录不保存。
- 清空存档：在 TWRP 把 darwin 块 2097152..3145727 清零（`dd if=/dev/zero of=/dev/block/<darwin 节点> bs=4096 seek=2097152 count=1048576`），先核对节点是 darwin；系统卷不受影响。
- 保存期间系统仍在运行，数据库可能存到一半的状态；周期保存、异常退出和存档增长尚未测试。

## 蓝牙（缺省开启）

需要先把蓝牙固件放进 `work/hackios/fw-bt/`（取法见[设备准备教程](DEVICE_PREPARATION.md#5-蓝牙固件实验)），再重建用户空间（构建入口已带 `BT=1`：蓝牙守护进程 `bluetoothd`、`BlueTool` 及其注入库和占位固件文件）。打包时加 `--wifi`：

```sh
python3 tools/build/build-payload.py --output "work/runs/$RUN_ID/candidate" --seconds 600 --wifi
```

dipper 缺省 bt=7；打包器在 --wifi 时核对启动卷里的固件与根镜像里的蓝牙文件，缺一项就拒绝打包。缺省 bt 在 mi8rp_mss=0 或缺少 wifi_mac 时跳过并记录原因；显式 bt=1..7 保持原诊断行为。显式 bt=0 关闭。芯片和 Wi-Fi 共用供电，蓝牙地址由 wifi_mac 推出，不写存储。

- 开机后内核先等 `bt_delay` 秒（默认 60），再下载固件，芯片约在开机 70 秒后就绪。这之前"设置"里蓝牙显示关闭，就绪后自动打开。
- 可以开关蓝牙、搜索设备、配对和连接耳机；蓝牙耳机声音仍未实现；扬声器会话是另一条输出路径。
- 配对记录不跨重启保留（与 `--persist` 的组合未测试），重启后需要重新配对。
- 启动日志里以 `bt:` 开头的行是内核侧记录；芯片拒绝的命令会以 `bridge: the chip refuses` 记下。

## 扬声器、电量、震动与手电（缺省开启）

配套内核和loader在dipper缺省启用 audio=5、battery=1、haptic=3、torch=3。分别显式追加 audio=0、battery=0、haptic=0、torch=0 可关闭；这些是对应功能的关闭开关。无需 --peripherals。扬声器需要配套的ADSP与功放固件启动卷；默认组合仍待设备验收。

`audio_level_db` 可选 −30/−24/−20/−12/−6/0，缺省0dB；例如 audio_level_db=-30 降低数字电平，0dB并非关闭。`audio_seconds=0` 为常驻：有loader_return_after时受运行结束及收尾期限约束，没有则持续运行；1–900为有界诊断，保留900秒/45000周期单窗与200次wake限制。常驻模式去掉这些时长/次数额度，保留LIVE、状态、时钟、单声道/幅度、缓冲地址、健康与失败锁存等检查。

mi8rp_mss开启时音频仍等待Wi-Fi FW_READY，失败或90秒超时就不启动；mss显式关闭时沿用独立音频路径。常驻会话空闲10秒（写入唤醒后无非零）或30秒（其他静默）软关断功放，DSP与DMA仍每20ms运行，功耗未测。音质未调校，组合与常驻的设备表现尚待验证。

## 蓝牙芯片诊断（实验）

`bt=N` 让内核运行蓝牙诊断到第 N 档，缺省为第7档；显式 `bt=0` 关闭，不写存储：`1` 只读摸底，`2` 再打开串口引擎时钟，`3` 引擎内部回环自检，`4` 再给芯片上电、发 HCI Reset 与读版本，`5` 再下载固件（补丁与 NVM，115200 baud，约 25 秒）并重发 HCI Reset 与读版本，`6` 与 `5` 相同但先把串口提速到 3.2 Mbaud（下载约 1 秒）。第 4 档会通过 RPMh 请求五路供电并切换四个引脚，先等待 `bt_delay` 秒（默认 60）；第 5、6 档需要启动卷 `fw/` 里有蓝牙固件，取法见[设备准备教程](DEVICE_PREPARATION.md#5-蓝牙固件实验)，限时建议不少于 300 秒。结果从启动日志里以 `bt:` 开头的行读取；建议同时加 `loader_return_after=240` 之类的限时，结束后完整重启。`bt=7` 即上一节的 iOS 蓝牙。各档结果见[验证记录](../validation/VALIDATION.md#蓝牙芯片的-uart-链路2026-11-10)。

## 降低渲染分辨率（可选，不是默认值）

在 daily 参数后显式追加 `fbscale=2 fb_dpu=1`，iOS 按 750×1624（iPhone X 的点尺寸、每点 2 像素）渲染，像素约为 1125×2436 的 44%：

| 参数 | 作用 |
| --- | --- |
| `fbscale=2` | 向系统报告 750×1624 @2x；同时写入设备树的缩放值 |
| `fb_dpu=1` | 需同时有 `fb_native=1`（默认）。翻页缓冲直接用 750×1624，由 DPU 的 QSEED3 放大到面板，处理器只做整块拷贝；不加则由处理器逐像素放大，每帧多数毫秒 |

使用前提和限制：

- 内核与根镜像都要用本版本。根镜像里的 SpringBoard 库把 UIKit 的状态栏后备样式换成 iPhone X 的样式；用旧根镜像会显示红色占位条（`rdar:45025538`）。
- 系统按“宽、高、缩放”查屏幕类别，只认本机型自己的 1125×2436 @3x（类别 15）；750×1624 @2x 查不到（类别 -1），状态栏已按上面处理，**实时壁纸不绘制**（PosterBoard 在该类别什么都不画，窗口是黑底），所以 SpringBoard 库在壁纸窗口最上面盖一张静态图：根镜像里有 `/redwood/etc/wallpaper.jpg` 就用它（建议先缩到 750×1624 的 JPEG），没有则用渐变。设置里换壁纸不会改变它。换成 iPhone XR 的 828×1792 @2x 同样查不到，不是出路。
- 在原分辨率下也想用静态壁纸（不用 PosterBoard 的实时壁纸）：显式追加 `still_wall=1`，图片规则同上；PosterBoard 仍在后台运行，是否因此省处理器未测。
- `fbscale` 与 `fbwidth`、`fbheight` 不能同时用于换尺寸。图像比原来软。
- 降分辨率的启动里，设置、信息等应用出现过闪退；原分辨率下各打开一次没有闪退（样本小），原因未定。
- 浏览器、触摸、按键等在此配置下的完整回归尚未做，见[验证记录](../validation/VALIDATION.md)。

## 3. 临时启动

日常启动 iOS 不需要重新刷入 TWRP，也不需要先进入 TWRP。Recovery 只在分区维护和回读等步骤使用；首次安装或进入已安装 TWRP 的说明见[设备准备教程](DEVICE_PREPARATION.md)。

命令在主机 Bash 执行。先进入厂商 bootloader，使用 `fastboot devices` 识别本机序列号，再设置变量；不是 TWRP 的 adb 模式。

```sh
: "${BOOT_SERIAL:?设置厂商 fastboot 序列号}"
: "${CANDIDATE:?设置本轮 candidate 的绝对路径}"
(cd "$CANDIDATE" && sha256sum -c SHA256SUMS)
fastboot -s "$BOOT_SERIAL" getvar product
# 只有 product 为 dipper、配置与摘要核对通过后继续。
fastboot -s "$BOOT_SERIAL" boot "$CANDIDATE/boot-dipper.img"
```

这是临时加载 UEFI，不是 `fastboot flash boot`。等待设备重新出现；厂商 fastboot 序列号与 loader 阶段不同，当前 loader 使用 `xnuloader`。若连接多台设备，先只保留本次目标，明确确认身份。

```sh
fastboot devices
fastboot -s xnuloader getvar product
# 只有 product 确认为 xnuloader 后才逐条继续。
fastboot -s xnuloader oem ramdisk
fastboot -s xnuloader stage "$CANDIDATE/flashboot.apfs"
fastboot -s xnuloader stage "$CANDIDATE/payload.bin"
fastboot -s xnuloader oem run
```

所有文件必须来自同一候选。系统根卷从 darwin 读取，启动卷与内核载荷传到 RAM；UFS 路线使用 `ufs=2 root_apfs=ufs_darwin`。基础测试不要加入 `ufs_write=1`；持久保存是单独的可选项，范围与恢复方法见[持久保存](#持久保存可选)。已安装并回读匹配后，日常启动从本节开始。

## 4. 验收、日志与结束

UEFI 画面、xnuloader 身份和 fastboot OKAY 分别只证明各自阶段；真正进入 iOS 需要观察实际屏幕。记录桌面、触摸及本轮实际测试项目，结合内核根卷挂载和用户态日志，不能从“能进桌面”推定全部外设正常。

loader 可响应时取证，文件放本轮新运行目录，避免覆盖旧日志：

```sh
fastboot -s xnuloader getvar result
fastboot -s xnuloader oem log
fastboot -s xnuloader get_staged "$LOG_DIR/kernel-log.txt"
```

先设置并创建本轮 `LOG_DIR`，确认输出文件不存在。接口暂不可用不应改用刷写命令。当前 GPU SMMU/基带退出恢复尚未闭合；限时结束或失败后，完整重启再开始下一轮，不能直接连续 rerun。回到 Android 后检查启动完成与 `/data`；需要恢复分区布局时才用[Android 回退章节](INSTALL.md#7-回退恢复-android-布局)。

首次安装测试已由测试者确认进入 iOS；详细内核日志、逐项外设回归和退出收尾的覆盖范围见[验证记录](../validation/VALIDATION.md)，不能仅依据 oem run 的 OKAY 判断成功。
