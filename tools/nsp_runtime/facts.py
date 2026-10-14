"""External shader metadata adapter; no application data is bundled."""
import json
from .interfaces import ShaderFacts


class JsonFactsProvider:
    name = 'external-json'

    def __init__(self, path):
        self.rows = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(self.rows, dict):
            raise ValueError('Shader facts must be an object keyed by control hash')

    def facts_for(self, key, stage):
        row = self.rows.get(key)
        if row is None:
            return ShaderFacts()
        allowed = {'tex', 'img', 'attr', 'fout', 'local', 'shared'}
        unknown = set(row.get('values', {})) - allowed
        if unknown:
            raise ValueError(f'Unknown shader facts fields: {sorted(unknown)}')
        if row.get('stage', stage) != stage:
            raise ValueError(f'Shader facts stage mismatch for {key}')
        return ShaderFacts(row.get('values', {}), row.get('source', self.name), bool(row.get('complete', False)))
