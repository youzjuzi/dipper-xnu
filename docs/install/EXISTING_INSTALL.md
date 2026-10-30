# 复用现有 darwin 分区测试新构建

这种测试验证的是“源码构建 → 已有布局上的启动”，不验证首次重新分区。若系统区已经与本轮 `darwin.img` 完全相同，可以省去重刷；这时也不能把测试记录写成“本轮刷写成功”。

## 1. 先核对现有布局和系统内容

在 Android 或适配 recovery 下只读检查；Android 需要已有 root，示例为 Magisk。不要为了执行示例解锁或格式化设备。

```sh
adb devices -l
adb shell "su -c 'blockdev --getss /dev/block/sda; blockdev --getsize64 /dev/block/sda; blockdev --getsize64 /dev/block/by-name/darwin'"
adb shell 'ls -l /dev/block/by-name/darwin /dev/block/by-name/userdata'
```

设备必须明确为自己的 dipper。记录主、备份 GPT，核对两份 header/entry CRC、分区边界、类型、唯一 GUID、容量及挂载状态。Linux sysfs 的 `start` / `size` 单位是 512 字节，不能直接当成这里的 4096 字节 GPT LBA。

系统区回读采用[分区与写入教程第 6 节](INSTALL.md#6-写入系统并回读校验)的带失败检查流程，进入 Recovery 后执行，避免掩盖 dd 读取错误。固定输入的前 8365539328 字节必须与主机镜像摘要相同；匹配只覆盖系统镜像范围，不代表分区尾部历史用户状态相同。

## 2. 从对应手机准备 GPU 固件

本次手机系统版本为 MIUI `V12.5.2.0.QEACNXM`，对应[小米原厂包](https://bn.d.miui.com/V12.5.2.0.QEACNXM/miui_MI8_V12.5.2.0.QEACNXM_f5ec813d1c_10.0.zip)，链接也由 [LineageOS 的 dipper 设备记录](https://github.com/LineageOS/lineage_wiki/blob/main/_data/devices/dipper.yml)列出。

可从自己的对应手机只读提取以下文件，逐个核对手机端与主机端 SHA256，放入 `work/hackios/fw-gpu/`：

| 手机路径 | 本轮 SHA256 |
| --- | --- |
| `/vendor/firmware/a630_gmu.bin` | `b07f90299ff2ae33948fcfd6ed67f53fbd287b5bf85ff2d43db11d4d32c1621f` |
| `/vendor/firmware/a630_sqe.fw` | `34edacb6fdedfbfc07ed5cd1d29b0b57a3543ef5be6ab34a43bd64686826fa1e` |
| `/vendor/firmware/a630_zap.mdt` | `f369d5614503a516a6443887f04dd8497cc7127b1ff3429c492666b26a9ab34b` |
| `/vendor/firmware/a630_zap.b02` | `519b5538809f54ee566246b0520746a8ea82ca9384ea6bddb0b0e0d3c2de520c` |

这些是手机实际文件的摘要；本轮未下载原厂 ZIP 做逐字节对照，不把手机端校验称为厂商签名验证。固件不提交到仓库。

## 3. 匹配源码并重建

按 [启动教程配置章节](STARTUP.md#1-让源码匹配新分区) 将 loader/内核的边界和 GUID 与实际 GPT 对齐。私人配置、GPT 备份和修改前源码放在忽略目录 `local/`；不要把唯一 GUID 回写到公共补丁和清单。

本轮实测边界已与公开源码相同，只需将 loader 的零 GUID 占位符替换成本机值，再重新编译 loader/UEFI；内核不需要因为 GUID 而改动。如果边界不同，必须修改内核并重编译。

```sh
bash tools/build/build-loader-uefi.sh
bash tools/build/build-userland.sh
python3 tools/build/build-payload.py --output work/runs/desktop-01 --seconds 300
```

用户空间入口启用按需服务，并加入 installd、sleepd；桌面验收不运行上游默认的后台 CPU 基准。打包入口会从 APFS 回读 4 个 GPU 固件，与输入比较后才生成载荷；输出目录必须不存在。

本次默认载荷启用 UFS 系统读取、A630 图形、触摸和按键，不启用 Wi-Fi、存储写入或 `var_store`。因此不会依赖尾部保存的旧用户配置。Wi-Fi 测试见第 5 节；其他外设需要分别验收。

## 4. 临时启动和取证

先在新输出目录执行 `sha256sum -c SHA256SUMS`。确认设备身份后，使用 [启动教程](STARTUP.md#3-临时启动) 的 RAM 启动顺序，文件全部取自该新目录。

启动后可用 loader 的接口读取结果和日志：

```sh
fastboot getvar product  # 必须为 xnuloader
fastboot getvar result
fastboot oem log
fastboot get_staged kernel-log.txt
```

应同时确认内核根卷挂载、用户空间及 SpringBoard 启动日志、实际屏幕与触摸响应。出现 fastboot OKAY、UEFI 画面或单纯进程日志，都不能独立证明桌面验收成功。测试结束或失败后完整重启，避免沿用 GPU/基带未恢复的状态直接 rerun。

## 5. Wi-Fi 与网页测试

在基础桌面测试通过、手机完整重启回 Android 后，先按 [外部材料](../build/INPUTS.md#wcn3990-wi-fi-特性描述文件) 补齐 `firmware-5.bin` 并重建用户空间，再生成新载荷：

```sh
python3 tools/build/build-payload.py --wifi --seconds 900 --output work/runs/wifi-01
```

按第 4 节的 RAM 启动顺序使用新目录中的文件。此配置开启 Mi8 的 MSS/GLINK/WLFW 与 ath10k station 路线，固件从本机原厂 `modem` 分区读取，包括 MBA、modem、wlanmdsp 和匹配设备的 bdwlan 文件。不要套用其他设备的 `wifi=1` 配置，也不要凭文件名猜测或替换板级校准文件。

入口会在忽略目录 `local/wifi-mac` 生成并保留一个随机、本地管理的单播 MAC；它不是手机的原厂 MAC。启动参数须连同 loader 追加内容一起小于 608 字节。测试限时 900 秒，不启用持久用户状态；Wi-Fi 密码由持有人在手机设置中输入，不写入教程或命令行。

无线初始化完成后，在设置中选网络并连接，再用 Safari 打开一个域名网页并刷新。分别记录固件就绪、en0 接口、获取地址、路由/DNS，以及实际网页成功显示；扫描到热点、状态栏图标或单独拿到 IP 均不代表外网上网成功。日志可能包含 SSID、MAC、局域网地址和浏览内容，应留在忽略的测试目录，公开记录只保留脱敏结论。

如果开关无法打开，先检查无线初始化日志。本次复现曾在 `FW_READY` 后出现 `lx: no 46137344 bytes of memory in one piece` 和 `redwood_lx_start rc=12`：固件正常，驱动却无法在桌面启动后取得 44 MiB 连续内存。源码修复在 modem 线程启动前预留内存，仍在 WLFW/SMMU 就绪后映射给无线设备；修改后必须重建 ath10k 和内核，再生成载荷。不要用更换密码或随机修改无线参数处理这类失败。

loader 日志只保留启动头部和有限的循环缓冲。排查早期初始化时，从 `oem run` 后立即定期执行第 4 节的取日志命令，例如前 100 秒每 2 秒保存到一个新文件；仅在桌面出现后取一次，可能已经丢失关键错误。

## 6. 外设与日常交互测试

```sh
python3 tools/build/build-payload.py --wifi --peripherals --seconds 900 --output work/runs/peripherals-01
```

`--peripherals` 加入 `battery=1 torch=3 haptic=3`：电量来自 loader 读取的 PMI8998，手电筒和马达由 iOS 操作触发，不在开机时自动播放。小米 8 的 PMIC 马达不需要另一设备使用的 `aw8697_haptic.bin`。亮度、锁屏和音量键使用已编译的适配逻辑，不需要添加实验用亮度扫描参数。Wi-Fi 可省略 `--wifi` 单独关闭。

这组配置连同 loader 追加字段的实际 bootargs 为 578 字节，包含电池共享地址；入口按最多 591 字节检查，低于 607 字节有效上限。若修改参数，仍须重新计算并核对设备实际命令行，不能只看 payload 内的长度。

按第 4 节临时启动后逐项观察，并保存对应操作期间的日志：

| 项目 | 操作与验收 |
| --- | --- |
| 屏幕亮度 | 控制中心和设置分别调低、调高、恢复中间；实际面板明暗应变化，不能只看滑块移动 |
| 锁屏、唤醒、触摸 | 电源键锁屏/唤醒各 3 次，唤醒后滑动、点击正常 |
| 手电筒 | 打开约 2 秒再关闭，重复两次；分档调光另记，不能由开关正常推断 |
| 震动 | 长按桌面图标或控制中心控件，感受触觉反馈；日志应有 iOS Actuator 波形与马达事件 |
| 音量 | 音量加减键与控制中心音量条都响应；这不证明扬声器输出正常 |
| 电量 | 对照开机前 Android 电量和 PMIC 读数，确认界面显示；满电读数不证明充电过程已验证 |
| 壁纸、小组件 | 桌面背景正常，日历等小组件有内容；本轮不保存旧 var_store，重启后的持久保存另测 |
| Wi-Fi 回归 | 在同时启用外设时重新连接网络并打开、刷新网页 |

2026-10-30 首次外设测试发现亮度调节无效：DSI 命令缓冲区分配到了 4 GiB 以上，而 DMA 地址寄存器只有 32 位。修复在 `kmem_alloc_contig` 中限制物理页号，并按实际 `PAGE_SIZE` 检查完整页范围；异常返回时释放缓冲区，避免每次拖动遗留一页。更新内核后须用实机验证，不能仅以编译通过为结论。结果见 [设备验收记录](../validation/device-validation-20261030.json)。

手电筒分档调光历史上肉眼不明显，需单列结果。完整音频、电话/移动数据，以及未建立小米 8 验收基线的摄像头、蓝牙、定位与其他传感器，不因上述检查通过而记为可用。长期功耗、充电全过程和持久保存也需要独立测试。
