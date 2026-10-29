# 离线验证记录

日期：2026-10-27。仅主机文件级验证，未连接设备，未运行上游构建。

- XNU recorded baseline matches Apple source + pinned HackiOS redwood.patch/files byte-for-byte.
- xnu-mi8: replay PASS; 34 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- hackios-kernel: replay PASS; 23 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- hackios-userland: replay PASS; 7 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- edk2-sdm845: replay PASS; 5 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- simpleinit: replay PASS; 1 changed/new/deleted text files match exported text (loader device GUID intentionally removed).
- unixnu: replay PASS; 1 changed/new/deleted text files match exported text (loader device GUID intentionally removed).

未验证：全新联网获取、完整编译、用户空间材料准备、启动打包和实机运行。

## 发布目录检查

- 重新核对 6 组补丁回放结果：71 个文件 SHA256 与导出清单一致。
- Python 语法解析、Shell `bash -n`、Markdown 本地链接检查通过。
- 全部发布文件均可解码为 UTF-8 文本，无符号链接、NUL 字节或镜像/二进制产物扩展名。
- 本机分区 GUID 与主机绝对路径的指定模式扫描无命中；这不等同于完整人工隐私审计。
- 获取脚本默认仅显示计划，已执行验证；联网 `--prepare` 未执行。
- `SHA256SUMS` 为此目录提供内容校验，不是数字签名或授权证明。
