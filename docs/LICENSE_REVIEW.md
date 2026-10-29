# 许可证核对记录（2026-10-29）

本次覆盖 source-manifest.json 的 71 个目标源文件和发布目录直接附带的代码/配置。以固定上游提交的许可证、文件级声明、开发任务来源和维护者授权为依据。逐项清单见 [license-inventory.json](../license-inventory.json)。这是源码来源与通知核对，不是法律意见或二进制分发许可认证。

## 已确认并修正

- 维护者确认：本项目原创人工作品和 AI 辅助代码可按 MIT 发布；该授权不覆盖第三方派生部分。
- WLFW 文件保留原 ISC 声明和 Linux Foundation/Qualcomm 版权。APSL 与 ISC 文件分别处理，不统一改成 MIT。
- HackiOS userland 的固定上游根许可证为 MIT；本补丁中的 redwood_drm.c 是其 IOKit 适配层，不能因目录名 mesa 就将全部 Mesa 代码归为本项目原创。
- SimpleInit 根 LICENSE 是 LGPL-3.0，但本补丁唯一修改的 libs/compatible/malloc.c 有 Intel BSD 文件级声明。补充了原文件通知、EDK2 历史许可文本；不把根 LGPL 机械应用到该文件。
- lx_ath10k_gaps.c 明确参考 FreeBSD linux_80211.c，按 BSD-2-Clause 保留原作者通知。
- XnuLoaderDxe 派生于 UniXNU 注册器，补回 UniXNU contributors 版权和 BSD-2-Clause-Patent 声明。其他直接附带的原创 shim、配置和 GCC 包装器明确标为 MIT。
- GPL、BSD、APSL、MIT 等不同条款不能由一句“仅研究用途”或“Experimental”替代。

## 公开前尚未解决的具体问题

1. bsd/dev/mi8_a630_hw_init.inc 的任务说明要求逐项提取 Linux a6xx_gpu.c/a6xx_catalog.c 的 a630 初始化与 HWCG/保护表，导出代码也逐项注明来源。对应本地 Linux 7.2.10 文件头分别为 GPL-2.0 与 GPL-2.0-only。仅能确定来源许可；尚未确认这些提取内容的版权适用范围以及与 APSL 内核组合后的分发条件。不能把它声明为 MIT 或直接判定“GPL 不适用”。
2. mi8_adreno.c 调用并集成该表，也有其他 Linux GPU 顺序/表值参考，需要连同上一项核对。尚未证明所有内容均为独立原创，维护者的 MIT 授权不能覆盖第三方代码。
3. XNU/HackiOS 的 APSL 修改需要逐文件保留/补齐适用通知及修改日期；当前增量补丁并非每处都包含这些声明。仅在仓库根目录放 APSL 全文不能代替所有文件要求。

以上问题未解决前，维持私有仓库。Experimental / Work in Progress 已用于说明开发状态，但不作为许可证核对完成的标志。未移除 GPU 文件、未变更 GUID、未改变实际驱动行为。

## 原创 MIT 范围

下面仅指维护者拥有权利的原创部分，包含在对应增量补丁中；任何原有第三方声明优先保留：

- `xnu-mi8 : bsd/dev/mi8_glink.c`
- `xnu-mi8 : bsd/dev/mi8_glink.h`
- `xnu-mi8 : bsd/dev/mi8_hostsvc.c`
- `xnu-mi8 : bsd/dev/mi8_hostsvc.h`
- `xnu-mi8 : bsd/dev/mi8_hostsvc_k.c`
- `xnu-mi8 : bsd/dev/mi8_wlfw_k.c`
- `xnu-mi8 : bsd/sys/mi8_lx.h`
- `hackios-kernel : tools/mk-ath10k.sh`
- `hackios-kernel : wifi/lx/include-ath10k/linux/acpi.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/clk.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/io.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/iommu.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/nvmem-consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/of.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/of_device.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/platform_device.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/property.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/pwrseq/consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/qrtr.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/regulator/consumer.h`
- `hackios-kernel : wifi/lx/include-ath10k/linux/remoteproc/qcom_rproc.h`
- `hackios-kernel : wifi/lx/include-ath10k/lx_ath10k_prelude.h`
- `hackios-kernel : wifi/lx/include/lx_ath10k_cfg.h`
- `hackios-kernel : wifi/lx/include/lx_wlfw.h`
- `hackios-kernel : wifi/lx/src-ath10k/lx_ath10k_bus.c`
- `hackios-kernel : wifi/lx/src-ath10k/lx_ath10k_qmi.c`

代码对应的精确内容摘要见 source-manifest.json。上游来源固定提交见 upstream.lock.json。发布目录新增文档、准备/构建脚本及明确标注 MIT 的独立配置/适配头也采用 MIT。
