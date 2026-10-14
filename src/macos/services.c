// Host service implementations for native title bring-up.
#include "hle.h"
#include "settings.h"
HLE_FORCE("_ZN2nn6socket10InitializeEPvmmi", "Offline socket backend", Result, socket_init_old, void *mem,size_t size,size_t alloc,int concurrency) { (void)mem;(void)size;(void)alloc;(void)concurrency;return RES_OK; }
HLE_FORCE("_ZN2nn2vi19SetLayerScalingModeEPNS0_5LayerENS0_11ScalingModeE", "Host Metal layer owns output scaling",Result,vi_scaling,void *layer,int mode) {(void)layer;(void)mode;return RES_OK;}
HLE_FORCE("_ZN2nn2fs6detail18IsEnabledAccessLogEj", "Host filesystem diagnostics use DM_FSLOG", int, fs_access_log, unsigned kind) { (void)kind; return 0; }

// Fixed foreground host; 720p handheld or 1080p console mode at startup.
static int handheld_mode(void) {return native_settings_handheld();}
HLE_FORCE("_ZN2nn2oe28SetResumeNotificationEnabledEb", "No suspend transitions during bounded probe", void, oe_resume, int enabled) { (void)enabled; }
HLE_FORCE("_ZN2nn2oe42SetOperationModeChangedNotificationEnabledEb", "Fixed docked mode", void, oe_mode_notify, int enabled) { (void)enabled; }
HLE_FORCE("_ZN2nn2oe44SetPerformanceModeChangedNotificationEnabledEb", "Fixed docked mode", void, oe_perf_notify, int enabled) { (void)enabled; }
HLE_FORCE("_ZN2nn2oe16GetOperationModeEv", "Host output mode", int, oe_mode, void) { return handheld_mode()?0:1; }
HLE_FORCE("_ZN2nn2oe18GetPerformanceModeEv", "Host performance mode", int, oe_perf, void) { return handheld_mode()?0:1; }
HLE_FORCE("_ZN2nn2oe20GetCurrentFocusStateEv", "Foreground probe", int, oe_focus, void) { return 1; }
HLE_FORCE("_ZN2nn2oe20SetFocusHandlingModeENS0_17FocusHandlingModeE", "Foreground probe has no focus transitions", void, oe_focus_mode, int mode) { (void)mode; }
HLE_FORCE("_ZN2nn2oe25TryPopNotificationMessageEPj", "No platform transitions during probe", int, oe_message, unsigned *out) { (void)out; return 0; }
HLE_FORCE("_ZN2nn2oe27SetPerformanceConfigurationENS0_15PerformanceModeEi", "macOS manages CPU and GPU clocks", void, oe_perf_config, int mode,int config) { (void)mode;(void)config; }
HLE_FORCE("_ZN2nn2oe27SetPerformanceConfigurationEi", "macOS manages CPU and GPU clocks", void, oe_perf_config_old, int config) { (void)config; }
HLE_FORCE("_ZN2nn2oe18GetDesiredLanguageEv", "Chinese language code", uint64_t, oe_lang, void) { uint64_t lang=0;memcpy(&lang,"zh-Hans",7);return lang; }
HLE_FORCE("_ZN2nn2oe31EnterExitRequestHandlingSectionEv", "Probe lifetime controlled by host", void, oe_enter_exit, void) {}
HLE_FORCE("_ZN2nn2oe31LeaveExitRequestHandlingSectionEv", "Probe lifetime controlled by host", void, oe_leave_exit, void) {}

// Base-package mode exposes no installed add-on content.
HLE_FORCE("_ZN2nn3aoc16CountAddOnContentEv", "No installed add-on content", int, aoc_count, void) {return 0;}
HLE_FORCE("_ZN2nn3aoc16ListAddOnContentEPiii", "Empty installed add-on content list", int, aoc_list, int *indices,int offset,int count) {(void)indices;(void)offset;(void)count;return 0;}
