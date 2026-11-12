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

## 嵌套组件导出回归（2026-11-05）

修复 patchtool 将父组件误作排除范围、漏报子组件清单外变更的问题。新增合成回归覆盖修改、新增、删除、已登记路径及遍历顺序，确认父树不重复报告子树文件；33/33 测试通过，旧实现无法通过新增回归。当前源码重新导出的六个补丁和清单与既有版本字节相同，仅保留 12 个已知清单外项，未写回补丁。证据在 `work/runs/20261106-bootargs-01/`；本次没有新增内核构建或设备验证。

## dipper 默认配置与短载荷（2026-11-06）

四个 XNU 文件实现集中默认值、设备树平台筛选、启动来源日志及 kern.bootargs 完整输出。没有修改 loader、驱动测量逻辑、ffix 或温控算法。实际 C 解析器和 ARM 默认值代码经主机 DT 桩编译测试：315 项断言通过，包括旧完整参数与短 bench 的输出字节及返回值一致、实际最坏前缀、非 dipper 空/完整参数不变、显式 0/其他值和重复参数、daily 无测量参数、日志身份脱敏、缓存边界，以及通用打包工具的 Wi-Fi/外设组合。此为主机模拟，不是设备启动证明。

证据在 `work/runs/20261106-bootargs-01/revision-1/`。固定 Git 对象仅通过本地 file 协议准备干净树；patchtool 重放通过，干净内核 build 退出 0。首次编译的 snprintf 声明错误已修复，失败日志保留；完整 all 仍不在此次通过范围。候选导出与最终写回字节一致，其他五组件补丁不变，许可清单保留既有边界。

`work/runs/20261106-bootargs-01/S-slim/` 包含新内核和 172 字节 bench cmdline；原 root.apfs、flashboot、loader、UEFI 字节复用，内嵌 rc.jobs 与旧基准载荷字节一致。现有 bench 工具的只读载荷校验接受该外部目录，并验证容器中的内核、ramdisk、cmdline。加 80 字节保守前缀为 252 字节，严格小于 600 的可追加余量为 347 字节。daily 为 87 字节，无测量开关或自动返回期限。

设备冒烟（2026-11-09，daily 载荷）：进入桌面，持有人手动使用；launchd 打印的 `kern.bootargs` 展开值与旧完整配置逐项一致（含 `wifi_mac`，此处不转录），无 panic；Wi-Fi 联网后 Safari 能打开页面。`bootcfg` 行没有出现在 loader 日志环里（早期 `printf` 未被收集），`def`/`arg` 来源标注因此没有在设备上看到，有效值依据 `kern.bootargs`。bench 载荷 S-slim 的自动场景冒烟未做，长时间稳定性未验证。

## 降低渲染分辨率与状态栏（2026-11-10）

**崩溃与修复。** 单独 `fbscale=2` 在启动约 14 秒、首批画面时内核崩溃（数据越界写，符号化落在 `IOMobileFramebuffer::drawRows`）：缩放行缓冲只按源图宽度分配，而输出按面板宽度写，源图比面板窄（750 < 1080/1125）时写穿；原来源图宽于面板，所以没有暴露。行缓冲每半改为按 `max(源图宽, 面板宽)` 分配。修复后 `fbscale=2` 启动正常。

**屏幕类别（MobileGestalt，设备上读取）。** 1125×2436 @3x：`main-screen-class` = 15；750×1624 @2x：无（`PUIProgressWindow` 报 -1）；828×1792 @2x（iPhone XR 规格）：同样 -1，状态栏仍是红条、壁纸仍黑，所以换成别的真实规格不是出路。机型身份仍为 iPhone10,3。红条 `rdar:45025538` 和黑壁纸都是该类别查不到的结果。

