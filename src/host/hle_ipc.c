// System-call transport shares one service registry across guest SDK versions.
#include "dm.h"
#include "../macos/ipc.h"

int svc_ipc(int number,uint64_t *registers) {
    if(number==0x1f){
        const char *name=(const char *)registers[1];uint32_t handle=0;
        char bounded[9]={0};if(name)memcpy(bounded,name,strnlen(name,8));
        registers[0]=native_ipc_connect(bounded,&handle);registers[1]=handle;return 1;
    }
    if(number==0x21 && native_ipc_owns(registers[0])){
        registers[0]=native_ipc_transact(registers[0],pthread_getspecific(g_keytlr),0x100);return 1;
    }
    if(number==0x16 && native_ipc_owns(registers[0])){
        registers[0]=native_ipc_close(registers[0]);return 1;
    }
    return 0;
}
