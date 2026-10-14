#include "dm.h"
#include <assert.h>
static module_t sample;
module_t *module_of(const void *pc) {
    uintptr_t value = (uintptr_t)pc, base = (uintptr_t)sample.base;
    return value >= base && value - base < sample.size ? &sample : NULL;
}
extern int dm_module_exception_info(uint64_t out[4], uintptr_t pc);
int main(void) {
    uint8_t image[1024] = {0};
    sample = (module_t){.base=image, .size=sizeof image, .data_off=768};
    uint32_t offset=8, magic=0x30444f4d; int32_t begin=248, end=312;
    memcpy(image+4,&offset,4); memcpy(image+8,&magic,4);
    memcpy(image+24,&begin,4); memcpy(image+28,&end,4);
    uint64_t result[4]={0};
    assert(dm_module_exception_info(result,(uintptr_t)image+128));
    assert(result[0]==(uintptr_t)image && result[1]==768 && result[2]==256 && result[3]==64);
    assert(!dm_module_exception_info(result,0));
    end=2048;memcpy(image+28,&end,4);
    assert(!dm_module_exception_info(result,(uintptr_t)image+128));
    offset=1020;memcpy(image+4,&offset,4);
    assert(!dm_module_exception_info(result,(uintptr_t)image+128));
    puts("Module unwind metadata bounds passed");
}
