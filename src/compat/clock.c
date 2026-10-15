#include "clock.h"
#include "../backend/backend.h"
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(CalendarTime)==8,"Calendar ABI");
_Static_assert(sizeof(CalendarAdditionalInfo)==24,"Calendar information ABI");
_Static_assert(sizeof(SteadyClockTimePoint)==24,"Steady clock ABI");
_Static_assert(sizeof(SystemClockContext)==32,"System clock context ABI");
static SystemClockContext context;
static bool initialized;
static int64_t fixed=-1;
/* Called under HOST_LOCK_CLOCK, shared by SDK and IPC entry points. */
static bool initialize(void) {
    if(initialized)return true;
    const HostBackend *host=host_backend();
    const char *value=getenv("DM_FIXED_TIME");
    if(value && *value){
        char *end;errno=0;
        long long parsed=strtoll(value,&end,0);
        if(!errno && !*end && parsed>=0)fixed=(int64_t)parsed;
    }
    int64_t wall;uint64_t steady;
    if(!host->clock.wall_seconds(&wall) || !host->clock.steady_ns(&steady) ||
       !host->entropy.fill(context.timestamp.source,sizeof context.timestamp.source))return false;
    context.timestamp.seconds=fixed>=0?0:(int64_t)(steady/1000000000ull);
    context.offset=(fixed>=0?fixed:wall)-context.timestamp.seconds;
    initialized=true;return true;
}
bool compat_clock_now(int64_t *out) {
    if(!out)return false;
    const HostBackend *host=host_backend();host->sync.lock(HOST_LOCK_CLOCK);
    bool okay=initialize();
    if(okay){if(fixed>=0)*out=fixed;else okay=host->clock.wall_seconds(out);}
    host->sync.unlock(HOST_LOCK_CLOCK);return okay;
}
bool compat_clock_context(SystemClockContext *out) {
    if(!out)return false;
    const HostBackend *host=host_backend();host->sync.lock(HOST_LOCK_CLOCK);
    bool okay=initialize();if(okay)*out=context;
    host->sync.unlock(HOST_LOCK_CLOCK);return okay;
}
bool compat_clock_steady(SteadyClockTimePoint *out) {
    if(!out)return false;
    const HostBackend *host=host_backend();host->sync.lock(HOST_LOCK_CLOCK);
    uint64_t steady;
    bool okay=initialize() && host->clock.steady_ns(&steady);
    if(okay){*out=context.timestamp;out->seconds=fixed>=0?0:(int64_t)(steady/1000000000ull);}
    host->sync.unlock(HOST_LOCK_CLOCK);return okay;
}
bool compat_clock_calendar(int64_t seconds,CalendarTime *calendar,CalendarAdditionalInfo *info) {
    HostCalendar local;
    if(!host_backend()->clock.calendar(seconds,&local) || local.year<INT16_MIN || local.year>INT16_MAX)return false;
    if(calendar)*calendar=(CalendarTime){(int16_t)local.year,(int8_t)local.month,(int8_t)local.day,
        (int8_t)local.hour,(int8_t)local.minute,(int8_t)local.second,0};
    if(info){
        memset(info,0,sizeof *info);info->wday=(uint32_t)local.weekday;info->yday=(uint32_t)local.yearday;
        info->dst=local.daylight_saving;info->offset=local.utc_offset_seconds;
        size_t length=strlen(local.zone);if(length>=sizeof info->tzname)length=sizeof info->tzname-1;
        memcpy(info->tzname,local.zone,length);
    }
    return true;
}
