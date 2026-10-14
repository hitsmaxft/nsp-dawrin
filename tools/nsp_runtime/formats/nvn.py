"""Extract validated graphics programs from supported native control layouts."""
import hashlib
import struct
from ..interfaces import DecodeResult, ShaderBlob, ShaderProgram


def compute_descriptor(control, code):
    """Decode revision-one raw compute metadata, without a graphics SPH."""
    if code[:4] == bytes.fromhex('78563412'):
        return None
    if len(control) != 0x880 or len(code) < 0x80:
        raise ValueError('Unsupported shader capture layout')
    magic, revision = struct.unpack_from('<II', control)
    stage = struct.unpack_from('<I', control, 0x714)[0]
    if (magic, revision, stage) != (0x98761234, 1, 5):
        raise ValueError('Unsupported raw compute control layout')
    local = list(struct.unpack_from('<III', control, 0x748))
    shared = struct.unpack_from('<I', control, 0x754)[0]
    if any(not 1 <= n <= 1024 for n in local) or local[0]*local[1]*local[2] > 1024:
        raise ValueError('Invalid compute workgroup dimensions')
    if shared > 65536 or shared % 4:
        raise ValueError('Invalid compute shared-memory extent')
    return dict(local=local, shared=shared)


class NvnBlobDecoder:
    format = 'nvn-blob'

    def decode(self, blob: ShaderBlob) -> DecodeResult:
        result = DecodeResult()
        raw = blob.data
        cursor = 0
        while True:
            cursor = raw.find(b'\x78\x56\x34\x12', cursor)
            if cursor < 0:
                break
            start = next((cursor - width for width in (0x850, 0x848)
                          if cursor >= width + 8 and raw[cursor-width-8:cursor-width-4] == struct.pack('<I', width)
                          and raw[cursor-width:cursor-width+4] == b'\x34\x12\x76\x98'), -1)
            code_start = cursor
            cursor += 4
            if start < 8:
                continue
            control = raw[start:start+0x880]
            if len(control) != 0x880:
                continue
            c1off, code_size = struct.unpack_from('<II', control, 0x700)
            declared = struct.unpack_from('<I', raw, start-4)[0]
            if not (0x80 <= c1off <= code_size == declared and code_start+code_size <= len(raw)):
                result.unsupported.append(f'{blob.label}: invalid shader extent at {code_start:#x}')
                continue
            code = raw[code_start:code_start+code_size]
            stage = (struct.unpack_from('<I', code, 0x30)[0] >> 10) & 15
            key = hashlib.sha256(control).hexdigest()[:16]
            if stage not in (1, 5):
                result.unsupported.append(f'{key}: unsupported shader stage {stage}')
                continue
            result.programs.append(ShaderProgram(key, 'vertex' if stage == 1 else 'fragment', control, code))
        if not result.programs and not result.unsupported:
            result.unsupported.append(f'{blob.label}: no supported native shader layout found')
        return result
