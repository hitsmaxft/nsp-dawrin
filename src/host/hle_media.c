#include "hle.h"
// Select a decoder that can execute in-process instead of opening a device
// channel. Component creation, decode, buffering and teardown stay in the SDK.
HLE_FORCE("_ZN7android8OMXCodec18findMatchingCodecsEPKcbS2_jPNS_6VectorINS_7String8EEE", "Host software codec selection", void, media_select, const char *mime,int encoder,const char *match,unsigned flags,void *output) {
    typedef void (*Select)(const char *,int,const char *,unsigned,void *);
    Select original=(Select)guest_sym("_ZN7android8OMXCodec18findMatchingCodecsEPKcbS2_jPNS_6VectorINS_7String8EEE");
    if(!original)die("Missing guest codec selector");
    LOG("Selecting in-process media codec: %s",mime);
    original(mime,encoder&1,match,(flags&~16u)|8u,output);
}
