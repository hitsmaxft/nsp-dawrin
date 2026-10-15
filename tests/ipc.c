#include "ipc.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

static void request(uint32_t *buffer,unsigned type,unsigned command,int domain) {
    memset(buffer,0,256);buffer[0]=type;buffer[1]=12+(domain?4:0);
    unsigned offset=4;if(domain){buffer[4]=1|(20u<<16);buffer[5]=1;offset=8;}
    buffer[offset]=0x49434653;buffer[offset+2]=command;
}
int main(void) {
    uint32_t sm,settings,b[64],stale;
    assert(!native_ipc_connect("sm:",&sm));
    request(b,4,0,0);assert(!native_ipc_transact(sm,b,sizeof b));assert(b[6]==0);
    request(b,4,1,0);memcpy(b+8,"set",4);assert(!native_ipc_transact(sm,b,sizeof b));
    settings=b[3];assert(native_ipc_owns(settings));
    request(b,5,0,0);assert(!native_ipc_transact(settings,b,sizeof b));assert(b[8]==1);
    request(b,4,2,1);b[12]=1;assert(!native_ipc_transact(settings,b,sizeof b));
    assert(b[8]==0x4f434653 && b[10]==0 && !memcmp(b+12,"en-US",5));
    request(b,4,999,1);assert(!native_ipc_transact(settings,b,sizeof b));assert(b[10]!=0);
    request(b,4,2,1);b[1]=1;assert(native_ipc_transact(settings,b,sizeof b)!=0);
    stale=settings;assert(!native_ipc_close(settings));assert(native_ipc_close(settings)!=0);
    assert(!native_ipc_connect("set",&settings));assert(settings!=stale);
    assert(native_ipc_transact(stale,b,sizeof b)!=0);
    request(b,2,0,0);assert(!native_ipc_transact(settings,b,sizeof b));
    assert(!native_ipc_close(settings));
    assert(!native_ipc_connect("set",&settings));
    request(b,5,0,0);assert(!native_ipc_transact(settings,b,sizeof b));
    request(b,4,0,1);b[4]=2;assert(!native_ipc_transact(settings,b,sizeof b));
    assert(!native_ipc_close(settings));
    assert(native_ipc_write((NativeIpcBuffer){(void *)1,8},"example",8)!=0);
    assert(!native_ipc_connect("set",&settings));
    uint64_t languages[3]={0};uintptr_t address=(uintptr_t)languages;
    request(b,4,5,0);b[0]|=1u<<24;b[2]=sizeof languages;b[3]=(uint32_t)address;
    b[4]=(uint32_t)((address>>36)<<2)|(uint32_t)((address>>32&15)<<28);
    b[8]=0x49434653;b[10]=5;
    assert(!native_ipc_transact(settings,b,sizeof b));assert(b[6]==0 && b[8]==3);
    assert(!memcmp(languages,"ja",2) && !memcmp(languages+1,"en-US",5));
    assert(native_ipc_transact(settings,(void *)1,sizeof b)!=0);
    request(b,5,2,0);assert(!native_ipc_transact(settings,b,sizeof b));
    uint32_t clone=b[3];assert(clone!=settings && native_ipc_owns(clone));
    assert(!native_ipc_close(settings));
    request(b,4,0,0);assert(!native_ipc_transact(clone,b,sizeof b));assert(b[6]==0);
    assert(!native_ipc_close(clone));
    assert(native_ipc_connect("missing",&settings)!=0);
    puts("PASS: service resolution, domain dispatch, unknown commands, bounds and stale handles");
}
