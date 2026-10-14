#import "settings.h"
#import <Cocoa/Cocoa.h>
#include <stdatomic.h>

NSString *const NativeSettingsChanged = @"NativeSettingsChanged";
static NSDictionary *settings;
static NSURL *settings_url;
static int active_handheld;

NSArray<NSString *> *native_binding_names(void) {
    return @[@"A", @"B", @"X", @"Y", @"Left stick click", @"Right stick click",
             @"L", @"R", @"ZL", @"ZR", @"Plus", @"Minus", @"D-pad left", @"D-pad up",
             @"D-pad right", @"D-pad down", @"Left stick left", @"Left stick up",
             @"Left stick right", @"Left stick down", @"Right stick left", @"Right stick up",
             @"Right stick right", @"Right stick down"];
}
static NSDictionary *defaults(void) {
    return @{@"mode":@"handheld", @"resolution":@0, @"fullscreen":@NO, @"controller":@"auto",
             @"bindings":@{@"0":@[@6,@49],@"1":@[@7,@53],@"2":@[@0],@"3":@[@1],
                           @"10":@[@36],@"12":@[@123],@"13":@[@126],@"14":@[@124],@"15":@[@125]}};
}
static BOOL integer(id value, NSInteger minimum, NSInteger maximum) {
    return [value isKindOfClass:NSNumber.class] && [value doubleValue] == [value integerValue]
        && [value integerValue] >= minimum && [value integerValue] <= maximum;
}
static BOOL valid(NSDictionary *data) {
    if (![data isKindOfClass:NSDictionary.class]) return NO;
    NSSet *allowed=[NSSet setWithArray:defaults().allKeys];
    for (id key in data) if (![allowed containsObject:key]) return NO;
    if (![@[@"handheld",@"console"] containsObject:data[@"mode"]]) return NO;
    if (!integer(data[@"resolution"],0,1080) || ![@[@0,@720,@1080] containsObject:data[@"resolution"]]) return NO;
    if (!integer(data[@"fullscreen"],0,1)) return NO;
    id controller=data[@"controller"];
    if (![@[@"auto",@"none"] containsObject:controller]) {
        if (![controller isKindOfClass:NSDictionary.class] || [controller count]!=2 ||
            ![controller[@"vendor"] isKindOfClass:NSString.class] ||
            ![controller[@"category"] isKindOfClass:NSString.class]) return NO;
    }
    NSDictionary *bindings=data[@"bindings"];
    if (![bindings isKindOfClass:NSDictionary.class]) return NO;
    NSMutableSet *seen=[NSMutableSet set];
    for (id action in bindings) {
        if (![action isKindOfClass:NSString.class] || ![[NSString stringWithFormat:@"%ld",(long)[action integerValue]] isEqual:action] ||
            [action integerValue]<0 || [action integerValue]>=24) return NO;
        id keys=bindings[action];
        if (![keys isKindOfClass:NSArray.class] || [keys count]>4) return NO;
        for (id key in keys) {
            if (!integer(key,0,127) || [seen containsObject:key]) return NO;
            [seen addObject:key];
        }
    }
    return YES;
}
void native_settings_init(void) {
    if (settings) return;
    const char *override=getenv("NSP_SETTINGS_PATH");
    settings_url=override ? [NSURL fileURLWithPath:@(override)] :
        [[NSFileManager.defaultManager URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject
            URLByAppendingPathComponent:@"nsp-dawrin/settings.json"];
    NSData *data=[NSData dataWithContentsOfURL:settings_url];
    id saved=data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    settings=valid(saved) ? [saved copy] : defaults();
    if (data && !valid(saved)) NSLog(@"Invalid settings; using defaults until new settings are saved");
    const char *mode=getenv("DM_HANDHELD");
    active_handheld=mode ? atoi(mode)!=0 : [settings[@"mode"] isEqual:@"handheld"];
}
int native_settings_handheld(void) { return active_handheld; }
NSDictionary *native_settings_snapshot(void) { native_settings_init(); return settings; }
BOOL native_settings_update(NSDictionary *patch, NSError **error) {
    native_settings_init();
    NSMutableDictionary *next=[settings mutableCopy];
    if (![patch isKindOfClass:NSDictionary.class]) return NO;
    [next addEntriesFromDictionary:patch];
    if (!valid(next)) {
        if (error) *error=[NSError errorWithDomain:@"nsp-dawrin.settings" code:1 userInfo:@{NSLocalizedDescriptionKey:@"Invalid settings or duplicate key binding"}];
        return NO;
    }
    NSURL *parent=[settings_url URLByDeletingLastPathComponent];
    if (![NSFileManager.defaultManager createDirectoryAtURL:parent withIntermediateDirectories:YES attributes:nil error:error]) return NO;
    NSData *data=[NSJSONSerialization dataWithJSONObject:next options:NSJSONWritingPrettyPrinted error:error];
    if (!data || ![data writeToURL:settings_url options:NSDataWritingAtomic error:error]) return NO;
    settings=[next copy];
    [NSNotificationCenter.defaultCenter postNotificationName:NativeSettingsChanged object:nil];
    return YES;
}
uint64_t native_settings_key_mask(unsigned short key) {
    NSDictionary *bindings=native_settings_snapshot()[@"bindings"];
    for (NSString *action in bindings) if ([bindings[action] containsObject:@(key)]) return 1ull<<action.intValue;
    return 0;
}
NSString *native_key_label(unsigned short key) {
    // Physical macOS key positions keep bindings independent of the active input method.
    static NSDictionary *labels;
    if (!labels) labels=@{@0:@"A",@1:@"S",@2:@"D",@3:@"F",@4:@"H",@5:@"G",@6:@"Z",@7:@"X",@8:@"C",@9:@"V",
        @11:@"B",@12:@"Q",@13:@"W",@14:@"E",@15:@"R",@16:@"Y",@17:@"T",@18:@"1",@19:@"2",@20:@"3",@21:@"4",
        @22:@"6",@23:@"5",@24:@"=",@25:@"9",@26:@"7",@27:@"-",@28:@"8",@29:@"0",@30:@"]",@31:@"O",@32:@"U",
        @33:@"[",@34:@"I",@35:@"P",@36:@"Return",@37:@"L",@38:@"J",@39:@"'",@40:@"K",@41:@";",@42:@"\\",
        @43:@",",@44:@"/",@45:@"N",@46:@"M",@47:@".",@48:@"Tab",@49:@"Space",@50:@"`",@51:@"Delete",@53:@"Escape",
        @123:@"Left",@124:@"Right",@125:@"Down",@126:@"Up"};
    return labels[@(key)] ?: [NSString stringWithFormat:@"Key %u",key];
}
