// Warm generated shader sources through the same API used by native replay.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdatomic.h>
int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 2) { fprintf(stderr,"usage: warm-metal SHADER_DIRECTORY\n"); return 2; }
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) return 2;
        NSString *root = @(argv[1]);
        NSArray *files = [[NSFileManager.defaultManager contentsOfDirectoryAtPath:root error:nil]
                         filteredArrayUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(NSString *name, NSDictionary *bindings) {
            return [name hasSuffix:@"_b.metal"];
        }]];
        if (!files.count) { fprintf(stderr,"No shader sources found\n"); return 2; }
        NSMutableArray *failures = [NSMutableArray array];
        NSMutableSet *seen = [NSMutableSet set];
        NSObject *lock = [NSObject new];
        __block _Atomic unsigned completed = 0, unique = 0;
        double start = CFAbsoluteTimeGetCurrent();
        dispatch_queue_t queue = dispatch_get_global_queue(QOS_CLASS_UTILITY,0);
        dispatch_apply(4,queue,^(size_t worker) {
            for (NSUInteger index=worker;index<files.count;index+=4) {
                @autoreleasepool {
                    NSError *error=nil;
                    NSString *path=[root stringByAppendingPathComponent:files[index]];
                    NSString *source=[NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&error];
                    BOOL duplicate=NO;
                    @synchronized(lock) {
                        duplicate=source && [seen containsObject:source];
                        if (source && !duplicate) [seen addObject:source];
                    }
                    if (!duplicate) {
                        atomic_fetch_add(&unique,1);
                        id<MTLLibrary> library=source ? [device newLibraryWithSource:source options:nil error:&error] : nil;
                        if (!library || !library.functionNames.count) {
                            @synchronized(lock) { [failures addObject:@{@"file":files[index],@"error":error.localizedDescription ?: @"Missing entry point"}]; }
                        }
                    }
                    unsigned count=atomic_fetch_add(&completed,1)+1;
                    if (!(count%500)) fprintf(stderr,"Metal warm-up: %u/%lu\n",count,(unsigned long)files.count);
                }
            }
        });
        NSDictionary *report=@{@"sources":@(files.count),@"unique":@(atomic_load(&unique)),@"failures":failures,
                               @"seconds":@(CFAbsoluteTimeGetCurrent()-start)};
        NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];
        [data writeToFile:[root stringByAppendingPathComponent:@"metal-validation.json"] atomically:YES];
        printf("{\"sources\":%lu,\"unique\":%u,\"failures\":%lu,\"seconds\":%.3f}\n",(unsigned long)files.count,atomic_load(&unique),(unsigned long)failures.count,CFAbsoluteTimeGetCurrent()-start);
        return failures.count ? 1 : 0;
    }
}
