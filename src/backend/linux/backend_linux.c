#define _GNU_SOURCE
#include "../backend.h"
#include "../posix/common.h"
#include <sys/uio.h>
#include <unistd.h>

static bool read_memory(void *destination,const void *guest,size_t size) {
    if(!size)return true;
    if(!destination || !guest || size>UINT32_MAX)return false;
    struct iovec local={destination,size},remote={(void *)guest,size};
    return process_vm_readv(getpid(),&local,1,&remote,1,0)==(ssize_t)size;
}
static bool write_memory(void *guest,const void *source,size_t size) {
    if(!size)return true;
    if(!guest || !source || size>UINT32_MAX)return false;
    struct iovec local={(void *)source,size},remote={guest,size};
    return process_vm_writev(getpid(),&local,1,&remote,1,0)==(ssize_t)size;
}
const HostBackend *host_backend(void) {
    static const HostBackend backend={HOST_BACKEND_ABI,"linux",HOST_POSIX_CLOCK,HOST_POSIX_ENTROPY,
        {read_memory,write_memory},HOST_POSIX_SYNC};
    return &backend;
}
