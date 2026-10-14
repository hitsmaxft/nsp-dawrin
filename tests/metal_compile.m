// Compile external generated sources with the same Metal API as the native host.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main(int argc, const char **argv) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device || argc < 2) return 2;
        int failed = 0;
        for (int i = 1; i < argc; ++i) {
            NSError *error = nil;
            NSString *source = [NSString stringWithContentsOfFile:@(argv[i]) encoding:NSUTF8StringEncoding error:&error];
            id<MTLLibrary> library = source ? [device newLibraryWithSource:source options:nil error:&error] : nil;
            if (!library || !library.functionNames.count) {
                fprintf(stderr, "%s: %s\n", argv[i], error.localizedDescription.UTF8String ?: "No entry point");
                failed++;
            }
        }
        printf("{\"compiled\":%d,\"failed\":%d}\n", argc - 1 - failed, failed);
        return failed ? 1 : 0;
    }
}
