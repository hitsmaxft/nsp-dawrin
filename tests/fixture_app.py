"""Build an original, deterministic NSP application for pipeline/CI checks.

Only generated test keys and original instructions/data are used. This is a
runtime test fixture, not a signed retail-installable application.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from content import ContentSet
from content_fixtures import APP, cnmt, nca, package, pfs, romfs, write_keys

FIXED_TIME = 1704067200
PASS = 'FIXTURE_PASS clock=ok x18=ok svc=ok'
FAIL = 'FIXTURE_FAIL'
CLOCK_SYMBOL = '_ZN2nn4time23StandardUserSystemClock14GetCurrentTimeEPNS0_9PosixTimeE'
STARTUP = ('_init_libc0', 'nnosInitialize', '_init_libc1',
           'nninitInitializeSdkModule', 'nninitStartup', '_init_libc2')


def instruction_program(expected):
    """Original AArch64 program; labels resolved without an external assembler."""
    words, labels, fixups = [], {}, []
    base = 0x100

    def emit(word):
        words.append(word)

    def relative(kind, target, register=0):
        fixups.append((len(words), kind, target, register))
        emit(0)

    emit(0xa9be7bfd)  # stp x29,x30,[sp,#-32]!
    emit(0x910003fd)  # mov x29,sp
    emit(0xd2800000 | (0x321 << 5) | 18)  # mov x18,#0x321
    emit(0x910043e0)  # add x0,sp,#16: output timestamp
    emit(0x90000050)  # adrp x16,0x8000: relocated import slot
    emit(0xf9400210)  # ldr x16,[x16]
    emit(0xd63f0200)  # blr x16: clock API
    relative('cbnz', 'fail', 0)
    emit(0xf9400be9)  # ldr x9,[sp,#16]
    emit(0xd2800000 | ((expected & 0xffff) << 5) | 10)
    emit(0xf2a00000 | (((expected >> 16) & 0xffff) << 5) | 10)
    emit(0xeb0a013f)  # cmp x9,x10
    relative('ne', 'fail')
    emit(0xf100001f | (0x321 << 10) | (18 << 5))  # cmp x18,#0x321
    relative('ne', 'fail')
    relative('adr', 0x4900, 0)
    emit(0xd2800001 | (len(PASS) << 5))
    emit(0xd40004e1)  # svc #0x27: OutputDebugString
    relative('b', 'return')
    labels['fail'] = base + len(words) * 4
    relative('adr', 0x4980, 0)
    emit(0xd2800001 | (len(FAIL) << 5))
    emit(0xd40004e1)
    labels['return'] = base + len(words) * 4
    emit(0xa8c27bfd)  # ldp x29,x30,[sp],#32
    emit(0xd65f03c0)  # ret
    for index, kind, target, register in fixups:
        target = labels[target] if isinstance(target, str) else target
        delta = target - (base + index * 4)
        if kind == 'adr':
            words[index] = 0x10000000 | ((delta & 3) << 29) | (((delta >> 2) & 0x7ffff) << 5) | register
        elif kind == 'b':
            words[index] = 0x14000000 | ((delta // 4) & 0x3ffffff)
        else:
            words[index] = (0x35000000 | register if kind == 'cbnz' else 0x54000001) | (((delta // 4) & 0x7ffff) << 5)
    return struct.pack('<' + 'I' * len(words), *words)


def executable(main=True, expected=FIXED_TIME):
    text, ro, data = bytearray(0x200), bytearray(0x1000), bytearray(0x100)
    struct.pack_into('<II', text, 0, 0x14000020, 0x4000)
    struct.pack_into('<I', text, 0x80, 0xd65f03c0)  # original no-op startup routine
    if main:
        program = instruction_program(expected)
        text[0x100:0x100 + len(program)] = program
    exports = [(name, 0x80) for name in STARTUP] + [('nnMain', 0x100)] if main else [('fixtureSupport', 0x80)]
    symbols, strings = bytearray(24), bytearray(b'\0')
    for name, address in exports:
        offset = len(strings); strings.extend(name.encode() + b'\0')
        symbols.extend(struct.pack('<IBBHQQ', offset, 0x12, 0, 1, address, 4))
    if main:
        import_index = len(symbols) // 24
        offset = len(strings); strings.extend(CLOCK_SYMBOL.encode() + b'\0')
        symbols.extend(struct.pack('<IBBHQQ', offset, 0x12, 0, 0, 0, 0))
        struct.pack_into('<QQq', ro, 0x700, 0x8000, (import_index << 32) | 1025, 0)
        ro[0x900:0x900 + len(PASS)] = PASS.encode()
        ro[0x980:0x980 + len(FAIL)] = FAIL.encode()
    ro[0x200:0x200 + len(symbols)] = symbols
    ro[0x200 + len(symbols):0x200 + len(symbols) + len(strings)] = strings
    dynamic = [(6, 0x4200), (5, 0x4200 + len(symbols))]
    if main:
        dynamic += [(7, 0x4700), (8, 24), (9, 24)]
    dynamic += [(0, 0)]
    for index, row in enumerate(dynamic):
        struct.pack_into('<QQ', ro, 0x40 + index * 16, *row)
    struct.pack_into('<4siiiiii', ro, 0, b'MOD0', 0x40, 0x4100, 0x4200, 0x800, 0x820, 0)
    # Minimal unwind index supplies function boundaries to the production rewriter.
    struct.pack_into('<4BII', ro, 0x800, 1, 3, 3, 3, 0, 2 if main else 1)
    struct.pack_into('<II', ro, 0x80c, 0x80, 0)
    if main:
        struct.pack_into('<II', ro, 0x814, 0x100, 0)
    header = bytearray(0x100); header[:4] = b'NSO0'
    position = len(header)
    for index, (address, segment) in enumerate(((0, text), (0x4000, ro), (0x8000, data))):
        struct.pack_into('<III', header, 0x10 + index * 16, position, address, len(segment))
        struct.pack_into('<I', header, 0x60 + index * 4, len(segment))
        header[0xa0 + index * 32:0xc0 + index * 32] = hashlib.sha256(segment).digest()
        position += len(segment)
    struct.pack_into('<I', header, 0x3c, 0x100)
    header[0x40:0x60] = hashlib.sha256(text + ro + data).digest()
    return bytes(header + text + ro + data)


def application(version=0, expected=FIXED_TIME):
    title, kind = (APP, 0x80) if not version else (APP + 0x800, 0x81)
    modules = pfs({'main': executable(expected=expected), 'sdk': executable(main=False)})
    code = nca(title, 0, [('pfs', modules), ('rom', romfs(b'updated fixture' if version else b'base fixture'))])
    name = hashlib.sha256(code).hexdigest()[:32]
    meta = nca(title, 1, [('pfs', pfs({'content.cnmt': cnmt(title, kind, version, [(name, code, 1)])}))])
    return pfs({name + '.nca': code, hashlib.sha256(meta).hexdigest()[:32] + '.cnmt.nca': meta})


def build(output, expected=FIXED_TIME):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Generate fixture packages outside the checkout')
    output.mkdir(parents=True, exist_ok=True)
    files = {'base.nsp': application(expected=expected),
             'update.nsp': application(2, expected),
             'addon.nsp': pfs(package(APP + 0x1001, 0x82, 0, b'fixture add-on', 2))}
    for name, value in files.items():
        (output / name).write_bytes(value)
    write_keys(output / 'fixture.keys')
    manifest = {'schema': 1, 'origin': 'original synthetic fixture', 'files': {
        name: {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()} for name, value in files.items()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def validate(root, native_host=None, expected=FIXED_TIME):
    root = Path(root); build(root / 'packages', expected)
    packages = root / 'packages'; keys = packages / 'fixture.keys'
    paths = [packages / name for name in ('base.nsp', 'update.nsp', 'addon.nsp')]
    content = ContentSet(paths, keys)
    try:
        if content.read_resource('sample') != b'updated fixture':
            raise AssertionError('Update resource selection failed')
        description = content.describe()
        if len(description['dlc']) != 1 or description['dlc'][0]['index'] != 1:
            raise AssertionError('Add-on selection failed')
        cache = root / 'cache'; content.prepare(cache)
        if (cache / 'ExeFS/main').read_bytes() != executable(expected=expected):
            raise AssertionError('Executable extraction changed bytes')
        mount = content.mounts[1]
        offset, size = mount['files']['sample']
        if mount['section'].read(offset, size) != b'fixture add-on':
            raise AssertionError('Add-on resource read failed')
    finally:
        content.close()
    for name in ('main', 'sdk'):
        subprocess.run([sys.executable, str(ROOT / 'tools/patch_nso.py'),
                        str(cache / 'ExeFS' / name), str(cache / 'patched'), name],
                       check=True, capture_output=True, text=True, timeout=30)
    result = {'package': 'passed', 'update': 'passed', 'dlc': 'passed', 'rewrite': 'passed',
              'native_execution': 'not_run'}
    if native_host:
        env = {key: value for key, value in os.environ.items() if not key.startswith(('DM_', 'NSP_'))}
        env.update(DM_FIXED_TIME=str(FIXED_TIME), DM_TIMEOUT='10', DM_SVC='1',
                   NSP_SETTINGS_PATH=str(root / 'settings.json'), DM_TITLE_ID=f'{APP:016x}',
                   DM_SAVE=str(root / 'save'), DM_TEMP=str(root / 'temp'),
                   DM_CONTROL=str(root / 'control.sock'))
        run = subprocess.run([str(Path(native_host).resolve()), str(cache / 'patched')],
                             env=env, capture_output=True, text=True, timeout=15)
        log = run.stdout + run.stderr
        (root / 'native.log').write_text(log)
        if run.returncode or PASS not in log or FAIL in log or 'NATIVE RETURN nnMain' not in log:
            raise AssertionError('Synthetic guest failed; inspect native.log')
        result['native_execution'] = 'passed'
    return result


def validate_with_negative_control(root, native_host):
    root = Path(root)
    result = validate(root / 'positive', native_host)
    negative = root / 'negative'
    try:
        validate(negative, native_host, expected=FIXED_TIME + 1)
    except AssertionError:
        log = (negative / 'native.log').read_text()
        if FAIL not in log or PASS in log or 'NATIVE RETURN nnMain' not in log:
            raise AssertionError('Negative control did not reach the guest assertion')
    else:
        raise AssertionError('Incorrect guest expectation was accepted')
    result['negative_control'] = 'passed'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Generate packages without executing')
    parser.add_argument('--native-host', type=Path)
    parser.add_argument('--negative-control', action='store_true')
    args = parser.parse_args()
    if args.negative_control and not args.native_host:
        parser.error('--negative-control requires --native-host')
    if args.output and (args.native_host or args.negative_control):
        parser.error('--output only generates packages; omit it to validate')
    if args.output:
        print(json.dumps(build(args.output), indent=2))
    else:
        with tempfile.TemporaryDirectory(prefix='nsp-fixture-') as directory:
            try:
                result = (validate_with_negative_control(directory, args.native_host)
                          if args.negative_control else validate(directory, args.native_host))
            except Exception:
                # Fixtures use original synthetic data only. Keep CI failures actionable.
                for log in Path(directory).rglob('native.log'):
                    print(log.read_text()[-8000:], file=sys.stderr)
                raise
            print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
