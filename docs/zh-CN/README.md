# dipper-xnu

[English](../../README.md) | **简体中文**


**Experimental / Work in Progress**

面向 `dipper`（SDM845）的 XNU 与移动用户空间实验性移植项目。

基于 [HackiOS](https://github.com/oosexgang/hackios-xnu-kernel) 的工作，为 `dipper` 适配启动、显示、触摸、A630 GPU、WCN3990 Wi-Fi、蓝牙和扬声器音频。支持 SpringBoard 桌面、GPU 渲染、触摸、Wi-Fi 上网、蓝牙连接和扬声器声音。

项目仍在开发中，尚不适合作为日常使用系统。


## 近期更新 · 2026-11-19

- **A630 GMEM 渲染、`fb_native=2` 零拷贝直扫与 GPU 页表批量映射（已设为默认）**：
  - 修正 `bsd/dev/mi8_adreno.c` 中 `MSM_PARAM_GMEM_BASE`（`0x06`）返回 `0x00100000ull`（`1 MiB` GMEM 基址）并移除默认的 `caenv=FD_MESA_DEBUG=sysmem` 回退参数，默认开启 A630 GMEM 分块渲染。
  - 新增并默认启用 `fb_native=2`（`pexpert/arm/pe_bootargs.c`）：建立 4 槽 Write-Combined `1125x2436` 零拷贝扫描输出池（`2` splash + `2` `< 4 GB` 连续内存，保留 0 号块 `0x9d400000` 用于兜底及 `MiniIOFlipQuiesce()` 安全还原），跳过 WC 扫描画布的 `dc civac` 清洗，改为在 `evictSurface()` 中仅释放读占锁以避免 WC 内存 CPU 回读尖刺，并使用基于屏幕 TE 的睡眠等待（`MiniIOFlipWaitHintUs()`）。
  - 将定期盲目清缓存周期 `gpu_push_ms`（`GPU_PUSH_AGAIN_MS`）从 `4 ms` 提高至 `100 ms`（`seed` 变化仍立即清洗），并在 `mi8_adreno.c` / `RedwoodGPU.cpp` 引入 O(1) 页表缓存与连续段批量映射/卸载（`mi8_gpu_map_range()` / `mi8_gpu_unmap()`）。
  - 实机 300 秒对比验证：清缓存由 `zc-sysmem` 的 `~85 GiB / 5.56 s` 降至 `1.75–3.26 GiB / 0.14–0.29 s`；零拷贝翻页 `5698/5700`（均耗时 `6.87 us`、峰值 `1.70 ms`，活跃窗口 `59 FPS`）；驱逐导致的 `173.5 ms` 等待尖刺消除（显示等待峰值 `<= 14.56 ms`）；`IOSurface` GPU 映射耗时由 `6.96–8.54 ms` 降至 `0.12–0.18 ms`，`gGPULock` 等待峰值由 `9.44 ms` 降至 `0.20 ms`。
- **Wi-Fi / 蓝牙原生内核化（移除 UI 注入补丁）**：在内核 `RedwoodBT.cpp` 原生发布 `AppleOLYHAL`，移除用户态蓝牙注入库 `libredwood-bt.dylib`；删除 `SpringBoard` 状态栏 Wi-Fi UI hook（`inject_sb.c`），由 `RedwoodWLAN.cpp` 暴露 `"wlan"` 父节点并提前注册 `en0`，将 `EVENT_LQM_CHANGED` 结构体收敛为 `0xb4`（总长 `220 <= MLEN 224`）并加上 RSSI 归一化与 `com.apple.wifi.manager` 预声明，实机连网后主屏信号格原生点亮；同步合入 Wi-Fi DMA `dsb sy` 屏障、RX 槽位清零、有界 `rx_confused` 恢复与多 AP 回退。
- **动态 CPU/DDR 调频降压与 GPU 刷新合并**：触摸与 GPU 负载联动 `mi8_perf_kick()` 动态调度，空闲时自动回落至 `825 MHz` / DDR `2/16`（受 `66 °C` 温控上限约束）；`RedwoodGPU` 支持 `IOSurface` 2 ms 帧内刷新合并。
- **TAS2557 软件 I2C 校验耗时修复**：`mi8_tas2557.c` 中 `<= 50 us` 短延迟改回忙等自旋（解决 `dipper` `cpu_idle_latency == 0` 下每次 `3 us` 翻转都阻塞切换调度的问题），休眠 Y-RAM 校验耗时由 `~486–1000+ ms` 降至 `~207–208 ms`、唤醒预热缩至 `~31 ms`，消除高负载下误触发的 `latched=coefficient` 锁死。
- **音量 HUD、侧载、有序退出与实时日志**：通过标准 HID Telephony Ring Switch（`0x0b`/`0x2e`）修复音量键静音提示；收敛 `/apps` `MNT_UNION` 联合挂载侧载；补齐常驻音频/蓝牙/Wi-Fi/GPU 有序收尾与只读抓日志工具 `tools/tests/device-log.py`。
- **当前边界**：含基带的轮次之间因 `halt port modem` 未归闲仍需冷重启；渲染线程绑大核、蓝牙音频、麦克风、蜂窝移动数据与 Adreno 630 原生 Metal 尚未实现；切回默认启动参数后的纯默认冒烟轮次可按需补测。
- 以上设备结果来自持有人的手动使用和设备日志，不是完整回归；细节见[更新日志](CHANGELOG.md)和[验证记录](docs/validation/VALIDATION.md)。

更早的更新见[更新日志](CHANGELOG.md)。

## 设备与系统

| 项目 | 配置 |
| --- | --- |
| 设备代号 | `dipper` |
| SoC | SDM845 |
| GPU | A630 |
| Wi-Fi | WCN3990 |
| 内核 | XNU 8796.121.2 |
| 用户空间 | iOS 16.5 |

启动流程：

```text
dipper 启动固件 → edk2-sdm845 UEFI → xnuloader → XNU → iOS 用户空间
```

## 功能状态

当前状态（2026-11-19）。已有分区的短时外设测试与重新分区后的 iOS 启动均有记录；下表外设结果大多来自重新分区之前的测试，原生 Wi-Fi 状态栏、蓝牙、扬声器、动态调频与降低分辨率等较新项目已在近期实机轮次单独验证；重新分区后的完整回归与长期稳定性仍待验。

| 功能 | 状态 |
| --- | --- |
| 系统启动 | 已进入 SpringBoard 桌面 |
| 显示与 GPU | Mesa / freedreno 默认 GMEM 渲染 + `fb_native=2` 零拷贝直扫（`59 FPS`）、动态 CPU/DDR 调频与批量页表映射；渲染绑大核待做 |
| 触摸 | 已可用 |
| 屏幕亮度与锁屏 | 设置及控制中心调光、锁屏与唤醒可用 |
| 音量键 | 已可用（标准 HID Telephony 振铃开关已修复“声音关闭”提示） |
| 手电筒与振动 | 手电筒开关和振动可用；手电筒分档亮度不明显 |
| 电量显示 | 已可用 |
| Wi-Fi | 原生 LQM 事件点亮状态栏信号格；已补充 DMA 屏障、`rx_confused` 恢复与多 AP 回退 |
| Safari | 已通过 Wi-Fi 打开并刷新网页；长时稳定性与网页视频解码待完善 |
| 蓝牙 | 缺省由内核原生 `AppleOLYHAL` 驱动（已移除用户态库）；可开关、搜索、配对耳机/手机；耳机无声 |
| 降低渲染分辨率（可选） | 已能进桌面且更流畅；状态栏已修复，壁纸改为静态图；部分应用闪退，原因未定 |
| 静态壁纸 | 可用（自备图片）；设置里换壁纸无效 |
| 电话与移动数据 | 尚未验证可用 |
| 扬声器声音 | 缺省开启（~31 ms 唤醒、~207 ms 空闲校验），多轮静音/再唤醒稳定出声；音质未调校，功耗未测 |
| 蓝牙音频、麦克风、通话 | 尚未实现 |

详细进度与限制见 [功能状态](docs/STATUS.md)。

## 构建与安装

构建使用 **Linux x86_64**，开发环境为 **Ubuntu 26.04.1 LTS**。本仓库通过固定上游版本和 dipper 适配补丁组织源码。

开始前先看[设备版本、TWRP 与固件准备](docs/install/DEVICE_PREPARATION.md)，确认本机版本和输入来源。

1. [构建教程](docs/build/BUILD.md)与[输入材料](docs/build/INPUTS.md)：固定来源、校验、编译内核和 UEFI。
2. [用户空间与打包](docs/build/USERLAND.md)：提取 IPSW、编译适配程序、生成启动卷和系统镜像。
3. [分区、写入与回退](docs/install/INSTALL.md)：备份、分区、格式化、系统镜像回读与恢复 Android。
4. [配置、重建与启动](docs/install/STARTUP.md)：匹配新 GUID、重建 loader/UEFI、打包和日常 RAM 启动；[外设测试参考](docs/install/EXISTING_INSTALL.md)。

工具入口按用途分类，命令均从仓库根目录执行：

| 目录 | 用途 |
| --- | --- |
| `tools/prepare/` | 固定源码准备、SDK 校验、IPSW 提取 |
| `tools/build/` | 编译加载器、UEFI、用户态，打包镜像与载荷 |
| `tools/partition/` | 分区及 Android 恢复方案生成、回读核验 |
| `tools/tests/` | 主机回归测试 |

完整脚本清单见[工具导航](tools/README.md)。旧实验记录保留当时路径，后续运行请使用当前教程的新路径。

**首次安装需要划出独立的 `darwin` 分区，会清空 Android 用户数据。** 系统持久写入该分区，之后通过临时加载 UEFI 启动。

仓库仅提供源码、补丁和构建工具，**不提供预编译内核或系统镜像**：内核需在你自己的机器上编译（原因见 [GPU 许可说明](docs/legal/GPU_LICENSE.md#分发方式2026-10-31-起)）。系统镜像、专有 SDK、设备固件与备份需自行合法获取。构建及实机测试的详细依据见 [验证记录](docs/validation/VALIDATION.md)。

## 已知问题

- 重负载下桌面仍有卡顿（DPU 零拷贝翻页与渲染线程大核亲和调度尚未实现；降低分辨率可缓解但部分应用会闪退）。
- 蓝牙耳机听不到声音，配对记录重启后丢失，开机约 70 秒后才就绪；只测过一副耳机和一部手机。
- 扬声器开机约 1 分钟（Wi-Fi 就绪后）才有声音，音质未调校；常驻音频的功耗与长时间运行未验收。
- Wi-Fi 长时间高负载稳定性与网页视频解码（如部分场景绿屏/卡顿）仍需进一步观察。
- 基带退出时 `halt port modem` 未归闲，含基带的测试轮次之间仍需完整冷重启设备。
- 存储配置仍来自特定实验布局，不能直接套用到其他设备。本仓库已移除开发设备的分区唯一 GUID，尚不提供通用安装或一键刷机流程。

设备操作前应准备可靠的备份和恢复方案。请先阅读安装教程中的设备配置限制，不要直接使用历史分区参数。

## 参与开发

欢迎提交问题、源码改进和可复现的测试结果。提交时请注明设备、源码版本和测试方法，并区分主机测试与实机结果。

开发过程与 AI 接手入口见[开发流程与现场交接](docs/development/DEVELOPMENT.md)，每轮证据沿用 `work/runs/`，不另复制源码树。

详见 [贡献指南](CONTRIBUTING.md)。请勿在 Issue 或补丁中附带个人数据、设备备份或专有固件。

## 致谢

本项目建立在多个开源项目的工作之上，特别感谢：

- **OOSEX GANG / HackiOS**：XNU 移植基础、加载器、用户空间适配及无线兼容层。
- **Apple 开源项目**：XNU 与相关开放源码。
- **edk2-porting / Renegade Project、TianoCore、SimpleInit**：SDM845 的 UEFI 与启动支持。
- **UniXNU / DarwinBoot**：启动组件与早期移植参考。
- **Linux、Mesa / freedreno、FreeBSD**：硬件驱动、图形与兼容层基础。
- **[Team Win / TWRP 与 dipper 维护者](https://twrp.me/xiaomi/xiaomimi8.html)**：提供分区维护、格式化与镜像回读所用的 Recovery 环境。
- **Theos、LLVM 及相关工具链项目**：构建工具。

完整说明见 [致谢](ACKNOWLEDGEMENTS.md) 与 [第三方来源](THIRD_PARTY_NOTICES.md)。

## 许可证

各部分代码遵循其对应许可证，第三方版权声明予以保留。本项目并非整体采用单一 MIT 许可证；具体适用范围见 [许可说明](LICENSE.md) 和 [LICENSES](../../LICENSES)。其他文件的许可范围见 [许可证说明](docs/legal/LICENSE_REVIEW.md)。

本项目为独立研究项目，与设备厂商、系统厂商及所参考项目不存在官方隶属关系。

全部文档按用途分类，见 [文档导航](docs/README.md)。
