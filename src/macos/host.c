// Minimal native bring-up harness. Executes rewritten ARM64 on the host CPU.
// Guest code runs directly; resources and executable caches are external.
#include "hle.h"
#include <signal.h>
#include <unistd.h>
#include <mach/mach_time.h>
#include <sys/ucontext.h>

struct dm_flags g_flag;
uint64_t g_t0_ns;
extern void dm_gate(void);
extern uint32_t svc_thread_main_init(void);

uint64_t now_ns(void) {
    static mach_timebase_info_data_t tb;
    if (!tb.denom) mach_timebase_info(&tb);
    return mach_absolute_time() * tb.numer / tb.denom;
}
uint64_t guest_ns(void) { return now_ns(); }
int dm_detclock_enabled(void) { return 0; }
uint64_t dm_entropy64(void) { uint64_t n; arc4random_buf(&n, sizeof n); return n; }
void dm_prof_add(int id, uint64_t ns, uint64_t bytes) { (void)id; (void)ns; (void)bytes; }
void *hlecount_wrap(const char *kind, const char *name, void *p) { (void)kind; (void)name; return p; }
void hlecount_seal(void) {}
void hlecount_svc(int n) { (void)n; }
uint64_t svc_host_call(int n, uint64_t *regs) { die("Unsupported private SVC %#x is not valid for this title", n); }
void crash_thread_init(void) {}
static int (*fault_hook)(void *,int,void *);
static void (*write_prep)(void *,size_t);
void dm_fault_hook_register(int (*fn)(void *,int,void *)) {fault_hook=fn;}
void dm_guest_write_prep_register(void (*fn)(void *,size_t)) {write_prep=fn;}
void dm_res_report_register(void (*fn)(uint32_t,const char *)) {(void)fn;}
void crash_set_wait_dump(void (*fn)(void)) {(void)fn;}
void dm_guest_write_prepare(void *p, size_t n) { if(write_prep)write_prep(p,n); }
extern int native_front_init(void);
extern void native_front_loop(void);
static struct {const void *key;void *value;} objects[128];
static pthread_mutex_t objects_mutex=PTHREAD_MUTEX_INITIALIZER;
void *objmap_get(const void *key) {
    void *v=NULL;pthread_mutex_lock(&objects_mutex);
    for(int i=0;i<128;i++)if(objects[i].key==key){v=objects[i].value;break;}
    pthread_mutex_unlock(&objects_mutex);return v;
}
void objmap_put(const void *key,void *value) {
    pthread_mutex_lock(&objects_mutex);int slot=-1;
    for(int i=0;i<128;i++){if(objects[i].key==key){slot=i;break;}if(!objects[i].key&&slot<0)slot=i;}
    if(slot<0)die("native object map full");objects[slot].key=key;objects[slot].value=value;
    pthread_mutex_unlock(&objects_mutex);
}
void *objmap_del(const void *key) {
    void *v=NULL;pthread_mutex_lock(&objects_mutex);
    for(int i=0;i<128;i++)if(objects[i].key==key){v=objects[i].value;objects[i].key=NULL;objects[i].value=NULL;break;}
    pthread_mutex_unlock(&objects_mutex);return v;
}

static void symbol_at(uint64_t pc) {
    module_t *m=module_of((void *)pc);
    if (!m) return;
    uint64_t off=pc-(uint64_t)m->base,best=0; const char *name=NULL;
    for (unsigned i=0;i<m->nsym;i++) {
        const Elf64_Sym *s=&m->symtab[i];
        if (s->st_shndx && (s->st_info&15)==2 && s->st_value<=off && s->st_value>=best) {best=s->st_value;name=m->strtab+s->st_name;}
    }
    if (name) LOG("nearest symbol %s+%#llx",name,off-best);
}
void dm_backtrace(uint64_t fp) {
    for (int i=0; fp && i<24; i++) {
        uint64_t *frame=(void *)fp;
        // Read only frames within the current host stack.
        uint64_t top=(uint64_t)pthread_get_stackaddr_np(pthread_self());
        size_t size=pthread_get_stacksize_np(pthread_self());
        if (fp<top-size || fp+16>top || (fp&15)) break;
        module_t *m=module_of((void *)frame[1]);
        LOG("frame %d: %s+%#llx",i,m?m->name:"host",m?frame[1]-(uint64_t)m->base:frame[1]);
        symbol_at(frame[1]);
        if (frame[0]<=fp) break;
        fp=frame[0];
    }
}
static void fault(int sig, siginfo_t *info, void *ctx) {
    ucontext_t *u=ctx;
    if ((sig==SIGSEGV || sig==SIGBUS) && fault_hook && fault_hook(info->si_addr,(u->uc_mcontext->__es.__esr & (1u<<6))!=0,ctx)) return;
    uint64_t pc=u->uc_mcontext->__ss.__pc;
    module_t *m=module_of((void *)pc);
    LOG("native fault signal=%d address=%p pc=%s+%#llx",sig,info->si_addr,m?m->name:"host",m?pc-(uint64_t)m->base:pc);
    symbol_at(pc);
    dm_backtrace(u->uc_mcontext->__ss.__fp);
    _exit(128+sig);
}

