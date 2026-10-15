# Desktop screenshots

These 1440 × 850 application-content captures render the actual Flutter widget
tree at revision `e958c7b`. They exclude desktop backgrounds, the Dock, menu bars,
notifications, native file pickers and personal paths.

The library entry comes from a real launcher-service preparation of the original
`tests/fixture_app.py` base package, update and add-on. Version 2 and the attached
content were checked before capture. The display name is `NSP Test Application`;
only synthetic filenames are visible. No commercial application content or
runtime keys are included.

Because the capture host was screen-locked, Flutter's offscreen renderer captured
the application content from a read-only snapshot of that prepared library.
These are UI documentation images, not native-window, guest-rendering or
cross-platform gameplay validation. The selected physical system font is rendered
by the host and is not redistributed as a font file.

- `library.png`: prepared test application and attached content.
- `content.png`: original `update.nsp` and `addon.nsp` associations.
- `controls.png`: display mode, output resolution, controller preference and key bindings.
