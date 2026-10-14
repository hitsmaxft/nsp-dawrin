// Persist logical save allocation separately from transactional game save files.
#import <Foundation/Foundation.h>
#include <sys/statvfs.h>
#include <errno.h>
#include <pthread.h>
#include "content.h"
#include "storage.h"

static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static NSString *save_path(void) {const char *p=getenv("DM_SAVE");return p&&*p?@(p):nil;}
int native_storage_space(const char *path,int64_t *free_bytes,int64_t *total_bytes) {
    if(!path || !free_bytes || !total_bytes)return EINVAL;
    struct statvfs st;if(statvfs(path,&st))return errno;
    if(!st.f_frsize || st.f_blocks>INT64_MAX/st.f_frsize)return EOVERFLOW;
    *free_bytes=(int64_t)st.f_bavail*st.f_frsize;*total_bytes=(int64_t)st.f_blocks*st.f_frsize;return 0;
}
static NSString *quota_path(NSString *path) {return [path stringByAppendingString:@".quota.json"];}
static int read_sizes(NSString *path,int64_t *data,int64_t *journal) {
    if(!path || !data || !journal)return EINVAL;
    NSData *bytes=[NSData dataWithContentsOfFile:quota_path(path)];
    if(bytes){
        NSDictionary *row=[NSJSONSerialization JSONObjectWithData:bytes options:0 error:nil];
        if(![row isKindOfClass:NSDictionary.class] || ![row[@"data"] isKindOfClass:NSNumber.class] ||
           ![row[@"journal"] isKindOfClass:NSNumber.class])return EINVAL;
        *data=[row[@"data"] longLongValue];*journal=[row[@"journal"] longLongValue];
        return *data>=0 && *journal>=0 && *journal<=INT64_MAX-*data?0:EINVAL;
    }
    return native_content_save_sizes(data,journal)?0:ENOENT;
}
static int write_sizes(NSString *path,int64_t data,int64_t journal) {
    NSError *error=nil;NSData *bytes=[NSJSONSerialization dataWithJSONObject:@{@"data":@(data),@"journal":@(journal)} options:0 error:&error];
    if(!bytes || ![bytes writeToFile:quota_path(path) options:NSDataWritingAtomic error:&error])return EIO;
    if(![NSFileManager.defaultManager setAttributes:@{NSFilePosixPermissions:@0600} ofItemAtPath:quota_path(path) error:&error])return EIO;
    return 0;
}
int native_save_sizes(int64_t *data,int64_t *journal) {
    @autoreleasepool {pthread_mutex_lock(&mutex);int error=read_sizes(save_path(),data,journal);pthread_mutex_unlock(&mutex);return error;}
}
int native_save_ensure(void) {
    @autoreleasepool {
        pthread_mutex_lock(&mutex);NSString *path=save_path();int64_t data,journal;int error=read_sizes(path,&data,&journal);
        if(!error){
            NSError *e=nil;
            if(![NSFileManager.defaultManager createDirectoryAtPath:path withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:&e])error=EIO;
            if(!error && ![NSFileManager.defaultManager fileExistsAtPath:quota_path(path)])error=write_sizes(path,data,journal);
        }
        pthread_mutex_unlock(&mutex);return error;
    }
}
int native_save_extend(int64_t data,int64_t journal) {
    if(data<0 || journal<0 || journal>INT64_MAX-data)return EINVAL;
    @autoreleasepool {
        pthread_mutex_lock(&mutex);NSString *path=save_path();int64_t old_data,old_journal,available,total;
        int error=read_sizes(path,&old_data,&old_journal);
        if(!error && (data<old_data || journal<old_journal))error=EINVAL;
        if(!error)error=native_storage_space(path.fileSystemRepresentation,&available,&total);
        if(!error && data-old_data+journal-old_journal>available)error=ENOSPC;
        if(!error)error=write_sizes(path,data,journal);
        pthread_mutex_unlock(&mutex);return error;
    }
}
