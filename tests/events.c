#include "../src/host/hle_thread.c"
#include <assert.h>
struct dm_flags g_flag;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
uint64_t now_ns(void){return clock_gettime_nsec_np(CLOCK_MONOTONIC);}
uint64_t guest_ns(void){return now_ns();}
int dm_detclock_enabled(void){return 0;}
void dm_prof_add(int id,uint64_t ns,uint64_t bytes){}
void guest_thread_init(void){abort();}
void crash_thread_init(void){}
void dm_thread_enter(uint64_t entry,uint64_t arg,uint64_t sp){abort();}
module_t *module_of(const void *p){return NULL;}
static unsigned creates;
typedef struct {uint32_t write,read;} TestEvent;
static uint32_t create_event(void *pointer,int clear,int interprocess) {
    (void)clear;assert(interprocess);uint64_t regs[31]={0};assert(svc_thread(0x45,regs));
    TestEvent *event=pointer;event->write=regs[1];event->read=regs[2];creates++;return regs[0];
}
static uint32_t write_handle(const void *pointer){return ((const TestEvent *)pointer)->write;}
void *guest_sym(const char *name) {
    if(strstr(name,"CreateSystemEvent"))return create_event;
    if(strstr(name,"GetWritableHandleOfSystemEvent"))return write_handle;
    abort();
}
static void close_handle(uint32_t handle){uint64_t regs[31]={handle};assert(svc_thread(0x16,regs));assert(!regs[0]);}
int main(void) {
    svc_thread_main_init();TestEvent event={0};
    hle_bind_system_event(&event,1);assert(creates==1);
    hle_bind_system_event(&event,1);assert(creates==1);
    hle_signal_system_event(&event);assert(((event_t *)h_get(event.write,O_EVENT_W))->signaled);
    close_handle(event.write);assert(h_get(event.read,O_EVENT_R));
    assert(!se_find(&event));close_handle(event.read);
    memset(&event,0,sizeof event);hle_bind_system_event(&event,1);assert(creates==2);
    assert(!((event_t *)h_get(event.write,O_EVENT_W))->signaled);
    hle_unbind_system_event(&event);assert(!se_find(&event));
    assert(h_get(event.write,O_EVENT_W)); // Association removal does not steal guest ownership.
    close_handle(event.read);close_handle(event.write);
    hle_bind_system_event(&event,1);assert(creates==3);
    close_handle(event.read);close_handle(event.write);
    assert(g_nse==0);
    puts("PASS: event pointer reuse, kernel handle reuse and guest-owned destruction");
}
