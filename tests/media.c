#include "../src/host/hle_media.c"
#include <assert.h>

typedef struct { void *vtable, *storage; uint64_t count; } Vector;
static unsigned flags_seen, additions, constructions, destructions;
static int factory_available = 1;
static uint32_t component_result;
static void select_codec(const char *mime,int encoder,const char *match,unsigned flags,void *output) {
    (void)mime;(void)encoder;(void)match;(void)output;flags_seen=flags;
}
static void construct(void *pointer,const char *text) {
    assert(!strcmp(text,"OMX.google.h264.decoder"));*(char **)pointer=strdup(text);constructions++;
}
static void destroy(void *pointer) { free(*(void **)pointer);destructions++; }
static int64_t add(void *pointer,const void *item) {
    assert(!strcmp(*(char *const *)item,"OMX.google.h264.decoder"));
    Vector *vector=pointer;additions++;return vector->count++;
}
static uint32_t component(void *self,const char *name,const void *callbacks,void *user,void **output) {
    assert(self&&name&&callbacks&&user&&output);*output=user;return component_result;
}
void *guest_sym(const char *name) {
    if(strstr(name,"findMatchingCodecs"))return select_codec;
    if(strstr(name,"SoftAVC_create"))return factory_available?(void *)component:NULL;
    if(strstr(name,"String8C1"))return construct;
    if(strstr(name,"String8D1"))return destroy;
    if(strstr(name,"VectorImpl3add"))return add;
    if(strstr(name,"makeComponentInstance"))return component;
    abort();
}
int main(void) {
    Vector vector={0};
    media_select("video/avc",0,NULL,16|32,&vector);
    assert(flags_seen==(8|32)&&vector.count==1&&additions==1&&constructions==1&&destructions==1);
    media_select("video/avc",0,NULL,0,&vector);assert(additions==1);
    vector.count=0;
    media_select("audio/mp4a-latm",0,NULL,0,&vector);
    media_select("video/avc",1,NULL,0,&vector);
    media_select("video/avc",0,"explicit.component",0,&vector);
    factory_available=0;media_select("video/avc",0,NULL,0,&vector);
    assert(!vector.count&&additions==1);
    void *out=NULL;component_result=0x80001001;
    assert(media_component(&vector,"test.component",&vector,&vector,&out)==component_result&&out==&vector);
    puts("PASS: software codec fallback, exported factory gating, explicit selection and failure forwarding");
}
