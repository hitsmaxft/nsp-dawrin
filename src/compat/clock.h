#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "ipc.h"

/* Guest ABI types: host backends never include this header. */
typedef struct { int16_t year; int8_t month,day,hour,minute,second,pad; } CalendarTime;
typedef struct { uint32_t wday,yday;char tzname[8];uint32_t dst;int32_t offset; } CalendarAdditionalInfo;
typedef struct { int64_t seconds;uint8_t source[16]; } SteadyClockTimePoint;
typedef struct { int64_t offset;SteadyClockTimePoint timestamp; } SystemClockContext;
bool compat_clock_now(int64_t *out);
bool compat_clock_context(SystemClockContext *out);
bool compat_clock_steady(SteadyClockTimePoint *out);
bool compat_clock_calendar(int64_t seconds,CalendarTime *calendar,CalendarAdditionalInfo *info);
