










# Generic NSO rewriter: Switch aarch64 module → an image that can execute natively on Apple systems.
# Usage: patch_nso.py <NSO file> <output dir> <module name>
# Rewrites (the Apple kernel modifies x18 and tpidr_el0; Horizon's thread area, svc and timers have no counterpart on Apple):
#   x18 read/write      → thread slot K18 (TSD, via tpidrro_el0)
#   mrs tpidr_el0       → read thread slot KTLS; msr tpidr_el0 → write KTLS
#   mrs tpidrro_el0     → read thread slot KTLR (Horizon ThreadLocalRegion pointer)
#   svc #n, mrs cntpct_el0 → host gate (gate address taken from thread slot KGATE; once in C, gates.tsv is looked up by return point)
#   Registered cuts (CUTS, restricted by NSO build ID): before rewriting, the original bytes are asserted one by one and any mismatch aborts; results are listed in <name>.cuts.tsv
#   Registered observation gates (OBS, restricted by build ID): one instruction at the entry is replaced with "enter the host observation callback → execute the original instruction → jump back", so diagnostics modify zero code at runtime; listed in <name>.obs.tsv
# The key page only stores "actual key number × 8" at the end of the data segment, and patch code fetches thread slots indirectly through the key page: the loader may use any key number.
# Output: <name>.patched.bin (key page and patch area appended after the image at PATCH_OFF), <name>.fixups.tsv (layout and key page index header), <name>.gates.tsv, <name>.sites.tsv, <name>.cuts.tsv, <name>.obs.tsv
import struct, re, sys, os, json, hashlib
from itertools import combinations
import lz4.block
from capstone import *
from capstone.arm64 import ARM64_OP_IMM

src, outdir, NAME = sys.argv[1], sys.argv[2], sys.argv[3]
d = open(src, 'rb').read()
assert d[:4] == b'NSO0'
flags = struct.unpack_from('<I', d, 0xc)[0]
segs = [struct.unpack_from('<III', d, 0x10 + i * 0x10) for i in range(3)]
bss = struct.unpack_from('<I', d, 0x3c)[0]
csz = struct.unpack_from('<III', d, 0x60)
IMG = bytearray(segs[2][1] + segs[2][2] + bss)
for i, (fo, mo, sz) in enumerate(segs):
    raw = d[fo:fo + csz[i]]
    if flags >> i & 1: raw = lz4.block.decompress(raw, uncompressed_size=sz)
    IMG[mo:mo + sz] = raw
TEXT_END = segs[0][2]
RO_OFF, DATA_OFF = segs[1][1], segs[2][1]
KEY_PAGE_OFF = (len(IMG) + 0x3FFF) & ~0x3FFF
IMG.extend(bytes(0x4000))
PATCH_OFF = (len(IMG) + 0xFFFF) & ~0xFFFF
# No title-specific instruction or gameplay patches.
CUTS = {}
OBS = {}
BUILD_ID = d[0x40:0x50].hex()
cuts = []
# Key page indices are fixed; the key page content is written by the loader as "actual key number × 8".
KEYS = {'K18': 508, 'KTLS': 509, 'KTLR': 510, 'KGATE': 511, 'KRES0': 506, 'KRES1': 507, 'KASPECT': 505, 'KASPECTUI': 504}   # KRES*: resolution parameter slots; KASPECT: picture aspect ratio cap (see PARAMS)
KEY_INDEX = {k: i for i, k in enumerate(('K18', 'KTLS', 'KTLR', 'KGATE', 'KRES0', 'KRES1', 'KASPECT', 'KASPECTUI'))}

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM); md.detail = True
patch = bytearray(); fix = []; gates = []; stats = {}
def stat(k): stats[k] = stats.get(k, 0) + 1
def here(): return PATCH_OFF + len(patch)
def emit(w, kind=None):
    if kind: fix.append((len(patch), kind))
    patch.extend(struct.pack('<I', w & 0xFFFFFFFF))

def emit_key_addr(reg, kind):
    fix.append((len(patch), kind)); emit(ADRP(reg, here(), KEY_PAGE_OFF)); emit(LDRX(reg, reg, KEY_INDEX[kind]))

def emit_slot_addr(base, key_reg, kind):
    emit_key_addr(key_reg, kind); emit(ADDR(base, base, key_reg))


