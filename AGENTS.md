# Project orientation

`nsp-dawrin` is an experimental cross-platform compatibility runtime and Flutter desktop launcher. Shared host services and package preparation support macOS, Windows and Linux; the native ARM64 executor and Metal renderer currently target macOS 26+. Guest CPU instructions run natively after NSO rewriting. The vendored shader library translates GPU instructions offline; it is not a CPU emulator. Unicorn is used only in isolated instruction tests.

Write code, comments, diagnostics and documentation in English. Keep the README focused on installation, usage and features. Put implementation caveats and agent guidance here or in technical docs. New project work uses GPL-3.0-or-later. Preserve upstream MIT notices and third-party licenses.

Prioritize the native launcher for application packages and associated DLC.
Standalone converted application export and installer generation are deferred.
Keep implemented package formats and content-loading capabilities distinct from
the roadmap; use docs/content-loading.md and docs/runtime-compatibility.md for current boundaries.

## Ownership and data

Keep source branding neutral; preserve required ABI symbol spellings and attribution. Never commit packages, game assets, firmware, keys, saves or captured shaders. Runtime screenshots remain private. User-authorized documentation captures under `docs/screenshots/` may show only this project's application UI and original test fixtures; exclude personal desktop content, local paths and real application assets. Runtime data belongs outside the checkout. Treat package paths and local key locations as private. Do not print secret values. Preserve saves and the user's original packages during debugging.

Inspect processes and mounts before cleanup. A work directory can contain live network mounts: never recursively delete its parent. Use the ignored project-root `build/` directory for build artifacts: `build/obj`, `build/bin`, `build/venv`, and `build/dotnet`. Retain the built translator needed by the runtime. Clean only identified inactive generated artifacts, not entire workspaces or shared caches.

## Source map

| Module | Responsibility |
| --- | --- |
| `tools/content.py`, `package.py` | NSP/XCI containers, CNMT selection, BKTR ranges, base/update/DLC resources |
| `src/macos/package_fs.m`, `content.h`, `storage.*` | Native virtual resource reads, content inventory and persistent save allocation |
| `src/backend/`, `src/compat/clock.*` | Portable host operations and shared clock semantics |
| `src/compat/ipc.*`, `src/host/hle_ipc.c` | Bounded HIPC/CMIF transport and SDK-independent service registry |
| `tools/patch_nso.py` | x18/TLS virtualization, guest SVC/timer gates, branch rewriting |
| `src/host/loader.c` | Module layout, relocation, symbol lookup and forced host imports |
| `src/host/hle_*.c` | Guest service implementations and host bridges |
| `src/macos/host.c` | Native entry, process setup and fault reporting |
| `src/macos/controller.*`, `input.c`, `window.m` | Controller selection and normalization, guest input sampling, menus and mouse touch |
| `src/macos/settings.*`, `settings_ui.*` | Validated persistent preferences and native settings UI |
| `src/gfx/nvn/hle_nvn.c` | NVN ABI and command recording |
| `src/gfx/nvn/nvn_mtl.m` | Metal replay, shader loading, resource binding and pipeline state |
| `tools/nsp_runtime/` | Engine, decoder, facts, translation and cache contracts |
| `tools/control.py`, `ocr.py`, `src/macos/control.c` | Local control socket, OCR regions and runtime status |
| `tools/run_with_report.py`, `crash_report.py`, `crash_report.m` | Session supervision, shareable diagnostics and independent report UI |

Read [docs/interfaces.md](docs/interfaces.md) before extending engine or shader support. Register engines explicitly in `Registry`. Engine adapters consume `ResourceReader` and emit format-tagged `ShaderBlob` records. GPU decoders validate those records. `ShaderFactsProvider` supplies metadata that instructions alone cannot establish. Translation and host shader generation have separate backend protocols. Do not add game-name conditionals to the common pipeline.

## Bring-up workflow for another application

