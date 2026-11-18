# Development Backlog

**English** | [简体中文](../zh-CN/docs/development/RELEASE_CHECKLIST.md)

This project is in the **Experimental / Work in Progress** stage; the items below remain open.

## Licensing

- [x] Verify Linux-derived provenance for GPU init tables and preserve GPL notices, copyrights, and full license text.
- [ ] Obtain a complete compatible GPU init source or additional authorization to resolve combined binary distribution with the APSL kernel.
- [ ] Complete per-file APSL notices and modification dates across incremental patches.

Per-file inventory: [license-inventory.json](../../license-inventory.json); details: [License Review](../legal/LICENSE_REVIEW.md).

## Build and Installation

- [ ] Verify end-to-end source fetch, transitive dependencies, and full kernel/UEFI compilation in a clean Ubuntu environment.
- [x] Complete clean userspace binaries, dylibs, and composite image builds from an isolated source tree without stale artifacts.
- [x] Re-test desktop, Wi-Fi/Safari, brightness, and listed peripherals in a short boot reusing a checksum-verified system partition.
- [ ] Fix remaining XNU `all` export symbol checks and host tool generation (explicit `build` target currently passes).
- [ ] Replace historical storage layout / GUID placeholders with independent configurable device inputs.
- [ ] Complete a full fresh repartition, flash, and readback cycle using newly built tutorial outputs end-to-end.

## Features and Stability

- [ ] Verify torch brightness steps (currently only on/off toggle verified).
- [ ] Verify sustained runtime, power draw, full charging cycle, persistent user state edge cases, and teardown recovery.
- [ ] Independently validate audio output tuning/power, cellular/mobile data, and remaining unported hardware.

Current capabilities: [STATUS.md](../STATUS.md); evidence scope: [VALIDATION.md](../validation/VALIDATION.md).
