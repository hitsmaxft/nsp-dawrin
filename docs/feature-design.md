# Multi-game feature design

The product review uses [LASRecomp at revision 03b1902](https://github.com/peiikai/LASRecomp/tree/03b19027df1731593903778073cad51dceb5f8dd).
Its start screen, configurable controls, display options and separate save data
are useful references for player-facing features. LASRecomp targets one game
on macOS, Windows and Linux. Here, features must work across applications and
keep application-specific behavior behind explicit adapters.

| Feature idea | Multi-game design | Status |
| --- | --- | --- |
| Convenient configuration | Per-application overrides over global defaults; reset to inheritance; expose the same actions in native UI and CLI | Implemented |
| Quick launch and setup | Library of user-selected packages, recent sessions, preparation progress and independent startup/menu/save validation status | Proposed; the package launcher and CLI validation already exist |
| Separate playthroughs | Named save slots per application, with snapshots taken while its session is stopped and explicit selection before launch | Proposed; current storage already persists application saves |
| Controller-aware prompts | Show detected controller labels in launcher/settings; retain positional guest mappings. In-game prompts need an engine/UI adapter | Proposed; controller selection and bindings already exist |
| Display presets | Per-game output resolution and mode now; internal-resolution adapters and measured scaling/upscaling support later | Output settings implemented; internal scaling and upscaling proposed |
| Application-specific extras | Optional, version-checked extension interfaces for supported applications | Proposed; randomizer logic and title-specific patches are not generic features |

## Independent game settings

`DM_TITLE_ID` selects a profile using a validated 16-digit application ID.
Updates and DLC share their base application's settings when launched through
`tools/launch.py`. Without an application ID, settings use global defaults.

A profile stores only overridden fields. Keyboard bindings form one field, so a
profile cannot accidentally merge duplicate key assignments from another map.
Changing a field back to its global value removes that override. Reset Game
Settings clears all overrides for the current application.

The Settings scope selector chooses **This game** or **Global defaults**.
Switching scope immediately applies that scope's display and input preferences
in the current session and releases held keys. System mode remains fixed until
restart. A new launch selects the application's profile again. Other running
processes read updated global defaults on their next launch.

Global settings remain in `~/Library/Application Support/nsp-dawrin/settings.json`;
profiles live in `profiles/<application-id>.json` beside it. `NSP_SETTINGS_PATH`
isolates tests: its profiles live under `<override-path>.profiles/`. Writes are
atomic; invalid profiles inherit valid global defaults until the user saves a
new configuration. `settings` API responses expose scope and overridden field
names without exposing local filesystem paths.

`tests/settings_profiles.m` checks isolation and inheritance across processes,
reset, invalid IDs, malformed profiles and failed writes. `tests/settings_ui.m`
exercises the real AppKit scope selector, reset action and corresponding API.

## Engineering support

The native runner links and receives its existing local ad-hoc signature in a
temporary sibling directory before atomic publication. A failed build leaves
the previous executable intact, and running processes retain the old file.
This follows the build-publication principle reviewed in LASRecomp's Makefile.

Its generated-code identity contract is also a useful future reference for
preparation-cache validation. That work is separate from these player-facing
features; this change does not add a new CPU backend or save-slot manager.
