#include "clock.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void request(uint32_t *b,unsigned command,unsigned object) {
    memset(b,0,256);b[0]=4;b[1]=12+(object?4:0);
    unsigned p=4;if(object){b[4]=1|(24u<<16);b[5]=object;p=8;}
    b[p]=0x49434653;b[p+2]=command;
}
static uint32_t child(uint32_t root,unsigned command) {
    uint32_t b[64];request(b,command,0);
    assert(!native_ipc_transact(root,b,sizeof b) && !b[6] && b[3]);return b[3];
}
int main(void) {
    SystemClockContext context;SteadyClockTimePoint steady;int64_t now;
    assert(compat_clock_context(&context) && compat_clock_steady(&steady) && compat_clock_now(&now));
    assert(!memcmp(context.timestamp.source,steady.source,16));
    assert(llabs(now-context.offset-steady.seconds)<=1);
    assert(!compat_clock_now(NULL) && !compat_clock_context(NULL) && !compat_clock_steady(NULL));
    if(getenv("DM_FIXED_TIME"))assert(now==1704067200 && steady.seconds==0);
    const char *names[]={"time:u","time:a","time:s"};
    for(unsigned i=0;i<3;i++){
        uint32_t root,b[64];assert(!native_ipc_connect(names[i],&root));
        uint32_t wall=child(root,0),local=child(root,4),monotonic=child(root,2),zone=child(root,3);
        request(b,2,0);assert(!native_ipc_transact(wall,b,sizeof b) && !b[6]);
        assert(!memcmp(b+8,&context,sizeof context));
        request(b,0,0);assert(!native_ipc_transact(local,b,sizeof b) && !b[6]);
        int64_t ipc_now;memcpy(&ipc_now,b+8,8);assert(llabs(ipc_now-now)<=2);
        request(b,0,0);assert(!native_ipc_transact(monotonic,b,sizeof b) && !b[6]);
        SteadyClockTimePoint ipc_steady;memcpy(&ipc_steady,b+8,sizeof ipc_steady);
        assert(ipc_steady.seconds>=steady.seconds && !memcmp(ipc_steady.source,steady.source,16));
        request(b,101,0);int64_t date=1704067200;memcpy(b+8,&date,8);
        assert(!native_ipc_transact(zone,b,sizeof b) && !b[6]);
        CalendarTime calendar;CalendarAdditionalInfo info;
        memcpy(&calendar,b+8,sizeof calendar);memcpy(&info,b+10,sizeof info);
        assert(calendar.year==2024 && calendar.month==1 && calendar.day==1 && !calendar.hour);
        assert(info.wday==1 && info.yday==0 && !info.offset);
        request(b,101,0);b[1]=6;assert(!native_ipc_transact(zone,b,sizeof b) && b[6]);
        request(b,100,0);assert(!native_ipc_transact(zone,b,sizeof b) && b[6]);
        request(b,20,0);assert(!native_ipc_transact(root,b,sizeof b) && b[6]);
        assert(!native_ipc_close(root));
        assert(!native_ipc_close(wall) && !native_ipc_close(local));
        assert(!native_ipc_close(monotonic) && !native_ipc_close(zone));
    }
    uint32_t root,b[64];assert(!native_ipc_connect("time:u",&root));
    request(b,0,0);b[0]=5;assert(!native_ipc_transact(root,b,sizeof b));
    request(b,0,1);assert(!native_ipc_transact(root,b,sizeof b) && b[4]==1 && !b[10]);
    uint32_t clock=b[12];request(b,2,clock);
    assert(!native_ipc_transact(root,b,sizeof b) && !b[10]);
    assert(!memcmp(b+12,&context,sizeof context));
    assert(!native_ipc_close(root));
    puts("PASS: SDK-independent clocks, IPC objects, calendar conversion, ABI and unsupported requests");
}
