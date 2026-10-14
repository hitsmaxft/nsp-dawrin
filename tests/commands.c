#include "../src/gfx/nvn/nvn_commands.h"
#include "../src/gfx/nvn/nvn_obj.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t child[4],first[5],last[5],output[16];
static unsigned written;
static void *allocate(void *context,uint32_t size) {
    // Simulate an allocator immediately recycling every source segment.
    memset(child,0xcc,sizeof child);memset(first,0xcc,sizeof first);memset(last,0xcc,sizeof last);
    assert(written+size<=sizeof output);void *p=(char *)output+written;written+=size;return p;
}
static void header(void *p,uint32_t op,uint32_t size){op_hdr h={op,size};memcpy(p,&h,8);}
int main(void) {
    header(child,OP_BEGIN,8);header(child+1,OP_BARRIER,16);child[2]=42;header(child+3,OP_END,8);
    header(first,OP_BEGIN,8);header(first+1,OP_CALL,16);first[2]=(uintptr_t)child;
    header(first+3,OP_JUMP,16);first[4]=(uintptr_t)last;
    header(last,OP_BARRIER,16);last[1]=99;header(last+2,OP_END,8);
    uint64_t handles[]={(uintptr_t)first,(uintptr_t)child};
    assert(!nvn_copy_commands(2,handles,NULL,allocate));assert(written==48);
    assert(output[1]==42&&output[3]==99&&output[5]==42);
    for(int i=0;i<6;i+=2){op_hdr h;memcpy(&h,output+i,8);assert(h.op==OP_BARRIER&&h.size==16);}
    written=0;header(first,OP_BARRIER,9);assert(nvn_copy_commands(1,handles,NULL,allocate));assert(!written);
    header(first,OP_JUMP,16);first[1]=(uintptr_t)first;
    assert(nvn_copy_commands(1,handles,NULL,allocate));assert(!written);
    header(first,OP_CALL,16);assert(nvn_copy_commands(1,handles,NULL,allocate));assert(!written);
    assert(nvn_copy_commands(-1,handles,NULL,allocate));
    assert(!nvn_copy_commands(0,NULL,NULL,allocate));
    puts("PASS: copied commands survive source recycling, preserve nested order and reject malformed/cyclic streams");
}
