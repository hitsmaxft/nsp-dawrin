#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <time.h>
#include <limits.h>
#include "../backend.h"

static SRWLOCK locks[HOST_LOCK_COUNT]={SRWLOCK_INIT,SRWLOCK_INIT};
static void lock_host(HostLock lock) { AcquireSRWLockExclusive(&locks[lock]); }
static void unlock_host(HostLock lock) { ReleaseSRWLockExclusive(&locks[lock]); }
static bool wall_seconds(int64_t *out) {
    if(!out)return false;
    FILETIME value;GetSystemTimeAsFileTime(&value);
    uint64_t ticks=((uint64_t)value.dwHighDateTime<<32)|value.dwLowDateTime;
    *out=(int64_t)(ticks/10000000ull)-11644473600ll;return true;
}
static bool steady_ns(uint64_t *out) {
    LARGE_INTEGER count,frequency;
    if(!out || !QueryPerformanceFrequency(&frequency) || !QueryPerformanceCounter(&count))return false;
    uint64_t ticks=(uint64_t)count.QuadPart,hz=(uint64_t)frequency.QuadPart;
    *out=(ticks/hz)*1000000000ull+(ticks%hz)*1000000000ull/hz;return true;
}
static bool calendar(int64_t seconds,HostCalendar *out) {
    __time64_t value=seconds;struct tm local;
    if(!out || _localtime64_s(&local,&value))return false;
    struct tm utc=local;
    __time64_t local_as_utc=_mkgmtime64(&utc);
    if(local_as_utc==-1)return false;
    *out=(HostCalendar){.year=local.tm_year+1900,.month=local.tm_mon+1,.day=local.tm_mday,
        .hour=local.tm_hour,.minute=local.tm_min,.second=local.tm_sec,.weekday=local.tm_wday,
        .yearday=local.tm_yday,.utc_offset_seconds=(int)(local_as_utc-seconds),.daylight_saving=local.tm_isdst>0};
    strftime(out->zone,sizeof out->zone,"%Z",&local);return true;
}
static bool random_bytes(void *out,size_t size) {
    if(!size)return true;
    if(!out || size>ULONG_MAX)return false;
    return BCryptGenRandom(NULL,out,(ULONG)size,BCRYPT_USE_SYSTEM_PREFERRED_RNG)==0;
}
static bool read_memory(void *destination,const void *guest,size_t size) {
    if(!size)return true;
    if(!destination || !guest || size>UINT32_MAX)return false;
    SIZE_T copied=0;
    return ReadProcessMemory(GetCurrentProcess(),guest,destination,size,&copied) && copied==size;
}
static bool write_memory(void *guest,const void *source,size_t size) {
    if(!size)return true;
    if(!guest || !source || size>UINT32_MAX)return false;
    SIZE_T copied=0;
    return WriteProcessMemory(GetCurrentProcess(),guest,source,size,&copied) && copied==size;
}
const HostBackend *host_backend(void) {
    static const HostBackend backend={HOST_BACKEND_ABI,"windows",
        {wall_seconds,steady_ns,calendar},{random_bytes},{read_memory,write_memory},{lock_host,unlock_host}};
    return &backend;
}
