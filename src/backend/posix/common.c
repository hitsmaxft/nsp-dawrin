#define _DEFAULT_SOURCE
#include "common.h"
#include <errno.h>
#include <sys/random.h>
#include <stdlib.h>
#include <pthread.h>
#include <string.h>
#include <stdio.h>

#include <time.h>
#include <unistd.h>

static pthread_mutex_t locks[HOST_LOCK_COUNT]={PTHREAD_MUTEX_INITIALIZER,PTHREAD_MUTEX_INITIALIZER};
void host_posix_lock(HostLock lock) { pthread_mutex_lock(&locks[lock]); }
void host_posix_unlock(HostLock lock) { pthread_mutex_unlock(&locks[lock]); }
bool host_posix_wall(int64_t *out) {
    struct timespec value;
    if(!out || clock_gettime(CLOCK_REALTIME,&value))return false;
    *out=(int64_t)value.tv_sec;return true;
}
bool host_posix_steady(uint64_t *out) {
    struct timespec value;
    if(!out || clock_gettime(CLOCK_MONOTONIC,&value))return false;
    *out=(uint64_t)value.tv_sec*1000000000ull+(uint64_t)value.tv_nsec;return true;
}
bool host_posix_calendar(int64_t seconds,HostCalendar *out) {
    time_t value=(time_t)seconds;struct tm local;
    if(!out || (int64_t)value!=seconds || !localtime_r(&value,&local))return false;
    *out=(HostCalendar){.year=local.tm_year+1900,.month=local.tm_mon+1,.day=local.tm_mday,
        .hour=local.tm_hour,.minute=local.tm_min,.second=local.tm_sec,.weekday=local.tm_wday,
        .yearday=local.tm_yday,.utc_offset_seconds=(int)local.tm_gmtoff,.daylight_saving=local.tm_isdst>0};
    if(local.tm_zone)snprintf(out->zone,sizeof out->zone,"%s",local.tm_zone);
    return true;
}
bool host_posix_random(void *out,size_t size) {
    if(size && !out)return false;
    unsigned char *p=out;
    while(size){
        size_t count=size>256?256:size;
        if(getentropy(p,count)){if(errno==EINTR)continue;return false;}
        p+=count;size-=count;
    }
    return true;
}
