# 验证记录

## 2026-10-27 历史离线回放

补丁回放记录日期：2026-10-27。范围为主机文件级验证，不包含上游完整构建或实机验证。

- XNU recorded baseline matches Apple source + pinned HackiOS redwood.patch/files byte-for-byte.
- xnu-mi8: replay PASS; 34 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- hackios-kernel: replay PASS; 23 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- hackios-userland: replay PASS; 7 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- edk2-sdm845: replay PASS; 5 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- simpleinit: replay PASS; 1 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- unixnu: replay PASS; 1 changed/new/deleted text files match exported text (loader device GUID intentionally removed).

未验证：全新联网获取、完整编译、用户空间材料准备、启动打包和实机运行。

### 当时的文件与脚本检查

- 6 组补丁回放结果：71 个文件 SHA256 与导出清单一致。
- Python 语法解析、Shell `bash -n`、Markdown 本地链接检查通过。
- 全部发布文件均可解码为 UTF-8 文本，无符号链接、NUL 字节或镜像/二进制产物扩展名。
- 本机分区 GUID 与主机绝对路径的指定模式扫描无命中；这不等同于完整人工隐私审计。
- 获取脚本默认仅显示计划，已执行验证；联网 `--prepare` 未执行。
- `SHA256SUMS` 提供仓库文件内容校验，不是数字签名或授权证明。

## 2026-10-30 独立目录复现

本轮已完成固定源码获取、构建修复及主机产物生成，详细范围见 [复现记录](REPRODUCTION.md)。

- 更新后的 6 组补丁在第二个空目录完整回放，72 个源码文件 SHA256 匹配；`hackios-userland` 现为 8 个文件。
- 内核显式 `build` 目标、ath10k、Mesa、用户空间、xnuloader、UEFI 和 darwin 镜像生成通过；默认 `all` 的附加检查仍失败。
- SDK 8,867 个文件/链接/模式的 Git tree 校验通过；错误 SDK 和 IPSW 摘要均被拒绝。
- 已有源码树、已有 darwin 输出、UEFI `--boot` 参数均被入口拒绝。
- UEFI 中 USB 引导载荷结构和内容检查通过；APFS 内 4 项程序/配置与本轮构建输入一致。
- 新增脚本语法、公开文本本地链接、源码与仓库校验清单已检查。
- 此主机阶段未操作设备；随后进行了已有分区实机验证，结果如下。

## 同日已有分区实机验证

- GPT 主、备份及系统区 SHA256 核验通过，复用现有系统，未分区/刷写。
- 第一轮暴露 launchd 拒绝组可写目录与配置；固定 umask 并增加 APFS 权限检查后，旧镜像被构建入口拒绝。
- 第二轮新构建进入 SpringBoard；设置界面前台、触摸与 GPU 绘制记录通过，取得部分原生 framebuffer 桌面图像。
- 后续 Wi-Fi 测试定位并修复 44 MiB 连续内存申请时机，补齐已核验的 WCN3990 特性描述文件；缺少文件的载荷在主机负向检查中被拒绝。
- 修复后设备日志确认驱动启动返回 0、en0 已连接且取得地址、Wi-Fi 网络路径可用；持有人确认 Safari 能打开并刷新网页。测试结束后完整重启回 Android 并确认启动完成。
- 本次 Wi-Fi 修复涉及的补丁重新从固定基线回放，更新后的 6 组源码清单共 74 个文件全部匹配；内核和 ath10k 重建通过。此结果不覆盖长期稳定性或首次安装。
- 外设测试发现并修复 DSI 亮度命令缓冲区超过 32 位地址范围的问题；新内核实机分配 4 GiB 以下的完整 16 KiB 页，所采亮度写入错误为 0。持有人确认两处亮度控制与锁屏唤醒正常。
- 震动、手电筒开关、音量键/音量条、电量、壁纸、小组件及 Wi-Fi 网页回归由持有人确认；退出日志确认马达和手电筒均关闭。手电筒分档亮度不明显，完整音频等未覆盖项不计通过。
- 新增配置、固件来源和临时启动流程见 [已有分区测试](../install/EXISTING_INSTALL.md)，证据见 [设备记录](device-validation-20261030.json)。