**状态栏。** SpringBoard 库把 `_UIStatusBarVisualProvider_Fallback` 换成 `_UIStatusBarVisualProvider_Split1125`（复制 35 个类方法，并让后备类的 `alloc` 创建后者的实例）。做法参考上游项目公开文档中的描述，代码为自写；类名在本系统中核实存在。设备上红条消失、状态栏正常（持有人确认）。

**DPU 放大（`fb_dpu=1`）。** 翻页缓冲用 750×1624（行距 3008），QSEED3 源尺寸由常量改为按缓冲取值。每帧拷贝耗时（调用线程，设备日志）中位数：处理器放大 6471 µs（p90 8551），DPU 放大 520 µs（p90 571）。画面正常，无 panic，持有人感到明显更流畅。

**帧统计。** 只统计画面在动的秒（每秒 ≥30 帧）：全分辨率（该场次壁纸每 2 分钟显示/隐藏交替）慢帧（>18 ms）25.1%、p95 28.3 ms、帧率中位 51；`fbscale=2` 处理器放大 17.6%、24.8 ms、54；`fbscale=2` + DPU 12.4%、21.8 ms、58。三者来自不同场次、操作不同、时长不同（DPU 场次仅 75 个活动秒），带测量开关，不是严格对照；`fbscale` 场次壁纸是黑的，壁纸本身也影响结果：全分辨率同一场次里，隐藏壁纸的段慢帧约 22.8%、显示约 30.6%。

**其他。** 测量开关（`perfprof` 等）开启的那一次，浏览器打不开页面；单独 `fbscale=2`（无测量开关）和 `S-daily` 均能打开，所以不是 `fbscale` 引起；测量开关的影响未再单独复现。

**静态壁纸（2026-11-10）。** 先把渐变层加在壁纸窗口的最下面，看不到（被窗口里的黑色盖住）；改为加在最上面后，持有人确认看到渐变。再改成读 `/redwood/etc/wallpaper.jpg`（持有人提供的 750×1624 JPEG，71 KB），设备日志确认读到图片并盖上（`a still picture is over the wallpaper window`），无 panic。想让壁纸进程相信屏幕是 iPhone X 的尝试没有成功：在 PosterBoard 和几个壁纸扩展里替换 MobileGestalt 的查询函数，被替换的两个函数在这些进程里一次都没有被调用（调用发生在共享缓存内部，替换看不到），已放弃，该实验代码不在仓库中。显示驱动日志显示查屏幕尺寸的是独立进程 `MobileGestaltHelper`（选择器 8），可作为以后的线索，未试。

**应用闪退与 PosterBoard。** 降分辨率的启动里，设置在一次启动中闪退 5 次（SIGBUS/SIGSEGV），信息在较早几次启动中闪退（累计 12 次）；原分辨率的 S-daily 日志里没有，但那次几乎没打开这些应用；后来的原分辨率对照见下一段。PosterBoard 在两次启动中出现过 `NSInvalidArgumentException`（字典里插入 nil）并被系统重启，其中一次启动没有我们的替换库，原因未定。

**原分辨率 + 静态壁纸（`still_wall=1`）。** 缓冲为 1125×2436，静态图已盖上，无 panic；持有人使用后确认基本没有问题。日志中打开了设置、信息、日历、Spotlight 各一次，没有应用闪退；Wi-Fi 联网（接入点 5 GHz）。这是对上一节闪退的对照：降分辨率的启动里设置、信息反复闪退，原分辨率下各打开一次没有闪退，所以闪退更可能和降分辨率有关；样本很小（各一次），不是定论。同一次启动里 PosterBoard 仍出现一次 `NSInvalidArgumentException` 退出并被系统重启，说明那个问题和降分辨率无关。

**未验证。** 最终提交内容已在干净树编译通过并重放通过。该配置下 Wi-Fi、触摸、按键的完整回归、长时间稳定性、应用在降分辨率下闪退的原因均未验证；静态壁纸是否降低处理器占用没有测量。

## 持久保存首测（2026-11-10）

