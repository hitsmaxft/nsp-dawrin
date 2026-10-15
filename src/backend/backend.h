#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define HOST_BACKEND_ABI 1u
/* Host data, independent of guest layouts and platform SDK types. */
typedef struct {
    int year, month, day, hour, minute, second, weekday, yearday;
    int utc_offset_seconds;
    bool daylight_saving;
    char zone[32];
} HostCalendar;
typedef enum { HOST_LOCK_IPC, HOST_LOCK_CLOCK, HOST_LOCK_COUNT } HostLock;
typedef struct {
    bool (*wall_seconds)(int64_t *out);
    bool (*steady_ns)(uint64_t *out);
    bool (*calendar)(int64_t seconds, HostCalendar *out);
} HostClockOps;
typedef struct { bool (*fill)(void *out, size_t size); } HostEntropyOps;
typedef struct {
    /* Same-process copies: invalid addresses return false without a host fault.
     * Failure may have copied a prefix; writes are not transactions. */
    bool (*read)(void *destination, const void *guest, size_t size);
    bool (*write)(void *guest, const void *source, size_t size);
} HostMemoryOps;
typedef struct {
    /* Locks are non-recursive. Acquire IPC before CLOCK when nesting. */
    void (*lock)(HostLock lock);
    void (*unlock)(HostLock lock);
} HostSyncOps;
typedef struct {
    uint32_t abi;
    const char *name;
    HostClockOps clock;
    HostEntropyOps entropy;
    HostMemoryOps memory;
    HostSyncOps sync;
} HostBackend;
/* Exactly one platform implementation is selected at build time. */
const HostBackend *host_backend(void);
