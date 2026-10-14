#pragma once
#include <stdint.h>
void native_settings_init(void);
int native_settings_handheld(void);
#ifdef __OBJC__
#import <Foundation/Foundation.h>
extern NSString *const NativeSettingsChanged;
NSDictionary *native_settings_snapshot(void);
BOOL native_settings_update(NSDictionary *patch, NSError **error);
NSArray<NSString *> *native_binding_names(void);
uint64_t native_settings_key_mask(unsigned short key);
uint64_t native_key_modifier(unsigned short key);
NSString *native_key_label(unsigned short key);
#endif
