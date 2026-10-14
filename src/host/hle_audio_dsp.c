// Execute renderer command lists through the guest's software DSP interpreter.
// The guest retains its command formats, codecs, mixing and effect processing.
#include "hle.h"
#include <stdatomic.h>
#include <unistd.h>

enum { DSP_SESSIONS = 2 };
static _Atomic uint64_t started[DSP_SESSIONS];
static _Atomic int remaining[DSP_SESSIONS];
static _Atomic uint64_t batch_period_ns = 5000000;
static void *dsp_export(const char *name) {
    void *fn = guest_sym(name);
    if (!fn) die("Required software DSP export is unavailable: %s", name);
    return fn;
}
HLE_FORCE("_ZN2nn5audio3dsp17SendCommandBufferEimmibm", "Execute commands with the guest software DSP", void, dsp_submit, int session, uint64_t address, uint64_t size, int processing_budget, unsigned reset, uint64_t applet_id) {
    (void)reset; (void)applet_id;
    if (session < 0 || session >= DSP_SESSIONS || !address || size < 32 || processing_budget < 0)
        die("Invalid software DSP submission");
    // Opaque processor scratch storage, matching the exported SDK interpreter ABI.
    _Alignas(16) uint8_t processor[0x50] = {0};
    void (*setup)(void *, const void *, uint64_t) = dsp_export("_ZN2nn5audio3dsp20CommandListProcessor5SetupEPKvm");
    void (*budget)(void *, uint32_t) = dsp_export("_ZN2nn5audio3dsp20CommandListProcessor17SetProcessTimeMaxEj");
    void (*process)(void *) = dsp_export("_ZN2nn5audio3dsp20CommandListProcessor7ProcessEv");
    int (*remain)(const void *) = dsp_export("_ZNK2nn5audio3dsp20CommandListProcessor21GetRemainCommandCountEv");
    atomic_store(&started[session], guest_ns() * 12 / 625);
    
    setup(processor, (const void *)address, size);
    int (*command_count)(const void *) = dsp_export("_ZNK2nn5audio3dsp20CommandListProcessor15GetCommandCountEv");
    int (*samples)(const void *) = dsp_export("_ZNK2nn5audio3dsp20CommandListProcessor14GetSampleCountEv");
    int (*rate)(const void *) = dsp_export("_ZNK2nn5audio3dsp20CommandListProcessor19GetTargetSampleRateEv");
    int sample_count=samples(processor), sample_rate=rate(processor);
    if(sample_count<=0||sample_rate<=0)die("Invalid software DSP sample period");
    atomic_store(&batch_period_ns,(uint64_t)sample_count*1000000000/sample_rate);
    atomic_store(&remaining[session], command_count(processor));
    budget(processor, UINT32_MAX);
    process(processor);
    int left = remain(processor);
    atomic_store(&remaining[session], left);
    if (left) die("Software DSP left %d commands unprocessed", left);
}
HLE_FORCE("_ZN2nn5audio3dsp21GetRemainCommandCountEi", "Report software DSP completion", int, dsp_remaining, int session) {
    return session >= 0 && session < DSP_SESSIONS ? atomic_load(&remaining[session]) : 0;
}
HLE_FORCE("_ZN2nn5audio3dsp21GetRenderingStartTickEi", "Report software DSP batch start", uint64_t, dsp_start_tick, int session) {
    return session >= 0 && session < DSP_SESSIONS ? atomic_load(&started[session]) : 0;
}
HLE_FORCE("_ZN2nn5audio3dsp4WaitEv", "Pace automatic renderer batches", void, dsp_wait, void) {
    // Keep sample cadence when the host coalesces a wake-up. Process the
    // actual missed batches instead of slowing the sample clock permanently.
    static _Thread_local uint64_t deadline;
    uint64_t now=guest_ns(), period=atomic_load(&batch_period_ns);
    if(!deadline||now>deadline+1000000000)deadline=now;
    deadline+=period;
    if(deadline>now)usleep((useconds_t)((deadline-now+999)/1000));
}