## 同日首次安装：Android GPT 恢复

持有人执行恢复脚本后，主备 GPT CRC、条目一致性及与已核验历史布局的比对通过。重新进入 TWRP 后再次回读，两份 GPT 字节均未变，内核识别 userdata 121425080320 字节（约 113.09 GiB），darwin 节点不存在。该轮旧文件系统自动挂载，当时尚未重建数据文件系统；后续格式化验收如下，不能将 GPT 单独通过计为完整首次安装通过。方案与阶段见 [任务记录](../development/FIRST_INSTALL.md)，私有证据保留在 work/runs/20261030-first-install-02/、03/。

## Android GPT 通用恢复工具的主机验证

`tools/restore-android-layout.py` 的 17 项合成测试通过，覆盖 CRC/摘要错误、主备不一致、分区重叠/越界、其他分区变化、属性不支持、注入参数、重复 GUID、输出覆盖和旧内核容量拒绝；生成脚本通过 sh 语法检查。使用本机第 01/03 轮已保存的 GPT 与容量进行离线回放通过，证据在 work/runs/20261030-restore-tool-01/。本轮没有连接或修改手机；新增保护后的生成脚本真机执行待验。

## Format Data 后 Android 恢复验收

持有人确认完成 Format Data 和 Android 初始化，设置系统固件约 9G；提供的 ADB 输出为 sys.boot_completed=1，/data 总量 116193656 KiB、可用 114887932 KiB。与此前代理核验的恢复后 GPT 和内核容量合并，Android 恢复阶段通过。此轮命令输出由持有人提供，root 未核验；没有重新划分 darwin 或写入 iOS 镜像。记录在 work/runs/20261030-first-install-04/。

## 重新分区后的 Android 验收

第 05/06 轮代理实读确认新主备 GPT 与方案一致，前 20 项未变；重进 Recovery 后 userdata 为 95655297024 字节、darwin 为 25769795584 字节。持有人随后 Format Data 并启动 Android，第 07 轮提供 sys.boot_completed=1、/data 总量 91422752 KiB、可用 90118260 KiB 的输出，重新分区阶段通过。第 07 轮为持有人提供的 ADB 证据，不宣称代理独立复读。当时镜像写入和 iOS 启动待验；后续见第 09/10 轮。

## 通用 darwin 分区工具

14 项分区工具测试通过，包含 10 个假设备 shell 拒绝子场景（身份、root、工具/GPT 摘要、挂载/卸载失败、holder、swap、已存在节点及确认参数）；17 项恢复工具回归通过。没有访问真实设备。使用第 05 轮分区前 GPT 生成的完整条目表，与已执行成功的预期条目逐字节相同；第 06 轮 GPT 与已记录节点容量通过验收。回放资料在 work/runs/20261030-partition-tool-01/，新生成脚本真机执行仍未单独验证。

## 新分区 GUID 的启动产物重建

第 08 轮按仓库教程构建 loader/UEFI，退出 0；仅更新本机 loader GUID，内核边界与之前一致。ARM64 EFI、GUID、压缩固件卷内完整 loader、BootShim+FD+USB XNUP、DTB、74 项适配源码对应关系验证通过。新 UEFI SHA256 为 `ad209c3caf29a474b76acb841067100714667665260e7df3171c7a0a8488238e`，loader 为 `a5643b7e45e539f58c843d6aacaedf08feb5a44c7c0b1d114b25a726bbb96d4a`。内核及两个用户态 APFS 沿用上次实机已验摘要；现有 darwin.img 完整摘要与固定输入一致。候选及证据在 work/runs/20261030-first-install-08/。此轮仅主机通过；后续设备结果见第 09/10 轮。

## 新分区镜像回读

第 09 轮在 TWRP 中确认 darwin 未挂载，主备 GPT 与已验证新布局相同，GUID/容量匹配候选配置。实际回读前 8365539328 字节，完整字节计数、退出码与 SHA256 通过；摘要为 `9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560`，与同期重新计算的主机镜像一致。未取得 fastboot 操作日志，成功依据为实时回读。当时新分区 iOS 启动待验；后续结果见第 10 轮。