# ---- Encoders ----
def B(frm, to):
    off = to - frm; assert -(1 << 27) <= off < (1 << 27) and off % 4 == 0
    return 0x14000000 | ((off >> 2) & 0x3FFFFFF)
def STP(t, t2, n, off): return 0xA9000000 | (((off // 8) & 0x7F) << 15) | (t2 << 10) | (n << 5) | t
def LDP(t, t2, n, off): return 0xA9400000 | (((off // 8) & 0x7F) << 15) | (t2 << 10) | (n << 5) | t
def STP_PRE(t, t2, n, off): return 0xA9800000 | (((off // 8) & 0x7F) << 15) | (t2 << 10) | (n << 5) | t
def LDP_POST(t, t2, n, off): return 0xA8C00000 | (((off // 8) & 0x7F) << 15) | (t2 << 10) | (n << 5) | t
def STUR(t, n, off): return 0xF8000000 | ((off & 0x1FF) << 12) | (n << 5) | t   # stur xt,[xn,#off] (off may be negative)
def LDUR(t, n, off): return 0xF8400000 | ((off & 0x1FF) << 12) | (n << 5) | t   # ldur xt,[xn,#off]
def LDRX(t, n, imm12=0): return 0xF9400000 | (imm12 << 10) | (n << 5) | t
def STRX(t, n, imm12=0): return 0xF9000000 | (imm12 << 10) | (n << 5) | t
def MRS_TPIDRRO(t): return 0xD53BD060 | t
def ADRP(dd, pc, target):
    imm = ((target & ~0xFFF) - (pc & ~0xFFF)) >> 12; assert -(1 << 20) <= imm < (1 << 20)
    return 0x90000000 | ((imm & 3) << 29) | (((imm >> 2) & 0x7FFFF) << 5) | dd
def ADDI(dd, n, imm12, sh=0): return 0x91000000 | (sh << 22) | (imm12 << 10) | (n << 5) | dd
def ADDR(dd, n, m): return 0x8B000000 | (m << 16) | (n << 5) | dd
def SUBI(dd, n, imm12, sh=0): return 0xD1000000 | (sh << 22) | (imm12 << 10) | (n << 5) | dd
def BR(n): return 0xD61F0000 | (n << 5)
def BLR(n): return 0xD63F0000 | (n << 5)
NOP = 0xD503201F

def dis(w, addr):
    l = list(md.disasm(struct.pack('<I', w), addr)); assert len(l) == 1, hex(w)
    return l[0]
def regset(ins):
    r, w = ins.regs_access()
    return {ins.reg_name(x) for x in r}, {ins.reg_name(x) for x in w}
def num(name):
    m = re.fullmatch(r'[xw](\d+)', name or ''); return int(m.group(1)) if m else None
def has18(ins): return re.search(r'\b[xw]18\b', ins.op_str) is not None
def regs_in(ins):
    s = {int(n) for n in re.findall(r'\b[xw](\d+)\b', ins.op_str)}
    try:
        rd, wr = regset(ins); s |= {num(n) for n in rd | wr} - {None}
    except Exception: pass
    return s
def pick(avoid, n=2):
    out = [r for r in range(0, 16) if r not in avoid and r != 18][:n]; assert len(out) == n; return out

def subst(ins, S):
    """x18/w18 → xS/wS: only the 4 register field positions are changed, verified against the disassembly text."""
    w = struct.unpack('<I', ins.bytes)[0]
    want = re.sub(r'\b([xw])18\b', lambda m: f'{m.group(1)}{S}', ins.op_str)
    pos = [p for p in (0, 5, 10, 16) if (w >> p) & 31 == 18]
    for k in range(len(pos), 0, -1):
        for c in combinations(pos, k):
            nw = w
            for p in c: nw = (nw & ~(31 << p)) | (S << p)
            try: dd = dis(nw, ins.address)
            except AssertionError: continue
            if dd.mnemonic == ins.mnemonic and dd.op_str == want: return nw
    raise RuntimeError(f'subst fail {ins.address:x} {ins.mnemonic} {ins.op_str}')


# ---- Rewrite blocks of each kind ----
def sp_delta(ins):
    """The amount an instruction writes back to sp (pre-index [sp, #i]! / post-index [sp], #i); returns 0 if sp is not written back."""
    m = re.search(r'\[sp, #(-?(?:0x)?[0-9a-f]+)\]!', ins.op_str)
    if m: return int(m.group(1), 0)
    m = re.search(r'\[sp\], #(-?(?:0x)?[0-9a-f]+)$', ins.op_str)
    if m: return int(m.group(1), 0)
    assert not re.match(r'(sp|wsp),', ins.op_str), f'writes sp: {ins.address:x} {ins.op_str}'
    return 0

def site_plain(ins):
    S, T = pick(regs_in(ins))
    dlt = sp_delta(ins)
    save = -16 if dlt == 0 else -112          # Instructions that modify sp write below sp, so the scratch save is placed deep in the reserved area
    assert dlt == 0 or dlt >= -96, f'sp delta {dlt} at {ins.address:x}'
    start = here()
    emit(STP(S, T, 31, save)); emit(MRS_TPIDRRO(T)); emit_slot_addr(T, S, 'K18'); emit(LDRX(S, T))
    emit(subst(ins, S))
    emit(STRX(S, T))                 # Always write back: capstone can miss reporting a write (the adds w18 instance)
    emit(LDP(S, T, 31, save - dlt)); emit(B(here(), ins.address + 4))
    return start

def site_cond(ins):
    w = struct.unpack('<I', ins.bytes)[0]
    S, T = pick(regs_in(ins))
    tgt = ins.operands[-1].imm
    start = here()
    emit(STP(S, T, 31, -16)); emit(MRS_TPIDRRO(T)); emit_slot_addr(T, S, 'K18'); emit(LDRX(S, T))
    m = ins.mnemonic
    taken = here() + 4 * 3
    off = (taken - here()) >> 2
    nw = ((w & 0xFF000000) | ((off & 0x7FFFF) << 5) | S) if m in ('cbz', 'cbnz') else ((w & 0xFFF80000) | ((off & 0x3FFF) << 5) | S)
    pc = here(); emit(nw)
    dd = dis(nw, pc); assert dd.mnemonic == m and dd.operands[-1].imm == taken
    emit(LDP(S, T, 31, -16)); emit(B(here(), ins.address + 4))
    assert here() == taken
    emit(LDP(S, T, 31, -16)); emit(B(here(), tgt))
    return start

def site_pcrel(ins):
    tgt = ins.operands[1].imm
    S, T = pick(set())
    start = here()
    emit(STP(S, T, 31, -16)); emit(MRS_TPIDRRO(T)); emit_slot_addr(T, S, 'K18')   # S first serves as a temporary for the key page offset; the next instruction then loads the target value
    pc = here(); emit(ADRP(S, pc, tgt))
    if ins.mnemonic == 'adr': emit(ADDI(S, S, tgt & 0xFFF))
    emit(STRX(S, T))
    emit(LDP(S, T, 31, -16)); emit(B(here(), ins.address + 4))
    return start

def site_br(ins, base, count):
    """Jump table br x18: target = base + 4i. Stash x16 in the red zone → equally spaced landing pads → restore x16 → original target."""
    start = here()
    emit(STUR(16, 31, -16)); emit(STUR(17, 31, -24))   # x16 / x17 are temporary registers that can stay live within a function; save them to the red zone before borrowing
    emit(MRS_TPIDRRO(16)); emit_slot_addr(16, 17, 'K18'); emit(LDRX(16, 16)); emit(LDUR(17, 31, -24))
    padbase = start + 4 * 24
    delta = padbase - base
    op = ADDI if delta >= 0 else SUBI; dl = abs(delta)
    ops = []; hi, lo = dl >> 12, dl & 0xFFF
    while hi: h = min(hi, 0xFFF); ops.append(op(16, 16, h, 1)); hi -= h
    if lo: ops.append(op(16, 16, lo, 0))
    assert len(ops) <= 12
    for o in ops: emit(o)
    emit(BR(16))
    while here() < padbase: emit(NOP)
    tails = padbase + 4 * count
    for i in range(count): emit(B(here(), tails + 8 * i))
    for i in range(count):
        emit(0xF85F0000 | (31 << 5) | 16)      # ldur x16,[sp,#-16]
        emit(B(here(), base + 4 * i))
    return start

def site_blr(ins):
    """Call through virtual x18 using ABI scratch x16; preserve the original LR."""
    assert ins.mnemonic == 'blr' and ins.op_str == 'x18'
    start = here()
    emit(STUR(17, 31, -16))
    emit(MRS_TPIDRRO(16)); emit_slot_addr(16, 17, 'K18'); emit(LDRX(16, 16))
    emit(LDUR(17, 31, -16))
    target = ins.address + 4
    emit(ADRP(30, here(), target)); emit(ADDI(30, 30, target & 0xFFF))
    emit(BR(16))
    return start

def site_sysreg_read(ins, kind):
    """mrs xN, tpidr_el0 / tpidrro_el0 → xN = thread slot value."""
    N = ins.bytes[0] & 31
    tmp = 16 if N != 16 else 17
    start = here()
    emit(STUR(tmp, 31, -16)); emit(MRS_TPIDRRO(N)); emit_slot_addr(N, tmp, kind); emit(LDRX(N, N)); emit(LDUR(tmp, 31, -16))   # tmp is saved by borrowing the red zone
    emit(B(here(), ins.address + 4))
    return start

def site_tpidr_write(ins):
    N = struct.unpack('<I', ins.bytes)[0] & 31
    (T,) = pick({N}, 1)
    start = here()
    emit(0xF81F0000 | (31 << 5) | T)           # stur xT,[sp,#-16]
    tmp = next(x for x in (16, 17) if x not in (N, T))
    emit(STUR(tmp, 31, -24)); emit(MRS_TPIDRRO(T)); emit_slot_addr(T, tmp, 'KTLS'); emit(STRX(N, T)); emit(LDUR(tmp, 31, -24))
    emit(0xF85F0000 | (31 << 5) | T)           # ldur xT,[sp,#-16]
    emit(B(here(), ins.address + 4))
    return start

def emit_gate_call():
    """    Common section of a gate block (right after stp x29,x30,[sp,#-16]! and before blr x30): x30 = the gate address in thread slot KGATE.
        Fetching the slot through the key page needs a second register to be borrowed; x29 is borrowed and then immediately restored from the stack: the x29 saved by _dm_gate must be the guest's original value --
        the host identifies the caller by [x29+8] (skill binding observation gate 6, private aiming gate svc86), and the crash backtrace also walks the x29 chain
        (since r24 plan C it was borrowed and not returned, the x29 the host got was the slot offset from the key page, and skill icons fell back to placeholder text)."""
    emit(MRS_TPIDRRO(30)); emit_slot_addr(30, 29, 'KGATE'); emit(LDRX(30, 30)); emit(LDRX(29, 31))

def site_gate(ins, kind, arg):
    """svc / mrs cntpct_el0 → host gate. The gate address is taken from thread slot KGATE; the gate looks up gates.tsv by return point (the address of this block's ldp)."""
    start = here()
    emit(STP_PRE(29, 30, 31, -16))
    emit_gate_call()
    emit(BLR(30))
    ret = here()
    emit(LDP_POST(29, 30, 31, 16))
    emit(B(here(), ins.address + 4))
    gates.append((ret, kind, arg, ins.address))
    return start

def site_obs(off, oid, word):
    """    Observation gate: original entry instruction → enter the host gate (arg = observation number) → restore x29/x30 → execute the original instruction → jump back to off+4.
        The first half of the gate block is word-for-word isomorphic with site_gate; the host only reads registers and does not modify them (the x0–x8 written back by dm_gate are the original values)."""
    ins = dis(word, off)
    assert ins.mnemonic not in ('adr', 'adrp', 'b', 'bl', 'br', 'blr', 'ret', 'cbz', 'cbnz', 'tbz', 'tbnz') and not ins.mnemonic.startswith('b.') \
        and not (ins.mnemonic.startswith('ldr') and '[' not in ins.op_str) and not has18(ins), f'观测门原指令不可搬 {off:#x} {ins.mnemonic} {ins.op_str}'
    start = here()
    emit(STP_PRE(29, 30, 31, -16))
    emit_gate_call()
    emit(BLR(30))
    ret = here()
    emit(LDP_POST(29, 30, 31, 16))
    emit(word)
    emit(B(here(), off + 4))
    gates.append((ret, 'obs', oid, off))
    return start


# ---- Exclusive windows ----
EXCL_LD = ('ldxr', 'ldaxr', 'ldxp', 'ldaxp', 'ldxrb', 'ldaxrb', 'ldxrh', 'ldaxrh')
EXCL_ST = ('stxr', 'stlxr', 'stxp', 'stlxp', 'stxrb', 'stlxrb', 'stxrh', 'stlxrh')
def find_windows(insl):
    out = []
    for i, ins in enumerate(insl):
        if ins.mnemonic not in EXCL_LD: continue
        j = i
        while j < len(insl) and insl[j].mnemonic not in EXCL_ST: j += 1
        if j >= len(insl) or j - i >= 16: continue
        if j + 1 < len(insl) and insl[j + 1].mnemonic in ('cbz', 'cbnz'): j += 1
        seg = insl[i:j + 1]
        if any(has18(x) for x in seg): out.append(seg)
    return out

def site_window(seg):
    used = set()
    for x in seg: used |= regs_in(x)
    S, T = pick(used)
    lo, hi = seg[0].address, seg[-1].address + 4
    start = here()
    emit(STP(S, T, 31, -16)); emit(MRS_TPIDRRO(T)); emit_slot_addr(T, S, 'K18'); emit(LDRX(S, T))
    copy0 = here(); n = len(seg)
    exits = copy0 + 4 * n
    ex_targets = []; words = []
    for k, x in enumerate(seg):
        w = struct.unpack('<I', x.bytes)[0]
        if has18(x): w = subst(x, S)
        m = x.mnemonic
        if m in ('cbz', 'cbnz', 'tbz', 'tbnz') or m.startswith('b.'):
            tgt = x.operands[-1].imm
            if lo <= tgt < hi: newt = copy0 + (tgt - lo)
            else: ex_targets.append(tgt); newt = exits + 16 * len(ex_targets)   # Exit stub 0 is reserved for the sequential fall-out (see below); targets outside the window start from stub 1
            pc = copy0 + 4 * k; off = (newt - pc) >> 2
            if m in ('tbz', 'tbnz'): w = (w & 0xFFF8001F) | ((off & 0x3FFF) << 5)
            else: w = (w & 0xFF00001F) | ((off & 0x7FFFF) << 5)
            dd = dis(w, pc); assert dd.operands[-1].imm == newt and dd.mnemonic == m
        else:
            assert m not in ('adr', 'adrp', 'b', 'bl', 'br', 'blr', 'ret') and not (m == 'ldr' and '[' not in x.op_str), hex(x.address)
        words.append(w)
    for w in words: emit(w)




    # Order of the exit stubs: when the last instruction of the copy has executed, control "falls out sequentially" into exit stub 0, which immediately follows the copy -- so stub 0 must be the fall-out exit back to hi, and jump targets outside the window come after it.
    # Up to r40 the fall-out exit was placed last: whenever a window contained a conditional jump to outside the window (the "compare not equal" exit of a compare-and-swap), a successful write fell into the first external exit = handled as a failed compare
    # (one operation done twice / a lock-free list popped more than once). The game has 6 such windows (main 0x1848eb8 / 0x1848f28 / 0x1848f84, sdk 0x2ea0fc / 0x2ea4cc / 0x2ea644);
    # windows whose only branch is a cbnz back into the window are not affected. The equivalence check used to never draw the "compare equal" direction at random, so it stayed green (equiv.py now forces both directions of window branches).
    for t in [hi] + ex_targets:
        emit(STRX(S, T)); emit(LDP(S, T, 31, -16)); emit(B(here(), t)); emit(NOP)
    return start, lo, hi


# ---- Function boundaries (eh_frame_hdr) ----
m0 = struct.unpack_from('<I', IMG, 4)[0]
assert IMG[m0:m0 + 4] == b'MOD0'
ehs = m0 + struct.unpack_from('<i', IMG, m0 + 16)[0]
def rd(o, enc):
    fmt, app = enc & 0xF, enc & 0x70
    v, sz = {0x3: (struct.unpack_from('<I', IMG, o)[0], 4), 0xB: (struct.unpack_from('<i', IMG, o)[0], 4),
             0x4: (struct.unpack_from('<Q', IMG, o)[0], 8)}[fmt]
    if app == 0x10: v += o
    if app == 0x30: v += ehs
    return v, sz
_, penc, cenc, tenc = IMG[ehs:ehs + 4]
o = ehs + 4
_, s = rd(o, penc); o += s
nfde, s = rd(o, cenc); o += s
starts = set()
for _ in range(nfde):
    a, s = rd(o, tenc); o += s
    _, s = rd(o, tenc); o += s
    starts.add(a)
starts = sorted(x for x in starts if x < TEXT_END)


# ---- Linear scan to find all rewrite points (not relying on register read/write reports) ----
kinds = {}
os.makedirs(outdir, exist_ok=True)
scan_path = os.path.join(outdir, '.' + NAME + '.scan.json')
scan_id = hashlib.sha256(IMG[:TEXT_END]).hexdigest() + ':' + str(cs_version()) + ':x18-spelling-v1'
try:
    scan_cached = json.load(open(scan_path))
    if scan_cached['id'] == scan_id:
        kinds = {int(k): tuple(v) for k,v in scan_cached['kinds'].items()}
        print(f'{NAME}: reused {len(kinds)} scan sites', flush=True)
except (OSError, ValueError, KeyError):
    pass
scan_reused = bool(kinds)
scan_md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
x18_words = {}
for o in ([] if scan_reused else range(0, TEXT_END, 4)):
    w = struct.unpack_from('<I', IMG, o)[0]
    if w & 0xFFE0001F == 0xD4000001: kinds[o] = ('svc', (w >> 5) & 0xFFFF); continue
    if w & 0xFFFFFFE0 == 0xD53BD040: kinds[o] = ('tpidr_r', None); continue
    if w & 0xFFFFFFE0 == 0xD51BD040: kinds[o] = ('tpidr_w', None); continue
    if w & 0xFFFFFFE0 == 0xD53BD060: kinds[o] = ('tpidrro_r', None); continue
    if w & 0xFFFFFFE0 == 0xD53BE020: kinds[o] = ('cntpct', w & 31); continue
    if w & 0xFFFFFFE0 == 0xD53BE040: kinds[o] = ('cntvct', w & 31); continue
    # Register spelling depends on the instruction word, not its PC. Reusing
    # this classification avoids millions of repeated detail-mode decodes.
    if w not in x18_words:
        decoded = next(scan_md.disasm_lite(IMG[o:o + 4], 0), None)
        x18_words[w] = bool(decoded and re.search(r'\b[xw]18\b', decoded[3]))
    if x18_words[w]: kinds[o] = ('x18', None)
if not scan_reused:
    with open(scan_path,'w') as f: json.dump({'id':scan_id,'kinds':kinds},f)


# Take the instruction table per function, find the windows and jump tables
import bisect
def func_of(a):
    i = bisect.bisect_right(starts, a) - 1
    return (starts[i], starts[i + 1] if i + 1 < len(starts) else TEXT_END) if i >= 0 else (a, a + 4)
done = set(); windows = []; jumps = {}

def relative32_jump_range(insl, j):
    """Clang's ldrsw x18,[base,index,lsl #2]; add x18,x18,base; br x18.

    Accept only a constant table address and an explicit unsigned upper bound.
    The existing landing-pad implementation then preserves every scratch register.
    """
    if j < 3: return None
    def writes(q, reg):
        return reg in {num(q.reg_name(r)) for r in q.regs_access()[1]}
    ai = next((k for k in range(j-1,max(-1,j-8),-1) if writes(insl[k],18)),None)
    if ai is None: return None
    add = insl[ai]
    if add.mnemonic != 'add' or len(add.operands) != 3: return None
    offset_reg = num(add.reg_name(add.operands[1].reg))
    li = next((k for k in range(ai-1,max(-1,ai-8),-1) if writes(insl[k],offset_reg)),None)
    if li is None: return None
    ld = insl[li]
    if ld.mnemonic != 'ldrsw': return None
    mem = ld.operands[1].mem
    base_reg = num(ld.reg_name(mem.base)); idx = num(ld.reg_name(mem.index))
    if base_reg != num(add.reg_name(add.operands[2].reg)) or mem.disp: return None
    if 'lsl #2' not in ld.op_str: return None
    limit = None
    for k in range(li-1, max(-1,li-14), -1):
        q = insl[k]
        if q.mnemonic == 'and' and num(q.reg_name(q.operands[0].reg)) == idx and q.operands[2].type == ARM64_OP_IMM:
            mask = q.operands[2].imm
            if 0 <= mask < 4096 and (mask & (mask + 1)) == 0: limit = mask + 1
            break
        if q.mnemonic == 'mov' and len(q.operands) == 2 and writes(q, idx):
            source = num(q.reg_name(q.operands[1].reg))
            if source is None: break
            idx = source
            continue
        if q.mnemonic == 'cmp' and num(q.reg_name(q.operands[0].reg)) == idx and q.operands[1].type == ARM64_OP_IMM:
            for branch in insl[k+1:li]:
                if branch.mnemonic in ('b.hi', 'b.hs'):
                    limit = q.operands[1].imm + (branch.mnemonic == 'b.hi')
                    break
                if branch.update_flags or branch.mnemonic.startswith('b'):
                    break
            break
        if writes(q, idx): break
    if not limit or limit > 4096: return None
    address = None; low = 0
    for q in reversed(insl[:li]):
        _, written = q.regs_access()
        if base_reg not in {num(q.reg_name(r)) for r in written}: continue
        if q.mnemonic == 'add' and len(q.operands) == 3 and q.operands[2].type == ARM64_OP_IMM and num(q.reg_name(q.operands[1].reg)) == base_reg and not low:
            low = q.operands[2].imm
            continue
        if q.mnemonic in ('adr','adrp'):
            address = q.operands[1].imm + low
        break
    if address is None or address < 0 or address+4*limit > len(IMG): return None
    targets = [address+struct.unpack_from('<i',IMG,address+4*k)[0] for k in range(limit)]
    if any(t < 0 or t >= TEXT_END or t%4 for t in targets): return None
    lo,hi = min(targets),max(targets)
    print(f'{NAME}: relative32 jump table {insl[j].address:#x}, table={address:#x}, entries={limit}, targets={lo:#x}..{hi:#x}', flush=True)
    return lo,(hi-lo)//4+1

funcs = sorted({func_of(a) for a, (k, _) in kinds.items() if k == 'x18'})
for fa, fb in funcs:
    insl = list(md.disasm(bytes(IMG[fa:fb]), fa))
    ws = find_windows(insl)
    for wseg in ws:
        windows.append(wseg); done |= {x.address for x in wseg}
    for j, ins in enumerate(insl):
        if ins.mnemonic == 'br' and ins.op_str == 'x18':
            base = width = None
            ctx = insl[max(0, j - 8):j]
            for p in reversed(ctx):
                if p.mnemonic == 'adr' and p.op_str.startswith('x18,'): base = p.operands[1].imm; break
            for p in reversed(ctx):
                if p.mnemonic == 'add' and p.op_str.startswith('x18, x18,') and 'lsl #2' in p.op_str:
                    idx = num(p.reg_name(p.operands[2].reg))
                    for q in reversed(ctx):
                        if q.mnemonic in ('ldrb', 'ldrsb') and num(q.reg_name(q.operands[0].reg)) == idx: width = 256
                        if q.mnemonic in ('ldrh', 'ldrsh') and num(q.reg_name(q.operands[0].reg)) == idx: width = 65536
                        if width: break
                    break
            if not (base and width):
                extra = relative32_jump_range(insl,j)
                if extra: base,width = extra
            assert base and width, f'jump table {ins.address:x}'
            jumps[ins.address] = (base, width)

    # No jump may land in the middle of a window
    inwin = {x.address for wseg in ws for x in wseg}; heads = {wseg[0].address for wseg in ws}
    for x in insl:
        if x.mnemonic in ('b', 'bl', 'cbz', 'cbnz', 'tbz', 'tbnz') or x.mnemonic.startswith('b.'):
            t = x.operands[-1].imm
            assert not (t in inwin and t not in heads), f'branch into window {x.address:x}'

def put_branch(at, to): struct.pack_into('<I', IMG, at, B(at, to))
for wseg in windows:
    st, lo, hi = site_window(wseg); stat('window'); put_branch(lo, st)
for a in sorted(kinds):
    if a in done: continue
    k, arg = kinds[a]
    ins = dis(struct.unpack_from('<I', IMG, a)[0], a)
    if k == 'x18':
        m = ins.mnemonic
        if m == 'br': st = site_br(ins, *jumps[a]); stat('br')
        elif m in ('cbz', 'cbnz', 'tbz', 'tbnz'): st = site_cond(ins); stat('cond')
        elif m in ('adr', 'adrp'): st = site_pcrel(ins); stat('pcrel')
        elif m == 'blr': st = site_blr(ins); stat('blr')
        elif m in ('ret', 'b', 'bl') or (m == 'ldr' and '[' not in ins.op_str): raise RuntimeError(f'{a:x} {m} {ins.op_str}')
        else: st = site_plain(ins); stat('plain')
    elif k == 'tpidr_r': st = site_sysreg_read(ins, 'KTLS'); stat(k)
    elif k == 'tpidrro_r': st = site_sysreg_read(ins, 'KTLR'); stat(k)
    elif k == 'tpidr_w': st = site_tpidr_write(ins); stat(k)
    elif k == 'svc': st = site_gate(ins, 'svc', arg); stat(k)
    elif k in ('cntpct', 'cntvct'): st = site_gate(ins, k, arg); stat(k)
    put_branch(a, st)

# No title-specific observation, parameter, or gameplay patches.
obs = []
params = []

os.makedirs(outdir, exist_ok=True)
P = lambda ext: os.path.join(outdir, f'{NAME}.{ext}')
open(P('patched.bin'), 'wb').write(IMG + bytearray(PATCH_OFF - len(IMG)) + patch)
import hashlib
with open(os.path.join(outdir, 'build_src.sha256'), 'w') as f:
    f.write(hashlib.sha256(open(os.path.abspath(__file__), 'rb').read()).hexdigest() + '  patch_nso.py\n')
with open(P('fixups.tsv'), 'w') as f:
    f.write(f'# PATCH_OFF\t{PATCH_OFF:#x}\n# KEY_PAGE_OFF\t{KEY_PAGE_OFF:#x}\n# KEY_PAGE_SIZE\t0x4000\n# TEXT_END\t{TEXT_END:#x}\n# RO_OFF\t{RO_OFF:#x}\n# DATA_OFF\t{DATA_OFF:#x}\n')
    for k in KEY_INDEX: f.write(f'# KEY_{k}_IDX\t{KEY_INDEX[k]}\n')
with open(P('gates.tsv'), 'w') as f:
    for ret, k, arg, orig in gates: f.write(f'{ret:#x}\t{k}\t{arg}\t{orig:#x}\n')
with open(P('sites.tsv'), 'w') as f:
    for a in sorted(kinds):
        if a not in done: f.write(f'{a:#x}\t{kinds[a][0]}\n')
    for wseg in windows: f.write(f'{wseg[0].address:#x}\tW\t{wseg[-1].address + 4:#x}\n')
    for a, (b, c) in jumps.items(): f.write(f'{a:#x}\tJ\t{b:#x}\t{c}\n')
with open(P('cuts.tsv'), 'w') as f:
    f.write(f'# BUILD_ID\t{BUILD_ID}\n')
    for off, ob, nb, why, scope in cuts: f.write(f'{off:#x}\t{ob}\t{nb}\t{scope}\t{why}\n')   # Columns: offset, original bytes, new bytes, scope, reason
with open(P('params.tsv'), 'w') as f:
    f.write(f'# BUILD_ID\t{BUILD_ID}\n')
    for oa, wa, ob_, wb, r, key, why in params: f.write(f'{oa:#x}\t{ob_:#x}\tx{r}\t{key}\t{why}\n')
with open(P('obs.tsv'), 'w') as f:
    f.write(f'# BUILD_ID\t{BUILD_ID}\n')
    for off, oid, ow, why in obs: f.write(f'{off:#x}\t{oid}\t{ow}\t{why}\n')
print(NAME, stats, 'cuts', len(cuts), 'obs', len(obs), 'patch', len(patch), 'PATCH_OFF', hex(PATCH_OFF), 'slot_refs', len(fix), 'gates', len(gates))
