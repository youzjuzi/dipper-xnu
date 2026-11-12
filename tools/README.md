# 工具导航

命令默认在仓库根目录执行。公共工具按用途归类；本机配置留在 `local/`，运行结果留在 `work/runs/`。这里不存源码副本、固件、系统镜像或每轮一次性脚本。

| 目录 | 用途 | 入口 |
| --- | --- | --- |
| prepare/ | 固定源码准备、补丁维护、SDK 校验、IPSW 提取 | [prepare.py](prepare/prepare.py)、[patchtool.py](prepare/patchtool.py)、[check-sdk.py](prepare/check-sdk.py)、[prepare-ios.py](prepare/prepare-ios.py) |
| build/ | loader/UEFI、用户态编译及镜像/载荷打包 | [build-loader-uefi.sh](build/build-loader-uefi.sh)、[build-userland.sh](build/build-userland.sh)、[build-payload.py](build/build-payload.py)、[pack-darwin.py](build/pack-darwin.py) |
| partition/ | 离线生成分区/恢复方案，核验回读 | [partition-darwin.py](partition/partition-darwin.py)、[restore-android-layout.py](partition/restore-android-layout.py) |
| tests/ | 合成 GPT、CLI 与假设备保护测试 | [test-patchtool.py](tests/test-patchtool.py)、[test-partition-darwin.py](tests/test-partition-darwin.py)、[test-restore-android-layout.py](tests/test-restore-android-layout.py) |

`build/cc-gnu17/cc` 是构建兼容包装器，保留原位置，由 UEFI 构建入口使用。分区工具只在主机生成方案；生成的设备脚本由持有人核对后执行，不会自动操作手机。

## 使用入口

