// Adapt the public AOSP component queue lifecycle to a buffered native decoder.
// Each available output buffer can advance independently of buffers held by a
// consumer. The guest component retains port allocation and state transitions.
#include "hle.h"
#include "../macos/video_decoder.h"
#include <OMX_Core.h>
#include <stddef.h>
#include <pthread.h>

typedef struct { OMX_BUFFERHEADERTYPE *header; uint8_t owned; } MediaBuffer;
typedef struct MediaNode { MediaBuffer *item; struct MediaNode *prev, *next; } MediaNode;
typedef struct { void *vtable; MediaNode *head; } MediaList;
typedef struct PictureTag { uint32_t id,flags; int64_t time; struct PictureTag *next; } PictureTag;
typedef struct Component {
    void *guest;
    NspVideoDecoder *decoder;
    PictureTag *tags;
    uint32_t next_id;
    int waiting, eos, failed;
    struct Component *next;
} Component;
static Component *components;
static pthread_mutex_t components_lock=PTHREAD_MUTEX_INITIALIZER;
_Static_assert(sizeof(OMX_BUFFERHEADERTYPE)==112,"OpenMAX buffer ABI");
_Static_assert(offsetof(OMX_BUFFERHEADERTYPE,nTimeStamp)==88,"OpenMAX timestamp ABI");
static void *component_export(const char *name) {
    void *fn=guest_sym(name);if(!fn)die("Missing media component interface: %s",name);return fn;
}
static Component *component_state(void *self,int create) {
    pthread_mutex_lock(&components_lock);
    Component *state=components;
    while(state&&state->guest!=self)state=state->next;
    if(!state&&create){
        state=calloc(1,sizeof *state);if(!state)die("Cannot allocate video component");
        state->guest=self;state->decoder=nsp_video_decoder_create("video/avc",0);
        if(!state->decoder)die("Cannot create video decoder");
        state->next=components;components=state;
    }
    pthread_mutex_unlock(&components_lock);return state;
}
static void component_remove(void *self) {
    pthread_mutex_lock(&components_lock);
    Component **link=&components;while(*link&&(*link)->guest!=self)link=&(*link)->next;
    Component *state=*link;if(state)*link=state->next;
    pthread_mutex_unlock(&components_lock);
    if(!state)return;
    nsp_video_decoder_destroy(state->decoder);
    while(state->tags){PictureTag *next=state->tags->next;free(state->tags);state->tags=next;}
    free(state);
}
static MediaList *component_queue(void *self,unsigned port) {
    MediaList *(*get)(void *,unsigned)=component_export("_ZN7android22SimpleSoftOMXComponent12getPortQueueEj");
    return get(self,port);
}
static MediaBuffer *queue_front(MediaList *list) {
    return list->head->next==list->head?NULL:list->head->next->item;
}
static void queue_remove(MediaList *list) {
    MediaNode *node=list->head->next;if(node==list->head)die("Empty media queue");
    node->prev->next=node->next;node->next->prev=node->prev;
    void (*release)(void *)=component_export("_ZdlPv");release(node);
}
static void component_error(Component *state) {
    state->failed=1;
    void (*notify)(void *,unsigned,unsigned,unsigned,void *)=component_export("_ZN7android16SoftOMXComponent6notifyE13OMX_EVENTTYPEjjPv");
    notify(state->guest,OMX_EventError,OMX_ErrorStreamCorrupt,0,NULL);
}
static void return_buffer(Component *state,MediaList *queue,int output) {
    MediaBuffer *item=queue_front(queue);OMX_BUFFERHEADERTYPE *header=item->header;
    queue_remove(queue);item->owned=0;
    const char *symbol=output?"_ZN7android16SoftOMXComponent20notifyFillBufferDoneEP20OMX_BUFFERHEADERTYPE":"_ZN7android16SoftOMXComponent21notifyEmptyBufferDoneEP20OMX_BUFFERHEADERTYPE";
    void (*done)(void *,void *)=component_export(symbol);done(state->guest,header);
}
static int component_drain(Component *state,MediaList *output) {
    MediaBuffer *item;
    while((item=queue_front(output))){
        NspVideoFrame frame;
        int result=nsp_video_decoder_pop(state->decoder,&frame,state->eos);
        if(result<0){component_error(state);return -1;}
        if(!result)return 0;
        OMX_BUFFERHEADERTYPE *header=item->header;
        size_t bytes=(size_t)frame.width*frame.height*3/2;
        PictureTag **link=&state->tags;while(*link&&(*link)->id!=frame.picture_id)link=&(*link)->next;
        PictureTag *tag=*link;
        if((frame.width&1)||(frame.height&1)||!tag||header->nOffset>header->nAllocLen||bytes>header->nAllocLen-header->nOffset){component_error(state);return -1;}
        void (*copy)(void *,void *,const void *,const void *,const void *,uint64_t,uint64_t,uint64_t)=component_export("_ZN7android28SoftVideoDecoderOMXComponent27copyYV12FrameToOutputBufferEPhPKhS3_S3_mmm");
        const uint8_t *y=frame.i420,*u=y+(size_t)frame.width*frame.height,*v=u+(size_t)frame.width*frame.height/4;
        copy(state->guest,header->pBuffer+header->nOffset,y,u,v,frame.width,frame.width/2,frame.width/2);
        header->nFilledLen=(OMX_U32)bytes;header->nTimeStamp=tag->time;header->nFlags=tag->flags&~OMX_BUFFERFLAG_EOS;
        *link=tag->next;free(tag);return_buffer(state,output,1);
    }
    return 0;
}
static void component_pump(Component *state) {
    if(state->waiting||state->failed||state->eos==2)return;
    MediaList *input=component_queue(state->guest,0),*output=component_queue(state->guest,1);
    if(component_drain(state,output)<0)return;
    MediaBuffer *item;
    while(!state->waiting&&queue_front(output)&&(item=queue_front(input))){
        OMX_BUFFERHEADERTYPE *header=item->header;
        if(header->nOffset>header->nAllocLen||header->nFilledLen>header->nAllocLen-header->nOffset){component_error(state);return;}
        PictureTag *tag=calloc(1,sizeof *tag);if(!tag)die("Cannot allocate video timestamp");
        tag->id=++state->next_id;tag->flags=header->nFlags;tag->time=header->nTimeStamp;tag->next=state->tags;state->tags=tag;
        int picture=0;
        while(header->nFilledLen){
            size_t consumed=0;
            int result=nsp_video_decoder_feed_timed(state->decoder,header->pBuffer+header->nOffset,header->nFilledLen,tag->id,tag->time,&consumed);
            if(result<0||!consumed||consumed>header->nFilledLen){component_error(state);return;}
            header->nOffset+=(OMX_U32)consumed;header->nFilledLen-=(OMX_U32)consumed;
            if(result==NSP_VIDEO_FRAME)picture=1;
            if(result==NSP_VIDEO_FORMAT){
                NspVideoInfo info;if(nsp_video_decoder_info(state->decoder,&info)){component_error(state);return;}
                uint8_t reset=0;
                void (*change)(void *,void *,unsigned,unsigned,int,unsigned)=component_export("_ZN7android28SoftVideoDecoderOMXComponent24handlePortSettingsChangeEPbjjNS0_16CropSettingsModeEb");
                // Native output is tightly packed. Refresh stride and slice
                // height even if the negotiated dimensions have not changed.
                change(state->guest,&reset,info.width,info.height,0,1);state->waiting=reset;
            }
        }
        if(!picture){state->tags=tag->next;free(tag);}
        if(header->nFlags&OMX_BUFFERFLAG_EOS)state->eos=1;
        return_buffer(state,input,0);
        if(state->waiting)return;
        if(component_drain(state,output)<0)return;
    }
    if(state->eos&&!queue_front(input)){
        while((item=queue_front(output))){state->eos=2;item->header->nFilledLen=0;item->header->nTimeStamp=0;item->header->nFlags=OMX_BUFFERFLAG_EOS;return_buffer(state,output,1);}
    }
}
HLE_FORCE("_ZN7android7SoftAVC13onQueueFilledEj","Pump native video through available component buffers",void,video_component_queue,void *self,unsigned port) {
    (void)port;component_pump(component_state(self,1));
}
HLE_FORCE("_ZN7android28SoftVideoDecoderOMXComponent21onPortEnableCompletedEjb","Resume native video after output port reconfiguration",void,video_component_port,void *self,unsigned port,unsigned enabled) {
    void (*original)(void *,unsigned,unsigned)=component_export("_ZN7android28SoftVideoDecoderOMXComponent21onPortEnableCompletedEjb");original(self,port,enabled&1);
    Component *state=component_state(self,0);if(state&&port==1&&(enabled&1)){state->waiting=0;component_pump(state);}
}
HLE_FORCE("_ZN7android7SoftAVCD2Ev","Release native video queue state",void,video_component_destroy_base,void *self) {
    component_remove(self);void (*original)(void *)=component_export("_ZN7android7SoftAVCD2Ev");original(self);
}
HLE_FORCE("_ZN7android7SoftAVCD1Ev","Release native video queue state",void,video_component_destroy,void *self) {
    component_remove(self);void (*original)(void *)=component_export("_ZN7android7SoftAVCD1Ev");original(self);
}
HLE_FORCE("_ZN7android28SoftVideoDecoderOMXComponent9initPortsEjjjPKcj","Provide native video output queue capacity",void,video_component_ports,void *self,unsigned inputs,unsigned input_size,unsigned outputs,const char *mime,unsigned ratio) {
    if(mime&&!strcmp(mime,"video/avc")&&outputs<8)outputs=8;
    void (*original)(void *,unsigned,unsigned,unsigned,const char *,unsigned)=component_export("_ZN7android28SoftVideoDecoderOMXComponent9initPortsEjjjPKcj");
    original(self,inputs,input_size,outputs,mime,ratio);
}

static void component_reset(Component *state) {
    if(!state)return;
    while(state->tags){PictureTag *next=state->tags->next;free(state->tags);state->tags=next;}
    state->eos=0;state->failed=0;
    if(nsp_video_decoder_reset(state->decoder))component_error(state);
}
HLE_FORCE("_ZN7android7SoftAVC20onPortFlushCompletedEj","Reset native video on input flush",void,video_component_flush,void *self,unsigned port) {
    void (*original)(void *,unsigned)=component_export("_ZN7android7SoftAVC20onPortFlushCompletedEj");original(self,port);
    if(!port)component_reset(component_state(self,0));
}
HLE_FORCE("_ZN7android7SoftAVC7onResetEv","Reset native video component state",void,video_component_reset,void *self) {
    void (*original)(void *)=component_export("_ZN7android7SoftAVC7onResetEv");original(self);
    Component *state=component_state(self,0);if(state)state->waiting=0;component_reset(state);
}
