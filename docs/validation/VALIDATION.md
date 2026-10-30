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
