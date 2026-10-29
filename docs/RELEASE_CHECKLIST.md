# 开发待办

本项目处于 Experimental / Work in Progress 阶段，以下工作仍需完成。

## 许可证

- [ ] 确认 GPU 初始化表及驱动集成的许可适用范围。
- [ ] 补齐 APSL 文件级通知和修改日期。

逐文件清单见 [license-inventory.json](../license-inventory.json)，具体问题见 [许可证说明](LICENSE_REVIEW.md)。

## 构建与安装

- [ ] 在干净的 Ubuntu 环境验证源码获取、传递依赖及完整内核/UEFI 编译。
- [ ] 完成用户空间程序、动态库和镜像组合的从零构建流程，消除对旧产物的依赖。
- [ ] 提供独立的设备存储配置输入，替代历史布局和 GUID 占位符。
- [ ] 使用按教程新构建的产物完成独立安装与启动验证。

当前功能状态见 [STATUS.md](STATUS.md)，验证范围见 [VALIDATION.md](VALIDATION.md)。
