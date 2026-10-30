# 用户空间构建与主机打包

先完成 [构建教程](BUILD.md) 的源码准备、内核依赖与编译，并设置 `DIPPER_PROJECT_ROOT`、`DIPPER_INPUTS` 和 `THEOS`。本页构建命令只操作主机文件；设备侧步骤见 [已有分区测试](../install/EXISTING_INSTALL.md)。

## 1. 提取已校验的 iOS 材料

需要支持 APFS 的 7-Zip（23 或更新版本）。在仓库根目录执行：

```sh
python3 tools/prepare-ios.py \
  --ipsw "$DIPPER_INPUTS/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw"
```

脚本先验证整个 IPSW 的 SHA-256 和 BuildManifest，再提取 3 个指定镜像。已有镜像会逐一与 IPSW 内容做 SHA-256 比对，失配即停止；不会覆盖失配文件。随后执行锁定上游的 `ios165/fetch.sh`，生成 rootfs、cryptex、dyld cache 等本工作树自己的目录。原始 DMG 保留，来源记录在 `work/hackios/ios165/input-provenance.json`。

这里不需要读取开发者的旧提取目录，也不要把 `ios165/rootfs` 设成指向另一棵工作树的符号链接。

## 2. 编译并生成两个小启动镜像

```sh
export BUILD_TIMEZONE=Asia/Tokyo   # 可改为自己的时区；未设置且主机无法查询时使用 UTC
export BUILD_JOBS=8
bash tools/build-userland.sh
```

入口明确采用 `GL=1 FLASHBOOT=1 CRYPTEXES=flash REST=1`，从源码编译 Mesa、图形适配、注入库及网络程序；拒绝 `PREBUILT`，缺少交叉链接器时直接报错。`SHARE=1` 排除上游脚本可选的本机网络密码和 SSH 密钥。不会额外生成 RAM 根卷方案的 `system.apfs`。固定 `umask 022`，避免 launchd 拒绝组可写的配置；桌面验收不执行后台 CPU 基准。

| 输出，相对于 `work/hackios/` | 用途 |
| --- | --- |
| `userland/root.apfs` | 适配程序、动态库、launchd 配置；后续作为内核载荷的 `ramdisk` |
| `userland/flashboot.apfs` | 小启动卷，后续用 `fastboot stage` 送入 RAM |
| `userland/obj/` | 本轮编译程序和库 |
| `xnu-deps/build/mesa/out/` | 本轮 Mesa 输出 |

缺少 GPU 固件时，入口仍可完成主机编译，但会明确列出缺项；此时产物不具备设备测试条件。不能把脚本退出成功解释为桌面启动成功。APFS 打包器使用 Python 多进程；受限容器需允许本地 IPC，否则 `PermissionError` 是打包失败，不能忽略。

## 3. 生成写入 darwin 的原始系统组合镜像

```sh
python3 tools/pack-darwin.py
```

输出为 `work/images/darwin.img`，8,365,539,328 字节。脚本不会覆盖已有输出，校验输入来源、各 APFS 魔数和大小，并要求最终 SHA-256 为：

```text
9efb156f417e32b6f92d709af33c0e8e584693c3fbd29eaf139b57eee3735560
```

关键区别：`rootfs.dmg` 的 UDIF 封装内含 GPT 磁盘。脚本使用 `7z x -tDmg -so ... 3.apfs` 只提取其中的 APFS 分区，再顺序拼接 OS、App cryptex。直接写入压缩 DMG，或把带 GPT 的整个展开磁盘拼进去，均不符合本项目布局。发生错误时保留 `.partial` 供检查，不能用于刷写。

## 4. 设备输入与实机测试

单独完成主机构建后，还需以下设备输入。复用已安装手机的核对、固件提取及启动步骤见 [已有分区测试](../install/EXISTING_INSTALL.md)：

- GPU 固件：在 `work/hackios/fw-gpu/` 放置与 dipper 匹配的 `a630_gmu.bin`、`a630_sqe.fw`、`a630_zap.mdt`、`a630_zap.b02`，记录获取链接/来源、版本和 SHA-256 后重建启动卷。
- Wi-Fi：内核通过本机 Android modem 分区读取基带与板级数据；另需 [WCN3990 特性描述文件](INPUTS.md#wcn3990-wi-fi-特性描述文件) `firmware-5.bin`，经校验后装入 root.apfs。需核对本机 modem 布局。上游 `wpss` / `qca6750` 示例属于另一设备，不能当作 WCN3990 的通用输入。
- 本机分区参数：公开 loader 的 `BLOCK_DARWIN_UNIQ` 是零占位符；内核和 loader 的边界需与本机 GPT 对齐后重编译。具体见 [安装教程第 5 节](../install/INSTALL.md#5-让源码匹配新分区)。
- dipper 完整启动参数及最终 `payload.bin`：现已提供 `tools/build-payload.py --output work/runs/desktop-01`，用于已核对 GPT 和系统区的 5 分钟桌面测试。它不包含 Wi-Fi、存储写入或旧用户状态恢复，不能代替设备配置核对。

先只读核对设备与输入，完成设备配置和载荷打包，再按 [已有分区测试](../install/EXISTING_INSTALL.md) 进行实机验收。结果与未通过项记录在 [复现记录](../validation/REPRODUCTION.md)。
