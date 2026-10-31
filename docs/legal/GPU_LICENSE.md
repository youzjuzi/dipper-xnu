# GPU 代码来源与许可处理

更新日期：2026-10-31。

现有 GPU 功能保留。`mi8_a630_hw_init.inc` 按其 Linux 派生来源标注 GPL-2.0-only，并附原作者通知及 [GPL 2.0 全文](../../LICENSES/GPL-2.0-only.txt)。这项来源声明**不构成将它与 APSL 内核组合分发的许可确认**。

## 分发方式（2026-10-31 起）

GPL-2.0 与 APSL 2.0 的冲突只在**分发把两者合并在一起的二进制**（预编译内核、含该内核的 kernelcache、启动镜像、系统镜像）时出现。因此本项目：

- **只分发源码、补丁、构建脚本和文档**。`mi8_a630_hw_init.inc` 作为独立文件保留 GPL-2.0-only 及原作者通知，其余文件保留各自许可，互不改标。
- **不分发、不托管**含该初始化表的预编译内核或任何包含它的合并二进制，包括网盘、Release 附件和安装包内置文件。
- 使用者在**自己的机器上**按[构建教程](../build/BUILD.md)编译，构建产物仅供其自用。

注意：
1. 这是对分发行为的限制，不是对许可冲突本身的解决。第三方若自行重新分发合并二进制，需自行承担许可风险；请勿在 Issue、网盘或安装器中提供这类文件。
2. 若日后要提供预编译内核，必须先完成下文“保留 GPU 的后续条件”中的独立来源替换，或取得权利人的额外授权。
3. 本文是来源核对记录，不是法律意见。

## 已确认的来源

`mi8_adreno.c` 直接 `#include "mi8_a630_hw_init.inc"`，并执行其中的初始化表。它参与内核编译，不是独立的文档或运行于其他进程的程序。

对仓库补丁中实际导出的表进行比对：

| 项目 | 结果 |
| --- | --- |
| 主初始化表 | 180 项写操作 |
| HWCG 表 | 105 项，符号名和值与 Linux v7.2.10 的 `a630_hwcg` 完全一致 |
| CP 保护表 | 32 项，编码值与 Linux v7.2.10 的 `a630_protect_regs` 完全一致 |
| 来源文件声明 | `a6xx_gpu.c` 为 GPL-2.0，`a6xx_catalog.c` 为 GPL-2.0-only |

比对仅证明来源对应关系，不判定单个寄存器数值是否受版权保护。公开补丁仍包含对上游表、顺序和实现的提取与改编，不能因其中包含硬件事实就将整个文件重新标为 MIT。

GNU 的[许可证列表](https://www.gnu.org/licenses/license-list.html#apsl2)明确将 APSL 2.0 列为与 GPL 不兼容。为文件保留 GPL 声明和提供源码是必要的来源处理，但不足以确认当前组合的分发条件。项目根目录改成 GPL、拆成补丁、仅在本机下载或增加 Experimental 标签，都不能自行改变上游授予的权利。

## 宽松许可来源

### Mesa / freedreno

[寄存器描述](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-25.0.7/src/freedreno/registers/adreno/a6xx.xml)导入了 [freedreno 版权和宽松许可声明](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-25.0.7/src/freedreno/registers/freedreno_copyright.xml)。它可作为寄存器名称、偏移和位域的来源。

寄存器定义不能替代初始化配方：目前没有从这组 XML 中确认到覆盖现有 105 项 HWCG 值、完整 CP 保护策略及所有执行顺序的等价实现。不能仅替换符号定义，就把 Linux 来源的整套初始化表视作已解决。

### Fuchsia 历史 Adreno 驱动

固定提交：`d05398df901609c870db41e1558eeafcbf4320b7`。

- [初始化实现](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/src/graphics/drivers/msd-qcom-adreno/src/msd_qcom_device.cc)
- [寄存器定义](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/src/graphics/drivers/msd-qcom-adreno/src/registers.h)
- [BSD-3-Clause 许可证](https://fuchsia.googlesource.com/fuchsia/+/d05398df901609c870db41e1558eeafcbf4320b7/LICENSE)

该实现可作为内存范围、部分核心寄存器、环缓冲和 CP 保护设置的候选来源，但存在明确差异：

- `HardwareInit()` 调用 `EnableClockGating(false)`；后者只在硬件时钟门控已关闭时返回成功，其他情况报未实现，没有提供 HWCG 配置表。
- CP 保护设置为 26 项，当前表为 32 项，保护区间和值也有差异，不能当作等价替换。
- GMU、供电、SMMU、固件和设备入口状态仍需与 dipper 平台单独匹配。未证明这份驱动能直接替代现有 A630 路线。

已核对的较新历史仍未提供完整替代：该驱动在提交 `16e2530aabedcb2f8cf8eff076278e60535965f7` 中作为未维护驱动被删除。不能据此宣称找到可直接移植的当前实现。

Fuchsia 是部分兼容来源，尚未集成到项目中；保留其许可证副本用于明确候选来源条件，不表示本项目已经采用该实现。

### Qualcomm KGSL

核对的 [Qualcomm KGSL A6xx 实现](https://github.com/qualcomm-linux/kgsl/blob/gfx-kernel.le.0.0/adreno_a6xx.c)同样标为 GPL-2.0-only，不是已找到的宽松许可替代。

## 保留 GPU 的后续条件

要替换现有 Linux 派生实现并保留 GPU 功能，需要取得完整的兼容许可来源或相关权利人的额外授权。选择独立实现时，需要为其余初始化值、保护策略和顺序建立独立、可使用的硬件依据，而不是仅换语言、变量名或删除来源注释。

替代实现还需验证：

1. 所有目标寄存器、取值、保留位及写入前提都有明确来源。
2. HWCG 与 GMU/安全设置的先后顺序满足 A630 和本机固件状态。
3. CP 保护范围没有因复用另一份驱动而减少或失效。
4. 主机检查通过后，由设备持有人验证冷启动、提交完成、图形输出及退出恢复。源码或主机检查不能代替这些实机结果。

目前缺少的是完整替代来源与相应验证，不能将许可问题标记为已解决。

## 验证记录

- 补充文件头声明前后，初始化片段的预处理结果完全一致；未更改寄存器值、顺序或函数实现。
- 修改后的 XNU 补丁在隔离目录严格回放，34 个输出文件均与更新后的 `source-manifest.json` 摘要一致。
- 开发目录中的原驱动和原初始化表保持原样，未执行设备操作。

精确来源 URL、文件 SHA256 与比对结果见 [gpu-source-audit.json](gpu-source-audit.json)。
