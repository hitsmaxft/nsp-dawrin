// Use the SDK's own in-process audio renderer, preserving its DSP and codec
// implementation. Its AudioOut calls use the existing host output adapter.
#include "hle.h"
HLE_GUEST_ALIAS("_ZN2nn5audio32CreateAudioRendererManagerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio41CreateAudioRendererManagerForAppletByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", applet_renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio43CreateAudioRendererManagerForDebuggerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", debug_renderer)

// The in-process renderer pools local auto-clear events. Service clients still
// request readable kernel handles, so promote each idle event before its first
// renderer takes ownership. Both sides then observe the same SDK-owned event.
static void prepare_renderer_event(void *event) {
    uint32_t (*read_handle)(const void *) = guest_sym("_ZN2nn2os30GetReadableHandleOfSystemEventEPKNS0_15SystemEventTypeE");
    void (*destroy)(void *) = guest_sym("_ZN2nn2os18DestroySystemEventEPNS0_15SystemEventTypeE");
    Result (*create)(void *, int, int) = guest_sym("_ZN2nn2os17CreateSystemEventEPNS0_15SystemEventTypeENS0_14EventClearModeEb");
    if (!read_handle || !destroy || !create) die("Audio renderer event interfaces are unavailable");
    if (read_handle(event)) return;
    destroy(event);
    Result result = create(event, 1, 1);
    if (result) die("Audio renderer event creation failed: %#x", result);
    LOG("Audio renderer event promoted to a shared kernel event");
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystemC2ERNS_2os11SystemEventE", "Share renderer completion events with service clients", void, renderer_construct, void *self, void *event) {
    prepare_renderer_event(event);
    void (*construct)(void *, void *) = guest_sym("_ZN2nn5audio6server17AudioRenderSystemC2ERNS_2os11SystemEventE");
    construct(self, event);
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystemC1ERNS_2os11SystemEventE", "Share renderer completion events with service clients", void, renderer_construct_complete, void *self, void *event) {
    prepare_renderer_event(event);
    void (*construct)(void *, void *) = guest_sym("_ZN2nn5audio6server17AudioRenderSystemC1ERNS_2os11SystemEventE");
    construct(self, event);
}
