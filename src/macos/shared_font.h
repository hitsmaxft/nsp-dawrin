#pragma once
#include <stddef.h>
// Process-lifetime read-only view of an installed host font, never bundled.
const void *native_shared_font(size_t *size);
