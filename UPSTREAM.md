# Source provenance

The ARM64 NSO rewriter, loader, Horizon service implementations and NVN/Metal
backend derive from https://github.com/jhaizhou-ops/d2r-mobile at
`685d3ddef8bf75768fd4c51228566f2e8d2a5182` (MIT, see LICENSES/d2r-mobile-MIT.txt).

This is a standalone macOS bring-up project. It does not retain the original
repository, its Git history, iOS application, product packaging, game assets,
gameplay patch tables, or title-specific host implementation branches. Shared
backend code still contains upstream diagnostics and optimization assumptions;
these require further generalization before claiming multi-title compatibility.

Local changes include the macOS host harness, startup sequencing, weak imports,
older ARM64 relative jump tables, native input state, Unity-required NVN buffer
and texture interfaces, and removal of title-specific allocation/save hooks.

`src/third_party/bcdec` retains its own license. `src/third_party/ryujinx` contains
only the upstream-vendored shader translator dependencies, with their licenses.
They are for offline Maxwell GPU shader translation, not CPU emulation.
`tests/equiv.py` uses Unicorn solely for isolated instruction equivalence tests.

Before the initial publication, the upstream extraction, translation, binding,
cache-version and native source-compilation paths were reviewed again. The local
pipeline adopts explicit adapter contracts, external shader facts, tool/source
fingerprints, per-input receipts, and atomic Python manifests. No title-derived
shader answer table or paired application reflection data is included.

The texture layout implementation in `src/gfx/nvn/nvn_tex.c` is an adaptation
of fincs/devkitPro's deko3d `source/dk_image.cpp`; its complete zlib notice is
retained in `LICENSES/deko3d-zlib.txt`. The `nvn.h` declaration header retains
h1k421's MIT notice. The vendored subset and external tool dependencies are
catalogued in [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).
