# Desktop client

Flutter UI for the shared launcher service. See [desktop architecture and
building](../docs/desktop-launcher.md). Application code is under `lib/`;
`test/` exercises library selection, runtime capability gates and preferences.

Build from the repository root with `python tools/build_gui.py --test --build`.
The helper stages the project and all generated build output under `build/`.
