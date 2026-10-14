// Use the host cache API instead of guest cache-control registers and opcodes.
#include "hle.h"
#include <libkern/OSCacheControl.h>
#include <stdatomic.h>

HLE_FORCE("_ZN2nn2os14FlushDataCacheEPKvm", "Native data-cache maintenance", void, flush_data_cache, const void *address, uint64_t size) {
    if (size) sys_dcache_flush((void *)address, (size_t)size);
    atomic_thread_fence(memory_order_seq_cst);
}
