"""Verify virtual-register calls preserve arguments, stack and guest return PC."""
import ast
from pathlib import Path
import random
import re
from capstone.arm64 import ARM64_OP_IMM
import struct
import unittest
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
try:
    import unicorn as uc
    from unicorn import arm64_const as regs
except ImportError:
    uc = None


@unittest.skipIf(uc is None, 'Install unicorn for isolated instruction verification')
class RewriteCallTests(unittest.TestCase):
    def test_jump_table_tracks_copied_index(self):
        source = Path(__file__).resolve().parents[1]/'tools/patch_nso.py'
        tree = ast.parse(source.read_text())
        namespace = dict(struct=struct, re=re, IMG=bytearray(0x9000), TEXT_END=0x2000,
                         NAME='synthetic', ARM64_OP_IMM=ARM64_OP_IMM)
        exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef)],[]),str(source),'exec'),namespace)
        md=Cs(CS_ARCH_ARM64,CS_MODE_ARM);md.detail=True
        words=[0x71001ebf,0x54000128,0x2a1503f2,namespace['ADRP'](4,0x100c,0x8000),
               namespace['ADDI'](4,4,0),0xb8b27892,namespace['ADDR'](18,18,4),namespace['BR'](18)]
        for i in range(8):struct.pack_into('<i',namespace['IMG'],0x8000+4*i,0x1100+4*i-0x8000)
        ins=list(md.disasm(b''.join(struct.pack('<I',w) for w in words),0x1000))
        self.assertEqual(namespace['relative32_jump_range'](ins,len(ins)-1),(0x1100,8))
        words[2]=0x110006b2  # add w18,w21,#1 invalidates the proven bound.
        ins=list(md.disasm(b''.join(struct.pack('<I',w) for w in words),0x1000))
        self.assertIsNone(namespace['relative32_jump_range'](ins,len(ins)-1))

    def test_indirect_call_preserves_guest_abi(self):
        source = Path(__file__).resolve().parents[1]/'tools/patch_nso.py'
        tree = ast.parse(source.read_text())
        functions = ast.Module([node for node in tree.body if isinstance(node, ast.FunctionDef)], [])
        rng = random.Random(718)
        for _ in range(32):
            namespace = dict(struct=struct, patch=bytearray(), fix=[], PATCH_OFF=0x20000,
                             KEY_PAGE_OFF=0x18000, KEY_INDEX={'K18':0})
            exec(compile(functions, str(source), 'exec'), namespace)
            decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
            instruction = next(decoder.disasm(struct.pack('<I',0xd63f0240),0x12340))
            entry = namespace['site_blr'](instruction)
            machine = uc.Uc(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
            machine.mem_map(0x10000,0x60000)
            machine.mem_write(entry, bytes(namespace['patch']))
            slot = rng.randrange(256,384)*8
            machine.mem_write(0x18000, struct.pack('<Q',slot))
            machine.mem_write(0x40000+slot, struct.pack('<Q',0x30000))
            machine.reg_write(regs.UC_ARM64_REG_TPIDRRO_EL0,0x40000)
            register_ids = [getattr(regs,f'UC_ARM64_REG_X{i}') for i in range(31)]
            original = [rng.getrandbits(64) for _ in register_ids]
            for register,value in zip(register_ids,original):machine.reg_write(register,value)
            machine.reg_write(regs.UC_ARM64_REG_SP,0x60000)
            flags = rng.randrange(16)<<28
            machine.reg_write(regs.UC_ARM64_REG_NZCV,flags)
            stack = rng.randbytes(128);machine.mem_write(0x60000,stack)
            machine.emu_start(entry,0x30000,count=32)
            self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_PC),0x30000)
            self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_LR),instruction.address+4)
            self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_SP),0x60000)
            self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_NZCV),flags)
            self.assertEqual(bytes(machine.mem_read(0x60000,128)),stack)
            for i,register in enumerate(register_ids):
                if i not in (16,30):self.assertEqual(machine.reg_read(register),original[i])
            # The callee returns directly to the original guest instruction stream.
            machine.mem_write(0x30000,struct.pack('<II',0x91000400,0xd65f03c0))
            machine.emu_start(0x30000,instruction.address+4,count=4)
            self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0),(original[0]+1)&((1<<64)-1))


if __name__ == '__main__':unittest.main()
