#pragma once
#include <stddef.h>
#include <stdint.h>
// Snapshot source records before requesting destination storage. Allocation may
// recycle guest command memory; copied streams must survive that recycling.
typedef void *(*NvnCommandAllocate)(void *context, uint32_t bytes);
int nvn_copy_commands(int count, const uint64_t *handles, void *context,
                      NvnCommandAllocate allocate);
