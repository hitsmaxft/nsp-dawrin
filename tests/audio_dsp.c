#include <unistd.h>
static int test_sleep(useconds_t duration);
#define usleep test_sleep
#include "../src/host/hle_audio_dsp.c"
#include <assert.h>
static uint64_t clock_ns=1000000000;
static unsigned executions,sleeps;
static uint32_t samples_per_batch=240;
uint64_t guest_ns(void){return clock_ns;}
static int test_sleep(useconds_t duration){clock_ns+=(uint64_t)duration*1000;sleeps++;return 0;}
static void setup(void *processor,const void *buffer,uint64_t size){assert(size==32);*(int *)processor=3;}
static void budget(void *processor,uint32_t value){assert(value==UINT32_MAX);}
static void process(void *processor){assert(*(int *)processor==3);*(int *)processor=0;executions++;}
static int remain(const void *processor){return *(const int *)processor;}
static int count(const void *processor){return 3;}
static int samples(const void *processor){return samples_per_batch;}
static int rate(const void *processor){return 48000;}
void *guest_sym(const char *name){
    if(strstr(name,"5Setup"))return setup;
    if(strstr(name,"SetProcessTimeMax"))return budget;
    if(strstr(name,"7Process"))return process;
    if(strstr(name,"GetRemainCommandCount"))return remain;
    if(strstr(name,"GetCommandCount"))return count;
    if(strstr(name,"GetSampleCount"))return samples;
    if(strstr(name,"GetTargetSampleRate"))return rate;
    abort();
}
int main(void){
    uint8_t command[32]={0};
    dsp_submit(0,(uintptr_t)command,sizeof command,2304000,1,42);
    assert(executions==1&&!dsp_remaining(0)&&dsp_start_tick(0)==19200000);
    assert(!dsp_start_tick(1)&&atomic_load(&batch_period_ns)==5000000);
    dsp_wait();assert(sleeps==1&&clock_ns==1005000000);
    clock_ns+=15000000;dsp_wait();dsp_wait();dsp_wait();assert(sleeps==1);
    dsp_wait();assert(sleeps==2&&clock_ns==1025000000);
    samples_per_batch=480;dsp_submit(1,(uintptr_t)command,sizeof command,4608000,0,42);
    assert(executions==2&&atomic_load(&batch_period_ns)==10000000&&!dsp_remaining(1));
    assert(!dsp_remaining(-1)&&!dsp_start_tick(2));
    puts("PASS: DSP batch ABI, completion, session isolation and delayed-wake cadence");
}
