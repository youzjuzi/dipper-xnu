# Documentation Index

**English** | [简体中文](zh-CN/docs/README.md)

Start with [Current Feature Status](STATUS.md). Coding agents should also read [Mainline Development and Handoff](development/DEVELOPMENT.md).

| Category | Documents |
| --- | --- |
| `development/` | [Development Workflow](development/DEVELOPMENT.md), [First-Install Checklist](development/FIRST_INSTALL.md), [Development Backlog](development/RELEASE_CHECKLIST.md) |
| `build/` | [Build Guide](build/BUILD.md), [External Inputs](build/INPUTS.md), [Userspace & Packaging](build/USERLAND.md) |
| `install/` | **[Partitioning, Flashing & Rollback](install/INSTALL.md)**, **[Configuration, Rebuild & Boot](install/STARTUP.md)** |
| `install/` (Reference) | [Device Preparation & Firmware](install/DEVICE_PREPARATION.md), [Darwin Partition Tool](install/PARTITION_DARWIN.md), [Existing-Partition Testing](install/EXISTING_INSTALL.md) |
| `validation/` | [Validation Log](validation/VALIDATION.md), [Reproduction Report](validation/REPRODUCTION.md), [Device Validation Data](validation/device-validation-20261030.json) |
| `legal/` | [License Review](legal/LICENSE_REVIEW.md), [GPU License Notes](legal/GPU_LICENSE.md), [GPU Source Audit Data](legal/gpu-source-audit.json) |
| `zh-CN/` | [Chinese Documentation Mirror (简体中文)](zh-CN/README.md) |

For tool layout and entry points see [Tools Index](../tools/README.md).

Keep task plans (what to do), installation guides (how to operate), and validation logs (what was actually verified) separated rather than mixing them. Raw private logs and device backups remain in `work/runs/` and `local/` and are never committed under `docs/`.

Place new documents in the appropriate category above and update this index; do not create new public docs per test run—fold verified findings into task docs and validation records.

The public landing page and `build/`/`install/` tutorials use a reader-facing perspective with standard directories, pinned versions, and explicit validation boundaries—no private experiment paths, chat references, or internal round numbers. `development/` and `validation/` track handoffs and evidence indices; referenced local files are not required inputs for readers.
