"""Engine-independent contracts. No platform SDK or engine imports belong here."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class Resource:
    path: str
    size: int


class ResourceReader(Protocol):
    def iter_resources(self) -> Iterable[Resource]: ...
    def read_resource(self, path: str, offset: int = 0, length: int | None = None) -> bytes: ...


@dataclass(frozen=True)
class Probe:
    confidence: float
    reason: str


@dataclass(frozen=True)
class ShaderBlob:
    format: str
    data: bytes
    label: str = ""


@dataclass
class AssetScan:
    source: str
    blobs: list[ShaderBlob] = field(default_factory=list)
    shader_objects: int = 0
    error: str | None = None


class EngineAdapter(Protocol):
    name: str
    def probe(self, resources: ResourceReader) -> Probe: ...
    def scan(self, resources: ResourceReader) -> Iterable[AssetScan]: ...


@dataclass(frozen=True)
class ShaderProgram:
    key: str
    stage: str
    control: bytes
    code: bytes


@dataclass
class DecodeResult:
    programs: list[ShaderProgram] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


class ShaderDecoder(Protocol):
    format: str
    def decode(self, blob: ShaderBlob) -> DecodeResult: ...


@dataclass
class BackendResult:
    completed: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class TranslationBackend(Protocol):
    name: str
    def translate(self, jobs: Sequence[Mapping], directory: Path) -> BackendResult: ...


@dataclass(frozen=True)
class ShaderFacts:
    values: Mapping = field(default_factory=dict)
    source: str = 'unavailable'
    complete: bool = False


class ShaderFactsProvider(Protocol):
    """Supply metadata that cannot be recovered from instructions alone."""
    name: str
    def facts_for(self, key: str, stage: str) -> ShaderFacts: ...


class ShaderBuildBackend(Protocol):
    name: str
    def build(self, directory: Path) -> BackendResult: ...
