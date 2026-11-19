# Tools Index

**English** | [简体中文](../docs/zh-CN/tools/README.md)

Run commands from the repository root. Public tools are grouped by purpose; local configurations stay in `local/` and run outputs stay in `work/runs/`. Source copies, firmware, system images, and one-off per-run scripts do not belong here.

| Directory | Purpose | Entry Points |
| --- | --- | --- |
| `prepare/` | Pinned source preparation, patch export/replay/scan, workspace status/cleanup, SDK checks, IPSW extraction | [prepare.py](prepare/prepare.py), [patchtool.py](prepare/patchtool.py), [status.py](prepare/status.py), [check-sdk.py](prepare/check-sdk.py), [prepare-ios.py](prepare/prepare-ios.py) |
| `build/` | Kernel, loader/UEFI, and userspace builds; `darwin.img` and payload packaging | [build-kernel.sh](build/build-kernel.sh), [build-loader-uefi.sh](build/build-loader-uefi.sh), [build-userland.sh](build/build-userland.sh), [build-payload.py](build/build-payload.py), [pack-darwin.py](build/pack-darwin.py) |
| `partition/` | Offline GPT partition/restore plan generation and readback checks | [partition-darwin.py](partition/partition-darwin.py), [restore-android-layout.py](partition/restore-android-layout.py) |
| `tests/` | Unified host test runner, clean replay, synthetic GPT, CLI, audio, and workflow tests | [run-tests.py](tests/run-tests.py), [test-patchtool.py](tests/test-patchtool.py), [test-workflow-tools.py](tests/test-workflow-tools.py), [test-partition-darwin.py](tests/test-partition-darwin.py), [test-restore-android-layout.py](tests/test-restore-android-layout.py), [device-log.py](tests/device-log.py) |

`build/cc-gnu17/cc` is a compiler compatibility wrapper kept in place for the UEFI build entry point. Partition tools generate host plans only; generated device scripts are reviewed and run by the owner and never touch a phone automatically.

## Usage Entry Points

