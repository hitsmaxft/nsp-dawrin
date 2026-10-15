#include "../backend.h"
#include "../posix/common.h"
#include <mach/mach.h>
#include <mach/mach_vm.h>

static bool read_memory(void *destination,const void *guest,size_t size) {
    if(!size)return true;
    if(!destination || !guest || size>UINT32_MAX)return false;
    mach_vm_size_t copied=0;
    return mach_vm_read_overwrite(mach_task_self(),(mach_vm_address_t)guest,size,
        (mach_vm_address_t)destination,&copied)==KERN_SUCCESS && copied==size;
}
static bool write_memory(void *guest,const void *source,size_t size) {
    if(!size)return true;
    if(!guest || !source || size>UINT32_MAX)return false;
    return mach_vm_write(mach_task_self(),(mach_vm_address_t)guest,(vm_offset_t)source,
        (mach_msg_type_number_t)size)==KERN_SUCCESS;
}
const HostBackend *host_backend(void) {
    static const HostBackend backend={HOST_BACKEND_ABI,"macos",HOST_POSIX_CLOCK,HOST_POSIX_ENTROPY,
        {read_memory,write_memory},HOST_POSIX_SYNC};
    return &backend;
}
