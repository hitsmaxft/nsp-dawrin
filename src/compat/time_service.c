#include "clock.h"
#include "services.h"
#include <string.h>

#define UNSUPPORTED 0x2a2u
#define BAD_REQUEST 0xf001u
static uint32_t system_clock(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
    (void)input;(void)size;(void)output;
    if(command==0){
        int64_t now;if(!compat_clock_now(&now))return UNSUPPORTED;
        memcpy(reply->data,&now,sizeof now);reply->size=sizeof now;return 0;
    }
    if(command==2){
        SystemClockContext context;if(!compat_clock_context(&context))return UNSUPPORTED;
        memcpy(reply->data,&context,sizeof context);reply->size=sizeof context;return 0;
    }
    return UNSUPPORTED;
}
static uint32_t steady_clock(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
    (void)input;(void)size;(void)output;
    if(command!=0)return UNSUPPORTED;
    SteadyClockTimePoint point;if(!compat_clock_steady(&point))return UNSUPPORTED;
    memcpy(reply->data,&point,sizeof point);reply->size=sizeof point;return 0;
}
static uint32_t time_zone(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
    (void)output;
    /* Explicit guest rules need a separate decoder; never treat them as UTC. */
    if(command!=101)return UNSUPPORTED;
    if(size<sizeof(int64_t))return BAD_REQUEST;
    int64_t seconds;memcpy(&seconds,input,sizeof seconds);
    struct {CalendarTime calendar;CalendarAdditionalInfo info;} result;
    if(!compat_clock_calendar(seconds,&result.calendar,&result.info))return BAD_REQUEST;
    memcpy(reply->data,&result,sizeof result);reply->size=sizeof result;return 0;
}
uint32_t compat_time_service(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
    (void)input;(void)size;(void)output;
    switch(command){
        case 0:case 4:reply->object=system_clock;return 0;
        case 2:reply->object=steady_clock;return 0;
        case 3:reply->object=time_zone;return 0;
        /* Network calibration and shared-memory clocks are not supplied. */
        default:return UNSUPPORTED;
    }
}
