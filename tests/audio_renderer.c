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
void *guest_sym(const char *name) {
    if (strstr(name, "GetReadableHandleOfSystemEvent")) return read_handle;
    if (strstr(name, "DestroySystemEvent")) return destroy_event;
    if (strstr(name, "CreateSystemEvent")) return create_event;
    if (strstr(name, "AudioRenderSystemC")) return construct;
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
    puts("PASS: renderer event promotion, pool reuse and existing shared event ownership");
}