void guest_thread_init(void) {
    uint8_t *tlr=calloc(1,0x600);
    pthread_setspecific(g_keygate,(void *)dm_gate);
    pthread_setspecific(g_key18,0);
    pthread_setspecific(g_keytls,calloc(1,8192));
    *(void **)(tlr+0x1f8)=tlr+0x200;
    pthread_setspecific(g_keytlr,tlr);
}
static void *required(const char *name) {
    void *p=guest_sym(name);
    if (!p) die("missing startup export %s",name);
    return p;
}
static void invoke(const char *name) {
    LOG("NATIVE CALL %s",name);
    ((void (*)(void))required(name))();
    LOG("NATIVE RETURN %s",name);
}
static void *run(void *arg) {
    (void)arg;
    guest_thread_init();
    uint32_t main_handle=svc_thread_main_init();
    invoke("_init_libc0");
    LOG("NATIVE CALL nnosInitialize");
    ((void (*)(uint64_t,uint64_t))required("nnosInitialize"))(main_handle,0);
    LOG("NATIVE RETURN nnosInitialize");
    invoke("_init_libc1");
    invoke("nninitInitializeSdkModule");
    invoke("nninitStartup");
    invoke("_init_libc2");
    run_module_inits();
    invoke("nnMain");
    return NULL;
}
int main(int argc,char **argv) {
    if (argc<2) { fprintf(stderr,"usage: %s PATCHED_DIR [--load-only]\n",argv[0]); return 2; }
    g_flag.svc=!!getenv("DM_SVC"); g_flag.thr=!!getenv("DM_THR");g_flag.dbg=1;g_flag.bootprof=1;
    g_t0_ns=now_ns();
    struct sigaction sa={0};sa.sa_sigaction=fault;sa.sa_flags=SA_SIGINFO;
    sigaction(SIGSEGV,&sa,0);sigaction(SIGBUS,&sa,0);sigaction(SIGILL,&sa,0);sigaction(SIGTRAP,&sa,0);
    const char *timeout=getenv("DM_TIMEOUT");alarm(timeout?(unsigned)strtoul(timeout,NULL,10):20);
    const char *names[12]; int count=0;
    names[count++]="main";
    static char optional[10][16];
    for (int i=0; i<10; i++) {
        snprintf(optional[i],sizeof optional[i],"subsdk%d",i);
        char path[4096];snprintf(path,sizeof path,"%s/%s.patched.bin",argv[1],optional[i]);
        if (!access(path,R_OK)) {
            if (count >= MAX_MOD-1) die("Too many executable modules");
            names[count++]=optional[i];
        }
    }
    names[count++]="sdk";
    load_modules(argv[1],names,count);
    LOG("NATIVE MODULE LOAD COMPLETE");
    if (argc>2 && !strcmp(argv[2],"--load-only")) return 0;
    int window=native_front_init();
    extern void native_control_start(void);native_control_start();
    pthread_attr_t attr;pthread_attr_init(&attr);pthread_attr_setstacksize(&attr,8<<20);
    pthread_t th;int rc=pthread_create(&th,&attr,run,0);if(rc)die("pthread_create %d",rc);
    pthread_attr_destroy(&attr);
    if(window)native_front_loop();
    pthread_join(th,0);
    return 0;
}
