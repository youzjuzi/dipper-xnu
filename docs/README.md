# 文档导航

先看 [当前功能状态](STATUS.md)。AI 接手再读 [开发流程与现场交接](development/DEVELOPMENT.md)。

| 分类 | 文档 |
| --- | --- |
| 开发与任务 development/ | [开发流程](development/DEVELOPMENT.md)、[首次安装验收任务](development/FIRST_INSTALL.md)、[开发待办](development/RELEASE_CHECKLIST.md) |
| 构建 build/ | [构建教程](build/BUILD.md)、[输入材料](build/INPUTS.md)、[用户空间与打包](build/USERLAND.md) |
| 安装操作 install/ | **[分区、写入与回退](install/INSTALL.md)**、**[配置、重建与启动](install/STARTUP.md)** |
| 安装工具与测试参考 | [设备版本、TWRP 与固件准备](install/DEVICE_PREPARATION.md)、 [darwin 分区工具](install/PARTITION_DARWIN.md)、[固件与已有分区测试](install/EXISTING_INSTALL.md) |
| 验证证据 validation/ | [验证记录](validation/VALIDATION.md)、[复现过程](validation/REPRODUCTION.md)、[设备验收数据](validation/device-validation-20261030.json) |
| 来源与许可 legal/ | [许可审查](legal/LICENSE_REVIEW.md)、[GPU 许可](legal/GPU_LICENSE.md)、[GPU 来源数据](legal/gpu-source-audit.json) |

工具分类与入口见[工具导航](../tools/README.md)。

images/ 放公开文档图片。任务计划说明要做什么，安装教程说明如何操作，验证记录说明实际做过什么，三者不要混写。原始私人日志和备份继续留在 work/runs/、local/，不搬进 docs。

新增文档归入已有类别并更新本导航；不为每轮实验新增公开文档，实验结论归并到对应任务和验证记录。

公开首页与 build/install 教程面向使用者：只写通用步骤、标准目录、版本与验证限制，不引用开发者的固定实验路径、对话或内部轮次。development/ 和 validation/ 用于维护交接与证据追溯，其中的私有文件索引不是读者必须拥有的输入。
