"""Decode serialized shader objects without changing the graphics backend."""
from pathlib import PurePosixPath
from ..interfaces import AssetScan, Probe, ResourceReader, ShaderBlob


def flatten(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from flatten(item)
    else:
        yield value


class UnityAdapter:
    name = 'unity'

    def probe(self, resources: ResourceReader) -> Probe:
        names = {item.path for item in resources.iter_resources()}
        if any(PurePosixPath(name).name == 'globalgamemanagers' for name in names):
            return Probe(1.0, 'Serialized engine metadata is present')
        for name in sorted(names):
            if name.endswith(('.unity3d', '.bundle')) and resources.read_resource(name, 0, 8).startswith(b'UnityFS'):
                return Probe(0.9, 'Recognized bundle signature')
        return Probe(0, 'No recognized metadata or bundle signature')

    def scan(self, resources: ResourceReader):
        # Optional dependencies remain isolated to this adapter.
        import lz4.block
        import UnityPy
        for resource in resources.iter_resources():
            name = resource.path
            if not (name.endswith(('.assets', '.unity3d', '.bundle')) or PurePosixPath(name).name == 'unity_builtin_extra'):
                continue
            result = AssetScan(name)
            try:
                environment = UnityPy.load(resources.read_resource(name))
                for obj in environment.objects:
                    if obj.type.name != 'Shader':
                        continue
                    shader = obj.read()
                    result.shader_objects += 1
                    blob = bytes(shader.compressedBlob)
                    offsets = list(flatten(shader.offsets))
                    lengths = list(flatten(shader.compressedLengths))
                    raw_lengths = list(flatten(shader.decompressedLengths))
                    if not (len(offsets) == len(lengths) == len(raw_lengths)):
                        raise ValueError('Shader block tables have different lengths')
                    for index, (off, length, raw_length) in enumerate(zip(offsets, lengths, raw_lengths)):
                        raw = lz4.block.decompress(blob[off:off+length], uncompressed_size=raw_length)
                        # A serialized program table containing only count=0 has no GPU records.
                        if raw == bytes(4):
                            continue
                        result.blobs.append(ShaderBlob('nvn-blob', raw, f'{obj.path_id}:{index}'))
            except Exception as error:
                result.error = str(error)
            yield result
