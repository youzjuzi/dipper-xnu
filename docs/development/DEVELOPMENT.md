# Mainline Development and Experiment Maintenance

**English** | [简体中文](../zh-CN/docs/development/DEVELOPMENT.md)

## What Lives on Mainline

Mainline comprises pinned upstream commits, adaptation patches, build/maintenance tools, file manifests, and documentation. `main` retains reviewed changes with clear validation scope, while feature and fix work happens on isolated branches. Doc or host-tool edits do not require hardware boots, though they must never alter hardware status claims.

The baseline started at `f784c8e` (2026-10-30), with capabilities and limits tracked in [STATUS](../STATUS.md) and [VALIDATION](../validation/VALIDATION.md).

`work/` holds the prepared upstream/build tree and `local/` holds private device configuration; a clean parent `git status` does not guarantee `work/` is unmodified. Currently `work/` is configured for local device testing and serves as the single sequential development tree—record diffs before changing tasks, keep verified artifacts, and never duplicate the entire source tree per task.

## Starting a Feature or Fix

From the repository root, inspect current state first (or run `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py --deep`):

```sh
git status --short
git branch -vv
sha256sum -c SHA256SUMS
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py --deep
```

Explain any checksum mismatch before refreshing `SHA256SUMS`. `origin/main` reflects the last local fetch, not necessarily live GitHub state.

Work one task per branch in the single repository and single `work/` tree; create new branches from a verified baseline and never switch tasks while unattributed edits remain in `work/`.

**Switching branches in the parent repository does not update gitignored `work/`.** Before switching away from a branch with code edits, export or back up all source changes and record the matching commit. Checking `git status` in the parent repository alone is insufficient.

When switching to a branch whose patches/inputs differ, confirm current `work/` edits are saved and align `work/` with the target branch before compiling—never resolve mismatches by deleting or overwriting `work/` blindly.

Create extra trees under workspace `experiments/<topic>/` only when explicitly needed for clean replay, from-scratch builds, or parallel isolation, and clean them up once verified.

## From Experiment to Committable Source

1. Edit sources inside `work/`, recording the problem, input commits, and scope; place each run's outputs in a new `work/runs/<run-id>/` subdirectory.
2. Build and run relevant host tests. Hardware verification is executed by the device owner per [Existing-Partition Testing](../install/EXISTING_INSTALL.md).
3. Export edits into `patches/*.patch`, update `source-manifest.json`, and review affected entries in `license-inventory.json` without altering inherited licenses.
4. Replay patches and verify the manifest on an isolated clean tree—local incremental builds alone do not prove reproducibility.
5. Update `STATUS`, `VALIDATION`, `CHANGELOG`, and `SHA256SUMS`, and review the diff.
6. Stage reviewed files explicitly by name on the task branch before merging into `main`; push/publish only with owner authorization.

Export diffs with `python3 tools/prepare/patchtool.py export --out work/runs/<run-id>/export` (read-only on `work/`; inspects unowned diffs, adds explicit entries via `--add COMPONENT:PATH`, restores loader identity placeholders, and aborts on privacy violations or unverified binaries). Pass `--write` only after reviewing the report and diffs, then review `license-inventory.json` and `SHA256SUMS`.

