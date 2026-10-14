// Expose loaded module unwind metadata without querying guest kernel mappings.
#include "hle.h"

int dm_module_exception_info(uint64_t out[4], uintptr_t pc) {
    module_t *module = module_of((const void *)pc);
    if (!module || !out || module->size < 24 || module->data_off > module->size) return 0;
    uint32_t offset, magic;
    memcpy(&offset, module->base + 4, sizeof offset);
    if (offset > module->size - 24) return 0;
    memcpy(&magic, module->base + offset, sizeof magic);
    if (magic != 0x30444f4d) return 0;
    int32_t begin, end;
    memcpy(&begin, module->base + offset + 16, sizeof begin);
    memcpy(&end, module->base + offset + 20, sizeof end);
    int64_t header = (int64_t)offset + begin, limit = (int64_t)offset + end;
    if (header < 0 || limit < header || (uint64_t)limit > module->data_off) return 0;
    out[0] = (uintptr_t)module->base;
    out[1] = module->data_off;
    out[2] = (uint64_t)header;
    out[3] = (uint64_t)(limit - header);
    return 1;
}

HLE_FORCE("_ZN2nn2ro6detail16GetExceptionInfoEPNS1_13ExceptionInfoEm",
          "Loaded modules provide their own exception table metadata", int,
          h_ro_GetExceptionInfo, uint64_t *out, uintptr_t pc) {
    return dm_module_exception_info(out, pc);
}
