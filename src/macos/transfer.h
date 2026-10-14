#pragma once
#include <stdint.h>
#include <stddef.h>
/* In-process transfer memory retains a borrowed guest range, never its ownership. */
uint32_t native_transfer_create(uintptr_t address,size_t size,unsigned permission,uint32_t *handle);
uint32_t native_transfer_close(uint32_t handle);
int native_transfer_owns(uint32_t handle);
uint32_t native_transfer_map(uint32_t handle,uintptr_t destination,size_t size,unsigned permission);
uint32_t native_transfer_unmap(uint32_t handle,uintptr_t destination,size_t size);
