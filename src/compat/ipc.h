#pragma once
#include <stddef.h>
#include <stdint.h>

typedef struct {void *data;size_t size;} NativeIpcBuffer;
typedef struct NativeIpcReply NativeIpcReply;
typedef uint32_t (*NativeServiceHandler)(uint32_t command,const void *input,size_t size,
                                       NativeIpcBuffer output,NativeIpcReply *reply);
struct NativeIpcReply {
    unsigned char data[128];
    size_t size;
    /* Optional stateless child interface, published only on successful replies. */
    NativeServiceHandler object;
};
/* Register before starting guest threads. Names contain at most eight bytes.
 * Handlers run under the transport lock and must not reenter the registry.
 * Output descriptors are guest pointers: use native_ipc_write for bounded writes. */
int native_ipc_register(const char *name,NativeServiceHandler handler);
uint32_t native_ipc_write(NativeIpcBuffer output,const void *data,size_t size);
uint32_t native_ipc_connect(const char *name,uint32_t *handle);
uint32_t native_ipc_close(uint32_t handle);
int native_ipc_owns(uint32_t handle);
uint32_t native_ipc_transact(uint32_t handle,void *buffer,size_t size);
