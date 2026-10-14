#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#include "profile.h"

static NSData *profile_image(void) {
    static NSData *image;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
        CGContextRef context = CGBitmapContextCreate(NULL, 256, 256, 8, 0, space,
                                                     (CGBitmapInfo)kCGImageAlphaNoneSkipLast);
        CGColorSpaceRelease(space);
        if (!context) return;
        CGContextSetRGBFillColor(context, 0.17, 0.23, 0.31, 1);
        CGContextFillRect(context, CGRectMake(0, 0, 256, 256));
        CGContextSetRGBFillColor(context, 0.82, 0.87, 0.92, 1);
        CGContextFillEllipseInRect(context, CGRectMake(86, 135, 84, 84));
        CGContextFillEllipseInRect(context, CGRectMake(43, -25, 170, 150));
        CGImageRef bitmap = CGBitmapContextCreateImage(context);
        CGContextRelease(context);
        if (!bitmap) return;
        NSMutableData *data = [NSMutableData data];
        CGImageDestinationRef encoder = CGImageDestinationCreateWithData(
            (__bridge CFMutableDataRef)data, CFSTR("public.jpeg"), 1, NULL);
        if (encoder) {
            CGImageDestinationAddImage(encoder, bitmap, NULL);
            if (CGImageDestinationFinalize(encoder)) image = [data copy];
            CFRelease(encoder);
        }
        CGImageRelease(bitmap);
    });
    return image;
}

size_t nsp_profile_image_size(void) { return profile_image().length; }
bool nsp_profile_image_copy(void *destination, size_t capacity, size_t *written) {
    if (written) *written = 0;
    NSData *image = profile_image();
    if (!destination || !image.length || capacity < image.length) return false;
    memcpy(destination, image.bytes, image.length);
    if (written) *written = image.length;
    return true;
}
