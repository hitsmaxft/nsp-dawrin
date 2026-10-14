"""Explicit adapter registration and conservative engine selection."""
from .interfaces import EngineAdapter, ResourceReader, ShaderDecoder


class UnsupportedEngineError(ValueError):
    pass


class Registry:
    def __init__(self):
        self.engines: dict[str, EngineAdapter] = {}
        self.decoders: dict[str, ShaderDecoder] = {}

    def register_engine(self, adapter: EngineAdapter):
        if adapter.name in self.engines:
            raise ValueError(f'Duplicate engine adapter: {adapter.name}')
        self.engines[adapter.name] = adapter

    def register_decoder(self, decoder: ShaderDecoder):
        if decoder.format in self.decoders:
            raise ValueError(f'Duplicate shader format: {decoder.format}')
        self.decoders[decoder.format] = decoder

    def select_engine(self, resources: ResourceReader, name='auto') -> EngineAdapter:
        if name != 'auto':
            if name not in self.engines:
                raise UnsupportedEngineError(f'Unknown engine adapter: {name}')
            return self.engines[name]
        matches = [(engine.probe(resources).confidence, engine) for engine in self.engines.values()]
        matches = sorted((item for item in matches if item[0] > 0), key=lambda item: item[0], reverse=True)
        if not matches:
            raise UnsupportedEngineError('No engine adapter recognizes these resources; select or implement an adapter')
        if len(matches) > 1 and matches[0][0] == matches[1][0]:
            raise UnsupportedEngineError('Engine detection is ambiguous; select an explicit adapter')
        return matches[0][1]


def default_registry():
    from .engines.unity import UnityAdapter
    from .formats.nvn import NvnBlobDecoder
    registry = Registry()
    registry.register_engine(UnityAdapter())
    registry.register_decoder(NvnBlobDecoder())
    return registry
