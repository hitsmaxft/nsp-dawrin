// nn::time: a real device gets the network-calibrated user clock through the time service; the host reads the system clock directly (single machine, offline).
// Layout follows the public Horizon ABI: PosixTime = int64 seconds; CalendarTime = {s16 year, s8 month/day/hour/minute/second};
// CalendarAdditionalInfo = {u32 day of week, u32 day of year, char time zone name[8], u32 DST, s32 UTC offset in seconds}.
#include "hle.h"
#include <stdatomic.h>
#include <time.h>

typedef struct { int16_t year; int8_t month, day, hour, minute, second; int8_t pad; } CalendarTime;
typedef struct { uint32_t wday, yday; char tzname[8]; uint32_t dst; int32_t offset; } CalendarAdditionalInfo;

// Optional fixed wall clock for reproducible interface tests.
static int64_t fixed_time(void) {
    static int64_t v = -2;
    if (v == -2) { const char *e = getenv("DM_FIXED_TIME"); v = e ? strtoll(e, 0, 0) : -1;
                   if (v >= 0) LOG("DM_FIXED_TIME=%lld：用户时钟返回定值", (long long)v); }
    return v;
}

typedef struct { int64_t seconds; uint8_t source[16]; } SteadyClockTimePoint;
typedef struct { int64_t offset; SteadyClockTimePoint timestamp; } SystemClockContext;
_Static_assert(sizeof(SteadyClockTimePoint) == 24, "Steady clock time point ABI");
_Static_assert(sizeof(SystemClockContext) == 32, "System clock context ABI");
static SystemClockContext local_clock;
static pthread_once_t clock_once = PTHREAD_ONCE_INIT;
static int64_t steady_seconds(void) { return fixed_time() >= 0 ? 0 : (int64_t)(now_ns() / 1000000000ull); }
static void initialize_clock_context(void) {
    local_clock.timestamp.seconds = steady_seconds();
    arc4random_buf(local_clock.timestamp.source, sizeof local_clock.timestamp.source);
    int64_t wall = fixed_time();
    local_clock.offset = (wall >= 0 ? wall : time(NULL)) - local_clock.timestamp.seconds;
}
HLE_FORCE("_ZN2nn4time23StandardUserSystemClock21GetSystemClockContextEPNS0_18SystemClockContextE", "Local wall-clock correlation and stable source identity", Result, h_time_Context, SystemClockContext *out) {
    if (!out) return RES_FAIL;
    pthread_once(&clock_once, initialize_clock_context);
    *out = local_clock;
    return RES_OK;
}
HLE_FORCE("_ZN2nn4time19StandardSteadyClock19GetCurrentTimePointEPNS0_20SteadyClockTimePointE", "Monotonic local clock time point", Result, h_time_Steady, SteadyClockTimePoint *out) {
    if (!out) return RES_FAIL;
    pthread_once(&clock_once, initialize_clock_context);
    *out = local_clock.timestamp;
    out->seconds = steady_seconds();
    return RES_OK;
}

HLE_FORCE("_ZN2nn4time10InitializeEv", "连 time 服务；时钟改取宿主系统时间", Result, h_time_Initialize, void) { return RES_OK; }
HLE_FORCE("_ZN2nn4time13IsInitializedEv", "time 服务已被接管，恒为已初始化", int, h_time_IsInitialized, void) { return 1; }
HLE_FORCE("_ZN2nn4time23StandardUserSystemClock14GetCurrentTimeEPNS0_9PosixTimeE", "用户时钟 → 宿主 time()", Result, h_time_GetCurrentTime, int64_t *out) {
    int64_t ft = fixed_time(); *out = ft >= 0 ? ft : time(NULL); return RES_OK;
}
HLE_FORCE("_ZN2nn4time23StandardUserSystemClock3nowEv", "用户时钟 → 宿主 time()", int64_t, h_time_now, void) {
    int64_t ft = fixed_time(); return ft >= 0 ? ft : time(NULL);
}
HLE_FORCE("_ZN2nn4time23StandardUserSystemClock9to_time_tERKNSt3__16chrono10time_pointINS0_17SystemClockTraitsENS3_8durationIlNS2_5ratioILl1ELl1EEEEEEE",
          "SDK 实现与 now() 配套，一并接管", int64_t, h_time_to_time_t, const int64_t *tp) { return *tp; }
HLE_FORCE("_ZN2nn4time14ToCalendarTimeEPNS0_12CalendarTimeEPNS0_22CalendarAdditionalInfoERKNS0_9PosixTimeE",
          "连 time 服务的时区规则；改用宿主 localtime_r", Result, h_time_ToCalendarTime, CalendarTime *ct, CalendarAdditionalInfo *ai, const int64_t *pt) {
    time_t t = *pt; struct tm tm; localtime_r(&t, &tm);
    static int once; if (!once++) LOG("ToCalendarTime：首次换算 %lld → %04d-%02d-%02d %02d:%02d（时区 %s，偏移 %ld 秒）", (long long)t, tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_zone ? tm.tm_zone : "?", (long)tm.tm_gmtoff);
    if (ct) *ct = (CalendarTime){(int16_t)(tm.tm_year + 1900), (int8_t)(tm.tm_mon + 1), (int8_t)tm.tm_mday, (int8_t)tm.tm_hour, (int8_t)tm.tm_min, (int8_t)tm.tm_sec, 0};
    if (ai) { memset(ai, 0, sizeof *ai); ai->wday = tm.tm_wday; ai->yday = tm.tm_yday; strlcpy(ai->tzname, tm.tm_zone ? tm.tm_zone : "UTC", sizeof ai->tzname);
              ai->dst = tm.tm_isdst > 0; ai->offset = (int32_t)tm.tm_gmtoff; }
    return RES_OK;
}
// main+0xb04d34 calling localtime and then strftime, and was off by 8 hours). The SDK on a real Switch converts by the system time zone, so only following the host system time zone here is consistent;
// the host TZ normally = the system time zone, and is pinned to UTC only for deterministic comparison with DM_FIXED_TIME (main.c). The struct tm layout is the same on both sides (9 ints, long offset, time zone name pointer).
// gmtime / gmtime_r / timegm are UTC anyway and are not taken over. The same-named pass-through entries in hle_table.c only take effect when the symbol has no definition (the SDK defines them), hence HLE_FORCE
HLE_FORCE("localtime", "本地时刻 → 宿主 localtime（跟系统时区）", struct tm *, h_localtime, const int64_t *t) { time_t v = (time_t)*t; return localtime(&v); }
HLE_FORCE("localtime_r", "本地时刻 → 宿主 localtime_r（跟系统时区）", struct tm *, h_localtime_r, const int64_t *t, struct tm *out) { time_t v = (time_t)*t; return localtime_r(&v, out); }
HLE_FORCE("mktime", "本地日历 → 绝对秒，宿主 mktime（跟系统时区）", int64_t, h_mktime, struct tm *tm) { return (int64_t)mktime(tm); }
