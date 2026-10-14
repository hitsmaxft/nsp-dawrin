"""Connect engine adapters to GPU decoders and the external shader cache."""
import json
from pathlib import Path
from .interfaces import ResourceReader
from .registry import Registry, default_registry


def scan(resources: ResourceReader, output: Path, engine='auto', registry: Registry | None = None, progress=None):
    registry = registry or default_registry()
    adapter = registry.select_engine(resources, engine)
    output.mkdir(parents=True, exist_ok=True)
    found = set()
    report = dict(schema_version=1, engine=adapter.name, assets=0, shader_objects=0,
                  shader_keys=[], unsupported_stages=[], errors=[])
    for asset in adapter.scan(resources):
        report['assets'] += 1
        report['shader_objects'] += asset.shader_objects
        if asset.error:
            report['errors'].append(dict(asset=asset.source, error=asset.error))
        for blob in asset.blobs:
            decoder = registry.decoders.get(blob.format)
            if decoder is None:
                report['errors'].append(dict(asset=asset.source, error=f'Unknown shader format: {blob.format}'))
                continue
            try:
                decoded = decoder.decode(blob)
            except Exception as error:
                report['errors'].append(dict(asset=asset.source, error=str(error)))
                continue
            report['unsupported_stages'].extend(decoded.unsupported)
            for shader in decoded.programs:
                if shader.key in found:
                    continue
                found.add(shader.key)
                (output/(shader.key+'.control')).write_bytes(shader.control)
                (output/(shader.key+'.code')).write_bytes(shader.code)
        if progress:
            progress(dict(asset=asset.source, shaders=len(found)))
    report['shader_keys'] = sorted(found)
    report['complete'] = bool(found) and not report['errors'] and not report['unsupported_stages']
    (output/'scan-report.json').write_text(json.dumps(report, indent=2))
    return report
