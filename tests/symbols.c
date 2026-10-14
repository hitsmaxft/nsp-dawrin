#include "symbols.h"
#include <assert.h>
int main(void) {
    Elf64_Sym symbol={.st_shndx=1,.st_info=0x22};
    assert(dm_symbol_exported(&symbol) && !dm_symbol_binds_locally(&symbol));
    symbol.st_info=0x12;
    assert(dm_symbol_exported(&symbol) && !dm_symbol_binds_locally(&symbol));
    symbol.st_other=3;
    assert(dm_symbol_exported(&symbol) && dm_symbol_binds_locally(&symbol));
    symbol.st_other=2;
    assert(!dm_symbol_exported(&symbol) && dm_symbol_binds_locally(&symbol));
    symbol.st_other=0;symbol.st_info=2;
    assert(!dm_symbol_exported(&symbol) && dm_symbol_binds_locally(&symbol));
    symbol.st_shndx=0;
    assert(!dm_symbol_exported(&symbol) && !dm_symbol_binds_locally(&symbol));
    puts("ELF symbol visibility and interposition passed");
}