- [构建教程](../docs/build/BUILD.md)、[输入材料](../docs/build/INPUTS.md)、[用户空间](../docs/build/USERLAND.md)。
- [分区、写入与回退](../docs/install/INSTALL.md)、[启动教程](../docs/install/STARTUP.md)。
- 回归测试：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/tests/test-patchtool.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/tests/test-restore-android-layout.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/tests/test-partition-darwin.py
```

## 补丁导出与重放

工具仅依赖 Python 标准库和 Git。`export` 只读 `work/`，从其本地 Git 对象读取锁定提交，在临时目录复用准备工具的叠加流程；不联网。XNU 基线是 Apple 加 HackiOS，不是内层仓库 HEAD。共享目录按源码清单分属组件。

```sh
python3 tools/prepare/patchtool.py export --out work/runs/<run-id>/export
python3 tools/prepare/prepare.py --prepare --dest ../experiments/patchtool/clean
python3 tools/prepare/patchtool.py replay --tree ../experiments/patchtool/clean
python3 tools/prepare/patchtool.py scan
```

导出目录必须不存在，包含各组件补丁、`source-manifest.json` 和 `report.json`。报告列出清单外差异、删除和显式新增，也检查已初始化子模块的改动及 gitlink 版本；辅助子模块缺少锁定对象时明确报告，保持离线且不纳入其文件；未登记文件不会自动进入补丁。`--component NAME` 可重复；新增使用 `--add COMPONENT:PATH`，只选一个组件时也可使用 `--add PATH`。删除项以空摘要和模式登记。已知 loader 身份字段恢复为现有公开补丁的占位值；其他隐私命中或无法确认的二进制源码会阻止导出。补丁保留原始文件字节，元数据使用 LF，无时间戳或绝对路径；文件按路径排序，逐文件生成固定 Git diff。

`--write` 明确要求将已检查的导出补丁及所选组件清单写回仓库，默认不启用。采纳前审查报告和差异，同时复核许可清单；随后更新摘要。构建垃圾排除规则不代表其他未登记文件可以删除。

`replay` 的输入是 `prepare.py` 已应用发布补丁的独立干净树。它先核对输入树的清单摘要和完整模式，再从锁定对象重建基线，逐个执行 `git apply --check` 和应用，核对重放摘要、模式与清单外差异，不重复修改输入树。旧式 unified 补丁不携带模式，以现有清单恢复权限；新导出格式还会核对补丁编码的可执行位。`--patch-dir DIR` 可验证完整导出目录中的补丁与清单，输入树须与该清单一致。失败摘录最多 50 行。准备工具默认仍使用 `work/`，`--dest` 指定的路径已存在时也会拒绝覆盖。

`scan [PATH ...]` 默认检查 Git 跟踪文件及补丁，仅打印文件、行号和分级类别，不回显命中值。私人路径、非允许 GUID、非零 MAC 和序列号属于 error；历史过程编号与署名字样属于 warning。允许表只包含公开协议/类型、固定上游示例和测试占位标识，并在脚本中注明来源。扫描属于格式检查，不能替代人工隐私与许可审查。

## 平台默认值主机测试

`python3 tools/tests/test-boot-defaults.py` 编译准备树中的实际 ARM 默认值代码和 XNU 解析器，以合成设备树测试配置等价、平台隔离和覆盖语义；需要本机 C 编译器。`--tree` 可指定干净 XNU 源码树，`--old-cmdline` 可读取本地完整参数文件，测试将 MAC 替换为零占位值且不打印输入。它不操作设备。公开短参数和打包选项见[启动教程](../docs/install/STARTUP.md#dipper-短启动参数与默认值)。

## ADSP GLINK/APR 主机测试

`python3 tools/tests/test-mi8-audio-apr.py` 用 `MI8_GLINK_HOST_TEST` 编译实际 GLINK/APR 源码，合成 SMEM 环形 FIFO 对端，测试 raw open、分片、intent 请求与关闭、APR 坏包拒绝、完整版本列表和默认 IPCRTR/QRTR 兼容性。`python3 tools/tests/test-mi8-rproc-state.py` 提取实际远端状态、查找、调度与互斥代码，检查 ADSP/modem 隔离、嵌套查询、失败收尾与共享事务互斥。两者需要本机 C 编译器与 pthread，输出 `SELFTEST PASS n/n`；`--tree` 指向准备树根目录（包含 `hackios/`）。这些检查不操作设备，不能代替真实固件的通道、APR 或停机验证。

## 有界音频 ring 主机测试

`python3 tools/tests/test-mi8-audio-ring.py` 编译实际 SPSC ring 与 PCM/AFE/APR/GLINK 路径，检查固定种子 10 万次操作、200 万帧并发顺序、关门守恒、6000 周期全零 DMA 与超时收尾。`--sanitize` 启用 ASan/UBSan，`--tsan` 独立启用 TSan，`--tree` 指定干净准备树。配合 `test-mi8-audio-sink.py` 检查实际 cdev 锁、参数冲突与 loader 尾部摘要；这些测试不操作设备。

## 路径迁移说明（2026-10-31）

原先直接位于 tools/ 根目录的脚本已移入上述分类，文件名不变，不保留第二套脚本或旧入口。当前教程使用新路径。历史验证记录和 work/runs/ 中的原始命令保留当时路径，不修改既有证据；需要再次运行时按本页选择新入口并新建轮次，不直接重跑历史脚本。历史源码/生成器摘要仍指向当时版本，不为目录整理刷新旧实验的来源记录。

新脚本按用途放进现有分类，并更新本页、相关教程和 SHA256SUMS；不要重新堆放到 tools/ 根目录。

## 音频工作线程栈预算

`python3 tools/tests/check-mi8-audio-stack.py <OBJROOT>/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT --json <报告路径>` 反汇编实际链接的 `mi8_*.o`，合计保存寄存器和局部栈分配，以直接调用、尾调用及工具内注明的原生 ops 回调保守并集建图。单帧超过 1 KiB 报警，工作线程最深路径超过 8 KiB 失败；动态 SP、调用环或未审查的间接调用拒绝。SMEM 查找需保留独立快照，列为有理由的单帧例外，其空间仍计入路径。JSON 列出对象摘要、最深路径、人工补边和外部 XNU 入口；余下 8 KiB 留给内核服务、抢占和中断，工具结果不等于整个内核的形式化栈界证明。必须确认对象来自当前源码和交付内核。

## 有界可听片段主机测试

`python3 tools/tests/test-mi8-audio-clip.py --firmware <固件> --reference <离线参考文本> --metadata <摘要JSON>` 链接实际 PCM、GLINK/APR 和 TAS 驱动，验证处理链、触发、150 周期窗口、错误守卫、预热/关断延迟、ring 守恒和完整 worker 出口；`--sanitize` 启用 ASan/UBSan，`--tree` 指定干净准备树。ring 并发继续由 `test-mi8-audio-ring.py --tsan` 验证。栈检查默认覆盖原 worker 与 clip worker；数据对象没有函数，其他线程的超 1 KiB 帧也列为警告，不混算进音频线程路径。

## 会话音频主机测试

`python3 tools/tests/test-mi8-audio-session.py --firmware <固件> --reference <离线参考文本> --metadata <摘要JSON>` 验证实际会话 feeder、TAS 控制、ring/GLINK/APR 路径与独立字对齐 I2C 对端。覆盖多次 wake/mute、静默/时长/次数上限、只读系数校验、健康失败、提交守卫、8 个零块尾段及 worker 出口。`--threads` 使用真实双线程和 0/50/500 ms 控制延迟，`--tsan` 为该并发检查启用 TSan；`--sanitize` 启用 ASan/UBSan。`--tree` 指向干净准备树。

`test-mi8-audio-session-join.py` 单独提取原生 join 实现，验证 300 ms 超时、复位拉低、幂等失败及资源保留。超时不等于线程退出：失败线程及其资源保留至完整重启。栈预算工具另覆盖 session feeder 和 TAS control 两个线程。
