// Read base, patch and add-on resources through immutable virtual ranges.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonCryptor.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <stdatomic.h>
#include "content.h"

typedef struct {int fd;uint64_t offset,total;unsigned char key[16],prefix[8];int encrypted;} source_t;
typedef struct {uint64_t start,size,offset;size_t source;} span_t;
typedef struct {uint64_t offset,size;size_t mount;int valid;} handle_t;
static source_t *sources;
static size_t source_count;
static NSArray *mounts;
static NSDictionary *save_sizes;
static span_t **spans;
static size_t *span_counts;
static pthread_once_t once=PTHREAD_ONCE_INIT;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static handle_t handles[4096];
_Atomic uint64_t native_package_reads,native_package_bytes;

static void fail(const char *message) {fprintf(stderr,"Package reader: %s\n",message);exit(1);}
static uint64_t number(id value) {
    if (![value isKindOfClass:NSNumber.class] || [value longLongValue]<0) fail("Invalid numeric field");
    return [value unsignedLongLongValue];
}
static NSString *string(id value) {
    if (![value isKindOfClass:NSString.class] || ![value length]) fail("Invalid string field");
    return value;
}
static void initialize(void) {
    const char *path=getenv("DM_PACKAGE_INDEX");if (!path || !*path)return;
    @autoreleasepool {
        NSData *data=[NSData dataWithContentsOfFile:@(path)];
        NSDictionary *manifest=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
        if (![manifest isKindOfClass:NSDictionary.class])fail("Invalid resource index");
        NSArray *rows=nil;
        if ([manifest[@"version"] intValue]==1) {
            rows=@[manifest];
            uint64_t total=number(manifest[@"package_bytes"]),offset=number(manifest[@"nca_offset"]);
            if(offset>total)fail("Invalid archive offset");
            mounts=@[@{@"root":string(manifest[@"root"]),@"files":manifest[@"files"],@"kind":@"base",
                @"segments":@[@{@"start":@0,@"size":@(total-offset),@"source":@0,@"offset":@0}]}];
        } else if ([manifest[@"version"] intValue]==2) {
            rows=manifest[@"sources"];mounts=manifest[@"mounts"];
            if ([manifest[@"save_sizes"] isKindOfClass:NSDictionary.class])save_sizes=manifest[@"save_sizes"];
        } else fail("Unsupported resource index version");
        if (![rows isKindOfClass:NSArray.class] || !rows.count || rows.count>65536 ||
            ![mounts isKindOfClass:NSArray.class] || !mounts.count || mounts.count>4096)fail("Invalid content inventory");
        source_count=rows.count;sources=calloc(source_count,sizeof(*sources));
        spans=calloc(mounts.count,sizeof(*spans));span_counts=calloc(mounts.count,sizeof(*span_counts));
        if (!sources || !spans || !span_counts)fail("Content allocation failed");
        NSMutableDictionary *openFiles=[NSMutableDictionary new];
        for (NSUInteger i=0;i<rows.count;i++) {
            NSDictionary *row=rows[i];source_t *s=&sources[i];
            NSString *package=string(row[@"package"]);NSNumber *existing=openFiles[package];
            s->fd=existing?existing.intValue:open(package.fileSystemRepresentation,O_RDONLY|O_CLOEXEC);
            if(s->fd>=0 && !existing)openFiles[package]=@(s->fd);
            s->total=number(row[@"package_bytes"]);s->offset=number(row[@"nca_offset"]);
            struct stat st;
            if(s->fd<0 || fstat(s->fd,&st) || st.st_size!=s->total || s->offset>s->total)fail("Original package is unavailable or changed");
            s->encrypted=[row[@"encrypted"] boolValue];
            NSData *secret=[NSData dataWithContentsOfFile:string(row[@"key_file"])];
            if(secret.length!=16)fail("Invalid local key cache");memcpy(s->key,secret.bytes,16);
            NSString *hex=string(row[@"ctr_prefix"]);
            if(hex.length!=16)fail("Invalid counter prefix");
            NSCharacterSet *nonHex=[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdefABCDEF"] invertedSet];
            if([hex rangeOfCharacterFromSet:nonHex].location!=NSNotFound)fail("Invalid counter prefix");
            for(unsigned j=0;j<8;j++){unsigned v;sscanf([[hex substringWithRange:NSMakeRange(j*2,2)] UTF8String],"%2x",&v);s->prefix[j]=v;}
        }
        NSMutableSet *roots=[NSMutableSet new],*indexes=[NSMutableSet new];
        for(NSUInteger i=0;i<mounts.count;i++) {
            NSDictionary *mount=mounts[i];NSString *root=[string(mount[@"root"]) stringByStandardizingPath];
            if(![root isAbsolutePath] || [roots containsObject:root])fail("Invalid mount root");[roots addObject:root];
            if(![mount[@"files"] isKindOfClass:NSDictionary.class])fail("Invalid file index");
            if([mount[@"kind"] isEqual:@"dlc"]){uint64_t index=number(mount[@"index"]);if(index>65535 || [indexes containsObject:@(index)])fail("Invalid add-on index");[indexes addObject:@(index)];}
            NSArray *segments=mount[@"segments"];
            if(![segments isKindOfClass:NSArray.class] || !segments.count || segments.count>1000000)fail("Invalid range table");
            span_counts[i]=segments.count;spans[i]=calloc(segments.count,sizeof(span_t));if(!spans[i])fail("Range allocation failed");
            uint64_t cursor=0;
            for(NSUInteger j=0;j<segments.count;j++) {
                NSDictionary *row=segments[j];span_t *s=&spans[i][j];
                s->start=number(row[@"start"]);s->size=number(row[@"size"]);s->source=number(row[@"source"]);s->offset=number(row[@"offset"]);
                if(s->start!=cursor || !s->size || s->size>INT64_MAX-cursor || s->source>=source_count)fail("Invalid virtual range");
                source_t *source=&sources[s->source];uint64_t available=source->total-source->offset;
                if(s->offset>available || s->size>available-s->offset)fail("Range extends beyond package");
                cursor+=s->size;
            }
        }
    }
}

int native_content_save_sizes(int64_t *data,int64_t *journal) {
    pthread_once(&once,initialize);if(!save_sizes || !data || !journal)return 0;
    *data=number(save_sizes[@"data"]);*journal=number(save_sizes[@"journal"]);return 1;
}
int native_content_count(void) {
    pthread_once(&once,initialize);int count=0;
    for(NSDictionary *mount in mounts)if([mount[@"kind"] isEqual:@"dlc"])count++;
    return count;
}
int native_content_list(int *out,int capacity,int offset) {
    pthread_once(&once,initialize);if(capacity<0 || offset<0 || (capacity && !out))return -1;
    int seen=0,count=0;
    for(NSDictionary *mount in mounts)if([mount[@"kind"] isEqual:@"dlc"]){if(seen++>=offset && count<capacity)out[count++]=[mount[@"index"] intValue];}
    return count;
}
int native_content_root(int index,char *out,size_t size) {
    pthread_once(&once,initialize);if(index<0 || !out || !size)return 0;
    for(NSDictionary *mount in mounts)if([mount[@"kind"] isEqual:@"dlc"] && [mount[@"index"] intValue]==index)
        return strlcpy(out,[mount[@"root"] fileSystemRepresentation],size)<size;
    return 0;
}
void dm_package_forget_fd(int fd) {
    if(fd<0 || fd>=4096)return;pthread_mutex_lock(&lock);handles[fd].valid=0;pthread_mutex_unlock(&lock);
}
void dm_package_note_fd(int fd,const char *path) {
    pthread_once(&once,initialize);dm_package_forget_fd(fd);if(fd<0 || fd>=4096)return;
    @autoreleasepool {
        NSString *host=[@(path) stringByStandardizingPath];
        for(NSUInteger i=0;i<mounts.count;i++) {
            NSDictionary *mount=mounts[i];NSString *base=[[mount[@"root"] stringByStandardizingPath] stringByAppendingString:@"/"];
            if(![host hasPrefix:base])continue;
            NSArray *entry=mount[@"files"][[host substringFromIndex:base.length]];
            if(![entry isKindOfClass:NSArray.class] || entry.count!=2)fail("Resource is absent from index");
            uint64_t offset=number(entry[0]),size=number(entry[1]);span_t last=spans[i][span_counts[i]-1];uint64_t total=last.start+last.size;
            if(offset>total || size>total-offset)fail("Resource exceeds virtual section");
            pthread_mutex_lock(&lock);handles[fd]=(handle_t){offset,size,i,1};pthread_mutex_unlock(&lock);return;
        }
    }
}
static int read_span(span_t span,uint64_t relative,void *buffer,size_t length) {
    source_t *s=&sources[span.source];uint64_t position=span.offset+relative,aligned=position&~15ull;
    size_t skip=position-aligned,count=(skip+length+15)&~(size_t)15;
    if(!s->encrypted){aligned=position;skip=0;count=length;}
    if(aligned>s->total-s->offset || count>s->total-s->offset-aligned){errno=EIO;return -1;}
    unsigned char *data=malloc(count);if(!data){errno=ENOMEM;return -1;}
    size_t got=0;
    while(got<count){ssize_t n=pread(s->fd,data+got,count-got,s->offset+aligned+got);if(n<0 && errno==EINTR)continue;if(n<=0){free(data);if(!n)errno=EIO;return -1;}got+=n;}
    if(s->encrypted){
        unsigned char iv[16];memcpy(iv,s->prefix,8);uint64_t counter=aligned/16;
        for(unsigned i=0;i<8;i++)iv[15-i]=counter>>(8*i);
        CCCryptorRef cryptor=NULL;size_t written=0;
        CCCryptorStatus result=CCCryptorCreateWithMode(kCCDecrypt,kCCModeCTR,kCCAlgorithmAES,ccNoPadding,iv,s->key,16,NULL,0,0,kCCModeOptionCTR_BE,&cryptor);
        if(result==kCCSuccess)result=CCCryptorUpdate(cryptor,data,count,data,count,&written);
        if(cryptor)CCCryptorRelease(cryptor);
        if(result!=kCCSuccess || written!=count){free(data);errno=EIO;return -1;}
    }
    memcpy(buffer,data+skip,length);free(data);return 0;
}
// -2 denotes an ordinary host file; indexed reads can cross patch/crypto boundaries.
ssize_t dm_package_pread(int fd,void *buffer,size_t length,off_t offset) {
    if(fd<0 || fd>=4096)return -2;
    pthread_mutex_lock(&lock);handle_t entry=handles[fd];pthread_mutex_unlock(&lock);
    if(!entry.valid)return -2;if(offset<0){errno=EINVAL;return -1;}
    if((uint64_t)offset>=entry.size || !length)return 0;
    if(length>entry.size-offset)length=entry.size-offset;
    if(length>(size_t)SSIZE_MAX-32){errno=EOVERFLOW;return -1;}
    uint64_t position=entry.offset+offset;size_t left=length;unsigned char *target=buffer;
    while(left){
        size_t lo=0,hi=span_counts[entry.mount];span_t *table=spans[entry.mount];
        while(lo+1<hi){size_t mid=(lo+hi)/2;if(table[mid].start<=position)lo=mid;else hi=mid;}
        span_t span=table[lo];uint64_t relative=position-span.start;
        if(relative>=span.size){errno=EIO;return -1;}
        size_t count=MIN(left,span.size-relative);count=MIN(count,(size_t)(4*1024*1024));
        if(read_span(span,relative,target,count))return -1;
        position+=count;target+=count;left-=count;
    }
    atomic_fetch_add(&native_package_reads,1);atomic_fetch_add(&native_package_bytes,length);return length;
}
