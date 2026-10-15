#import <Foundation/Foundation.h>
#import "settings.h"
#include <assert.h>
#include <stdlib.h>

static void child(NSString *phase) {
    native_settings_init();NSError *error=nil;
    NSDictionary *data=native_settings_snapshot(), *profile=native_settings_profile();
    if ([phase isEqual:@"global"]) {
        assert([profile[@"scope"] isEqual:@"global"]);
        assert(native_settings_update(@{@"mode":@"console",@"resolution":@720,@"controller":@"none",
                                        @"bindings":@{@"0":@[@12]}},&error));
    } else if ([phase isEqual:@"game"]) {
        assert([profile[@"scope"] isEqual:@"game"]);
        assert([profile[@"application_id"] isEqual:@"0123456789abcdef"]);
        assert(![profile[@"override_keys"] count]);
        assert([data[@"resolution"] intValue]==720 && !native_settings_handheld());
        assert(native_settings_update(@{@"resolution":@1080,@"controller":@"auto",
                                        @"bindings":@{@"0":@[@13]}},&error));
        assert(!native_settings_update(@{@"bindings":@{@"0":@[@12],@"1":@[@12]}},&error));
        assert(native_settings_key_mask(13)==1);
    } else if ([phase isEqual:@"other"]) {
        assert([data[@"resolution"] intValue]==720 && native_settings_key_mask(12)==1);
        assert([data[@"controller"] isEqual:@"none"] && ![profile[@"override_keys"] count]);
    } else if ([phase isEqual:@"change-global"]) {
        assert(native_settings_update(@{@"mode":@"handheld",@"fullscreen":@YES},&error));
    } else if ([phase isEqual:@"inherit"]) {
        assert(native_settings_handheld() && [data[@"fullscreen"] boolValue]);
        assert([data[@"resolution"] intValue]==1080 && native_settings_key_mask(13)==1);
        assert([data[@"controller"] isEqual:@"auto"]);
        assert(([profile[@"override_keys"] isEqual:@[@"bindings",@"controller",@"resolution"]]));
        assert(native_settings_select_scope(@"global",&error));
        assert([native_settings_snapshot()[@"resolution"] intValue]==720 && native_settings_key_mask(12)==1);
        assert(!native_settings_reset_game(&error));
        assert(native_settings_update(@{@"resolution":@0,@"mode":@"console"},&error));
        assert(native_settings_handheld()); // The running guest mode never changes with the editing scope.
        assert(native_settings_select_scope(@"game",&error));
        assert(!native_settings_select_scope(@"unknown",&error));
        assert([native_settings_snapshot()[@"resolution"] intValue]==1080);
        assert(native_settings_reset_game(&error));
        assert([native_settings_snapshot()[@"resolution"] intValue]==0 && native_settings_key_mask(12)==1);
    } else if ([phase isEqual:@"reset"]) {
        assert([data[@"resolution"] intValue]==0 && native_settings_key_mask(12)==1);
        assert([data[@"controller"] isEqual:@"none"] && ![profile[@"override_keys"] count]);
        assert(!native_settings_handheld());
    } else if ([phase isEqual:@"invalid-id"]) {
        assert([profile[@"scope"] isEqual:@"global"] && ![profile[@"application_id"] length]);
        assert(!native_settings_select_scope(@"game",&error) && !native_settings_reset_game(&error));
    } else if ([phase isEqual:@"write-failure"]) {
        assert(!native_settings_update(@{@"resolution":@1080},&error));
        assert(error && [native_settings_snapshot() isEqual:data]);
    } else abort();
}

int main(int argc,char **argv) {
    @autoreleasepool {
        if (argc>1) {child(@(argv[1]));return 0;}
        char folder[]="/tmp/nsp-settings-profiles-XXXXXX";assert(mkdtemp(folder));
        NSString *root=@(folder), *file=[root stringByAppendingPathComponent:@"settings.json"];
        void (^run)(NSString *,NSString *)=^(NSString *phase,NSString *identity) {
            NSTask *task=[NSTask new];task.executableURL=[NSURL fileURLWithPath:@(argv[0])];task.arguments=@[phase];
            NSMutableDictionary *env=[NSProcessInfo.processInfo.environment mutableCopy];
            env[@"NSP_SETTINGS_PATH"]=file;env[@"DM_TITLE_ID"]=identity;[env removeObjectForKey:@"DM_HANDHELD"];
            task.environment=env;assert([task launchAndReturnError:nil]);[task waitUntilExit];assert(task.terminationStatus==0);
        };
        run(@"global",@"");run(@"game",@"0123456789ABCDEF");run(@"other",@"1123456789abcdef");
        run(@"change-global",@"");run(@"inherit",@"0123456789abcdef");
        run(@"reset",@"0123456789abcdef");run(@"reset",@"1123456789abcdef");
        run(@"invalid-id",@"../../outside");
        NSString *profiles=[file stringByAppendingString:@".profiles"];
        NSString *profile=[profiles stringByAppendingPathComponent:@"0123456789abcdef.json"];
        [@"corrupt" writeToFile:profile atomically:YES encoding:NSUTF8StringEncoding error:nil];
        run(@"reset",@"0123456789abcdef");
        assert([[NSString stringWithContentsOfFile:profile encoding:NSUTF8StringEncoding error:nil] isEqual:@"corrupt"]);
        assert([NSFileManager.defaultManager removeItemAtPath:profiles error:nil]);
        [@"not a directory" writeToFile:profiles atomically:YES encoding:NSUTF8StringEncoding error:nil];
        run(@"write-failure",@"0123456789abcdef");
        assert([NSFileManager.defaultManager removeItemAtPath:root error:nil]);
        puts("PASS: per-game isolation, inherited defaults, scope changes, reset, corrupt profiles and failed persistence");
    }
}
