#include "../src/host/hle_audio_renderer.c"
#include <assert.h>

typedef struct { uint32_t handle; int initialized; } Event;
static unsigned created, destroyed, constructed;
static uint32_t read_handle(const void *pointer) { return ((const Event *)pointer)->handle; }
static void destroy_event(void *pointer) {
    Event *event = pointer; assert(event->initialized);
    event->initialized = 0; destroyed++;
}
static Result create_event(void *pointer, int clear, int shared) {
    Event *event = pointer; assert(!event->initialized && clear == 1 && shared == 1);
    event->initialized = 1; event->handle = 0x1002; created++; return RES_OK;
}
static void construct(void *self, void *event) {
    assert(((Event *)event)->initialized && read_handle(event));
    *(void **)self = event; constructed++;
}
static void *map_key,*map_value;
void *objmap_get(const void *key){return key==map_key?map_value:NULL;}
void objmap_put(const void *key,void *value){assert(!map_value);map_key=(void *)key;map_value=value;}
void *objmap_del(const void *key){void *value=objmap_get(key);if(value){map_key=NULL;map_value=NULL;}return value;}
static Result initialize_result,start_result;
static unsigned starts,stops,adds,removes,finalizes;
static int add_ok=1,manager_token;
static Result initialize(void *self,const void *param,uint32_t process,void *buffer,uint64_t size,const void *user,int session){return initialize_result;}
static Result start(void *self){starts++;return start_result;}
static void stop(void *self){stops++;}
static void *manager(void){return &manager_token;}
static int add(void *manager,void *self){assert(manager==&manager_token);adds++;return add_ok;}
static void remove_renderer(void *manager,void *self){assert(manager==&manager_token);removes++;}
static void finalize(void *self){assert(!objmap_get(self));finalizes++;}
void *guest_sym(const char *name) {
    if (strstr(name, "GetReadableHandleOfSystemEvent")) return read_handle;
    if (strstr(name, "DestroySystemEvent")) return destroy_event;
    if (strstr(name, "CreateSystemEvent")) return create_event;
    if (strstr(name, "AudioRenderSystemC")) return construct;
    if(strstr(name,"AudioRenderSystem10Initialize"))return initialize;
    if(strstr(name,"AudioRenderSystem5Start"))return start;
    if(strstr(name,"AudioRenderSystem4Stop"))return stop;
    if(strstr(name,"GetInstance"))return manager;
    if(strstr(name,"Manager3Add"))return add;
    if(strstr(name,"Manager6Remove"))return remove_renderer;
    if(strstr(name,"AudioRenderSystem8Finalize"))return finalize;
    abort();
}
int main(void) {
    Event local = {.initialized = 1}, shared = {.initialized = 1, .handle = 0x1010};
    void *owner = NULL;
    renderer_construct(&owner, &local);
    assert(owner == &local && created == 1 && destroyed == 1 && constructed == 1);
    renderer_construct_complete(&owner, &local);
    assert(created == 1 && destroyed == 1 && constructed == 2);
    renderer_construct(&owner, &shared);
    assert(owner == &shared && shared.handle == 0x1010 && created == 1 && destroyed == 1);
    uint8_t param[0x24]={0};int renderer;
    initialize_result=RES_FAIL;assert(renderer_initialize(&renderer,param,0,NULL,0,NULL,0)==RES_FAIL&&!map_value);
    initialize_result=0;assert(!renderer_initialize(&renderer,param,0,NULL,0,NULL,0));
    start_result=RES_FAIL;assert(renderer_start(&renderer)==RES_FAIL&&!adds);
    start_result=0;add_ok=0;assert(renderer_start(&renderer)==RES_FAIL&&adds==1&&stops==1);
    add_ok=1;assert(!renderer_start(&renderer));assert(!renderer_start(&renderer)&&adds==2);
    renderer_finalize(&renderer);assert(removes==1&&finalizes==1&&!map_value);
    param[0x23]=1;assert(!renderer_initialize(&renderer,param,0,NULL,0,NULL,0));
    assert(!renderer_start(&renderer)&&adds==2);renderer_finalize(&renderer);assert(removes==1&&finalizes==2);
    puts("PASS: renderer event promotion, pool reuse, automatic scheduling, failure rollback and manual execution");
}
