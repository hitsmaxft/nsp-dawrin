// Common header of the native Switch host (multi-module).
#pragma once
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_MOD 8
#define LOG(...) do { fprintf(stderr, "[dm] " __VA_ARGS__); fputc('\n', stderr); } while (0)
#define die(...) do { LOG("FATAL " __VA_ARGS__); abort(); } while (0)

typedef struct { uint32_t st_name; uint8_t st_info, st_other; uint16_t st_shndx; uint64_t st_value, st_size; } Elf64_Sym;
typedef struct { int64_t d_tag; union { uint64_t d_val, d_ptr; } d_un; } Elf64_Dyn;
typedef struct { uint64_t r_offset, r_info; int64_t r_addend; } Elf64_Rela;
typedef struct { uint8_t *d; size_t n; } dm_blob;   // One save file of the original game read whole into memory (dm_pages.c dm_save_blobs)
#define ELF64_R_SYM(i) ((i) >> 32)
#define ELF64_R_TYPE(i) ((i) & 0xffffffff)
enum { DT_INIT = 12, DT_RELA = 7, DT_RELASZ = 8, DT_JMPREL = 23, DT_PLTRELSZ = 2, DT_SYMTAB = 6, DT_STRTAB = 5,
       DT_INIT_ARRAY = 25, DT_INIT_ARRAYSZ = 27 };
enum { R_AARCH64_ABS64 = 257, R_AARCH64_GLOB_DAT = 1025, R_AARCH64_JUMP_SLOT = 1026, R_AARCH64_RELATIVE = 1027 };

// Run-time state of one NSO module
typedef struct {
    char name[16];
    uint8_t *base;             // Start address of the image (including the patch area) in the host address space
    size_t size;
    uint64_t text_end, ro_off, data_off, patch_off, key_page_off, key_page_size;   // From the rewriter fixups header
    unsigned key_idx[8];
    const Elf64_Dyn *dyn;
    const Elf64_Sym *symtab;
    const char *strtab;
    unsigned nsym;
    uint32_t *symh; unsigned symh_mask;   // Name hash table of defined symbols (open addressing, stores symbol indices; for a duplicated name only the smallest index is kept = the first hit of a linear scan)
    uint64_t init, init_array, init_arraysz;   // init = DT_INIT (the module's _init: registers the DSO and runs this module's init_array)
} module_t;

extern module_t g_mod[MAX_MOD];
extern int g_nmod;
// Four thread-local slots: K18 = the Switch's x18, KTLS = tpidr_el0, KTLR = tpidrro_el0 (ThreadLocalRegion), KGATE = host gate entry; the actual key numbers are written into the key page by the loader
extern pthread_key_t g_key18, g_keytls, g_keytlr, g_keygate;
extern pthread_key_t g_keyres[2], g_keyaspect, g_keyaspectui;