载荷复用已验证的 daily 内核与根镜像，只改启动参数；用同一参数重建 daily 载荷与原文件逐字节一致。首轮 `ufs_write=1 var_store=1 var_save_ms=120000 loader_return_after=240`：loader 确认 darwin 块 2042368 起可写，内核报告尚无存档；进入桌面后持有人挪动图标、建文件夹、改一个设置开关，240 秒后内核返回，loader 汇总 `45 writes into darwin, 177827840 bytes, read back the same; 0 refused`。

回到 TWRP 只读检查：槽 0 魔数正确，generation 1，182012768 字节、16904 项，头校验和整份存档 CRC32 均正确；槽 1 为空（首次保存）。完整重启后只加 `var_store=1` 读回：内核日志 `slot 0: generation 1 ... 16904 entries, 182012768 bytes`，恢复 6926 个目录、2851 个文件（179206807 字节）和 2 个链接；持有人确认图标、文件夹和设置开关都保留。只读轮的 `cannot be written` 是预期提示。

边界：内核返回后取到的内核日志只有开头 32 KB，看不到 `saver has finished` 一行，以 loader 汇总和存档校验为准。仅测了一次存、一次读；第二次保存写入槽 1、周期保存、长按电源丢失量、保存时的数据库一致性、存档增长和耗时都未测。存档约 174 MB，远大于较早实验的 48 MB，原因（内容不同）未查。主机部分：打包工具新增 `--persist`，主机测试 327 项断言通过。

## 蓝牙芯片的 UART 链路（2026-11-10）

新增诊断驱动 `bsd/dev/mi8_bt.c`，只在 `bt=N` 时运行，默认关闭，N 为执行到第几档。小米 8 的蓝牙是高通 WCN3990（与 Wi-Fi 同一颗），经 QUP 串口引擎 SE6（设备树 `hsuart0`，引脚 45 CTS、46 RTS、47 TX、48 RX）通信。三轮设备运行都在 daily 参数上追加 `bt=N loader_return_after=…`，均正常返回，无 panic，不写存储。

- `bt=1/2`（只读摸底、再开引擎时钟）：SE6 的固件协议为 UART（版本 10），FIFO 接口开启（与触摸用的 I2C 引擎相反），DMA 接口存在，FIFO 深度各 32 字；四个引脚此时仍是普通 GPIO。
- `bt=3`：引擎时钟源切到 GPLL0 偶数输出除以 3（100 MHz），串口时钟分频 27（约 115740 baud），FIFO 模式 8N1、无流控；经引擎自带的 TX→RX 回环发 12 字节，收到的与发出的一致。
- `bt=4`（等待 `bt_delay` 秒，默认 60，让 Wi-Fi 启动先用完 RPMh 通道）：通过 RPMh 请求设备树里蓝牙节点的五路供电（五路均返回完成），引脚切到 `qup6`，回环 12 字节用时 1142 µs（115200 baud 的理论值 1042 µs，多出部分为轮询开销），关流控发上电脉冲 0xFC，100 ms 后开流控；`HCI Reset` 收到 Command Complete 状态 0（`04 0e 04 01 03 0c 00`）；`读本地版本` 返回 HCI 版本 8、LMP 版本 8、厂商 29（Qualcomm）、LMP 子版本 `0x2be`。

边界：只证明了内核到芯片的 HCI 命令链路（115200 baud，芯片未下载固件）。尚未做：固件（rampatch 与 NVM）下载、提高波特率、扫描或连接、iOS 侧的蓝牙服务和蓝牙音频；设置里的蓝牙开关目前不能用。波特率只做了回环耗时的间接核对，没有用外部仪器测量。主机侧：补丁干净重放通过，隐私扫描只有既有的警告。

