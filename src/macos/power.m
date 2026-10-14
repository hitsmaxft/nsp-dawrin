#import <Foundation/Foundation.h>
#include <pthread.h>
#include <errno.h>
#include "power.h"
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static id activity;
int native_power_boost(int enabled) {
    if(enabled!=0 && enabled!=1)return EINVAL;
    pthread_mutex_lock(&lock);
    if(enabled && !activity)activity=[NSProcessInfo.processInfo beginActivityWithOptions:NSActivityUserInitiated reason:@"Loading application content"];
    if(!enabled && activity){[NSProcessInfo.processInfo endActivity:activity];activity=nil;}
    int error=enabled && !activity?EIO:0;
    pthread_mutex_unlock(&lock);return error;
}
int native_power_boost_enabled(void) {
    pthread_mutex_lock(&lock);int enabled=activity!=nil;pthread_mutex_unlock(&lock);return enabled;
}
