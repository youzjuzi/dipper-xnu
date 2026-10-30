# dipper-xnu 开发约定

## 开始工作

- 本仓库是后续开发入口。先读 `docs/README.md`、`docs/STATUS.md`、`docs/development/DEVELOPMENT.md`（含当前现场交接），再检查 Git 分支与未提交修改。
- 当前可复现交付物是固定上游版本 + `patches/` + `source-manifest.json` + 构建工具，不是单独的 `work/`。
- `work/` 和 `local/` 虽被 Git 忽略，可能包含未导出的源码、本机配置、固件和唯一的测试证据。不得默认清理、覆盖或切换其内层仓库。
- 旧 MI8-IOS 工作区只作历史参考。不要把旧启动脚本、旧产物和当前复现树混合使用。

## 修改与验证

- 每次改动围绕一个问题；默认一任务一分支，在本仓库唯一的 work/ 顺序开发。不为每个任务复制仓库或建立工作树；每轮仅新建运行记录目录。
- 修改上游衍生源码后，导出对应补丁；更新源码清单，并检查许可清单中受影响的条目。不能只改忽略目录后宣称已提交修复。
- 导出必须基于相应组件的正确基线，先审查文件列表。XNU 的 dipper 补丁基于 HackiOS 基线，不直接基于 Apple 原版。
- 私人 GUID、MAC、密码、固件、SDK、系统镜像和原始设备日志不进入补丁或提交。公开 loader 保留占位值，本机配置单独保存。
- 改动后按范围验证：文档做链接和摘要检查；源码做补丁重放、编译及必要的主机回归。设备成功只能依据实际设备证据。
- 有效源码变更更新 `docs/STATUS.md`、`docs/validation/VALIDATION.md`，面向使用者的变化写 `CHANGELOG.md`；维护 `SHA256SUMS`。
- 不使用 `git add .`；逐个指定审查过的文件。未获授权不 push、发布或创建 Release。

## 设备与输入

- 构建和主机检查不自动操作手机。设备操作由持有人执行；不得自行 flash、erase、分区、写块设备或解锁。
- 遇到指定 SHA256 不一致立即停止对应步骤，不换版本、不绕过校验。
- 当前 GPU/基带退出恢复尚未闭合；设备轮次之间完整重启，不能沿用旧记录直接 rerun。
- 保留已有产物，每轮使用新输出目录；不以主机通过替代真机验证。

## 目录纪律

- 严格遵循 `docs/development/DEVELOPMENT.md` 的固定目录表。已有类别不得另建顶层目录；新增类别先说明用途并更新目录表。
- 仅干净重放/重建验证或明确需要的并行工作使用顶层 `experiments/<topic>/` 临时树；日常运行日志和产物放本仓库的 `work/runs/YYYYMMDD-<topic>-NN/`，发布审查放 `local/reviews/YYYYMMDD-<topic>/`。
- 顶层 `sources/` 停用；工作区 archive/20261030 下的历史 reproduction-logs、release-review 和旧 MI8-IOS 工作区不再追加日常内容。禁止再维护第二套发布源码副本。
- 不为整理外观移动现有构建树或输入。路径调整须同步脚本、文档并验证；可复用脚本放 `tools/`，一次性脚本跟随对应实验记录。

- `local/` 遵循开发文档的 local 管理约定：现有配置路径不变，新配置/来源/备份/审查分别归入 devices、provenance、backups、reviews；同步本机 index.json，禁止临时堆在根目录。运行产物放 work/runs，不放 local。

## 单源码树与交接

- 父仓库分支切换不更新被忽略的 work/。切任务前先导出并保存所有源码差异；切到不同源码版本后，核对 work/ 与目标提交的对应关系才能编译。禁止以覆盖、清空或另复制一份来回避未保存修改。
- docs/development/DEVELOPMENT.md 的“当前开发现场交接”是唯一开发现场入口，每次结束更新任务、分支/提交、未导出修改、产物证据和下一步。STATUS 记录产品功能边界，不复制一份平行状态文档。

- 文档分类见 docs/README.md：development、build、install、validation、legal；新增文档归入相应类别，不平铺 docs 根目录。当前分支计划为 docs/development/FIRST_INSTALL.md。
