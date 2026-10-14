# Project conventions

- The project name is `nsp-dawrin`.
- Write new code, comments, diagnostics, and documentation in English.
- Keep project branding neutral. Preserve required third-party license notices and exact interoperability symbols.
- Never add application packages, game assets, keys, firmware, saves, screenshots, or captured shader data to the source tree.
- Keep runtime data and generated build caches outside the source directory. Reuse the shared build directory.
- Prefer bounded CLI and local API validation. Use OCR for interaction and inspect images only when text cannot resolve a rendering issue.
- Distinguish virtual input tests from tests with connected physical devices.
