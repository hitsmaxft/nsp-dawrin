# Runtime compatibility workflow

The launcher defaults to `--shaders runtime`. It rewrites executable modules,
indexes content, and starts the native host without requiring an engine adapter.
`--shaders prewarm --engine auto` opts into the asset scanner for early preparation.
An unknown asset engine therefore does not block the default launch path.

## Shader requests

`nvnProgramSetShaders` publishes a bounded capture pair, code first and control
last. At replay, the host observes texture targets, image formats, vertex input
classes and render-target output classes. A shader variant is identified by its
capture control hash and the observed facts. Different resource types do not
reuse the same in-memory program variant.

`shader_jobs.prepare` is the common job builder. An individual request reads only
its capture, validates metadata, and retains unrelated jobs. The translator and
Metal backend compile the selected key and merge its map entry atomically. Bad
unrelated captures cannot block a first-use request. The conversion chain still
tracks source, tool binaries and explicit external facts. Changed chains reset
the active map; caches from another chain are never relabeled as current.

The runtime collector is deliberately separate from the GPU instruction
translator. Extend `nvn_runtime_facts.inc` for additional observed state and
`shader_jobs.validate_facts` for metadata validation. `ShaderFactsProvider` remains
available for format-specific facts. Runtime observations override the same
explicitly observed slots in external metadata.

Vertex and fragment captures with the validated layout work automatically.
Compute translation and Metal generation accept an external descriptor with
`stage: "cs"`, `code_offset`, and explicit `values.local` and `values.shared`.
Unknown compute control layouts cannot yet supply these automatically and fail
with a metadata diagnostic. Geometry/tessellation and resource descriptor arrays
remain unsupported. Missing texture facts are still reported by the translator;
first-use conversion is not proof of complete rendering accuracy.

## Shared services

Content inventory and save allocation are host modules with C interfaces in
`src/macos/content.h` and `storage.h`. SDK symbol bindings delegate to these
operations rather than maintaining per-application behavior. The inventory is
immutable during a session; DLC mounts are read-only. Save allocation comes from
the selected application control metadata and persists independently of save
transactions. It is logical allocation, not a physical disk-space reservation.

```sh
python tools/service_catalog.py --check
python tools/service_catalog.py
```

The first command checks conflicting forced registrations before launching; the
second lists symbols, handlers, source modules and reasons for takeover. Add
synthetic checks for common service behavior and preserve ABI-specific wrappers.
This inventory is not a claim that all OS services or IPC commands exist.

`src/macos/ipc.h` defines a transport-level service interface independent of SDK
symbol names. Register a command handler with `native_ipc_register` before guest
threads start. HIPC/CMIF requests support service resolution, session handles,
single-object domains and one output descriptor. Handlers receive bounded input
and use `native_ipc_write` for output. Settings language commands use this path.
Unknown services and commands return errors and stable diagnostic identifiers.
Multiple domain objects, input buffer dispatch and asynchronous IPC need further
implementation. Protocol-session closure and kernel-handle closure are separate.
`native_power_boost` maps loading hints to a reversible macOS activity token;
clock frequencies remain managed by the host OS.

## Batch validation

Create a local manifest outside the checkout:

```json
{
  "cases": [
    {"id": "sample-a", "cache": "/path/prepared-a", "timeout": 90},
    {"id": "sample-b", "cache": "/path/prepared-b", "timeout": 90}
  ]
}
```

```sh
python tools/validate_matrix.py /path/cases.json --output /path/results
```

Registration conflicts are checked before cases start. Cases run sequentially
with bounded startup checks and isolated control sockets.
Each check owns a process group, including any first-use shader compiler children.
The matrix continues after a failed case and checkpoints `matrix.json` after
each result. Raw logs remain in per-case directories. The summary includes only
case IDs, counters and classified failures, grouped by service symbol, IPC command, syscall,
shader stage/metadata, native fault or startup outcome. Fix groups affecting
multiple samples first, then rerun the matrix.

Use fresh external caches for cold conversion checks, and repeat the same caches
for warm checks. Preserve original saves; use separate validation caches where
launching may initialize or change save files. Rendering startup, interaction,
DLC content access and save/load remain separate acceptance checks.

Native fault diagnostics include the return address and bounded frame reads from
both host and mapped guest stacks. This keeps failures in media allocators or
other guest subsystems distinguishable from shader conversion failures. The
runtime selects the guest's in-process audio renderer through ABI-preserving
guest aliases when that backend is exported. Software codec selection remains
in the guest SDK. Graphics allocator registration is preserved because media
components share that allocator; a host-only callback record is insufficient.

Transfer-memory handles track a borrowed range and reject overlap and stale
handles. Compatible host-page offsets use coherent VM aliases. For isolated
transfers (owner permission None), differing 4 KiB offsets on a 16 KiB host move
contents at map/unmap ownership boundaries. The runtime does not enforce source
subpage protection; callers must respect the exclusive-ownership contract.
Shared transfers with incompatible page offsets are rejected. These paths use
the application-provided SDK and codecs; no media implementation is bundled.

The local `control.py status` response includes `audio_callbacks` and
`save_commits`. A callback proves host audio activity, not audible correctness;
a commit may contain settings alone. Confirm a progress save in the application
and reload it in a new process. `control.py threads` writes thread states to the
private runtime log for diagnosing stalls without a debugger attachment. Raw
thread dumps include guest addresses and must not enter shared crash reports.

OCR capture normally waits at most five seconds for the next rendered frame.
During first-use compilation, use `control.py state --capture-timeout 30` to
allow a longer bounded wait; `status` remains available while shaders compile.
