# 工具导航

命令默认在仓库根目录执行。公共工具按用途归类；本机配置留在 `local/`，运行结果留在 `work/runs/`。这里不存源码副本、固件、系统镜像或每轮一次性脚本。

| 目录 | 用途 | 入口 |
| --- | --- | --- |
| prepare/ | 固定源码准备、SDK 校验、IPSW 提取 | [prepare.py](prepare/prepare.py)、[check-sdk.py](prepare/check-sdk.py)、[prepare-ios.py](prepare/prepare-ios.py) |
| build/ | loader/UEFI、用户态编译及镜像/载荷打包 | [build-loader-uefi.sh](build/build-loader-uefi.sh)、[build-userland.sh](build/build-userland.sh)、[build-payload.py](build/build-payload.py)、[pack-darwin.py](build/pack-darwin.py) |
| partition/ | 离线生成分区/恢复方案，核验回读 | [partition-darwin.py](partition/partition-darwin.py)、[restore-android-layout.py](partition/restore-android-layout.py) |
| tests/ | 合成 GPT、CLI 与假设备保护测试 | [test-partition-darwin.py](tests/test-partition-darwin.py)、[test-restore-android-layout.py](tests/test-restore-android-layout.py) |

`build/cc-gnu17/cc` 是构建兼容包装器，保留原位置，由 UEFI 构建入口使用。分区工具只在主机生成方案；生成的设备脚本由持有人核对后执行，不会自动操作手机。

## 使用入口

- [构建教程](../docs/build/BUILD.md)、[输入材料](../docs/build/INPUTS.md)、[用户空间](../docs/build/USERLAND.md)。
- [分区、写入与回退](../docs/install/INSTALL.md)、[启动教程](../docs/install/STARTUP.md)。
- 回归测试：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/tests/test-restore-android-layout.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/tests/test-partition-darwin.py
```

## 路径迁移说明（2026-10-31）

原先直接位于 tools/ 根目录的脚本已移入上述分类，文件名不变，不保留第二套脚本或旧入口。当前教程使用新路径。历史验证记录和 work/runs/ 中的原始命令保留当时路径，不修改既有证据；需要再次运行时按本页选择新入口并新建轮次，不直接重跑历史脚本。历史源码/生成器摘要仍指向当时版本，不为目录整理刷新旧实验的来源记录。

新脚本按用途放进现有分类，并更新本页、相关教程和 SHA256SUMS；不要重新堆放到 tools/ 根目录。