void load_modules(const char *dir, const char **names, int n);
void run_module_inits(void);
void *module_sym(module_t *m, const char *name);
void *guest_sym(const char *name);
module_t *module_of(const void *p);
// Gate dispatch: rewritten svc / timer reads come in through the common entry, ret_addr = the return point of that gate block, regs points to the saved x0..x30
uint64_t gate_dispatch(uint64_t ret_addr, uint64_t *regs);
// Observation gates (rewriter OBS table; numbering matches patch_nso.py): read-only callbacks, called on a gate hit once attached
enum { OBS_UIMSG = 1, OBS_TICK = 2, OBS_C2S = 3, OBS_C2S_SYS = 4, OBS_SETLANG = 5, OBS_TARGET_RANK = 7, OBS_UI_PROJECT = 8, OBS_FREEZE_WORLD = 10, OBS_FREEZE_CLIENT = 11, OBS_FREEZE_ANIM = 12, OBS_FREEZE_RENDER = 13, OBS_TEXTBOX = 14, OBS_EVENT_MSG = 15, OBS_LEVEL_WARP = 16, OBS_QUEST_KILL = 17, OBS_NOTICE_INPUT = 18, OBS_ERR_SMOOTH = 19, OBS_MODEL_YAW = 20, OBS_TOOLTIP = 21, OBS_PRESET_SPAWN = 22, OBS_MAX = 23 };   // 6 = iOS binding read (dm_touch_game_bridge.c)
void gate_obs_set(int id, void (*fn)(const uint64_t *regs));
int gate_obs_present(int id);
void dm_quiet_difficulty_msg(int on);   //
int gate_svc_present(int num);   // Whether the build output has a gate for this svc number (for host call numbers introduced by cuts)   // whether the build output has this observation gate (registered in gates.tsv)
uint64_t now_ns(void);
uint64_t guest_ns(void);              // Guest clock (hle_os.c; does not advance while DM_TICK_HOLD is frozen)
int dm_detclock_enabled(void);
void dm_guest_clock_advanced(void);
void guest_clock_freeze(int on);
void guest_clock_freeze_for(int reason, int on);   // Freeze by reason (1 background, 2 system keyboard); see hle_os.c
void dm_guest_frame_tick(void);        // Called on every present (hle_nvn.c): when DM_DETCLOCK is on, advances the guest clock by one fixed step
int dm_nvn_ruler_truth(void);         // 1 during the ground-truth phase of the visual ruler (the first two screenshots with DM_NVN_RULER=1)
uint64_t dm_nvn_frame_count(void);
uint64_t dm_nvn_sub_cpu_ns(void);     // Cumulative CPU nanoseconds of submit (excluding present)
int dm_ingame_now(void);              // Whether we are in a run (diag.c)
void dm_3d_scale_feed(double iv_ms);   // The present thread reports the actual present interval every frame (−1 discard / 0 no reading), driving the dynamic 3D scale
float dm_3d_scale_cur(void);          // The 3D render scale currently in effect (hle_oe.c scale3d_tick)     // current cumulative count of presented frames (for DM_TICKS alignment observation)
void dm_backtrace(uint64_t fp);
void crash_watch_progress(uint32_t tick, const char *stage);
void crash_watch_frame(void);
void crash_watch_pregame_done(void);
uint64_t crash_watch_progress_count(void);
void crash_dump_now(const char *why);   // Dump state on demand (threads + graphics wait points), without exiting
// Diagnostic switches: read once from environment variables when main starts (getenv takes the libc global environment lock, and on a hot path it would make all guest threads queue up)
extern uint64_t g_t0_ns;   // Host start time (now_ns), used for relative times in the log
extern struct dm_flags { int thr, svc, fs, movie, dbg, imports, bootprof; } g_flag;
// Boot timeline (DM_BOOTPROF=1, diag.c): segment marks + counters (nanoseconds / bytes, accumulated over all threads); PROF_GFX_* can be used for instrumentation
enum { PROF_FS_READ, PROF_WAIT_LOCK, PROF_WAIT_CV, PROF_WAIT_ADDR, PROF_WAIT_SYNC, PROF_SLEEP, PROF_MAIN_WAIT,
       PROF_GFX_PRESENT, PROF_GFX_SHADER, PROF_TACT, PROF_N };   // PROF_TACT: time and output bytes of TACT block zlib decode (svc #0x80, host libdeflate)
void dm_prof_add(int id, uint64_t ns, uint64_t bytes);
void dm_prof_mark(const char *seg);
uint64_t dm_prof_ribbon_ns(void);   // The now_ns time at which OpenPanel MainMenuButtonRibbon first appeared (0 = not yet; needs DM_BOOTPROF=1)
void *objmap_get(const void *guest); void objmap_put(const void *guest, void *host); void *objmap_del(const void *guest);
void hle_signal_system_event(void *g);   // hle_thread.c: signal a service-layer SystemEvent (any thread)
void hle_bind_system_event(void *g, int autoclear);   // On a guest thread, bind a guest SystemEvent to a kernel event
// Page fault hook / hook before the host writes guest memory (crash.c; used for write-protect dirty page tracking)
void dm_fault_hook_register(int (*fn)(void *addr, int is_write, void *uc));
void dm_guest_write_prep_register(void (*fn)(void *addr, size_t len));
void dm_res_report_register(void (*fn)(uint32_t tick, const char *why));   // Resource count callback (registered by the graphics layer): called every 250 ticks, when the loading screen has been dismissed, and on exit when the record is full
void (*dm_res_report_cb(void))(uint32_t tick, const char *why);   // Get the registered resource count callback (null if not registered)
void dm_guest_write_prepare(void *addr, size_t len);
// Graphics lifecycle (hle_nvn.c): on=1 suspends (afterwards submit / present block, and in-flight GPU work is drained before returning), on=0 resumes; called by the iOS front end when entering and leaving the background
void dm_gfx_suspend(int on);
void dm_gfx_shot_at(long k, const char *path);
void dm_shot_written(const char *path, int ok);   // The graphics side finished writing a screenshot to disk (diag.c: DM_TICK_HOLD=E:SHOT unfreezes on this)
void dm_host_shutdown(const char *why);   // Graceful exit (crash.c): stop background threads and audio, drain graphics, then _exit(0); used by SIGTERM and the iOS App termination callback   // graphics side: screenshot of the k-th frame after the current presented frame (nvn_mtl.m)