**固件下载（`bt=5`，同日）。** 固件放进启动卷的 `fw/`（`userland/build.sh` 从 `fw-bt/` 取），内核按 Linux 的 `btqca.c` 流程在 115200 baud 下操作：读 SoC 版本（厂商命令 `0xFC00` 子命令 `0x19`）得产品号 0xa、SoC 号 0x40010214、ROM 0x201、补丁版本 0x1，与固件文件的 ROM 0x21 一致；补丁 `crbtfw21.tlv`（222988 字节）分 918 段发出，用时约 20.7 s，只有最后一段有应答（头部下载模式 3）；NVM `crnv21.bin` 分 19 段，每段有应答，用时 438 ms，其 HCI 传输标签里的波特率字节原为 0x11（3.2 Mbaud），发送前改为 0（115200），其余未改。下载后芯片进入带内睡眠协议（NVM 自带启用位）：不做握手直接发命令时芯片只重复 `0xFD`；实现最小握手（发命令前发 `0xFD` 等 `0xFC`，收到 `0xFD` 回 `0xFC`）后，`HCI Reset` 成功，`读本地版本` 由下载前的 HCI 版本 8 变为 9（蓝牙 5.0），厂商 29，LMP 子版本仍为 0x2be，SoC 版本里的补丁版本由 0x1 变为 0x2。无 panic。

边界：本段在 115200 baud；睡眠协议只做了唤醒应答，主机从不让芯片睡眠，也没有休眠恢复的测试；首次连续运行中出现过一次读取错位（清空接收 FIFO 时丢掉半个包），已改为保留队列。当时未做扫描、连接、蓝牙音频，iOS 里的蓝牙开关仍不可用；这一状态已在下一节（`bt=7`）改变。

**提高波特率（`bt=6`，同日）。** 3.2 Mbaud 的串口时钟要 32 × 3.2 MHz = 102.4 MHz：引擎时钟源仍是 GPLL0 偶数输出（300 MHz），改用分数分频 M/N = 128/375（寄存器 M=128，N 取 ~(375−128)，D 取 ~375，模式为双沿；读回 `0x00102600`，根切换完成），串口分频 1。流程按 Linux 的 `qca_set_speed`：读 SoC 版本、核对 ROM 后，在 115200 下发厂商命令 `0xFC48`（码 0x11），等 10 ms，主机停引擎、换时钟、重设引擎、开流控、重启接收；ROM 的厂商事件按预期未被收到（不要求），随后 `HCI Reset` 在 3.2 Mbaud 下得到应答。补丁 222988 字节（918 段）用时 969 ms（115200 下 20.7 s），NVM 19 段 20 ms；NVM 的波特率标签保持原值 0x11，芯片留在 3.2 Mbaud，随后 `HCI Reset`、读版本（HCI 版本 8→9、补丁版本 1→2）和 SoC 版本都在 3.2 Mbaud 下通过；无 panic、无 REFUSED。同一流程共跑 3 次：第 1 次把 NVM 标签改成 0 导致芯片在 NVM 后回到 115200、主机仍在 3.2 M 而读到乱码（因此 `bt=6` 不改标签），其后两次通过（其中最后一次为合入的最终内核）。边界：未用仪器测量波特率，只以 969 ms 的下载耗时（理论线速约 0.7 s 加命令开销）间接核对；未测长时间或大流量稳定性，也没有降速、休眠恢复或重新提速的处理。

## 音频 DSP：启动、APR 握手与 QUAT MI2S 端口（2026-11-11）

条件：小米 8，`fastboot boot` 的内存启动（不写存储），内核含 `mi8rp_step=8..10`；参数为默认短参数加无线关闭、`gpu=0 fts=0 buttons=0`（内核日志返回后只留最后 32 KB，GPU 日志会把早期行挤掉）、限时 90 秒；每轮之间完整重启。ADSP 固件取自手机自己的 modem 分区，没有额外打包。

