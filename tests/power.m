#include "power.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    assert(!native_power_boost_enabled());
    assert(!native_power_boost(1));assert(native_power_boost_enabled());
    assert(!native_power_boost(1));assert(native_power_boost(2));
    assert(native_power_boost_enabled());assert(!native_power_boost(0));
    assert(!native_power_boost_enabled());assert(!native_power_boost(0));
    puts("PASS: host loading activity is bounded, idempotent and reversible");
}