Clean verification and the full host suite run via `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite all --clean-replay --sanitize` (builds a disposable clean replay tree, runs `patchtool.py replay` and all tests, and cleans up on exit). For manual debugging, use `prepare.py --prepare --dest ../experiments/<topic>/clean` followed by `patchtool.py replay --tree ../experiments/<topic>/clean` and remove the temporary tree afterward. Before committing, run `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py check --refresh-sums` (`SHA256SUMS`, `patchtool.py scan`, `git diff --check`); fix all privacy errors and review warnings. See [Tools Index](../../tools/README.md#patch-export-and-replay).

## Patch-to-Source Mapping

Paths below are relative to `work/`:

| Patch Component | Source Directory | Baseline Notes |
| --- | --- | --- |
| `xnu-mi8` | `hackios/xnu-src/xnu-8796.121.2/` | Apple XNU + pinned HackiOS patch/files |
| `hackios-kernel` | `hackios/` | Pinned HackiOS commit scoped by manifest |
| `hackios-userland` | Userspace files in `hackios/` | Pinned `userland` repo overlay |
| `edk2-sdm845` | `edk2/` | Pinned `edk2` commit and gitlink |
| `simpleinit` | `edk2/GPLDrivers/Library/SimpleInit/` | Pinned submodule baseline |
| `unixnu` | `unixnu/` | Pinned UniXNU commit |

Components share physical directories, so never dump raw `git diff` into a single patch or export local loader GUIDs/identity fields. Register additions and deletions in `source-manifest.json`.

## Minimum Verification Matrix

| Change Type | Minimum Checks |
| --- | --- |
| Documentation | Local links/anchors, factual consistency, `SHA256SUMS` |
| Build / packaging scripts | Syntax, valid/failure input handling, no overwriting existing outputs |
| Drivers / userspace | Clean patch replay, manifest match, compilation, host tests, plus device validation (or explicit pending note) |
| Upstream lock bumps | Dedicated task updating `upstream.lock.json` and auditing all patches, interfaces, and licenses |

`SHA256SUMS` excludes itself. Refresh reviewed entries with `python3 -B tools/prepare/status.py check --refresh-sums` (never scan `work/`, `local/`, or `downloads/`). Run `git diff --check` and inspect `git diff --cached` before committing.

Full XNU `all` checks still fail; `build` passing does not claim `all` passes (see [BUILD](../build/BUILD.md)).

## Evidence and Rollback

Record source commit + unexported diffs, upstream lock, build commands, input/output SHA-256, private device config location, outcome, and verification level per experiment. Keep raw device logs in gitignored paths and sanitized summaries in public docs.

Never overwrite known-good boot artifacts. Prefer `git revert` over resetting shared history. Never delete a worktree based on `git status` alone without checking gitignored edits, configs, and logs first.

## Fixed Directory Layout

Keep one canonical location per artifact category rather than adding ad-hoc top-level dated copies:

| Artifact | Canonical Location |
| --- | --- |
| Main repository | `dipper-xnu/` |
| Shared SDK / toolchain inputs | Workspace `dependencies/` |
| Original downloaded archives | Workspace `downloads/` |
| Temporary verification / parallel tree (exception) | Workspace `experiments/<topic>/` (removed after use) |
| Prepared upstream trees and native builds | Repo `work/` |
| Per-run artifacts, commands, and raw logs | Repo `work/runs/YYYYMMDD-<topic>-NN/` (never overwrite old runs) |
| Private device configuration | Repo `local/` (`local/wifi-mac` path preserved) |
| Pre-release review records | Repo `local/reviews/YYYYMMDD-<topic>-NN/` |
| Pre-edit recovery backups | Repo `local/backups/YYYYMMDD-<topic>-NN/` |
| Reusable tools | Repo `tools/` (one-off scripts stay in run directories) |
| Public conclusions and status | Repo `docs/` (single `STATUS.md`) |

The deprecated top-level `sources/` directory has been removed and must not be recreated. Do not append daily work to workspace `archive/20261030/` or the legacy MI8-IOS workspace. Expired `experiments/` verification trees and duplicate `work/release/` images are not retained; use `tools/build/build-payload.py --link-inputs` for payloads and `python3 -B tools/prepare/status.py prune-runs --apply` for periodic run-directory cleanup.

## Tool Categories

`tools/` uses `prepare/`, `build/`, `partition/`, and `tests/` (see [Tools Index](../../tools/README.md)); keep `tools/build/cc-gnu17/cc` in place and place new scripts in the matching category rather than `tools/` root.

## `local/` Management Rules

`local/` stores private device configs, provenance notes, recovery backups, and reviews. Preserve `local/wifi-mac` and legacy backup paths; file new items under `devices/<alias>/`, `provenance/<component>/`, `backups/YYYYMMDD-<topic>-NN/`, or `reviews/YYYYMMDD-<topic>-NN/`, registering each group in `local/index.json` (without storing secret values). Never track `local/` in Git or `SHA256SUMS`.

## Run Records and Handoff

Create a fresh `work/runs/YYYYMMDD-<topic>-NN/` per round with a short README, exact commands, logs, source commit + diffs, and artifact checksums.

Handoff reading order: `AGENTS.md` -> `docs/README.md` -> `STATUS.md` -> this document. Update the handoff section below in place at the end of each task without creating parallel status files or copying private logs into public docs.

### Current Development Handoff (2026-11-19 — Re-verify on Pickup)

- **Mainline & branch state**: `feat/gpu-flush-zerocopy` builds atop `main` with Adreno 630 GMEM enablement (`MSM_PARAM_GMEM_BASE = 0x00100000ull`), `fb_native=2` 4-slot WC zero-copy scanout pool + non-copy `evictSurface()` hold flags + TE wait hint (`MiniIOFlipWaitHintUs`) + `gpu_push_ms=100`, O(1) GPU SMMU L2/L3 table lookup (`keep_l2_virt`/`keep_l3_virt`) + batched segment `map_range`/`unmap` (`redwood_gpu_map_range`/`mi8_gpu_map_range`) + fast spin-then-sleep `keep_tlb()` + `kRedwoodDescribe` early return, and updated `dipper` defaults (`fb_native=2`, `caenv=FD_MESA_DEBUG=sysmem` removed, `33` defaults in `pe_bootargs.c`).
- **`work/` unexported state**: `xnuloader/loader.c` differs only in local device identity fields (normalizes cleanly against `source-manifest.json`); **`0` manifest diffs remain** after exporting into `patches/{xnu-mi8,hackios-kernel,hackios-userland}.patch`, `license-inventory.json` matches all `105` manifest entries, and original published core source/tool files carry `Copyright (c) 2026 yanei` without modifying third-party or upstream-derived files.
- **Build & verification state**: Incremental kernel (`mach.development.bcm2837`), `test-boot-defaults.py` (`512` assertions, `33` defaults), clean patch replay, full host regression suite (`PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite all --clean-replay --sanitize`), and `status.py check` pass. Four 300 s RAM-boot device runs (`zc-sysmem`, `zc-gmem-prof`, `zc-gmem-step3`, `zc-gmem-step4`) verified `5698/5700` zero-copy flips (`6.87 us` avg flip), `103–180 us` `IOSurfaces taken as buffers`, `9.88 ms` total / `0.20 ms` max submit `lock`, and `0` panics or faults. Baseband `halt port modem` still does not idle on warm stop, so full reboot remains required between modem runs.
- **Next steps**: Optional zero-override default-bootargs smoke boot (cold/warm), remaining Route 2 scheduling/decode items (render-thread big-core affinity, optional `inject.c` kernelization / NV12 Safari video fix), or Route 3 hardware features (`QMI` + `IPA` cellular data, `SLIMbus` + `WCD9340` mic input, or Adreno 630 native Metal).

Follow `docs/README.md` for all doc placements (`development/`, `build/`, `install/`, `validation/`, `legal/`, and `zh-CN/` mirrors); never flatten new docs into `docs/` root.
