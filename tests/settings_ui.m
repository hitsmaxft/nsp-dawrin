#import <Cocoa/Cocoa.h>
#import <QuartzCore/CAMetalLayer.h>
#import "settings.h"
#import "controller.h"
#include <stdatomic.h>
#include <assert.h>
#include <unistd.h>
_Atomic uint64_t native_buttons, native_keyboard_buttons;
void native_touch(int down,int x,int y) {}
extern int native_front_init(void);
extern void *front_metal_layer(void);
extern char *native_front_settings(const char *);
static void pump(double seconds) {
    NSDate *end=[NSDate dateWithTimeIntervalSinceNow:seconds];
    while (end.timeIntervalSinceNow>0) {
        NSEvent *event=[NSApp nextEventMatchingMask:NSEventMaskAny untilDate:[NSDate dateWithTimeIntervalSinceNow:0.02]
            inMode:NSDefaultRunLoopMode dequeue:YES];
        if (event) [NSApp sendEvent:event];[NSApp updateWindows];
        CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.01,true);
    }
}
static NSEvent *key(NSWindow *window, unsigned short code, NSEventType type) {
    return [NSEvent keyEventWithType:type location:NSZeroPoint modifierFlags:0 timestamp:0
        windowNumber:window.windowNumber context:nil characters:@"q" charactersIgnoringModifiers:@"q" isARepeat:NO keyCode:code];
}
static NSButton *button(NSWindow *window,NSString *title) {
    for (NSView *view in window.contentView.subviews)
        if ([view isKindOfClass:NSButton.class] && [[(NSButton *)view title] isEqual:title]) return (NSButton *)view;
    return nil;
}
int main(int argc, char **argv) {
    @autoreleasepool {
        alarm(getenv("NSP_TEST_WAIT_ACTIVE") ? 90 : 20);
        setenv("DM_WINDOW","1",1);assert(native_front_init());[NSApp finishLaunching];pump(0.5);
        if (getenv("NSP_TEST_WAIT_ACTIVE")) {
            NSDate *limit=[NSDate dateWithTimeIntervalSinceNow:60];
            while (!NSApp.active && limit.timeIntervalSinceNow>0) pump(0.1);
        }
        NSWindow *game=NSApp.windows.firstObject;NSView *view=game.contentView;
        assert(game && [game.title isEqual:@"nsp-dawrin"]);
        assert(NSApp.mainMenu.numberOfItems==4);
        assert([NSApp.mainMenu.itemArray[1].title isEqual:@"View"]);
        assert([NSApp.mainMenu.itemArray[2].title isEqual:@"Window"]);
        [view keyDown:key(game,6,NSEventTypeKeyDown)];[view keyDown:key(game,49,NSEventTypeKeyDown)];
        [view keyUp:key(game,6,NSEventTypeKeyUp)];assert(native_keyboard_buttons==1);
        [view keyUp:key(game,49,NSEventTypeKeyUp)];assert(!native_keyboard_buttons);
        NSError *error=nil;
        assert(native_settings_update(@{@"bindings":@{@"0":@[@56,@60]}},&error));
        for (NSNumber *code in @[@56,@60,@56]) {
            NSEvent *modifier=[NSEvent keyEventWithType:NSEventTypeFlagsChanged location:NSZeroPoint modifierFlags:NSEventModifierFlagShift timestamp:0
                windowNumber:game.windowNumber context:nil characters:@"" charactersIgnoringModifiers:@"" isARepeat:NO keyCode:code.unsignedShortValue];
            [view flagsChanged:modifier];assert(native_keyboard_buttons==1);
        }
        [view flagsChanged:[NSEvent keyEventWithType:NSEventTypeFlagsChanged location:NSZeroPoint modifierFlags:0 timestamp:0
            windowNumber:game.windowNumber context:nil characters:@"" charactersIgnoringModifiers:@"" isARepeat:NO keyCode:60]];
        assert(!native_keyboard_buttons);
        assert(native_settings_update(@{@"bindings":@{@"0":@[@6,@49],@"1":@[@7,@53]}},&error));
        assert(native_settings_update(@{@"resolution":@720},&error));
        CAMetalLayer *layer=(__bridge CAMetalLayer *)front_metal_layer();
        assert(layer.drawableSize.width==1280 && layer.drawableSize.height==720);
        assert(native_settings_update(@{@"resolution":@1080},&error));
        assert(layer.drawableSize.width==1920 && layer.drawableSize.height==1080);
        [NSApp.mainMenu.itemArray[0].submenu performActionForItemAtIndex:0];pump(0.2);
        NSWindow *settings=nil;
        for (NSWindow *candidate in NSApp.windows) if ([candidate.title isEqual:@"Settings"]) settings=candidate;
        assert(settings);
        NSButton *binding=button(settings,@"Z / Space");assert(binding);
        [binding performClick:nil];
        [NSApp sendEvent:key(settings,12,NSEventTypeKeyDown)];
        assert(native_settings_key_mask(12)==1 && !native_settings_key_mask(6));
        assert(!native_keyboard_buttons);
        // Move the same key to B using the same recording event path.
        binding=button(settings,@"X / Escape");assert(binding);[binding performClick:nil];
        [NSApp sendEvent:key(settings,12,NSEventTypeKeyDown)];assert(native_settings_key_mask(12)==2);
        [button(settings,@"Reset Keyboard") performClick:nil];assert(native_settings_key_mask(6)==1);
        NSBitmapImageRep *bitmap=[settings.contentView bitmapImageRepForCachingDisplayInRect:settings.contentView.bounds];
        [settings.contentView cacheDisplayInRect:settings.contentView.bounds toBitmapImageRep:bitmap];
        const char *capture=getenv("NSP_TEST_CAPTURE");
        if (capture) [[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}] writeToFile:@(capture) atomically:YES];
        [settings close];[game makeKeyAndOrderFront:nil];[game makeFirstResponder:view];pump(0.2);
        [view keyDown:key(game,6,NSEventTypeKeyDown)];assert(native_keyboard_buttons==1);
        [game.delegate windowDidResignKey:[NSNotification notificationWithName:NSWindowDidResignKeyNotification object:game]];
        assert(!native_keyboard_buttons);
        if (!(argc>1 && !strcmp(argv[1],"--skip-fullscreen"))) {
        assert(native_settings_update(@{@"fullscreen":@YES},&error));pump(2);
        if (!(game.styleMask & NSWindowStyleMaskFullScreen)) { char *debug=native_front_settings("");fprintf(stderr,"fullscreen state: %s active=%d visible=%d key=%d\n",debug,NSApp.active,game.visible,game.keyWindow);free(debug); }
        assert(game.styleMask & NSWindowStyleMaskFullScreen);
        assert([native_settings_snapshot()[@"fullscreen"] boolValue]);
        assert(native_settings_update(@{@"fullscreen":@NO},&error));pump(2);
        assert(!(game.styleMask & NSWindowStyleMaskFullScreen));
        puts("PASS: native fullscreen round trip");
        } else puts("SKIP: fullscreen requires an unlocked foreground session");
        char *json=native_front_settings("");
        NSDictionary *state=[NSJSONSerialization JSONObjectWithData:[@(json) dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];free(json);
        assert(([state[@"output_size"] isEqual:@[@1920,@1080]]));
        assert([state[@"active_mode"] isEqual:@"handheld"]);
        [game orderOut:nil];
        puts("PASS: menus, settings key capture and reassignment, aliases, focus release, resolution and API state");
    }
}
