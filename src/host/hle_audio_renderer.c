// Use the SDK's own in-process audio renderer, preserving its DSP and codec
// implementation. Its AudioOut calls use the existing host output adapter.
#include "hle.h"
HLE_GUEST_ALIAS("_ZN2nn5audio32CreateAudioRendererManagerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio41CreateAudioRendererManagerForAppletByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", applet_renderer)
HLE_GUEST_ALIAS("_ZN2nn5audio43CreateAudioRendererManagerForDebuggerByHipcEv", "_ZN2nn5audio31CreateAudioRendererManagerByDfcEv", "Guest in-process audio renderer", debug_renderer)

// The in-process renderer pools local auto-clear events. Service clients still
// request readable kernel handles, so promote each idle event before its first
// renderer takes ownership. Both sides then observe the same SDK-owned event.
static void *renderer_export(const char *name) {
    void *symbol=guest_sym(name);
    if(!symbol)die("Required renderer interface is unavailable: %s",name);
    return symbol;
}
static void prepare_renderer_event(void *event) {
    uint32_t (*read_handle)(const void *) = renderer_export("_ZN2nn2os30GetReadableHandleOfSystemEventEPKNS0_15SystemEventTypeE");
    void (*destroy)(void *) = renderer_export("_ZN2nn2os18DestroySystemEventEPNS0_15SystemEventTypeE");
    Result (*create)(void *, int, int) = renderer_export("_ZN2nn2os17CreateSystemEventEPNS0_15SystemEventTypeENS0_14EventClearModeEb");
    if (!read_handle || !destroy || !create) die("Audio renderer event interfaces are unavailable");
    if (read_handle(event)) return;
    destroy(event);
    Result result = create(event, 1, 1);
    if (result) die("Audio renderer event creation failed: %#x", result);
    LOG("Audio renderer event promoted to a shared kernel event");
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystemC2ERNS_2os11SystemEventE", "Share renderer completion events with service clients", void, renderer_construct, void *self, void *event) {
    prepare_renderer_event(event);
    void (*construct)(void *, void *) = renderer_export("_ZN2nn5audio6server17AudioRenderSystemC2ERNS_2os11SystemEventE");
    construct(self, event);
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystemC1ERNS_2os11SystemEventE", "Share renderer completion events with service clients", void, renderer_construct_complete, void *self, void *event) {
    prepare_renderer_event(event);
    void (*construct)(void *, void *) = renderer_export("_ZN2nn5audio6server17AudioRenderSystemC1ERNS_2os11SystemEventE");
    construct(self, event);
}

typedef struct { int automatic, registered; } RendererSchedule;
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystem10InitializeERKNS0_6detail30AudioRendererParameterInternalEjPvmRKNS_6applet20AppletResourceUserIdEi", "Track renderer execution mode", Result, renderer_initialize, void *self, const uint8_t *param, uint32_t process, void *buffer, uint64_t size, const void *user, int session) {
    Result (*initialize)(void *, const void *, uint32_t, void *, uint64_t, const void *, int) = renderer_export("_ZN2nn5audio6server17AudioRenderSystem10InitializeERKNS0_6detail30AudioRendererParameterInternalEjPvmRKNS_6applet20AppletResourceUserIdEi");
    Result result = initialize(self, param, process, buffer, size, user, session);
    if (!result) {
        RendererSchedule *schedule = calloc(1, sizeof *schedule);
        if(!schedule)die("Cannot allocate renderer schedule");
        schedule->automatic = param[0x23] == 0;
        objmap_put(self, schedule);
    }
    return result;
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystem5StartEv", "Schedule automatic in-process rendering", Result, renderer_start, void *self) {
    Result (*start)(void *) = renderer_export("_ZN2nn5audio6server17AudioRenderSystem5StartEv");
    Result result = start(self);
    RendererSchedule *schedule = objmap_get(self);
    if (!result && schedule && schedule->automatic && !schedule->registered) {
        void *(*manager)(void) = renderer_export("_ZN2nn5audio6server24AudioRenderSystemManager11GetInstanceEv");
        int (*add)(void *, void *) = renderer_export("_ZN2nn5audio6server24AudioRenderSystemManager3AddERNS1_17AudioRenderSystemE");
        if (!add(manager(), self)) {
            void (*stop)(void *)=renderer_export("_ZN2nn5audio6server17AudioRenderSystem4StopEv");
            stop(self);return RES_FAIL;
        }
        schedule->registered = 1;
        LOG("Automatic audio renderer registered with the guest scheduler");
    }
    return result;
}
HLE_FORCE("_ZN2nn5audio6server17AudioRenderSystem8FinalizeEv", "Release scheduled renderer before finalization", void, renderer_finalize, void *self) {
    RendererSchedule *schedule = objmap_del(self);
    if (schedule && schedule->registered) {
        void *(*manager)(void) = renderer_export("_ZN2nn5audio6server24AudioRenderSystemManager11GetInstanceEv");
        void (*remove)(void *, void *) = renderer_export("_ZN2nn5audio6server24AudioRenderSystemManager6RemoveERNS1_17AudioRenderSystemE");
        remove(manager(), self);
    }
    free(schedule);
    void (*finalize)(void *) = renderer_export("_ZN2nn5audio6server17AudioRenderSystem8FinalizeEv");
    finalize(self);
}
