#pragma once
#include <stdint.h>
// Publish physical macOS key positions from the focused application window.
void native_keyboard_publish(const uint8_t held[128]);
