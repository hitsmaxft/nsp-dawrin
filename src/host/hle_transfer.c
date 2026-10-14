#include "dm.h"
#include "../macos/transfer.h"
int svc_transfer(int number,uint64_t *registers) {
    if(number==0x15) {
        uint32_t handle=0;
        registers[0]=native_transfer_create(registers[1],registers[2],registers[3],&handle);
        registers[1]=handle;return 1;
    }
    if(number==0x16 && native_transfer_owns(registers[0])){registers[0]=native_transfer_close(registers[0]);return 1;}
    return 0;
}
