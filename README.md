# nsp-dawrin

An experimental native ARM64 application compatibility layer. Guest CPU instructions run directly after offline rewriting; host services and graphics are implemented locally. The current build targets macOS 26 or later on ARM64.

No application packages, game assets, firmware, keys, captured shaders, saves, or screenshots belong in this source tree. Keep all runtime data outside it. Third-party source retains its original license and required API names; this project does not claim affiliation with any platform or application vendor.

## Build

```sh
make -j4
python3 tools/build_app.py
```

Objects are shared in `../work/build/obj`; the runner is `../work/bin/nsp-dawrin`. The optional app bundle contains the runner and a local launcher, without application data. It currently requires this checkout to remain in place.

## Direct package resources

```sh
python3 tools/launch.py /path/application.nsp --keys /path/local.keys
```

Install `requirements.txt` in an external virtual environment first. The launcher caches the executable rewrite, resource index, and shader results under a title-specific directory in `~/Library/Caches/nsp-dawrin`. It reuses a completed preparation on later launches. Use `--cache-root /path/cache` to select another location, or `--prepare-only` to stop before execution. Preparation failures remain visible; compatibility is not guaranteed.

For an already prepared cache:

```sh
GAME_DIR=/path/cache DM_WINDOW=1 DM_TIMEOUT=0 ./run.sh
```

Base NSP packages using supported plain or CTR sections can provide resources directly. Preparation caches executable modules and creates sparse directory-index entries; resource payloads remain in the original package. The package must remain accessible while running. A derived local key cache has mode 0600. XCI, personalized tickets, update merging, and all title compatibility are not yet supported. An extracted resource directory can still be used with an explicit `DM_TITLE_ID`.

## Input

The window accepts mouse press, drag, and release as a single touch contact. Coordinates scale with the window into the guest 1280 by 720 touch space. Losing focus releases touch and keyboard state and suppresses controller input.

Extended-profile controllers are discovered through the system framework. The first available controller occupies player slot zero; disconnecting clears its state and selects another available controller. Face buttons use physical positions: east maps to guest A, south to B, north to X, west to Y. Both sticks, stick clicks, direction pad, shoulders, triggers, and primary/secondary menu buttons are mapped. Sticks have a 15 percent deadzone. Motion, vibration, and multiple simultaneous players are not implemented.

Keyboard: Z/Space = A, X/Escape = B, A = X, S = Y, Return = primary menu, arrows = direction pad. The default handheld mode uses 720p; `DM_HANDHELD=0` requests 1080p console mode.

## Local control and OCR

```sh
python3 tools/control.py status
python3 tools/control.py state --game-dir /path/cache
python3 tools/control.py click 5 --game-dir /path/cache
python3 tools/control.py press A
python3 tools/control.py shot /path/frame.png
```

OCR returns text regions and touch coordinates, not verified UI controls. IDs expire after 60 seconds or a process restart. Recognition runs locally with a bounded CPU pipeline. The socket defaults to `/tmp/nsp-dawrin-<uid>.sock` and is restricted to its owner. Runtime status includes controller state, frame count, touch samples, and direct package read counters.

## Shader preparation

`tools/scan_shaders.py` scans supported serialized assets inside a package. `tools/compile_pending_shaders.py` translates captured or scanned shader data and reuses output only for the matching conversion chain and input fingerprint. Translation requires a local .NET 10 SDK, the offline translator, and `spirv-cross`. Build the translator with `dotnet build tools/shader_translate -c Release`. Set `DOTNET` if the SDK executable is outside PATH. The scanner requires `UnityPy`, `lz4`, and `cryptography`. Unsupported asset formats and shader stages remain explicit limitations; a scan is not proof that every runtime variant is covered. First-use compilation remains a fallback. Missing texture and other metadata is reported separately from conversion success. The current backend generates MSL; the native host compiles it through Metal at runtime.

See [Extension interfaces](docs/interfaces.md) for engine adapters, resource readers, shader facts providers, translation backends, and cache rules. Use `--engine auto` or an explicitly registered adapter on the scanner and launcher.

## Acknowledgments

Thanks to [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) for publishing the native compatibility implementation that made this project possible. Its ARM64 rewriting, host service implementation, NVN command recording and Metal replay, and Maxwell → SPIR-V → MSL translation pipeline form the foundation of this macOS work. Its explicit resource reflection and versioned shader caches also inform the preparation pipeline here.

See [UPSTREAM.md](UPSTREAM.md) for the reference revision, adaptation scope, and retained third-party licenses. This project is independently maintained and does not imply endorsement by the upstream authors.

## Validation boundary

The host build, virtual extended-controller mapping, native mouse event handling, and 25 package-read comparisons have passed local checks. The modular pipeline also passes eight synthetic contract tests; a 498-key scan matches the earlier extractor, and eight generated samples compile through the native Metal framework. Repeating that sample preparation preserves cached SPIR-V and MSL files. No physical controller was connected for this validation. Package reads were compared with independently extracted reference bytes, including unaligned reads and end-of-file handling.

Application compatibility remains incomplete. Unsupported indirect calls and guest exception unwinding can prevent startup or later interaction. Shader scan and binding reports identify unresolved variants; compiled shader files alone do not prove correct rendering for every application.
