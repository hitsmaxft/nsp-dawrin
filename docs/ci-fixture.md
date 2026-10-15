# Original NSP fixture

`tests/fixture_app.py` generates a small, deterministic application package plus
an update and add-on. Its AArch64 instructions, startup routines, text resources,
metadata and encryption keys are original synthetic test inputs. Package binaries
are generated in a temporary directory and are not committed. The fixture is
intended for this runtime's tests, not installation on retail hardware.

```sh
python -m pip install -r requirements-core.txt
python -m unittest discover -s tests -p test_fixture_app.py -v
```

The package tests exercise the production PFS0/NCA/CNMT reader, update precedence,
DLC version requirements, resource bytes, executable extraction and NSO rewriter.
They reject truncated packages and a DLC requirement newer than the selected
application. A byte-for-byte determinism check detects accidental host-dependent
fixture output. These tests run on macOS, Windows and Linux.

On an ARM64 Mac, execute the rewritten guest program:

```sh
make -j3 build/bin/nsp-dawrin
python tests/fixture_app.py --native-host build/bin/nsp-dawrin --negative-control
```

The guest calls the clock SDK import through a relocated function slot, checks a
fixed expected timestamp and a virtualized x18 value, then emits a result through
an SVC debug-output gate. Success requires both the guest's exact success marker
and a normal return from `nnMain`; loading modules alone cannot pass. The negative
control regenerates the executable with an incorrect timestamp expectation and
requires the guest failure marker. A crash or timeout cannot satisfy that check.
The fixture uses original minimal startup routines, including the required ABI
export names; no SDK implementation is bundled.

Each run has isolated settings and a finite timeout. It opens no game window and
needs no shader compiler. Temporary packages, keys, caches, logs and settings are
cleaned at exit. JSON results distinguish package, update, DLC, rewriting, native
execution and the negative control. When no native runner was requested, native
execution is explicitly `not_run`.

To retain generated inputs for local inspection:

```sh
python tests/fixture_app.py --output /path/outside-checkout/fixture
```

The `Host services` workflow executes platform service tests and package tests on
all three OSes. Its separate `native-fixture` job runs the program on `macos-26`
ARM64. This fixture does not validate graphics, audio, controller hardware, game
menus or progress saves; add independent assertions for those modules when they
have a deterministic headless contract.