- **步骤 8（启动）**：TrustZone 接受 ADSP 签名（PAS 镜像 1）；30 MB 镜像写入保留内存并读回，0 字差异；放出复位后 ADSP 的 SMP2P 项约 13 ms 出现，`slave-kernel` 在约 30 ms 报告运行；停止位发出后约 10 ms 应答，TrustZone 关闭成功，无 panic。
- **步骤 9（GLINK 与 APR）**：`apr_audio_svc` 通道双向打开（本地 2、远端 5）；q6core `state=1`；服务版本 AFE=4 为 0x2、ASM=7 为 0x1、ADM=8 为 0x2，共解析 8 个服务条目，没有被拒绝的包；通道关闭正常，随后停止与 TrustZone 关闭成功。设备上暴露并已修复两点：ADSP 在该通道上一次给出 65 个以上接收缓冲（原表只有 64 项）；ADSP 的应答头是 8 个字（头长字段 8，32 字节），而我们发出的请求头是 5 个字（20 字节），应答必须按头长字段取负载。
- **步骤 10（AFE，Quaternary MI2S 端口 0x1006）**：先只读放大器相关引脚（复位 GPIO76、型号脚 GPIO87、中断 GPIO30 均读到低电平，功放在复位中，全程未写这些引脚、未碰 I2C）；GPIO58 至 61 切到 `qua_mi2s` 功能，读回一致，GPIO57（MCLK）未动；1.536 MHz 时钟开启、I2S 配置（16 位、SD0、立体声、ADSP 为主、48 kHz）、端口启动，ADSP 回报状态均为 0；保持 2 秒后停止、时钟关闭，状态均为 0，引脚还原；随后通道关闭、停止与 TrustZone 关闭成功，无 panic。首个版本在结束时对永久 IO 映射调用 `ml_io_unmap` 引起内核断言，已改为不解除（见下节），修复后同一流程复验通过。

当时边界：**步骤 8–10 没有声音**（后续进展见下文）。时钟与数据线的物理波形没有测量手段（无示波器），ADSP 回报与引脚读回只证明控制面，不证明引脚上有正确信号。共享内存、SMMU、ASM/ADM、功放（TAS2557）、iOS 声音接入均未做。默认参数（GPU 开启）下加步骤 9/10 后的桌面回归没有测；与 Wi-Fi/modem 同时运行未测；ADSP 停止后再启动未测。步骤 8 至 10 共 10 轮中有 4 轮 loader 结果为 `hung`（全部出现在步骤 9 载荷的轮次，成败都有），日志均可取回、设备可冷重启恢复，原因未查明。

## AFE 引脚映射收尾（2026-11-11）

`ml_io_map` 返回 io_submap 内的永久映射，可能包含 16 KB 页内偏移，不能交给 `ml_io_unmap`。AFE 诊断保留既有修复：不再解除 TLMM 映射，使用静态引脚表按需映射并复用。旧 ADSP 大区域的可解除映射及收尾保持原样。

本轮修复源码与此前设备验证版本逐字节一致；主机静态检查 3/3、音频回归 72727/72727、状态回归 101/101、增量内核构建及干净补丁重放通过。重打包后的内核、载荷和固定输入与既有设备候选摘要一致。本轮未操作设备，不新增声音输出、物理波形或长期稳定性结论。

## iOS 蓝牙（2026-11-11）

`bt=7` 在 `bt=6` 的固件下载之后把芯片交给 iOS：内核线程持续读串口、应答带内睡眠字节，把 H4 包放进队列。新增的 IOKit 垫片 `iokit/Kernel/RedwoodBT.cpp` 提供 `bluetoothd` 要找的服务 `AppleBTHci`（选择子 0 打开、1 关闭、2 写、3 读、4 传输复位，属性 `pipes`），以及 `AppleBTMgmt` 和带 `local-mac-address` 的 `bluetooth` 节点。另有内核控制套接字 `com.apple.uart.bluetooth`，`BlueTool` 经它运行启动脚本。用户态由 `userland/build.sh BT=1` 加入两个作业（`bluetoothd` 的环境 `BT_HCI_TRANSPORT=APPLEBT`）、注入库 `inject_bt.c`（MobileGestalt 的 Wi-Fi 厂商答 Murata，`BlueTool` 据此选启动脚本）、`/etc/bluetool` 下的占位固件文件（`init` 绑定过去）。

