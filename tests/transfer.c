#include "transfer.h"
#include <assert.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdio.h>
int main(void) {
    mach_vm_address_t source=0,destination=0;size_t size=vm_page_size;
    assert(mach_vm_allocate(mach_task_self(),&source,size,VM_FLAGS_ANYWHERE)==KERN_SUCCESS);
    assert(mach_vm_allocate(mach_task_self(),&destination,size,VM_FLAGS_ANYWHERE)==KERN_SUCCESS);
    assert(mach_vm_protect(mach_task_self(),destination,size,FALSE,VM_PROT_NONE)==KERN_SUCCESS);
    uint32_t handle,again;
    assert(native_transfer_create(source+1,size,0,&handle));
    assert(!native_transfer_create(source,size,0,&handle));
    assert(native_transfer_create(source,size,0,&again));
    assert(native_transfer_map(handle,destination,size,3));
    assert(native_transfer_map(handle,UINTPTR_MAX-4095,size,0));
    assert(!native_transfer_map(handle,destination,size,0));
    *(int *)source=73;assert(*(int *)destination==73);
    *(int *)destination=91;assert(*(int *)source==91);
    assert(native_transfer_close(handle));
    assert(!native_transfer_unmap(handle,destination,size));
    assert(*(int *)source==91);
    assert(!native_transfer_close(handle));assert(native_transfer_close(handle));
    assert(!native_transfer_create(source,size,0,&again));assert(again!=handle);
    assert(native_transfer_map(handle,destination,size,0));assert(!native_transfer_close(again));
    assert(!native_transfer_create(source+4096,4096,0,&handle));
    *(int *)(source+4096)=41;
    assert(!native_transfer_map(handle,destination,4096,0));assert(*(int *)destination==41);
    *(int *)destination=62;
    assert(!native_transfer_unmap(handle,destination,4096));assert(*(int *)(source+4096)==62);
    assert(!native_transfer_close(handle));
    mach_vm_deallocate(mach_task_self(),source,size);mach_vm_deallocate(mach_task_self(),destination,size);
    puts("PASS: coherent transfer aliases, permissions, overlap, stale handles and ownership");
}
