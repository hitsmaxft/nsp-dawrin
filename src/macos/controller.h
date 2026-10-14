#pragma once
#include <stdint.h>

typedef struct {
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t connected;
} NativePad;

void native_controller_start(void);
void native_controller_focus(int active);
NativePad native_controller_read(void);
