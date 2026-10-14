"""Translate explicit resource reflection into native binding slots."""


def resource_writable(resource, kind):
    # Ryujinx BufferUsageFlags.Write and TextureUsageFlags.ImageStore differ.
    return bool(resource['flags'] & {'buffer': 1, 'image': 4}[kind])


def storage_binding(resource, stage):
    base = {'vs': 0x110, 'ps': 0x510, 'cs': 0x310}.get(stage)
    offset = resource['cb_offset'] * 4
    if resource['cb_slot'] != 0 or base is None:
        raise ValueError('Unsupported storage buffer address table')
    relative = offset - base
    if relative < 0 or relative >= 0x100 or relative % 16:
        raise ValueError(f'Storage buffer offset outside the {stage} slot table: {offset:#x}')
    return dict(kind='sbuf', reg=relative // 16, rw=resource_writable(resource, 'buffer'))


def texture_slot(resource, sampler=False):
    handle = resource["handle"] & 0xffffffff
    kind = handle >> 28
    if kind not in (0,1):raise ValueError(f'Unsupported texture handle kind: {kind}')
    off = ((handle >> 14) & 0x3fff) if sampler and kind else handle & 0x3fff
    byte = off * 4
    if kind:
        base = 0x568 if sampler else 0x168
    else:
        base = 0x20  # Combined texture/sampler handles in NVN driver constant buffer 2.
    if byte < base or (byte - base) % 8:
        raise ValueError(f"unmapped NVN texture handle {handle:#x}, sampler={sampler}")
    slot = (byte - base) // 8
    if slot >= 128:
        raise ValueError(f"texture slot out of range: {slot}")
    return slot, bool(kind)

def image_slot(resource, stage):
    # Compute image handles occupy their own 32-entry table after the
    # combined texture handles. Their offsets are words, not slot indices.
    handle = resource['handle'] & 0xffffffff
    if stage not in ('vs', 'ps', 'cs') or resource['cbuf_slot'] != 2 or handle >> 28:
        raise ValueError('Unsupported image handle table')
    base = 0x120 if stage == 'cs' else 0x20
    relative = (handle & 0x3fff) * 4 - base
    if relative < 0 or relative >= 32 * 8 or relative % 8:
        raise ValueError(f'Image offset outside the {stage} slot table: {handle:#x}')
    return relative // 8
