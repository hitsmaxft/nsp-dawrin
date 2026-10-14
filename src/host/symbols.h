// ELF visibility and binding rules used by cross-module relocation.
#pragma once
#include "dm.h"
static inline int dm_symbol_exported(const Elf64_Sym *symbol) {
    unsigned binding = symbol->st_info >> 4, visibility = symbol->st_other & 3;
    return symbol->st_shndx && (binding == 1 || binding == 2) && (visibility == 0 || visibility == 3);
}
static inline int dm_symbol_binds_locally(const Elf64_Sym *symbol) {
    return symbol->st_shndx && (!(symbol->st_info >> 4) || (symbol->st_other & 3));
}
