# 许可范围

本项目包含多种来源，**不存在覆盖所有文件的统一 MIT 授权**。

- 本次新增的发布文档及 `tools/prepare.py`、`tools/build-loader-uefi.sh`：MIT，见 `LICENSES/MI8-packaging-MIT.txt`。
- 基于 HackiOS/XNU 的内核补丁：保留原文件适用的 APSL 2.0 及其他逐文件许可；见 `LICENSES/APSL-2.0.txt`。补丁不改变原文件许可。
- HackiOS 用户空间上游根许可证为 MIT；独立第三方部分继续适用其自身条款，见 `LICENSES/HackiOS-userland-MIT.txt`。
- edk2、SimpleInit、UniXNU 派生内容分别保留原许可；见 `LICENSES/` 与第三方清单。
- 标有 ISC 的 WLFW 等代码继续适用 ISC；原版权头保留，许可证正文见 `LICENSES/ISC.txt`。

导出补丁中包含新增文件和修改上下文。未明确标注许可的新文件，必须依据实际来源进一步核对，不能仅凭所在目录认定许可证。发布整理不会替第三方重新授权。

在逐文件归属核对完成前，本目录应作为本地候选版审阅，不应标记为已完成许可证审计的正式开源版本。需要检查的项目见 `docs/RELEASE_CHECKLIST.md`。
