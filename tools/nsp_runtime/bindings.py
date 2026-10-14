"""Translate explicit resource reflection into native binding slots."""


def storage_binding(resource, stage):
    base = {'vs': 0x110, 'ps': 0x510, 'cs': 0x310}.get(stage)
    offset = resource['cb_offset'] * 4
    if resource['cb_slot'] != 0 or base is None:
        raise ValueError('Unsupported storage buffer address table')
    relative = offset - base
    if relative < 0 or relative >= 0x100 or relative % 16:
        raise ValueError(f'Storage buffer offset outside the {stage} slot table: {offset:#x}')
    return dict(kind='sbuf', reg=relative // 16, rw=bool(resource['flags'] & 2))