1. Identify the package revision and existing session. Check available disk space, mounted package path, key generation and active runner before preparation. Use the supplied local keys; missing decryption keys are a package prerequisite, not a shader bug.
2. Run package preparation and check resource counts. Only executable modules and an index should be materialized; resource payloads stay in the package. Compare bounded native reads against independent reference bytes when changing the filesystem layer.
3. Rewrite every executable module actually present. The loader supports `main`, optional subsdk modules and `sdk`, with a finite module-count guard. An unsupported instruction must stop rewriting. Inspect the instruction and surrounding data flow, implement a generic transformation, and prove argument, register, stack, flag and return-address semantics with focused instruction tests. Never bypass the rewriter assertion or patch a title offset blindly.
4. Default to runtime capture and first-use translation. For optional prewarming, select or implement an engine adapter, run `scan_shaders.py`, and inspect `scan-report.json`. Validate control/code extents and compare key sets on regressions. Empty program tables are valid; unknown layouts and stages must remain visible.
5. Run `compile_pending_shaders.py`. Review `translation-failures.json`, `binding-failures.json`, `facts-report.json` and `build-report.json`. Convert resource reflection to explicit slots; a storage buffer is not an ordinary uniform buffer. Validate stage-specific driver tables and reject unknown mappings.
6. Compile generated MSL with the native Metal API before runtime acceptance. Launch one session at a time with a bounded timeout and a unique control socket/log path. Check `status` for increasing frames, package reads, shader loads and zero shader failures. Use OCR to confirm application state. One loading frame is not proof of a working menu.
7. Exercise input and a basic menu transition through CLI/API. If testing save/load, preserve existing saves and verify a successful in-application save followed by reload; an initialized save file or a button click alone is insufficient.
8. Record separate outcomes for decryption, rewrite, scanning, translation, actual Metal compilation, shader loading, rendered frames, interaction and save/load. State unresolved failures with their log evidence. Do not equate MSL generation with successful rendering or general compatibility.

## Shader cache rules

The chain identity hashes pipeline source, binding source, actual compiler DLLs, SPIRV-Cross, options and external facts. The translator checks its embedded source fingerprint. Python receipts track job/code inputs; host artifacts track SPIR-V, reflection and constants. The launcher and native loader must use the same chain. Never copy an old cache into a new chain directory merely to make a test pass.

MSL is compiled by the installed Metal framework. The system's compilation cache is distinct from this project's conversion cache. Pipeline states also depend on runtime state. Preserve observed first-use order for future warm-up work. Use bounded batches and modest concurrency; prefer cached CLI/API checks over repeated screenshots or full rescans. A shader capture can add runtime variants that a static engine scan did not find.

## Known gaps and diagnostic boundaries

- Content loading supports NSP/XCI secure content, base/update selection, basic BKTR patch ranges and separate DLC mounts. Personalized tickets, sparse/compressed storage and deeper BKTR trees need adapters.
- The asset adapter currently understands serialized assets from one engine family. GPU decoding handles validated vertex/fragment layouts. Additional engines and compute/tessellation coverage need adapters or decoder/backend work.
- Bound texture/image/vertex/output facts are collected at replay. Compute descriptors and unobserved resource types still require explicit metadata; translation with missing facts does not establish correct rendering.
- Guest exception unwinding depends on valid module metadata and matching guest frame descriptions. Diagnose the first failure, not only the final abort.
- Media allocation and codec services are not fully covered. A successful shader load followed by a media-thread crash must remain a failed startup result; do not bypass the media call or mark it playable.
- Some inherited graphics optimizations and diagnostics retain assumptions from the upstream application. Audit them before enabling optimizations on another application; the launcher disables the optional tile-specific path by default.
- Input currently exposes one controller and one touch contact. Motion, vibration and simultaneous multiplayer need implementation. Virtual controller and native mouse tests do not establish behavior on physical controllers.
- OCR reports text rectangles, not semantic UI controls. IDs expire and must not be reused across process restarts.
- Unbounded play requires an explicit `DM_TIMEOUT=0`; use finite timeouts for automated bring-up and terminate only the process owned by the current test.

## Verification and publication

Run `make -j4` for the native host and `dotnet build tools/shader_translate -c Release --artifacts-path build/dotnet` when changing translator code. Use `build/venv` for `python -m unittest discover -s tests -p 'test_*.py' -v`. Instruction tests require Unicorn; scanner tests require the dependencies in `requirements.txt`. Use targeted native harnesses in `tests/` for controller, mouse, package, unwind and Metal checks.

Run only checks relevant to the change, then stop repeating successful checks unless evidence changes. Keep game-specific validation records outside the repository. Stage explicit source paths, inspect the diff for private data and generated files, and verify repository visibility and remote SHA after an authorized push. If the user requests unsigned commits, use `git -c commit.gpgsign=false commit`; do not alter global signing preferences.