iOS 16.5 的 iPhone X 版本按博通 BCM4357 写成，桥接层为此做了几处适配，都基于设备上的实际应答和对 `bluetoothd` 的反汇编：
- 读本地版本的应答把厂商号和 LMP 子版本改成博通的 15 / `0x420e`，`BlueTool` 和 `bluetoothd` 都靠它选固件条目。
- 读支持命令的掩码补上 Write/Read Default Erroneous Data Reporting 两位，这两条命令由内核本地应答。
- 博通厂商命令（OGF 0x3f）不发给芯片。`BlueTool` 的回成功；`bluetoothd` 的回"未知命令"，后接子操作码和一个 0。原因：只回状态时，它的多路广播解析器断言失败（`bcm_vsc.c:642`），原始数据解析器丢掉不足 2 字节的应答，同步等待 15 秒后判定芯片崩溃。
- `LE Read Periodic Advertiser List Size`（`0x204a`）由内核本地应答 0。芯片收到这条扩展广播命令后，会以 0x0c 拒绝传统广播命令（如读广播功率）。
- 扫描、广播、建连三条命令里的本机地址类型从随机改为公共。`bluetoothd` 在 iPhone 上用厂商命令设置随机地址，这颗芯片没有设置过，会以 0x12 拒绝开扫描。
- 这些服务在内核线程开始时就挂出来；芯片就绪前，`BlueTool` 连串口和 `bluetoothd` 打开 HCI 时会等待（最多 3 分钟，可被信号打断）。此前开机早期 `bluetoothd` 报"没有蓝牙"，"设置"会一直显示"不可用"。

设备轮次：日常参数加 `wifi_mac=… bt=7`，每轮限时 6–25 分钟，均正常返回或由持有人强制重启，无 panic，不写存储。定位上面每个问题时各跑了一轮，最后两轮为合入前的内核：
- 第一轮：芯片约开机 70 秒就绪，`bluetoothd` 进入 `STACK_READY`、电源状态"开"。收到周围设备的 BLE 广播报告；"设置"里传统蓝牙查询搜到一副 OPPO Enco Free4 耳机。随后安全简易配对、链路密钥、认证、加密都成功（状态 0），SDP 经 L2CAP 查到 AVRCP、A2DP、免提、GATT 服务，免提 SLC 建立，A2DP 媒体通道打开。持有人确认耳机已连接。
- 第二轮：服务提前挂出后，"设置"在芯片就绪前打开，蓝牙先显示关闭，就绪后自动变为打开，没有再出现"不可用"。持有人两次关开蓝牙均正常，日志记录电源状态 1→0→1 两次，每次耳机都自动重连（一次耳机主动连回，一次手机去连），免提和 A2DP 通道重新打开。开机时 `BlueTool` 的第一次启动脚本因等芯片超时了一次，`bluetoothd` 随后自己恢复，不影响结果。
- 第三轮（`tools/build/build-userland.sh` 构建入口产出的 `root.apfs` 与启动卷，不再用手工拼装的镜像）：服务提前挂出，芯片就绪，`bluetoothd` 没有退出。持有人用另一部手机连接小米 8，芯片事件依次为连接完成（状态 0）、安全简易配对完成（状态 0）、加密开启，之后没有断开。标准构建不打开 `bluetoothd` 的详细日志，所以这一轮只有内核侧事件，没有 iOS 侧的服务记录。

