#pragma once
#include "ipc.h"
uint32_t compat_settings_service(uint32_t command,const void *input,size_t size,
                                NativeIpcBuffer output,NativeIpcReply *reply);
uint32_t compat_time_service(uint32_t command,const void *input,size_t size,
                            NativeIpcBuffer output,NativeIpcReply *reply);
