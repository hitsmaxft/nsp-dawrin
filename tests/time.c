#include "../src/host/hle_time.c"
#include <assert.h>
#include <unistd.h>

uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }
int main(void) {
    struct { SystemClockContext value; uint64_t guard; } context = {.guard = UINT64_MAX};
    SystemClockContext again;
    SteadyClockTimePoint point, later;
    assert(h_time_Context(&context.value) == RES_OK && context.guard == UINT64_MAX);
    assert(h_time_Steady(&point) == RES_OK);
    int64_t wall;
    assert(h_time_GetCurrentTime(&wall) == RES_OK);
    assert(llabs(wall - context.value.offset - point.seconds) <= 1);
    assert(!memcmp(point.source, context.value.timestamp.source, sizeof point.source));
    usleep(20000);
    assert(h_time_Context(&again) == RES_OK);
    assert(!memcmp(&again, &context.value, sizeof again));
    assert(h_time_Steady(&later) == RES_OK && later.seconds >= point.seconds);
    assert(!memcmp(point.source, later.source, sizeof point.source));
    assert(h_time_Context(NULL) != RES_OK && h_time_Steady(NULL) != RES_OK);
    if (getenv("DM_FIXED_TIME")) assert(point.seconds == 0 && context.value.offset == wall);
    puts("PASS: clock context ABI, wall/steady correlation and stable source identity");
}
