import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from shader_jobs import prepare,prepare_observed,validate_facts


def capture(root,stage=1):
    control=bytearray(0x880);struct.pack_into('<II',control,0x700,0x80,0x100)
    control[8]=stage
    code=bytearray(0x100);code[:4]=bytes.fromhex('78563412');struct.pack_into('<I',code,0x30,stage<<10)
    key=hashlib.sha256(control).hexdigest()[:16]
    (root/(key+'.control')).write_bytes(control);(root/(key+'.code')).write_bytes(code)
    return key


class ShaderJobTests(unittest.TestCase):
    def test_raw_compute_descriptor_and_metadata_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            control=bytearray(0x880);code=bytes(0x180)
            struct.pack_into('<II',control,0,0x98761234,1)
            struct.pack_into('<II',control,0x700,0x100,len(code))
            struct.pack_into('<I',control,0x714,5)
            struct.pack_into('<4I',control,0x748,4,8,2,2048)
            def publish():
                key=hashlib.sha256(control).hexdigest()[:16]
                (root/(key+'.control')).write_bytes(control)
                (root/(key+'.code')).write_bytes(code)
                return key
            key=publish();jobs,failures=prepare(root,'chain',key)
            self.assertFalse(failures)
            self.assertEqual(jobs[0]['stage'],'cs')
            self.assertEqual(jobs[0]['local'],[4,8,2])
            self.assertEqual(jobs[0]['shared'],2048)
            self.assertEqual(Path(jobs[0]['code']).read_bytes(),code[:0x100])
            self.assertEqual(jobs[0]['c1'],code[0x100:].hex())
            with self.assertRaisesRegex(ValueError,'conflicts'):
                prepare(root,'chain',key,runtime_facts=dict(stage='ps'))
            with self.assertRaisesRegex(ValueError,'conflicts'):
                prepare(root,'chain',key,runtime_facts=dict(stage='cs',values=dict(local=[1,1,1])))
            for offset,value,error in ((4,2,'layout'),(0x748,0,'dimensions'),(0x754,65540,'extent')):
                original=control[offset:offset+4]
                struct.pack_into('<I',control,offset,value)
                with self.assertRaisesRegex(ValueError,error):prepare(root,'chain',publish())
                control[offset:offset+4]=original

    def test_requested_capture_ignores_unrelated_malformed_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=capture(root)
            (root/('f'*16+'.control')).write_bytes(b'invalid')
            jobs,failures=prepare(root,'test-chain',key)
            self.assertEqual(len(jobs),1);self.assertFalse(failures)
            _,failures=prepare(root,'test-chain')
            self.assertIn('f'*16,failures)

    def test_runtime_facts_and_variants_keep_independent_receipts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=capture(root)
            for variant,kind in (('a'*16,'cube'),('b'*16,'2d')):
                jobs,_=prepare(root,'test-chain',key,variant,dict(stage='vs',values=dict(tex={'0':kind})))
                self.assertEqual(jobs[0]['tex']['0'],kind)
                self.assertEqual(jobs[0]['source_key'],key)
            self.assertEqual(len(json.loads((root/'jobs.json').read_text())),2)
            prepare(root,'new-chain',key)
            self.assertEqual(len(json.loads((root/'jobs.json').read_text())),1)

    def test_compute_requires_explicit_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=capture(root,0)
            row=dict(stage='cs',values=dict(local=[8,4,1],shared=0))
            (root/'shader-facts.json').write_text(json.dumps({key:row}))
            with self.assertRaisesRegex(ValueError,'code offset'):prepare(root,'chain',key)
            row['code_offset']=0x30
            (root/'shader-facts.json').write_text(json.dumps({key:row}))
            jobs,_=prepare(root,'chain',key)
            self.assertEqual(jobs[0]['stage'],'cs');self.assertEqual(jobs[0]['local'],[8,4,1])

    def test_observed_variants_rebuild_from_validated_inputs_for_new_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = capture(root); identities = []
            for kind in ('cube', '2d'):
                facts = dict(stage='vs', values=dict(tex={'0': kind}))
                encoded = json.dumps(dict(capture=source, facts=facts), sort_keys=True,
                                     separators=(',', ':')).encode()
                key = hashlib.sha256(encoded).hexdigest()[:16]; identities.append(key)
                (root/(key+'.facts.json')).write_text(json.dumps(facts))
                prepare(root, 'old-chain', source, key, facts)
            jobs, failures = prepare_observed(root, 'new-chain')
            self.assertFalse(failures)
            self.assertEqual({job['key'] for job in jobs}, set(identities))
            self.assertEqual({job['tex']['0'] for job in jobs}, {'cube', '2d'})
            self.assertTrue(all(Path(job['code']).parent == root/'translated/new-chain' for job in jobs))
            self.assertTrue(all(not Path(job['code']).with_suffix('.spv').exists() for job in jobs))
            before = (root/'jobs.json').read_bytes()
            (root/(identities[0]+'.facts.json')).write_text(json.dumps(dict(stage='ps', values={})))
            with self.assertRaisesRegex(ValueError, 'variant identity'):
                prepare_observed(root, 'another-chain')
            self.assertEqual((root/'jobs.json').read_bytes(), before)

    def test_invalid_facts_rejected_before_translation(self):
        for values in ({'attr':{'32':'float'}},{'tex':{'0':'invalid'}},{'code':'path'},
                       {'img':{'0':{'type':'2d','fmt':'../path'}}}):
            with self.assertRaises(ValueError):validate_facts(values,'vs')
        with self.assertRaises(ValueError):validate_facts(dict(local=[1024,1024,1],shared=0),'cs')

if __name__=='__main__':unittest.main()
