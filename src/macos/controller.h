#pragma once
#include <stdint.h>

typedef struct {
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t connected;
} NativePad;

void native_controller_start(void);
void native_controller_focus(int active);
NativePad native_controller_read(void);

#ifdef __OBJC__
#import <Foundation/Foundation.h>
extern NSString *const NativeControllersChanged;
NSArray<NSDictionary *> *native_controller_devices(void);
NSString *native_controller_selection(void);
BOOL native_controller_choose(NSString *identifier, NSError **error);
#endif