Before changing repository visibility, audit all reachable Git history as well as
the current tree for secrets and application artifacts. Include remote refs,
release assets and workflow artifacts. Report findings without printing secret
values. Preserve dependency copyrights and complete license notices.

Crash diagnostics use an explicit field allowlist; see
[docs/crash-reporting.md](docs/crash-reporting.md). Never put raw log lines or
package paths into an issue draft. Test previews offline without submitting
issues, opening draft URLs or replacing the user's clipboard.

## Attribution when adding dependencies

Record each adopted library, copied algorithm, header, generated definition, and external build/test tool in `docs/DEPENDENCIES.md` in the same commit that introduces it. Include author, source URL, version or revision, local location, purpose, license, and any local modifications. Preserve complete notices alongside vendored code or under `LICENSES/`; a README thank-you is not a substitute for them. Keep concise acknowledgments in the README.

Audit the actual build graph, including Python and NuGet transitive dependencies, when packaging a binary release. Ship the applicable license texts and notices with bundled components. Distinguish original upstream work, local adaptations, and independent contributors; do not copy another author's apology or claim an upstream contributor worked directly on this project. Do not label an adapted subset as unmodified.

After completing and validating a coherent feature or fix, make one focused unsigned commit with its relevant checks. Stage explicit paths; keep unrelated work for its own commit. Commit attribution and license changes independently from runtime features.

## macOS settings and input

Initialize settings before starting guest threads. Preference snapshots, updates, controller discovery/selection and UI actions run on the main thread; the control socket dispatches them there. The active guest mode is immutable during a session. Resolution controls the Metal drawable, not application-internal render targets. Do not fake live mode switching without implementing the guest notification and reconfiguration protocol.

Keep CLI-injected input separate from held keyboard keys; recompute keyboard buttons from all held physical keys so releasing one alias does not release another. Clear held input on focus loss and preference changes. Controller device IDs identify live framework objects; persisted vendor/category preferences identify a model, not a guaranteed physical-device serial number. An explicit device disconnect must not silently transfer held input to another identical controller.

`tests/settings.m` checks persistence across processes and virtual controller selection. `tests/settings_ui.m` exercises real AppKit menu actions, key capture, focus release, drawable resolution and fullscreen transitions. Run both with a fresh `NSP_SETTINGS_PATH` outside the checkout; this keeps the user's preferences unchanged. Full-screen tests need an unlocked foreground macOS session. `--skip-fullscreen` runs the independent menu/input/resolution checks while explicitly reporting that skip. Reuse `build/bin` for their small executables.

Run `tools/service_catalog.py --check` before startup validation to detect binding conflicts. Use `tools/validate_matrix.py` to group failures by shared interface. See [runtime compatibility](docs/runtime-compatibility.md) for variant metadata, content loading and validation boundaries.

Per-game settings use a validated `DM_TITLE_ID`, partial overrides, and the same
validation/persistence path as global defaults. Keep editing scope distinct from
the immutable active guest mode. `tests/settings_profiles.m` runs isolated child
processes to check persistence and global inheritance; `tests/settings_ui.m`
checks the native scope/reset actions and CLI API. Use the synthetic IDs in
these tests, never actual package metadata in committed fixtures.

For service/backend work, read `docs/backend-architecture.md` and run the portable
CMake/CTest target in `build/services`. Keep OS headers out of `src/compat`; keep
guest ABI layouts out of `src/backend`. Do not confuse the portable service
library with a complete Windows/Linux execution or graphics backend.

Use `tests/fixture_app.py` for original synthetic NSP checks before commercial
application bring-up. Keep generated packages and keys outside the checkout.
Run `--native-host build/bin/nsp-dawrin --negative-control` for actual guest
execution; package/rewrite success alone must not be reported as native execution.

## Flutter desktop client

Read `docs/desktop-launcher.md` for GUI/API boundaries. Keep UI state independent
of transport through `LauncherApi`. Extend structured launcher methods rather
than assembling shell commands in widgets. Reuse content, settings, shader and
crash-report contracts. Never replace a failed launch with simulated success.
Use `tools/build_gui.py --test --build` to keep generated files and Pub downloads
under root `build/`. Platform runners derive from Flutter templates; preserve
notices and regenerate only after reviewing local window/entitlement changes.