## 第 10 轮：新分区 iOS 启动成功

代理实时 fastboot 查询确认 product 为 xnuloader；使用第 08 轮 300 秒候选，存储写入关闭。持有人随后明确报告“成功进入ios了 没问题”。据此确认本次恢复、重新分区、镜像回读、配置匹配及新 loader/UEFI 启动链已走通。boot.log 仅含 oem run 的 OKAY，不是内核启动日志；本轮未补采详细启动日志。外设逐项回归、限时退出后的完整 Android 重启仍待验，不能继承旧布局的全部功能验收。原始记录在 work/runs/20261030-first-install-10/。

教程已分为[分区、写入与回退](../install/INSTALL.md)和[配置、重建与启动](../install/STARTUP.md)，独立恢复说明整合为前者的回退章节。

## 2026-10-31 主线合并前检查

审查 test/first-install 相对 main 的工具与文档变更，17 项恢复测试及 14 项分区测试通过；151 个本地 Markdown 链接（含章节锚点）、SHA256SUMS 和 git diff --check 通过。分支未改变公共适配补丁、上游锁定或源码清单，未跟踪 work/local 私人文件。本轮不操作手机、不重新编译；保留通用生成脚本单独实机执行、逐项外设回归及退出后 Android 验收的待验边界。合并仅在本地进行，不推送。

## 2026-10-31 tools 分类迁移

维护分支 chore/tools-layout 将 11 个工具移至 prepare/build/partition/tests，未改变分区算法、设备保护或构建参数。旧历史记录中的 tools 根路径代表当时实际执行命令；当前入口见[工具导航](../../tools/README.md)。

17 项恢复测试和 14 项分区测试通过；Python AST 与 Bash 语法、6 个仓库根目录解析、6 个 CLI 帮助入口、从 /tmp 执行只读源码准备计划通过。UEFI 非法参数和用户态 PREBUILT 拒绝检查通过，11 个迁移文件逐项对照仅含预期路径变化。170 个本地文档链接及锚点检查通过。未运行完整编译、未改动已有源码/镜像或历史轮次、未操作设备；这些结果不新增实机功能结论。

## 2026-10-31 设备准备教程

从第 01/02 轮记录确认 Android 10、MIUI V12.5.2.0.QEACNXM 和 Recovery 3.7.0_9-0；未将历史读取标为实时版本。核对 Team Win dipper 设备及下载页面，补 GPU 固件双端校验示例和输入归档说明。新增命令仅做 Bash 语法检查，未在手机复测；当时刷入的 TWRP 文件摘要、来源和实际目标仍待核验。

## 2026-10-31 Android root 固件提取实测

持有人授权后，代理实时确认 dipper、sys.boot_completed=1、Android 10、MIUI V12.5.2.0.QEACNXM，以及 su uid=0。直接使用设备准备教程的提取命令块，选择 MODE=root；4 个 A630 固件均提取成功，手机端前后与主机 SHA256 一致，固定摘要全部通过，与既有 work/hackios/fw-gpu/ 文件逐字节相同。新文件仅保存在 work/runs/20261031-firmware-01/gpu/，命令、版本、输出、比对 JSON 和摘要随轮次保存。未覆盖既有输入、未写块设备、未重新构建。TWRP 与普通无 root 提取路线本轮未执行；TWRP 镜像来源/刷写证据的待补项不变。

## 性能源码导出与主机重建（2026-11-05）

证据目录：`work/runs/20261105-export-01/`，最终核验在其中 `revision-2/`。内容变化为 8 个 XNU 文件和 4 个用户态文件；其余四个组件仅更新补丁格式，旧/新补丁在相同基线上重放的完整文件树与模式一致（`format-equivalence.json`）。

全量清扫 `revision-2/sweep.json` 比较锁定基线加候选与 work 的文件内容和可执行位，纳入两个遗漏的内核依赖后，`sweep-after.json` 不再有未解释源码差异。既有 loader 本机字段、wifi 服务复制和 edk2 豁免保留。辅助 krb5 子模块缺少锁定对象的既知边界未消除。导出工具对嵌套 XNU 树存在清单外差异漏报，本轮以独立清扫补足，工具修复仍待完成。