- [Build Guide](../docs/build/BUILD.md), [External Inputs](../docs/build/INPUTS.md), [Userspace and Packaging](../docs/build/USERLAND.md).
- [Partitioning, Flashing & Rollback](../docs/install/INSTALL.md), [Configuration, Rebuild & Boot](../docs/install/STARTUP.md).
- Host regression suite:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite fast
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/run-tests.py --suite all --clean-replay --sanitize
```

`run-tests.py` injects `PYTHONDONTWRITEBYTECODE=1` into child processes and auto-discovers TAS2557 reference fixtures under `local/devices/*/audio-android/`. Passing `--clean-replay` builds a disposable clean tree from pinned Git objects, runs `patchtool.py replay` and the selected tests, and deletes the temporary tree on exit. Standalone suites such as `tools/tests/test-workflow-tools.py`, `test-patchtool.py`, `test-restore-android-layout.py`, and `test-partition-darwin.py` can also be invoked directly.

## Workspace Status, Kernel Build, and Daily Checks

`tools/prepare/status.py` provides daily status, diff, hygiene, and cleanup commands without writing Python bytecode:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py --deep
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py diff
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py check --refresh-sums
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/prepare/status.py prune-runs [--apply]
```

- `status` (default subcommand): reports Git branch and tracked changes, verifies `SHA256SUMS`, detects `THEOS`, diffs `work/` against `source-manifest.json` (normalizing local identity placeholders in `xnuloader/loader.c` to avoid false positives), and summarizes kernel/UEFI/userspace artifact status. Adding `--deep` scans unowned changes (collapsing known build symlinks and auxiliary submodules unless `--all-unowned` is passed).
- `diff`: generates unified diffs against an offline reconstructed public reference; output passes through privacy scanning first and redacts files matching error patterns.
- `check`: verifies staged paths exclude ignored directories, checks `SHA256SUMS` matches `git ls-files` completely, runs privacy scan (`0` errors), and runs `git diff --check`; `--refresh-sums` updates `SHA256SUMS` from tracked files.
- `prune-runs`: runs in dry-run mode by default; with `--apply`, removes leftover `replay-tree*` directories and build intermediates (`.o`, `.cpo`, `.d`, `.a`, `*.dSYM`, `mach.*.unstripped*`, while preserving `mach.development.bcm2837` and `kernel.macho`) inside `obj/`, `sym/`, `dst/`, hard-links identical large images (`.apfs`, `.img`, `.macho`, `.efi`) on the same filesystem, and logs deleted entries to `_pruned-YYYYMMDD.tsv`.

`bash tools/build/build-kernel.sh [-j N] [--with-ath10k] [--out DIR]` runs from the repository root, auto-detects `THEOS` (`THEOS` env, `local/theos`, or `../dependencies/theos`), passes `SOURCE_DIR="$XNU_SRC"` explicitly to build incrementally in the standard `BUILD/` directory, and optionally copies `kernel.macho`, `kernel.sha256`, and `kernel-build.log` to `--out DIR`. `build-userland.sh` shares the same `THEOS` fallback detection, and `build-payload.py --link-inputs` hard-links read-only inputs on the same filesystem to save disk space.

`PYTHONDONTWRITEBYTECODE=1 python3 -B tools/tests/device-log.py {snapshot,watch,stop} --out <path>` reads logs (`oem log` + `get_staged`) or requests an orderly return (`oem stop`) only after verifying `getvar product == xnuloader`; `watch` streams incremental lines while handling loader ring wrap to avoid losing middle-session logs to the final 32 KiB tail cap.

## Patch Export and Replay

Tools depend only on the Python standard library and Git. `export` reads `work/` only, extracts pinned commits from local Git objects, and reuses `prepare.py`'s overlay flow in a temporary directory without network access. The XNU baseline is Apple XNU plus HackiOS, not an inner repo `HEAD`. Shared directories are split by component according to `source-manifest.json`.

```sh
python3 tools/prepare/patchtool.py export --out work/runs/<run-id>/export
python3 tools/prepare/prepare.py --prepare --dest ../experiments/patchtool/clean
python3 tools/prepare/patchtool.py replay --tree ../experiments/patchtool/clean
python3 tools/prepare/patchtool.py scan
```

The export directory must not already exist and receives component patches, `source-manifest.json`, and `report.json`. The report lists unowned changes, deletions, and explicit additions, plus initialized submodule changes and gitlinks (auxiliary submodules missing pinned objects are reported without fetching or copying their files; unowned files are never added automatically). `--component NAME` is repeatable; register additions with `--add COMPONENT:PATH` (or `--add PATH` when one component is selected). Deletions are recorded with null digest and mode. Known loader identity fields are restored to the existing public placeholders; other privacy hits or unverified binary files abort export. Patches preserve exact file bytes, use LF metadata without timestamps or absolute paths, and generate deterministic per-file Git diffs sorted by path.

Passing `--write` replaces the repository patches and selected component manifest entries; disabled by default. Review the report, diff, `license-inventory.json`, and `SHA256SUMS` before adopting changes. Ignored build junk patterns do not authorize deleting unrelated unowned files.

`replay` validates a separate clean `prepare.py` output tree. It verifies manifest digests and full file modes on the input tree, reconstructs the baseline from pinned objects, runs `git apply --check` and `git apply` per patch, and verifies post-replay digests, modes, and unowned diffs without mutating the input tree twice. Legacy unified patches lack file modes and fall back to the manifest; modern Git diffs also verify executable bits. `--patch-dir DIR` checks an export bundle against an aligned input tree. Failure excerpts are capped at 50 lines, and `prepare.py --dest` refuses to overwrite existing paths.

`scan [PATH ...]` checks Git-tracked files and `patches/*.patch` by default, printing only file path, line number, and severity/category without echoing matched values. Private paths, non-allowed GUIDs, non-zero MACs, and serial numbers are `error`s; process IDs and attributions are `warning`s. The allowlist covers only public protocol/type GUIDs, fixed upstream examples, and synthetic test placeholders documented in code. Scanning is format hygiene, not a substitute for human privacy and license review.

## Platform Boot-Default Host Test

`python3 tools/tests/test-boot-defaults.py` compiles the actual ARM boot-default table and XNU parser from the prepared tree against synthetic device-tree stubs to verify config equivalence, platform isolation, and override semantics (requires a host C compiler). `--tree` selects a clean XNU tree and `--old-cmdline` reads a full cmdline file while masking any MAC to zero without printing inputs. It never touches a device. See [Startup Guide](../docs/install/STARTUP.md#short-dipper-boot-arguments-and-defaults) for public short boot-args.

## ADSP GLINK/APR Host Tests

`python3 tools/tests/test-mi8-audio-apr.py` compiles the real GLINK/APR implementation under `MI8_GLINK_HOST_TEST` against a synthetic SMEM ring FIFO peer, testing raw open, fragmentation, intent requests/close, malformed APR packet rejection, full service version list, and default IPCRTR/QRTR compatibility. `python3 tools/tests/test-mi8-rproc-state.py` extracts the real remoteproc state, lookup, scheduling, and mutex paths to check ADSP/modem isolation, nested queries, failure teardown, and shared transaction locking. Both require a host C compiler and `pthread`, output `SELFTEST PASS n/n`, and accept `--tree` pointing to the prepared root containing `hackios/`. These checks never contact a device and cannot replace real firmware channel, APR, or shutdown verification.

## Bounded Audio Ring Host Tests

`python3 tools/tests/test-mi8-audio-ring.py` compiles the real SPSC ring and PCM/AFE/APR/GLINK path, checking 100k seeded operations, 2M-frame concurrent ordering, gate conservation, 6000 zero-DMA periods, and timeout teardown (`--sanitize` enables ASan/UBSan, `--tsan` enables TSan independently, `--tree` selects a clean prepared tree). Together with `test-mi8-audio-sink.py`, it verifies cdev locking, parameter conflicts, and loader tail-log summaries without device access.

## Path Migration Note (2026-10-31)

Scripts previously at `tools/` root were moved into the four category directories above without renaming files or keeping duplicate wrappers. Historical logs and `work/runs/` entries keep their original commands; new runs should use the categorized paths and a fresh run directory.

## Audio Worker Stack Budget

`python3 tools/tests/check-mi8-audio-stack.py <OBJROOT>/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT --json <report>` disassembles linked `mi8_*.o` objects, sums saved registers and local stack allocations, and builds a conservative call graph over direct calls, tail calls, and documented ops callbacks. Single frames > 1 KiB warn; worker deepest paths > 8 KiB fail; dynamic SP, recursion cycles, or unaudited indirect calls are rejected. The SMEM lookup snapshot frame is documented as a justified single-frame exception still counted in total depth. The remaining 8 KiB reserves headroom for kernel services, preemption, and interrupts, though this static bound is not a whole-kernel formal proof; objects must match the delivered kernel.

## Bounded Audible Clip Host Test

`python3 tools/tests/test-mi8-audio-clip.py --firmware <fw> --reference <ref.txt> --metadata <meta.json>` links the actual PCM, GLINK/APR, and TAS drivers to validate the pipeline, trigger, 150-period window, error guards, warmup/shutdown delays, ring conservation, and full worker exit (`--sanitize` and `--tree` supported). Ring concurrency continues to be tested by `test-mi8-audio-ring.py --tsan`. Stack checks cover both the original and clip workers, warning on > 1 KiB frames on other threads without mixing them into audio thread depth.

## Session Audio Host Tests

`python3 tools/tests/test-mi8-audio-session.py --firmware <fw> --reference <ref.txt> --metadata <meta.json>` validates the real session feeder, TAS control thread, ring/GLINK/APR path, and word-aligned I2C peer across multiple wake/mute cycles, silence/duration/count limits, read-only coefficient checks, health failures, submit guards, 8-block zero tails, and worker teardown. Supports `--threads` (dual threads with 0/50/500 ms control delays), `--tsan`, `--sanitize`, and `--tree`.

`test-mi8-audio-session-join.py` extracts the native join implementation to verify the 300 ms timeout, reset-low fallback, idempotent failure, and thread retention until full reboot. Stack checks cover both the session feeder and TAS control threads.

`python3 tools/tests/test-mi8-audio-panic.py [--tree <clean-tree>]` extracts the native panic hook and argument parser to verify held-only behavior, single MMIO write, repeat latch, 84 argument combinations, and triggering 1 s after first LIVE (host simulates MMIO with normal memory and replaces ARM barriers; also statically checks XNU hook and panic buffer entry; cannot replace real panic or audio cutoff verification).

`test-mi8-audio-coexist.py [--tree <tree>] [--sanitize|--tsan]` extracts the short-lock bridge, Wi-Fi mapping, resource ownership, and dependency waits under real thread contention (unmap is test-model only; device driver keeps append-only mappings). `test-mi8-audio-session.py --long` simulates 300 s / 15000 periods and combines with `--sanitize` or `--tsan`.

`build-payload.py --kernel <mach> --wifi --bluetooth --seconds 420 --output <new-dir>` selects the current kernel explicitly (keeping the default path if omitted); `--flashboot <img >` overrides the amp firmware boot image while enforcing the same permission and Bluetooth firmware checks. Defaults enable `audio=5`, `audio_seconds=0` (resident), and `0 dB`; `--wifi` builds need no extra audio flags, `--no-audio` disables audio explicitly, and `--bluetooth`/`--peripherals` remain compatibility no-ops (former still requires `--wifi`; omitting `--wifi` forces `bt=0` and disables the Wi-Fi side).

Session regressions support `--level -30|-24|-20|-12|-6|0` (plus invalid-value fallback) and `--long` (300 s) covering independent submit guards and LIVE underflow accounting; count-sink regressions support `--tsan`, covering concurrent audio writes with LIVE generation publishing, source clipping and intra-window HAL gaps, rolling worker tail logs, and the loader's final 32 KiB.

`test-mi8-audio-session-log.py [--tree <tree>] [--sanitize]` exercises real `audio=5` init flags and the PCM->rproc->loader logging chain, reproducing the old 20-line cap exhaustion at 195 s and verifying `play`, `asm close`, and summary remain in the final 32 KiB after 300 s / 200 wakes. Session tests also verify all six coefficient levels, all 65536 mono inputs, 499/500 (write-wake silence) and 1499/1500 (other silence) zero periods, WARMING/first-LIVE trimming with conservation, and TSan consumer trimming plus producer concurrency.

Session regressions further verify `OFF_READY` read-only `Y` pre-verification, pre-verified wake I2C transaction bounds with zero coefficient reads, re-verification after cache invalidation, the 200 ms health retry bound, and immediate alarm latching across simulated zero-write HAL wakes, `idle_wakes`, 10/30 s silence, and 2400-frame fade-in. The fast-wake model uses the existing 3 µs bit-bang half-period, zero extra stretch/MMIO overhead, and 2 ms polling (~29.6 ms normal path; does not replace device timing).

`test-mi8-default-peripherals.py [--tree <tree>]` extracts real BT entry and loader peripheral setup to verify 64 default/explicit dependency combinations, `bt=1..6`, explicit disable, and non-`dipper` isolation under ASan/UBSan. `test-boot-defaults.py --package-cmdline <file>` verifies candidate 7 defaults via the native parser without printing MACs against an independently written reference profile.

`test-mi8-audio-session.py --resident` runs a fixed-array simulation spanning 47976 virtual seconds, 1000 random short clips, and three 21-minute continuous streams through real PCM/GLINK/APR and the I2C model (supports `--sanitize`), verifying post-boot native allocation stays at 27512 bytes, returns to zero on exit, and preserves the fixed tail log. Resident mode adds independent property rejection tests while keeping bounded 900 s / 45000 / 201 and `--tsan`/`--long` checks intact.
