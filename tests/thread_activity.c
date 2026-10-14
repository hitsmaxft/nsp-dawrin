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
#include <stdatomic.h>
#include <unistd.h>
void *guest_sym(const char *name) { (void)name; abort(); }
static atomic_int entered, finished, release_worker;
static void *sleeper(void *opaque) {
    thr_t *thread=opaque;
    pthread_setspecific(g_keythr,thread);
    thread->mport=pthread_mach_thread_np(pthread_self());
    uint64_t regs[31]={500000000};
    atomic_store(&entered,1);
    svc_thread(0x0b,regs);
    atomic_store(&finished,1);
    while(!atomic_load(&release_worker))sched_yield();
    return NULL;
}
static uint64_t activity(thr_t *thread,unsigned value) {
    uint64_t regs[31]={thread->handle,value};
    assert(svc_thread(0x32,regs));return regs[0];
}
int main(void) {
    svc_thread_main_init();
    thr_t thread={.started=1};
    pthread_cond_init(&thread.cv,NULL);
    pthread_mutex_lock(&G);thread.handle=h_new(O_THREAD,&thread);pthread_mutex_unlock(&G);
    assert(!pthread_create(&thread.pt,NULL,sleeper,&thread));
    while(!atomic_load(&entered))sched_yield();
    usleep(20000);
    assert(!activity(&thread,1));
    assert(thread.paused);
    assert(!activity(&thread,1));
    usleep(600000);
    assert(!atomic_load(&finished));
    assert(!activity(&thread,0));
    assert(!thread.paused);
    while(!atomic_load(&finished))sched_yield();
    assert(activity(&thread,1)==R_BAD_STATE);
    assert(!thread.paused);
    atomic_store(&release_worker,1);
    pthread_join(thread.pt,NULL);
    assert(activity(cur(),1)==R_BAD_STATE);
    assert(activity(&thread,2)==0xf001);
    pthread_mutex_lock(&G);g_h[thread.handle-0x1000].type=O_FREE;pthread_mutex_unlock(&G);
    pthread_cond_destroy(&thread.cv);
    puts("PASS: sleep suspension, duplicate suspend, resume and unsafe-host rejection");
}
