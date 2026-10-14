#include "hle.h"
// Select a decoder that can execute in-process instead of opening a device
// channel. Component creation, decode, buffering and teardown stay in the SDK.
HLE_FORCE("_ZN7android8OMXCodec18findMatchingCodecsEPKcbS2_jPNS_6VectorINS_7String8EEE", "Host software codec selection", void, media_select, const char *mime,int encoder,const char *match,unsigned flags,void *output) {
    typedef void (*Select)(const char *,int,const char *,unsigned,void *);
    Select original=(Select)guest_sym("_ZN7android8OMXCodec18findMatchingCodecsEPKcbS2_jPNS_6VectorINS_7String8EEE");
    if(!original)die("Missing guest codec selector");
    LOG("Selecting in-process media codec: %s requested=%s",mime,match?match:"automatic");
    original(mime,encoder&1,match,(flags&~16u)|8u,output);
    // Some guest codec registries omit a software decoder that is linked into
    // the same module. Use its exported factory only when MIME lookup is empty.
    struct VectorPrefix { void *vtable, *storage; uint64_t count; } prefix;
    memcpy(&prefix, output, sizeof prefix);
    if (!(encoder & 1) && !match && !prefix.count && !strcmp(mime, "video/avc") &&
        guest_sym("_Z30SoftAVC_createSoftOMXComponentPKcPK16OMX_CALLBACKTYPEPvPP17OMX_COMPONENTTYPE")) {
        void (*construct)(void *, const char *) = guest_sym("_ZN7android7String8C1EPKc");
        void (*destroy)(void *) = guest_sym("_ZN7android7String8D1Ev");
        int64_t (*add)(void *, const void *) = guest_sym("_ZN7android10VectorImpl3addEPKv");
        if (!construct || !destroy || !add) die("Guest codec registry interfaces are unavailable");
        void *name = NULL;
        construct(&name, "OMX.google.h264.decoder");
        int64_t index = add(output, &name);
        destroy(&name);
        if (index < 0) die("Cannot register software AVC candidate: %lld", (long long)index);
        LOG("Selected exported software AVC decoder missing from the guest registry");
    }
}
HLE_FORCE("_ZN7android13SoftOMXPlugin21makeComponentInstanceEPKcPK16OMX_CALLBACKTYPEPvPP17OMX_COMPONENTTYPE", "Diagnose software component creation", uint32_t, media_component, void *self,const char *name,const void *callbacks,void *user,void **component) {
    uint32_t (*create)(void *,const char *,const void *,void *,void **) = guest_sym("_ZN7android13SoftOMXPlugin21makeComponentInstanceEPKcPK16OMX_CALLBACKTYPEPvPP17OMX_COMPONENTTYPE");
    uint32_t result = create(self,name,callbacks,user,component);
    LOG("Software media component %s result=%#x",name,result);
    return result;
}
