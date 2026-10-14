// Replace device initialization while retaining guest allocator registration.
// Graphics and media components share NvOs allocation state. Let the guest SDK
// install its callbacks so allocations and frees stay with the same allocator.
#include "../host/hle.h"

HLE_FORCE("_ZN2nv18InitializeGraphicsEPvm", "Metal owns the host graphics device", void, h_nv_Init, void *mem, unsigned long size) { (void)mem; (void)size; }
HLE_FORCE("_ZN2nv16FinalizeGraphicsEv", "Metal owns the host graphics device", void, h_nv_Fin, void) {}
