#pragma once
#include "../backend.h"
bool host_posix_wall(int64_t *out);
bool host_posix_steady(uint64_t *out);
bool host_posix_calendar(int64_t seconds,HostCalendar *out);
bool host_posix_random(void *out,size_t size);
void host_posix_lock(HostLock lock);
void host_posix_unlock(HostLock lock);
#define HOST_POSIX_CLOCK {host_posix_wall,host_posix_steady,host_posix_calendar}
#define HOST_POSIX_ENTROPY {host_posix_random}
#define HOST_POSIX_SYNC {host_posix_lock,host_posix_unlock}