边界：只连过一副耳机，只在一次开机内测试。没有声音：`bluetoothd` 找不到音频服务的 XPC 客户端，音频子系统未移植。配对记录未跨重启测试（钥匙串写入报 -25300 后改为新增）。BLE 设备的连接、HID 设备、文件传输、长时间运行、芯片睡眠省电（主机仍从不让芯片睡）都未测。博通专有功能（多路广播、硬件过滤、天线分集等）全部回答"不支持"，依赖它们的 iOS 功能（例如"查找"的广播）不可用。开机到蓝牙就绪约 70 秒，由 `bt_delay` 决定，缩短它是否影响 Wi-Fi 未测。主机侧：补丁由 patchtool 导出写回，干净树重放通过，隐私扫描无错误、警告数不变；`build-payload.py --wifi --bluetooth` 的固件与文件核对通过，缺 `--wifi` 时拒绝打包。

## 音频映射、播放与功放（2026-11-11–12）

条件：内存启动、不写存储，每轮完整重启；`mi8rp_step=11..16` 显式启用，无线关闭，`gpu=0 fts=0 buttons=0`，通常限时 90 秒。以下为既有设备记录的整理，本次文档更新未操作设备。

- **步骤 11/12（apps SMMU）**：只读调查确认流 0x1821 未匹配；使用空闲 SMR 槽 8、上下文 43 自建页表。软件走表、配置掩码比较及 200 ms 读回稳定性通过，无新增 fault；apps SMMU 不支持 ATOS，这一步不单独证明 DMA 硬件翻译。设备上 CBAR/S2CR 首次写入后不能还原，按认领记录保留；收尾撤销 SMR、禁用上下文、同步 TLB，确认惰性才释放内存。比较掩码含明确的硬件/配置策略例外，不能把所有未比较位都叫未定义位；不能确认惰性则保留资源。证据在 `work/runs/20261111-audio-smmu-01/` 至 `-07/`。
- **步骤 13（ASM/ADM/AFE）**：管线建立后，150/150 块零/正弦数据被消费。仅映射前 32 KiB、给 ASM 登记 64 KiB 后，越界金丝雀触发 CB43 翻译故障，证明 ADSP DMA 经自建页表；金丝雀导致整颗 ADSP fatal，后续 APR（含 AFE）不应答。PAS 关停后 SMMU 惰性化及内存释放成功，但 stop-ack/AFE 收尾仍有 Pending，翻译证明不等于完整清理通过。金丝雀只留在步骤 13，后续播放不能发越界 DMA。证据在 `work/runs/20261111-audio-play-02/` 至 `-04/`。
- **步骤 14（功放下载）**：SE5 FIFO 被启动固件禁用，改由 GPIO85/86 手工 I2C。TAS2557 ID 与 Android 记录一致，选中 program0/config0 的 program、PLL、pre、coeff 下载及 P/Y 校验全匹配，0 个读回不符；未上电，结束复位低、引脚还原，无 panic。证据在 `work/runs/20261111-audio-amp-01/`、`-02/`；不代表功放能驱动扬声器。
- **步骤 15（零数据、硬静音上电）**：零 PCM 播放期间上电但保持硬静音；健康读数 INT1=02、INT2=00、PUF=fc 与 Android 上电记录一致，150/150 块完成；在 AFE 停止前关断、复位低，close/unmap/AFE/PAS/SMMU 收尾完整，无 panic。证据在 `work/runs/20261111-audio-amp-04/DEVICE.md`；该轮无可听输出。
- **步骤 16（首次出声）**：内核自产 1 kHz、−30 dBFS（峰值 1036）、1 秒短音，持有人确认音量适中，结尾无爆音。初版静音读回误用上电值、慢关断触发 late 检查的问题已修复；732ac32 设备复验静音读回 03/01、shutdown 正常、150/150、AFE completed、无 panic。证据在 `work/runs/20261112-audio-tone-01/`、`-02/` 及 `work/runs/20261112-audio-hal-design-01/`；听感不等于物理波形或扬声器保护/热安全认证。

