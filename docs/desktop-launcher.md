# Desktop launcher

The Flutter client provides a library, package/update/DLC selection, preparation,
launch/stop controls, per-application display and keyboard preferences, connected
controller selection, session counters, logs and a copyable repair prompt.

Open the desktop application, choose the runtime folder in **Settings**, then
select the local key file and optional .NET executable. **Add package** imports
an NSP/XCI by reference. Select an entry, use **Updates & add-ons** to associate
content, then **Play**. **Prepare content** runs preparation independently.
The setup indicators explain unavailable prerequisites; missing execution support
disables Play while leaving content management available.

The desktop client builds for macOS, Windows and Linux. Native guest execution
currently requires macOS 26+ on ARM64. Windows and Linux provide the desktop
library and package preparation; portable service tests do not establish a
complete execution/graphics backend on those platforms.

## Build and distribution

Use Flutter 3.47.7, Python 3.10+, and the platform's desktop development tools:
Xcode on macOS, Visual Studio C++ on Windows, or Clang/CMake/Ninja/GTK 3 development
headers on Linux. From the repository root:

```sh
python tools/build_gui.py --test --build
```

Use `--flutter /path/to/flutter` for an SDK outside PATH. The helper stages the
source under `build/flutter/project`, keeps Pub packages under `build/pub-cache`,
and emits native bundles below `build/flutter/project/build`. It does not change
global Flutter configuration. The Desktop GUI workflow tests and builds all
three platforms and publishes downloadable artifacts. macOS uses local ad-hoc
signing only; there is no developer certificate or notarization step.

The application is a development launcher that connects to a prepared runtime
checkout. Runtime binaries, Python dependencies, .NET and shader tools are not
bundled into the GUI artifact. Initial runtime building follows the [developer guide](development.md#native-runtime-build-macos);
after setup, ordinary library and session operations use the GUI. Automatic
runtime installation and standalone installers remain separate future work.

## Modules and protocol

- `gui/lib/ui/`: desktop views and original procedural artwork.
- `gui/lib/models/`: observable library/session state and request orchestration.
- `gui/lib/api/`: subprocess transport implementing `LauncherApi`.
- `tools/launcher/store.py`: atomic library persistence and portable preferences.
- `tools/launcher/service.py`: validated content associations and owned tasks.
- `tools/launcher/runtime.py`: native launch environment and process lifecycle.
- `tools/launcher_service.py`: versioned JSON-lines request dispatcher.

The client starts Python directly using `Process.start`, without a command
shell. Each request is `{version: 1, id, method, params}`; responses contain the
same ID and either `result` or `error.message`. Methods include `snapshot`,
`config.update`, `library.add/update/remove`, `session.prepare/start/stop`,
`session.devices`, `session.settings`, and `session.preferences`. Preparation
returns immediately and runs in an owned background task. The UI polls status
at two-second intervals. Closing the transport stops its owned session.

Keyboard preferences use USB HID usage codes in the UI and library. The macOS
adapter translates these to native virtual keycodes. Device enumeration and
selection use the existing runtime control API. System mode changes take effect
on the next launch; fullscreen, resolution and bindings can be applied live.
Controller IDs refer to live devices; library preferences persist automatic or
keyboard-only selection. The existing runtime handles mouse touch and controller
normalization.

Library data lives under the OS application-data directory, in
`nsp-dawrin/launcher` (macOS: `~/Library/Application Support/nsp-dawrin/launcher`).
Prepared content uses a content/rewrite fingerprint; saves use a stable title ID
and survive cache generations. Removing an entry preserves packages, caches and
saves. Stop ends the owned process; it does not perform an in-game save.

## Verification

`tests/test_launcher.py` generates original NSP/update/DLC packages and tests
association validation, real preparation, persistence, protocol errors, input
conflicts and cancellation. Flutter widget tests cover navigation, search,
selection/start, capability gates, preferences and a 900-pixel window. These
checks do not claim commercial-game compatibility or physical controller proof.
