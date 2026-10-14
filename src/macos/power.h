#pragma once
/* Loading hints affect host activity policy; macOS retains clock control. */
int native_power_boost(int enabled);
int native_power_boost_enabled(void);
