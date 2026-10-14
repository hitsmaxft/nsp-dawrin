# nsp-dawrin

A native ARM64 compatibility runtime for macOS. Guest CPU instructions execute directly after rewriting, with local host services and an NVN-to-Metal graphics backend.

- Launch NSP packages with resources read directly from the package.
- Prepare shaders through a modular Maxwell → SPIR-V → MSL pipeline.
- Use mouse touch, keyboard, and system-supported game controllers.
- Inspect runtime state and interact through a local CLI with OCR.
- Add engine adapters through [documented extension interfaces](docs/interfaces.md).

## Build

Requires an ARM64 Mac with macOS 26 or later, Command Line Tools, Python, .NET 10, and `spirv-cross`.

```sh
python3 -m venv ../work/venv
. ../work/venv/bin/activate
pip install -r requirements.txt

dotnet build tools/shader_translate -c Release
make -j4
python3 tools/build_app.py
```

The runner is built at `../work/bin/nsp-dawrin`. Build objects are shared in `../work/build/obj`.

## Launch

```sh
python tools/launch.py /path/application.nsp --keys /path/local.keys
```

Preparation results are cached under `~/Library/Caches/nsp-dawrin`. Use `--cache-root /path/cache` to choose a location, `--prepare-only` to prepare without launching, and `--engine` to select an adapter.

For an existing prepared session:

```sh
GAME_DIR=/path/cache DM_WINDOW=1 DM_TIMEOUT=0 ./run.sh
```

The app bundle uses the same `GAME_DIR` and local checkout. `DOTNET` can select an SDK executable outside PATH.

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
../work/bin/warm-metal /path/cache/shaders/metal/b-CHAIN
python tools/shader_report.py /path/cache/shaders
```

The second command emits a compact conversion report suitable for a shader issue.

## Controls

Mouse press, drag, and release provide touch input. Coordinates follow window resizing. Choose Automatic, Keyboard only, or a connected controller in Settings. The selected extended-profile controller maps to player one, including sticks, face buttons, direction pad, shoulders, triggers, and menu buttons. Default positional mapping supports system-recognized Xbox and Pro controllers.

| Keyboard | Input |
| --- | --- |
| Z / Space | A |
| X / Escape | B |
| A | X |
| S | Y |
| Return | Primary menu |
| Arrow keys | Direction pad |

## Menus and settings

Open **nsp-dawrin → Settings…** with **⌘,**. Use **View → Enter Full Screen** or **⌃⌘F** to toggle full screen.

- **System mode:** handheld (720p) or console (1080p), applied on the next game launch. `DM_HANDHELD` overrides the saved mode for that launch.
- **Display output:** automatic window/display sizing, 1280 × 720, or 1920 × 1080. Changes apply immediately to the presented image; the game chooses its internal render resolution. Full-screen output keeps a 16:9 aspect ratio.
- **Keyboard:** click one of the 24 binding buttons, then press a key. Bindings cover buttons, direction pad, and both sticks. Assigning an occupied key moves it to the selected action. Shift, Control, and Option keys are supported; Command shortcuts remain available for menus. Clear an individual binding or restore the defaults with Reset Keyboard.
- **Controller:** switch the active device immediately, use automatic selection, or disable controller input with Keyboard only. The preferred model is remembered; with multiple identical devices, select the desired device again after restarting.

Settings are saved to `~/Library/Application Support/nsp-dawrin/settings.json`. Keyboard and controller input are released when the game loses focus.

The control API exposes the same settings for automation:

```sh
python tools/control.py settings
python tools/control.py settings show
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

## Acknowledgments

Thanks to [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) for publishing the implementation that forms the foundation of this project: ARM64 rewriting, host services, NVN command recording and Metal replay, and offline shader translation. Its explicit resource reflection and versioned caches also inform this macOS implementation.

This project builds on the work of many authors and maintainers. In particular, thank you to:

- **Ryujinx / Ryubing contributors** for the MIT-licensed `Ryujinx.Graphics.Shader`, `Spv.Generator`, and `Ryujinx.Common` libraries used for Maxwell-to-SPIR-V translation.
- **fincs and devkitPro** for [deko3d](https://github.com/devkitPro/deko3d), whose zlib-licensed texture layout algorithm is adapted in `nvn_tex.c`.
- **h1k421** for the MIT-licensed `nvn.h` graphics interface declarations.
- **Sergii Kudlai (iOrange)** for [bcdec](https://github.com/iOrange/bcdec), used for BC texture decoding under its MIT license option.
- **Khronos Group and SPIRV-Cross contributors** for the SPIR-V definitions and [SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross) translation to Metal Shading Language.
- **UnityPy, cryptography, python-lz4, Capstone, Unicorn, Tesseract, Python, .NET, and LLVM contributors**, and the maintainers of their dependencies, for asset inspection, package reading, instruction verification, OCR, and the build tools.

See [Dependencies](docs/DEPENDENCIES.md) for component versions, authors, uses, and licenses, and [UPSTREAM.md](UPSTREAM.md) for source provenance.

## License

[GPL-3.0-or-later](LICENSE); see [COPYING](COPYING).