## iOS 音频计数与桌面零流（2026-11-12）

条件：内存启动、不写存储，GPU/触摸/按键采用桌面默认开启配置，Wi-Fi/蓝牙关闭，不带 `mi8rp_step`，限时约 240 秒，每轮完整重启。

- **audio=1（ef0b864）**：计数 sink 接收到 iOS 的 S16LE 立体声 PCM，每次 1024 帧，稳定时约 47 次/秒；总计 4604 次、4714496 帧，其中非零 498298 帧。安静时可以持续写零，也有约 4.7 秒停写及锁屏后的长时间停写；GPU 桌面负载下记录过 1.31 秒间隔。volume 世代变化而 below 保持 0，结合样本电平变化，设备记录判断 iOS 在样本上乘音量，最高峰约 −6.7 dBFS；全程峰值本身不能证明音量下降的幅度关系。结束摘要确实保留在日志尾部，无 panic。证据在 `work/runs/20261112-audio-sink-01/DEVICE.md`。本模式不启动 DSP、不碰功放，声音只计数。
- **audio=2（051215b）**：GPU 桌面下 ADSP/AFE/SMMU/ASM/ADM 零流 3000/3000 周期（60 秒）完成，underflow=0、faults=0，cleanup=complete；功放未操作、保持复位。loader returned、无 panic；本轮无人操作，计数 sink 没有写入，不能据此声称 HAL 数据已进入 DMA。证据在 `work/runs/20261112-audio-zero-01/README.md`。

共同边界：只有内核自产诊断短音出过声，iOS 音频输出尚未接通。`audio`、`mi8rp_step` 缺省关闭；未与 Wi-Fi/蓝牙并存，SMMU 共享锁仍跨播放持有。当前流程不支持 ADSP 停后再启，需完整重启；长期与热安全、物理波形未测。历史 loader 偶发 `hung` 仍未解决，近期正常返回不代表该问题消失。

## 音频 ring 强制零输出：主机候选（2026-11-12）

`audio=3` 沿用零流的 ADSP/AFE/SMMU/ASM/ADM 路径，启动时安装有界 ring 接收端，播放期消费真实 PCM 但 DMA 整槽只写零，功放保持复位。缺省关闭，非 dipper 或与非零 `mi8rp_step`/`mi8rp_mss`、其他 sink 选择冲突时拒绝。未改变既有诊断、计数/零流和默认参数表。

干净重放源码下，10 万次固定种子 ring 操作、200 万帧并发顺序、关闭与生产者并发、6000 次全零 DMA 提交（120 秒模拟）、超时/丢回包收尾通过；正常例接受 5775424 帧，消费 5759040 帧，丢弃 16384 帧，守恒成立。普通、ASan/UBSan 和 TSan 均通过，既有全部主机测试继续通过。显式 SOURCE_DIR 构建并核对 sink/rproc/PCM/loader 对象来源，P19 参数为默认桌面、无线关闭、240 秒、audio=3。证据在 `work/runs/20261112-audio-ring-01/`。

以上为主机模拟与构建，**设备 Pending**：不证明真实 HAL 到 ring 到 DSP 的消费、无声、调度稳定性或最终退出。共享 SMMU 锁的持有方式未改，不能据此推断无线并存；未操作设备、未提高输出电平。

## 音频线程栈预算（2026-11-12）

静态 PCM 暂存区沿用已有设备修复。准备阶段禁止内联到长期播放入口，单 worker 的 session 与 SMP2P 启动快照改用静态存储；可嵌套的 SMEM 查找保留私有快照。主机构建对象的保守调用图上界 6752 字节，低于 8192；包含人工补齐 ops 回调的并集，另留空间给 XNU 服务/抢占/中断。新增栈压缩的设备回归待验证。

`audio=4` 主机完成，设备待验证。
