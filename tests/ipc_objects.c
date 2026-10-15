#include "ipc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t leaf(uint32_t cmd,const void *input,size_t size,NativeIpcBuffer out,NativeIpcReply *reply) {
    (void)input;(void)size;(void)out;
    if(cmd)return 0x2a2;
    uint32_t value=42;memcpy(reply->data,&value,4);reply->size=4;return 0;
}
static uint32_t root(uint32_t cmd,const void *input,size_t size,NativeIpcBuffer out,NativeIpcReply *reply) {
    (void)input;(void)size;(void)out;
    if(cmd)return 0x2a2;
    reply->object=leaf;return 0;
}
static void request(uint32_t *b,unsigned type,unsigned cmd,unsigned object) {
    memset(b,0,256);b[0]=type;b[1]=12+(object?4:0);
    unsigned p=4;if(object){b[4]=1|(20u<<16);b[5]=object;p=8;}
    b[p]=0x49434653;b[p+2]=cmd;
}
int main(void) {
    uint32_t parent,b[64];
    assert(native_ipc_register("fixture",root));
    assert(!native_ipc_register("fixture",root));
    assert(!native_ipc_connect("fixture",&parent));
    request(b,4,0,0);assert(!native_ipc_transact(parent,b,sizeof b));
    uint32_t child=b[3];assert(child && !b[6]);
    assert(!native_ipc_close(parent));
    request(b,4,0,0);assert(!native_ipc_transact(child,b,sizeof b) && b[8]==42);
    assert(!native_ipc_close(child));

    assert(!native_ipc_connect("fixture",&parent));
    request(b,5,0,0);assert(!native_ipc_transact(parent,b,sizeof b) && b[8]==1);
    request(b,4,0,1);assert(!native_ipc_transact(parent,b,sizeof b));
    uint32_t object=b[12];assert(b[4]==1 && object>1 && !b[10]);
    request(b,5,2,0);assert(!native_ipc_transact(parent,b,sizeof b));
    uint32_t clone=b[3];assert(clone);
    request(b,4,0,object);assert(!native_ipc_transact(clone,b,sizeof b) && b[12]==42);
    request(b,5,1,0);b[8]=object;assert(!native_ipc_transact(clone,b,sizeof b));
    uint32_t copied=b[3];assert(copied && !b[6]);
    request(b,4,0,object);b[4]=2;assert(!native_ipc_transact(parent,b,sizeof b));
    request(b,4,0,object);assert(native_ipc_transact(clone,b,sizeof b));
    request(b,4,0,0);assert(!native_ipc_transact(copied,b,sizeof b) && b[8]==42);
    assert(!native_ipc_close(copied));
    /* Root closure leaves children addressable; released IDs cannot alias new objects. */
    request(b,4,0,1);assert(!native_ipc_transact(parent,b,sizeof b));
    uint32_t next=b[12];assert(next>object);
    request(b,4,0,1);b[4]=2;assert(!native_ipc_transact(parent,b,sizeof b));
    assert(!native_ipc_close(parent));
    request(b,4,0,next);assert(!native_ipc_transact(clone,b,sizeof b) && b[12]==42);
    assert(!native_ipc_close(clone));

    /* Exhaustion reports failure and closing one object restores capacity. */
    assert(!native_ipc_connect("fixture",&parent));
    request(b,5,0,0);assert(!native_ipc_transact(parent,b,sizeof b));
    uint32_t last=0;
    for(unsigned i=0;i<63;i++){
        request(b,4,0,1);assert(!native_ipc_transact(parent,b,sizeof b) && !b[10]);last=b[12];
    }
    request(b,4,0,1);assert(!native_ipc_transact(parent,b,sizeof b) && b[10] && !b[4]);
    request(b,4,0,last);b[4]=2;assert(!native_ipc_transact(parent,b,sizeof b));
    request(b,4,0,1);assert(!native_ipc_transact(parent,b,sizeof b) && !b[10] && b[12]>last);
    assert(!native_ipc_close(parent));
    puts("PASS: child sessions, domain objects, clones, copy-out, lifetime and bounded exhaustion");
}
