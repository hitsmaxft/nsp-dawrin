"""Synthetic extension contracts and cache isolation; no application fixtures."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from nsp_runtime.cache import atomic_write, digest_files
from nsp_runtime.facts import JsonFactsProvider
from nsp_runtime.formats.nvn import NvnBlobDecoder
from nsp_runtime.interfaces import AssetScan, Probe, Resource, ShaderBlob
from nsp_runtime.pipeline import scan
from nsp_runtime.registry import Registry, UnsupportedEngineError
from package import Package
from nsp_runtime.bindings import storage_binding, resource_writable, image_slot, texture_slot


def shader(width=0x850, stage=1):
    control = bytearray(width)
    control[:4] = bytes.fromhex('34127698')
    struct.pack_into('<II', control, 0x700, 0x80, 0x100)
    code = bytearray(0x100)
    code[:4] = bytes.fromhex('78563412')
    struct.pack_into('<I', code, 0x30, stage << 10)
    return struct.pack('<II', width, len(code)) + control + code


class Reader:
    def iter_resources(self):
        return [Resource('sample', 6)]
    def read_resource(self, path, offset=0, length=None):
        return b'sample'[offset:None if length is None else offset+length]


class Adapter:
    name = 'synthetic'
    def probe(self, resources):
        return Probe(1, 'Test resource')
    def scan(self, resources):
        yield AssetScan('sample', [ShaderBlob('nvn-blob', shader())], 1)


class PipelineTests(unittest.TestCase):
    def test_layouts_and_runtime_identity(self):
        for width in (0x848, 0x850):
            raw = shader(width)
            result = NvnBlobDecoder().decode(ShaderBlob('nvn-blob', raw))
            self.assertEqual(len(result.programs), 1)
            self.assertFalse(result.unsupported)
            self.assertEqual(result.programs[0].key, hashlib.sha256(raw[8:8+0x880]).hexdigest()[:16])

    def test_truncation_and_unsupported_stage(self):
        for raw in (shader()[:-80], shader(stage=3), b'not-a-shader'):
            result = NvnBlobDecoder().decode(ShaderBlob('nvn-blob', raw))
            self.assertFalse(result.programs)
            self.assertTrue(result.unsupported)

    def test_registration_and_selection(self):
        registry = Registry()
        with self.assertRaises(UnsupportedEngineError):
            registry.select_engine(Reader())
        registry.register_engine(Adapter())
        with self.assertRaises(ValueError):
            registry.register_engine(Adapter())
        other = Adapter(); other.name = 'second'
        registry.register_engine(other)
        with self.assertRaises(UnsupportedEngineError):
            registry.select_engine(Reader())
        self.assertIs(registry.select_engine(Reader(), 'second'), other)

    def test_extension_runs_without_engine_dependency(self):
        registry = Registry()
        registry.register_engine(Adapter())
        registry.register_decoder(NvnBlobDecoder())
        with tempfile.TemporaryDirectory() as path:
            report = scan(Reader(), Path(path), registry=registry)
            self.assertTrue(report['complete'])
            self.assertEqual(report['engine'], 'synthetic')
            self.assertEqual(len(list(Path(path).glob('*.code'))), 1)

    def test_unknown_format_is_reported(self):
        registry = Registry(); registry.register_engine(Adapter())
        with tempfile.TemporaryDirectory() as path:
            report = scan(Reader(), Path(path), registry=registry)
            self.assertFalse(report['complete'])
            self.assertIn('Unknown shader format', report['errors'][0]['error'])

    def test_facts_are_explicit_and_cannot_replace_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'facts.json'
            self.assertFalse(JsonFactsProvider(path).facts_for('abc', 'vs').complete)
            atomic_write(path, json.dumps({'abc': {'values': {'tex': {'0': 'cube'}}, 'source': 'test', 'complete': True}}))
            fact = JsonFactsProvider(path).facts_for('abc', 'vs')
            self.assertEqual(fact.values['tex']['0'], 'cube')
            self.assertTrue(fact.complete)
            atomic_write(path, json.dumps({'abc': {'values': {'code': 'unexpected'}}}))
            with self.assertRaises(ValueError):
                JsonFactsProvider(path).facts_for('abc', 'vs')

    def test_cache_fingerprint_tracks_content_and_options(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source'
            atomic_write(path, b'a')
            old = digest_files({'source': path}, {'option': 1})
            atomic_write(path, b'b')
            self.assertNotEqual(old, digest_files({'source': path}, {'option': 1}))
            self.assertNotEqual(digest_files({'source': path}, {'option': 1}), digest_files({'source': path}, {'option': 2}))
            self.assertEqual(list(Path(folder).glob('*.tmp-*')), [])

    def test_storage_binding_requires_exact_slot_table(self):
        for stage, base in (('vs', 0x110), ('ps', 0x510), ('cs', 0x310)):
            binding = storage_binding(dict(cb_slot=0, cb_offset=(base+32)//4, flags=1), stage)
            self.assertEqual(binding, dict(kind='sbuf', reg=2, rw=True))
        for resource in (dict(cb_slot=1, cb_offset=324, flags=0),
                         dict(cb_slot=0, cb_offset=325, flags=0)):
            with self.assertRaises(ValueError):storage_binding(resource, 'ps')
        self.assertFalse(resource_writable({'flags':2},'buffer'))
        self.assertFalse(resource_writable({'flags':2},'image'))
        self.assertTrue(resource_writable({'flags':4},'image'))

    def test_image_and_sampled_texture_tables_are_distinct(self):
        for stage, base in [('cs', 0x120), ('vs', 0x20), ('ps', 0x20)]:
            for slot in (0, 1, 31):
                resource = dict(cbuf_slot=2, handle=(base + slot * 8) // 4)
                self.assertEqual(image_slot(resource, stage), slot)
            for handle in ((base-8)//4, (base+4)//4, (base+32*8)//4, 0x10000048):
                with self.assertRaises(ValueError):
                    image_slot(dict(cbuf_slot=2, handle=handle), stage)
        with self.assertRaises(ValueError):
            image_slot(dict(cbuf_slot=3, handle=0x48), 'cs')
        self.assertEqual(texture_slot(dict(handle=8)), (0, False))
        self.assertEqual(texture_slot(dict(handle=0x1000005a)), (0, True))

    def test_resource_reader_clamps_ranges(self):
        package = Package.__new__(Package)
        package.files = {'sample': (100, 6)}
        from types import SimpleNamespace
        package.rom_section = SimpleNamespace(read=lambda start, length: b'sample'[start-100:start-100+length])
        self.assertEqual(package.read_resource('sample', 4, 30), b'le')
        self.assertEqual(package.read_resource('sample', 6, 30), b'')
        self.assertEqual(package.resource('sample'), b'sample')
        with self.assertRaises(ValueError):
            package.read_resource('sample', -1)


if __name__ == '__main__':
    unittest.main()
