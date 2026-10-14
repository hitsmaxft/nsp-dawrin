// Use the SDK's own in-process audio renderer, preserving its DSP and codec
// implementation. Its AudioOut calls use the existing host output adapter.
#include "hle.h"
HLE_GUEST_ALIAS("_ZN2nn5audio32CreateAudioRendererManagerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio41CreateAudioRendererManagerForAppletByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", applet_renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio43CreateAudioRendererManagerForDebuggerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", debug_renderer)
