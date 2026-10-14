#import "settings.h"
#import "controller.h"
#import <GameController/GameController.h>
#include <assert.h>
extern void native_controller_refresh(NSArray<GCController *> *);
extern NativePad native_controller_map(GCExtendedGamepad *);
int main(int argc, char **argv) {
    @autoreleasepool {
        native_settings_init();
        if (argc>1) {
            assert(!native_settings_handheld());
            assert([native_settings_snapshot()[@"resolution"] intValue]==1080);
            assert(native_settings_key_mask(12)==1);
            puts("PASS: persisted settings restored in a new process"); return 0;
        }
        assert(native_settings_handheld());
        assert(native_settings_key_mask(6)==1 && native_settings_key_mask(49)==1);
        NSError *error=nil;
        assert(!native_settings_update(@{@"resolution":@900},&error));
        assert([native_settings_snapshot()[@"resolution"] intValue]==0);
        assert(!native_settings_update(@{@"bindings":@{@"0":@[@12],@"1":@[@12]}},&error));
        assert(native_settings_update(@{@"mode":@"console",@"resolution":@1080,@"bindings":@{@"0":@[@12]}},&error));
        assert(native_settings_handheld()); // Active guest mode remains stable until restart.
        assert(!native_settings_key_mask(6) && native_settings_key_mask(12)==1);
        GCController *first=[GCController controllerWithExtendedGamepad];
        GCController *second=[GCController controllerWithExtendedGamepad];
        native_controller_refresh(@[first,second]);
        [first.extendedGamepad.buttonB setValue:1];
        native_controller_focus(1);
        assert(native_controller_read().buttons==1);
        NSString *secondID=native_controller_devices()[1][@"id"];
        assert(native_controller_choose(secondID,&error));
        assert(!native_controller_read().buttons);
        [second.extendedGamepad.buttonA setValue:1];native_controller_focus(1);
        assert(native_controller_read().buttons==2);
        native_controller_focus(0);assert(!native_controller_read().buttons);
        native_controller_refresh(@[first]);assert(!native_controller_read().connected);
        native_controller_refresh(@[first,second]);native_controller_focus(1);assert(native_controller_read().buttons==2);
        assert(native_controller_choose(@"none",&error));
        assert(!native_controller_read().connected);
        native_controller_refresh(@[first]);assert(!native_controller_read().connected);
        assert(!native_controller_choose(@"missing",&error));
        assert(native_controller_choose(@"auto",&error));native_controller_focus(1);
        assert(native_controller_read().buttons==1);
        native_controller_refresh(@[]);assert(!native_controller_read().connected);
        puts("PASS: settings validation, mode staging, key mapping, device selection and neutral disconnect");
    }
}
