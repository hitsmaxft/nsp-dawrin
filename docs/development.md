# Development

Use the Flutter desktop launcher for ordinary library management and play.
The commands below are developer entry points for building the runtime,
application bring-up, CI and debugging. Run them from the repository root.
The GUI still uses the shared Python launcher service internally.

## Desktop client build

See [desktop launcher](desktop-launcher.md#build-and-distribution) for Flutter
prerequisites, platform artifacts and GUI build output locations.

## Native runtime build (macOS)

Requires an ARM64 Mac with macOS 26 or later, Command Line Tools, Python, .NET 10, and `spirv-cross`.

```sh
python3 -m venv build/venv
. build/venv/bin/activate
pip install -r requirements.txt

dotnet build tools/shader_translate -c Release --artifacts-path build/dotnet
make -j4
```

Build outputs stay under the ignored `build/` directory: `bin/` for native tools,
`obj/` for native objects, `dotnet/` for the translator, `venv/` for Python, and
GUI output under `build/flutter/project/build/`. Run `make clean` to remove compiled
outputs while keeping the Python environment, or remove `build/` for a full reset.

The optional `python tools/build_app.py` command creates
`build/nsp-dawrin.app`, a native-runner development wrapper. It is separate from
the Flutter desktop launcher and still requires a prepared session and checkout.

## Script launch and package inspection

```sh
python tools/launch.py /path/application.nsp --keys /path/local.keys
```

Shaders are captured and compiled on first use by default. Use `--shaders prewarm`
to scan a supported engine before launch.

Preparation results are cached under `~/Library/Caches/nsp-dawrin`. Use `--cache-root /path/cache` to choose a location, `--prepare-only` to prepare without launching, and `--engine` to select an adapter.

For an existing prepared session:

```sh
GAME_DIR=/path/cache DM_WINDOW=1 DM_TIMEOUT=0 ./run.sh
```

The native-runner development wrapper uses the same `GAME_DIR` and local checkout. `DOTNET` can select an SDK executable outside PATH.

The launcher reads NSP and XCI secure partitions and accepts associated updates
and DLC selected through content metadata:

```sh
python tools/launch.py /path/base.nsp --keys /path/local.keys \
  --update /path/update.nsp --dlc /path/addon.nsp --inspect
```

Remove `--inspect` to prepare and launch. Repeat `--dlc` for additional content.
See [Content loading](content-loading.md) for supported storage formats.

## Startup check

```sh
python tools/smoke.py /path/cache --timeout 90
```

The check launches one session, waits for loaded shaders and continuing frames,
checks the input API, and stops its own process. It writes `validation/smoke.json`
and `validation/runtime.log` in the cache. `rendering_started` confirms rendering
startup; menu interaction and save/load can then be exercised through the CLI.

Generated MSL can also be compiled in advance through the native Metal API:

```sh
build/bin/warm-metal /path/cache/shaders/metal/b-CHAIN
python tools/shader_report.py /path/cache/shaders
```

The second command emits a compact conversion report suitable for a shader issue.

For several prepared applications, use the [batch compatibility workflow](runtime-compatibility.md) to group failures by shared interface.

## Settings automation

`DM_HANDHELD` overrides the saved system mode for a script launch.

The control API exposes the same settings for automation:

```sh
python tools/control.py settings
python tools/control.py settings show
python tools/control.py settings "profile game"
python tools/control.py settings "profile global"
python tools/control.py settings "profile reset"
python tools/control.py settings '{"resolution":1080,"fullscreen":true}'
python tools/control.py settings '{"mode":"console"}'
python tools/control.py controller none
python tools/control.py controller auto
```

Use a device ID from `settings` with `controller DEVICE_ID` to select a particular connected device. IDs last for the current host session.

## CLI and OCR

```sh
python tools/control.py status
python tools/control.py state --game-dir /path/cache
python tools/control.py click 5 --game-dir /path/cache
python tools/control.py press A
python tools/control.py shot /path/frame.png
```

`state` lists recognized text regions and their touch coordinates. Use the returned ID with `click`. Runtime status includes frame count, shader loading, input state, and direct package reads.

## Crash supervision

For an existing prepared session with crash reporting:

```sh
GAME_DIR=/path/cache DM_WINDOW=1 DM_TIMEOUT=0 python tools/run_with_report.py
```

See [Crash reporting](crash-reporting.md) for CLI options and report contents.

## Automated checks

Use the [original NSP fixture](ci-fixture.md) for package/update/DLC preparation
and native execution checks. See [desktop verification](desktop-launcher.md#verification)
for launcher-service and Flutter tests. [AGENTS.md](../AGENTS.md) records targeted
checks, cache handling and the application bring-up workflow.
