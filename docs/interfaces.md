# Extension interfaces

The contracts live in `tools/nsp_runtime/interfaces.py`. Modules receive resource readers or shader records; they do not open application-specific paths themselves. Register adapters explicitly in a `Registry`, then pass it to `pipeline.scan`. The default registry contains one serialized-asset engine adapter and one graphics blob decoder. It does not claim support for other engines.

| Boundary | Contract | Current implementation |
| --- | --- | --- |
| Package resources | `ResourceReader.iter_resources`, `read_resource` | `package.Package`; bounded reads from the original base package |
| Engine asset layout | `EngineAdapter.probe`, `scan` | `engines.unity.UnityAdapter`; emits format-tagged blobs |
| GPU blob layout | `ShaderDecoder.decode` | `formats.nvn.NvnBlobDecoder`; validates two control layouts and vertex/fragment stages |
| Supplemental metadata | `ShaderFactsProvider.facts_for` | `facts.JsonFactsProvider`; reads optional external metadata |
| Instruction translation | `TranslationBackend.translate` | `backends.MaxwellSpirvBackend`; bounded subprocess batches |
| Host shader generation | `ShaderBuildBackend.build` | `backends.MetalSourceBackend`; MSL plus resource binding manifests |
| Native controller state | `NativePad`, `native_controller_read` | `src/macos/controller.h` and the system framework adapter |

A new engine normally adds only an `EngineAdapter`. Reuse an existing decoder when its GPU blob layout matches. A new package format implements `ResourceReader`, independently of engine parsing. A new GPU format implements `ShaderDecoder`. Unsupported formats, ambiguous detection, malformed extents and unsupported stages are reported; they are not counted as successful coverage.

```python
from nsp_runtime.pipeline import scan
from nsp_runtime.registry import default_registry

registry = default_registry()
registry.register_engine(MyEngineAdapter())
report = scan(resources, output, engine="my-engine", registry=registry)
```

`MyEngineAdapter.scan` yields `AssetScan` records with `ShaderBlob(format, data, label)` values. `probe` returns `Probe(confidence, reason)`; zero means unrecognized. Automatic selection rejects equal highest scores. Use `--engine` on the scanner or launcher to select an adapter explicitly.

## Supplemental shader facts

Machine code alone does not establish all texture dimensions, image formats, vertex/output types or compute workgroup properties. An engine parser or runtime-state collector can implement `ShaderFactsProvider`. The current job preparer uses an optional `shader-facts.json` outside the repository, keyed by the 16-character control hash:

```json
{
  "0123456789abcdef": {
    "stage": "vs",
    "source": "engine-metadata",
    "complete": false,
    "values": {"tex": {"0": "cube"}, "attr": {"0": "float"}}
  }
}
```

The example identifier and values are synthetic. Allowed fields are `tex`, `img`, `attr`, `fout`, `local`, and `shared`, matching the offline translator job schema. Facts cannot replace code paths, keys or compiler options. `complete` is the provider's assertion, not independently verified coverage. Missing metadata is recorded in `facts-report.json`; translator assumptions also appear in reflection notes. The current asset adapter does not yet extract these facts. Producing MSL with defaults does not prove correct rendering.

## Cache and runtime contract

The conversion chain hashes pipeline sources, binding implementation, actual translator DLLs, the SPIRV-Cross executable, conversion options, and external facts. The translator verifies its embedded source fingerprint before processing jobs. Changed tools or metadata select a new `translated/<chain>` and `metal/b-<chain>` directory. The launcher supplies that same identity to the native loader, which rejects mismatched reflection.

Each translation receipt also includes job options and machine-code bytes. Metal output reuse includes SPIR-V, resource reflection and constant bytes. Python manifests are replaced atomically. Translation and binding failures are structured reports; incomplete full preparation exits unsuccessfully. First-use requests check the requested key independently. Conversion uses bounded batches, four Metal-source workers and in-process deduplication of identical SPIR-V.

The backend currently generates MSL, not offline metallib files. The native host compiles MSL with the installed Metal framework and benefits from its system cache. GPU pipeline-state creation still depends on runtime render state. There is no claim that a static scan covers every dynamic shader or eliminates all first-use work. Old cache generations are external and can be removed when no process uses them; they are not silently deleted alongside saves.

## Upstream design review

The reference implementation is [d2r-mobile at the recorded revision](https://github.com/jhaizhou-ops/d2r-mobile/tree/685d3ddef8bf75768fd4c51228566f2e8d2a5182). The review covered `dm/gfx/README.md`, `dmsh_build.py`, `dmsh_chain.py`, `shader_map.py`, `dmsh_fetch.py`, and the native shader preparation helper.

Retained principles are command recording separated from Metal replay, explicit resource reflection, control-hash shader identity, constant-buffer preservation and versioned conversion caches. Upstream supplies some translation facts through a title-derived answer table; this project uses an external provider contract instead. Its title-specific mapping tables and rendering shortcuts are not new engine adapters here. Existing inherited graphics optimization assumptions still need broader auditing before general compatibility can be claimed.

## Verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

Use the external environment with `requirements.txt` installed. Tests use synthetic shader records, a synthetic engine adapter, bounded resource reads, invalid formats, ambiguous detection, metadata restrictions and cache invalidation. Native input harnesses remain separate: virtual framework input and mouse events do not establish physical controller behavior.
