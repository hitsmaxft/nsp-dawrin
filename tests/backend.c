#include "backend.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    const HostBackend *host=host_backend();
    assert(host && host->abi==HOST_BACKEND_ABI && host->name);
    int64_t wall;uint64_t first,second;
    assert(host->clock.wall_seconds(&wall) && wall>0);
    assert(host->clock.steady_ns(&first) && host->clock.steady_ns(&second) && second>=first);
    HostCalendar calendar;
    assert(host->clock.calendar(1704067200,&calendar));
    assert(calendar.year>=2023 && calendar.year<=2024 && calendar.month>=1 && calendar.month<=12);
    assert(calendar.zone[sizeof calendar.zone-1]==0);
    assert(!host->clock.wall_seconds(NULL) && !host->clock.steady_ns(NULL));
    assert(!host->clock.calendar(0,NULL));
    unsigned char random[512]={0},zero[512]={0};
    assert(host->entropy.fill(random,sizeof random));
    assert(memcmp(random,zero,sizeof random));
    assert(!host->entropy.fill(NULL,1));
    char source[]="backend",destination[8]={0},copy[8]={0};
    assert(host->memory.write(destination,source,sizeof source));
    assert(host->memory.read(copy,destination,sizeof copy) && !memcmp(copy,source,sizeof copy));
    assert(!host->memory.write((void *)1,source,sizeof source));
    assert(!host->memory.read(copy,(void *)1,sizeof copy));
    assert(host->memory.write(NULL,NULL,0) && host->memory.read(NULL,NULL,0));
    for(int i=0;i<HOST_LOCK_COUNT;i++){host->sync.lock((HostLock)i);host->sync.unlock((HostLock)i);}
    printf("PASS: %s backend clock, calendar, entropy, memory copies and locks\n",host->name);
}
