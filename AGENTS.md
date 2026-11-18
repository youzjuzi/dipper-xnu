# dipper-xnu Development Conventions

**English** | [简体中文](docs/zh-CN/AGENTS.md)

## Getting Started

- This repository is the single mainline development entry point. First run `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py --deep` to inspect the active Git branch, checksums, build artifacts, and any unexported changes in `work/` (automatically normalizing local identity fields in `loader.c`), then read `docs/README.md`, `docs/STATUS.md`, and `docs/development/DEVELOPMENT.md` (including the current handoff section). If local indices or private planning files exist under `local/`, consult them read-only only and never copy private paths, internal IDs, or private notes into public files or commits.
- Standard daily commands: inspect unexported diffs with `python3 -B tools/prepare/status.py diff`; run incremental kernel builds with `bash tools/build/build-kernel.sh`; run host regressions and disposable clean-replay verification with `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite all --clean-replay`; run pre-commit verification with `python3 -B tools/prepare/status.py check --refresh-sums`.
- The reproducible deliverable is pinned upstream commits + `patches/` + `source-manifest.json` + build tools, not `work/` by itself.
- Although `work/` and `local/` are gitignored, they may hold unexported source changes, local device configurations, firmware blobs, and unique test evidence. Never wipe, overwrite, or reset their inner repositories by default.
- The legacy MI8-IOS workspace is historical reference only. Never mix legacy boot scripts or legacy artifacts with the current reproducible tree.

## Modifying and Verifying

- Keep each change focused on one problem; use one branch per task and develop sequentially inside this repository's single `work/` tree. Never duplicate the full source tree per task; create a fresh subdirectory under `work/runs/` for each test round.
- After modifying upstream-derived sources, export the corresponding patches, update `source-manifest.json`, and review affected entries in `license-inventory.json`. Never claim a fix is committed when it only exists inside gitignored directories.
- Export patches against the proper baseline for each component and review the file list first. XNU `dipper` patches apply on top of the HackiOS baseline, not directly on stock Apple XNU.
- Use `tools/prepare/patchtool.py` for patch export, clean replay, and privacy scanning (see `tools/README.md`). Always export into a new directory under `work/runs/` for review first; never hand-edit patches or run raw `git diff` across `work/`.
- Private GUIDs, MACs, passwords, firmware, SDKs, system images, and raw device logs must never enter patches or commits. Public `loader.c` retains placeholder values while device-specific configuration lives in `local/`.
- Verify changes according to scope: check links and checksums for docs; verify clean patch replay, compilation, and host regressions for code. Hardware status claims must rely solely on real device evidence.
- Meaningful code changes must update `docs/STATUS.md` and `docs/validation/VALIDATION.md`, user-visible changes go into `CHANGELOG.md`, and `SHA256SUMS` must be maintained.
- Never run `git add .`; stage reviewed files explicitly by name. Never push, publish, or create a release without owner authorization.

## Device and Inputs

- Builds and host checks must never touch a phone automatically. Device operations are performed by the owner; never run flash, erase, partition, block-write, or unlock commands autonomously.
- If any expected SHA-256 mismatches, stop immediately rather than swapping versions or bypassing checks.
- GPU/baseband teardown recovery is still incomplete; perform a full reboot between device test rounds instead of reusing a dirty state.
- Preserve existing artifacts and write each round to a new output directory; host test passes never replace physical hardware verification.

## Directory Discipline

- Strictly follow the fixed directory layout in `docs/development/DEVELOPMENT.md`. Do not add top-level directories for existing categories; document and update the layout table before introducing a new category.
- Use workspace-level `experiments/<topic>/` only for clean replay/rebuild verification or explicit parallel isolation (clean up after verification); place daily run logs and artifacts in `work/runs/YYYYMMDD-<topic>-NN/`, and pre-release reviews in `local/reviews/YYYYMMDD-<topic>/`.
- The deprecated top-level `sources/` directory has been removed and must not be recreated; do not append daily work to workspace `archive/20261030/` logs or the legacy MI8-IOS workspace, and never maintain a second release source copy.
- Do not move existing build trees or inputs purely for cosmetic cleanup. Any path change must update scripts, docs, and verification together; reusable scripts belong under `tools/`, while one-off scripts stay in their run directories.
- `local/` follows the local management rules in `DEVELOPMENT.md`: preserve existing config paths (`local/wifi-mac` is read directly by build scripts), file new entries under `devices/`, `provenance/`, `backups/`, or `reviews/`, and keep `local/index.json` synchronized without dumping files in `local/` root. Run artifacts belong in `work/runs/`, not `local/`.

## Single Source Tree and Handoff

- Switching branches in the parent repository does not change gitignored `work/`. Export and save all source diffs before switching tasks; after switching branches, verify `work/` matches the target commit before building. Never resolve mismatches by overwriting, wiping, or cloning a duplicate tree.
- The "Current Development Handoff" section in `docs/development/DEVELOPMENT.md` is the single live status entry point; update task, branch/commit, unexported changes, artifact evidence, and next steps at handoff. `docs/STATUS.md` tracks product capabilities without duplicating a parallel status doc.
- Documentation follows `docs/README.md`: `development/`, `build/`, `install/`, `validation/`, `legal/`, with Chinese mirrors under `docs/zh-CN/`. Do not flatten new docs into `docs/` root.
- `tools/` uses fixed categories `prepare/`, `build/`, `partition/`, and `tests/` (see `tools/README.md`). Legacy runs preserve their historical commands; current tutorials use the categorized paths.
- Public home pages and `build/`/`install/` tutorials use a reader perspective with standard placeholder paths, pinned versions, and explicit validation boundaries—no private experiment paths, chat references, or internal round numbers. Detailed procedures and evidence indices belong in `development/` and `validation/` without hiding unverified gaps.
