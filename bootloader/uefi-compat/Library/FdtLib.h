/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 yanei
 */
// 新版 edk2/Mu_Basecore 的 Library/FdtLib.h 导出驼峰命名的 Fdt* 封装；
// 我们的 tianocore edk2 (2023-01) 只有 EmbeddedPkg/Include/libfdt.h（标准 fdt_* 函数）。这里把 UniXNU 实际用到的 13 个名字一一映射。
// 由 EXP-0018 的脚本生成：对照 UniXNU 源码里出现的 Fdt* 名字与 libfdt.h 的声明。
#include <libfdt.h>
#define FdtAddSubnode fdt_add_subnode
#define FdtCheckHeader fdt_check_header
#define FdtDelNode fdt_del_node
#define FdtDelProp fdt_delprop
#define FdtGetProp fdt_getprop
#define FdtOpenInto fdt_open_into
#define FdtOverlayApply fdt_overlay_apply
#define FdtPack fdt_pack
#define FdtPathOffset fdt_path_offset
#define FdtSetProp fdt_setprop
#define FdtStrerror fdt_strerror
#define FdtString fdt_string
#define FdtSubnodeOffsetNameLen fdt_subnode_offset_namelen

// 新版 FdtLib.h 里的头结构（驼峰字段名），布局与 libfdt 的 struct fdt_header 相同（大端原始值）。
#define Fdt32ToCpu fdt32_to_cpu
typedef struct {
  UINT32  Magic;
  UINT32  TotalSize;
  UINT32  OffDtStruct;
  UINT32  OffDtStrings;
  UINT32  OffMemRsvmap;
  UINT32  Version;
  UINT32  LastCompVersion;
  UINT32  BootCpuidPhys;
  UINT32  SizeDtStrings;
  UINT32  SizeDtStruct;
} FDT_HEADER;