干净重放、隐私 error 检查和 patchtool 离线自测 32/32 通过。历史扫描 warning 仍保留，新增源码差异未引入任务编号、协作署名或私人路径。干净树内核 `build` 及 rwtouch、libredwood-gl 目标构建通过。用户态与当前 work 源码独立重建的产物逐字相同；内核原始二进制受源码路径和构建时间影响，比较细节见 `revision-2/kernel-comparison.json` 及归一化重建记录。统一路径映射和构建日期、去掉 UBSan 诊断路径后，915 个目标文件的代码段全部逐字一致；14 个字符串段仅顺序不同、字符串多重集合相同，其余非调试段相同（`revision-2/object-comparison.json`）。链接产物仍因字符串布局及重定位等差异不逐字相同，不宣称内核二进制完全一致。旧 work 产物保留，未覆盖。

以下表覆盖本次引入的启动参数、相关既有控制项与 TUNABLE 默认值。完整源码差异核对见 `revision-2/default-review.json`。

| 参数或开关 | 代码默认值和启用条件 | 默认行为与边界 |
|---|---|---|
| `thermgov` | 缺失或 0 关闭；目标范围 55–69 °C | 不启动主动降档；启用后仅降低大核请求档位，不提高频率或改硬件热保护 |
| `mi8_cpufreq` / `mi8_cpufreq_big` | 既有显式频率参数；任一个出现就拒绝启用 thermgov | thermgov 不接管显式请求；本次未更改其既有默认策略 |
| `ffix` | 用户态和内核均缺省 1；仅接受单字符 0–9，其他显式值归 0 | bit0 开启静止 fallback 图像的间隔检查优化；这是默认功能变化，不是默认关闭的仪表 |
| `ffix` bit1（2） | 默认关 | IOSurface 包装/缓存路径；显式启用也会启动包装统计报告线程，不依赖 fprof 非零 |
| `ffix` bit2（4） | 默认关 | 通道重排共享导入，依赖同步更新的 gl_osmesa 和 redwood_gl.h |
| `ffix` bit3（8） | 默认关 | 渲染目标初始内容的 GPU 拷贝及失败回退 |
| `fprof` | 缺省 0；有效非零间隔 200–10000 微秒 | 不启动用户态采样或内核 surface 剖析报告；无效显式值会输出禁用原因 |
| `perfprof` | 缺失或非 1 不启动；`perfprof_enabled` 初始 0 | 不启动采样器及附属时钟线程；调度切换挂钩每次仍有一次原子读和一次判断 |
| `perfprof_hz` | 1000 Hz，启用后限制在 100–2000 | 只有 perfprof=1 才读取和使用 |
| `mi8_cpuclk` | 既有独立入口缺失/0 不启动；perfprof 附属入口默认 10 秒，限制 1–3600 秒 | perfprof=1 时即使不指定此参数也启动附属时钟线程；显式非零还可触发既有独立入口 |
| `touch_lat` | 既有 `TUNABLE` 默认 0；用户态延迟日志开关也默认 0 | 延迟日志默认关闭 |
| `taskload` / `cpuload` | 既有参数缺失或 0 不启动，非零为报告间隔毫秒 | 默认不启动相应报告线程 |
| `gpu_keep` / `surftrace` / `surf_clear` | 相关既有 `TUNABLE` 分别为 1 / 24 / 1 | 本次未新增 TUNABLE 声明；不能把既有 surface 跟踪默认 24 说成系统零日志 |

未加剖析参数时不启动上述新增采样器，也不产生其周期采样日志；这不等于零开销或系统零日志。调度路径仍有原子读/判断，其他路径保留条件分支与静态存储，ffix bit0 默认执行功能逻辑。`redwood_battery_profile` 只读已发布软件缓存，不启动电池通道或调用固件。`rwtouch mark`、`mem` 是显式脚本步骤，不是启动参数；`mem` 未经设备验证。
