#include "hle.h"
#include "../macos/power.h"
HLE_FORCE("_ZN2nn6applet15SetCpuBoostModeEi", "Host loading activity policy", Result, h_power_boost, int mode) {
    return native_power_boost(mode)?RES_FAIL:RES_OK;
}
