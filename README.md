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

## Controls

Mouse press, drag, and release provide touch input. Coordinates follow window resizing. The first connected extended-profile controller maps to player one, including sticks, face buttons, direction pad, shoulders, triggers, and menu buttons.

| Keyboard | Input |
| --- | --- |
| Z / Space | A |
| X / Escape | B |
| A | X |
| S | Y |
| Return | Primary menu |
| Arrow keys | Direction pad |

Handheld mode uses 720p. Set `DM_HANDHELD=0` for 1080p console mode.

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
