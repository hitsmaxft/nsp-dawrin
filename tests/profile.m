#import <Foundation/Foundation.h>
#import <ImageIO/ImageIO.h>
#include <assert.h>
#include "../src/macos/profile.h"

int main(void) {
    @autoreleasepool {
        size_t size = nsp_profile_image_size(), written = 999;
        assert(size > 100 && size < 0x20000);
        unsigned char *bytes = malloc(size);
        memset(bytes, 0xA5, size);
        assert(!nsp_profile_image_copy(bytes, size - 1, &written));
        assert(written == 0);
        for (size_t i = 0; i < size; i++) assert(bytes[i] == 0xA5);
        assert(!nsp_profile_image_copy(NULL, size, &written));
        assert(nsp_profile_image_copy(bytes, size, &written) && written == size);
        NSData *data = [NSData dataWithBytes:bytes length:size];
        CGImageSourceRef decoder = CGImageSourceCreateWithData((__bridge CFDataRef)data, NULL);
        assert(decoder && CFEqual(CGImageSourceGetType(decoder), CFSTR("public.jpeg")));
        CGImageRef image = CGImageSourceCreateImageAtIndex(decoder, 0, NULL);
        assert(image && CGImageGetWidth(image) == 256 && CGImageGetHeight(image) == 256);
        CGImageRelease(image); CFRelease(decoder); free(bytes);
        puts("PASS: generated JPEG decoding and bounded profile image copies");
    }
}
