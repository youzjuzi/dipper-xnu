# 许可证适用范围与待确认事项

更新日期：2026-10-29。

本页说明 `source-manifest.json` 中 71 个目标源文件及仓库附带代码/配置的许可依据。判断依据包括固定上游提交、文件级声明和代码来源。逐文件清单见 [license-inventory.json](../license-inventory.json)。

## 已有许可声明

- yanei 的原创模块、文档、独立配置和构建脚本采用 MIT；第三方派生部分沿用相应许可证。
- WLFW 的 ISC 文件保留 Linux Foundation/Qualcomm 版权，与 APSL 文件分别处理。
- HackiOS 用户空间上游采用 MIT。`redwood_drm.c` 是其 IOKit DRM 适配层；外部 Mesa 依赖仍适用各自的文件许可。
- SimpleInit 的 `libs/compatible/malloc.c` 适用 Intel 文件级 BSD 声明，原通知和 EDK2 历史许可位于 `LICENSES/`。SimpleInit 根目录的 LGPL 不用于替代该文件声明。
- `lx_ath10k_gaps.c` 参考 FreeBSD `linux_80211.c`，相关 BSD-2-Clause 作者通知位于 `LICENSES/`。
- `XnuLoaderDxe` 派生于 UniXNU 注册器，保留 UniXNU contributors 版权和 BSD-2-Clause-Patent 声明。

## 待确认的许可范围

1. **GPU 初始化表**：`bsd/dev/mi8_a630_hw_init.inc` 包含从 Linux `a6xx_gpu.c`、`a6xx_catalog.c` 提取的 a630 初始化及 HWCG/保护表，注释标明对应来源。Linux 7.2.10 的两个来源文件分别标注 GPL-2.0 和 GPL-2.0-only。提取内容的版权适用范围及其与 APSL 内核组合后的分发条件尚待确认，该部分不授予 MIT 重许可。
2. **GPU 驱动集成**：`mi8_adreno.c` 调用上述表，并参考其他 Linux GPU 顺序和表值，需要与初始化表一并核对；原创部分的 MIT 授权不覆盖第三方代码。
3. **APSL 文件通知**：XNU/HackiOS 派生修改需要逐文件保留适用声明并记录修改日期；部分增量补丁尚需补齐相应通知。根目录的许可证全文不能替代文件级要求。

`Experimental / Work in Progress` 表示开发状态，不改变上述许可条件。本页不构成对完整系统或二进制分发的许可认证。

## 原创 MIT 范围

以下原创模块位于对应增量补丁中，采用 MIT；原有第三方声明继续保留：

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

代码对应的精确内容摘要见 source-manifest.json。上游来源固定提交见 upstream.lock.json。项目文档、源码准备和构建脚本，以及明确标注 MIT 的独立配置/适配头也采用 MIT。
