#import <Cocoa/Cocoa.h>
#import <QuartzCore/CAMetalLayer.h>
#import <QuartzCore/CATransaction.h>
#import <Metal/Metal.h>
#include <stdatomic.h>
#import "controller.h"
#import "settings.h"
#import "settings_ui.h"

extern _Atomic uint64_t native_buttons, native_keyboard_buttons;
extern void native_touch(int,int,int);
static CAMetalLayer *game_layer;
static NSWindow *game_window;
static BOOL held[128], fullscreen_transition;
static NSMenuItem *fullscreen_item;
static void release_input(void) {
    memset(held,0,sizeof held);atomic_store(&native_keyboard_buttons,0);
    atomic_store(&native_buttons,0);native_touch(0,0,0);
}
static void publish_keys(void) {
    uint64_t buttons=0;
    for (unsigned short key=0;key<128;key++) if (held[key]) buttons|=native_settings_key_mask(key);
    atomic_store(&native_keyboard_buttons,buttons);
}
static void update_surface(void) {
    NSSize size=game_window.contentView.bounds.size;
    CGFloat width=MIN(size.width,size.height*16/9),height=width*9/16;
    CGFloat scale=game_window.backingScaleFactor ?: 1;
    NSInteger resolution=[native_settings_snapshot()[@"resolution"] integerValue];
    [CATransaction begin];[CATransaction setDisableActions:YES];
    game_layer.frame=CGRectMake((size.width-width)/2,(size.height-height)/2,width,height);
    game_layer.contentsScale=scale;
    game_layer.drawableSize=resolution ? CGSizeMake(resolution*16/9,resolution) : CGSizeMake(MAX(1,width*scale),MAX(1,height*scale));
    [CATransaction commit];
}
@interface GameView : NSView
@end
@implementation GameView
- (BOOL)acceptsFirstResponder {return YES;}
- (void)keyDown:(NSEvent *)event {
    if (event.modifierFlags & NSEventModifierFlagCommand) { [super keyDown:event];return; }
    if (event.keyCode<128) { held[event.keyCode]=YES;publish_keys(); }
}
- (void)flagsChanged:(NSEvent *)event {
    uint64_t modifier=native_key_modifier(event.keyCode);
    if (modifier && event.keyCode<128) {
        held[event.keyCode]=(event.modifierFlags & modifier) ? !held[event.keyCode] : NO;
        publish_keys();
    }
}
- (void)keyUp:(NSEvent *)event { if (event.keyCode<128) { held[event.keyCode]=NO;publish_keys(); } }
- (void)pointer:(NSEvent *)event down:(int)down {
    NSPoint p=[self convertPoint:event.locationInWindow fromView:nil];
    NSRect frame=game_layer.frame;
    if (frame.size.width<=0 || frame.size.height<=0) return;
    if ((p.x<NSMinX(frame) || p.x>NSMaxX(frame) || p.y<NSMinY(frame) || p.y>NSMaxY(frame)) && down) { native_touch(0,0,0);return; }
    int x=MAX(0,MIN(1279,(int)((p.x-frame.origin.x)*1280/frame.size.width)));
    int y=MAX(0,MIN(719,(int)((NSMaxY(frame)-p.y)*720/frame.size.height)));
    native_touch(down,x,y);
}
- (void)mouseDown:(NSEvent *)event {[self pointer:event down:1];}
- (void)mouseDragged:(NSEvent *)event {[self pointer:event down:1];}
- (void)mouseUp:(NSEvent *)event {[self pointer:event down:0];}
- (void)setFrameSize:(NSSize)size { [super setFrameSize:size];update_surface(); }
@end

@interface GameDelegate : NSObject <NSApplicationDelegate,NSWindowDelegate,NSMenuItemValidation>
- (void)applySettings;
@end
@implementation GameDelegate
- (void)applicationDidBecomeActive:(NSNotification *)note { [self applySettings]; }
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app {(void)app;return YES;}
- (void)windowWillClose:(NSNotification *)note { if (note.object==game_window) [NSApp terminate:nil]; }
- (void)windowDidResignKey:(NSNotification *)note {release_input();native_controller_focus(0);}
- (void)windowDidBecomeKey:(NSNotification *)note {native_controller_focus(1);}
- (void)windowDidChangeBackingProperties:(NSNotification *)note {update_surface();}
- (void)windowWillEnterFullScreen:(NSNotification *)note {fullscreen_transition=YES;}
- (void)windowWillExitFullScreen:(NSNotification *)note {fullscreen_transition=YES;}
- (void)windowDidEnterFullScreen:(NSNotification *)note {fullscreen_transition=NO;native_settings_update(@{@"fullscreen":@YES},nil);update_surface();}
- (void)windowDidExitFullScreen:(NSNotification *)note {fullscreen_transition=NO;native_settings_update(@{@"fullscreen":@NO},nil);update_surface();}
- (void)windowDidFailToEnterFullScreen:(NSWindow *)window {fullscreen_transition=NO;native_settings_update(@{@"fullscreen":@NO},nil);}
- (void)windowDidFailToExitFullScreen:(NSWindow *)window {fullscreen_transition=NO;native_settings_update(@{@"fullscreen":@YES},nil);}
- (void)showSettings:(id)sender {release_input();native_settings_show(game_window);}
- (void)toggleFullscreen:(id)sender {
    if (!fullscreen_transition) [game_window toggleFullScreen:nil];
}
- (void)selectMode:(NSMenuItem *)sender {
    NSError *error=nil;
    if (!native_settings_update(@{@"mode":sender.representedObject},&error)) [NSApp presentError:error];
}
- (void)selectResolution:(NSMenuItem *)sender {
    NSError *error=nil;
    if (!native_settings_update(@{@"resolution":sender.representedObject},&error)) [NSApp presentError:error];
}
- (BOOL)validateMenuItem:(NSMenuItem *)item {
    NSDictionary *data=native_settings_snapshot();
    if (item.action==@selector(selectMode:)) item.state=[item.representedObject isEqual:data[@"mode"]];
    if (item.action==@selector(selectResolution:)) item.state=[item.representedObject isEqual:data[@"resolution"]];
    if (item==fullscreen_item) {
        item.title=(game_window.styleMask & NSWindowStyleMaskFullScreen) ? @"Exit Full Screen":@"Enter Full Screen";
        return !fullscreen_transition;
    }
    return YES;
}
- (void)applySettings {
    release_input();update_surface();
    BOOL requested=[native_settings_snapshot()[@"fullscreen"] boolValue];
    if (!fullscreen_transition && requested != !!(game_window.styleMask & NSWindowStyleMaskFullScreen)) {
        if (NSApp.active) [game_window toggleFullScreen:nil];
        else [NSApp activate];
    }
}
@end
static GameDelegate *game_delegate;
static NSMenuItem *menu_item(NSMenu *menu,NSString *title,SEL action,NSString *key,id object) {
    NSMenuItem *item=[[NSMenuItem alloc] initWithTitle:title action:action keyEquivalent:key];
    item.target=game_delegate;item.representedObject=object;[menu addItem:item];return item;
}
static void build_menu(void) {
    NSMenu *bar=[NSMenu new];NSApp.mainMenu=bar;
    NSMenuItem *app=[[NSMenuItem alloc] initWithTitle:@"nsp-dawrin" action:NULL keyEquivalent:@""];[bar addItem:app];app.submenu=[[NSMenu alloc] initWithTitle:@"nsp-dawrin"];
    menu_item(app.submenu,@"Settings…",@selector(showSettings:),@",",nil);
    [app.submenu addItem:NSMenuItem.separatorItem];
    NSMenuItem *quit=menu_item(app.submenu,@"Quit nsp-dawrin",@selector(terminate:),@"q",nil);quit.target=NSApp;
    NSMenuItem *view=[[NSMenuItem alloc] initWithTitle:@"View" action:NULL keyEquivalent:@""];[bar addItem:view];view.submenu=[[NSMenu alloc] initWithTitle:@"View"];
    fullscreen_item=menu_item(view.submenu,@"Enter Full Screen",@selector(toggleFullscreen:),@"f",nil);
    fullscreen_item.keyEquivalentModifierMask=NSEventModifierFlagCommand|NSEventModifierFlagControl;
    NSMenuItem *mode=menu_item(view.submenu,@"System Mode (Next Launch)",NULL,@"",nil);
    mode.submenu=[[NSMenu alloc] initWithTitle:@"System Mode"];
    menu_item(mode.submenu,@"Handheld — 720p",@selector(selectMode:),@"",@"handheld");
    menu_item(mode.submenu,@"Console — 1080p",@selector(selectMode:),@"",@"console");
    NSMenuItem *resolution=menu_item(view.submenu,@"Display Output",NULL,@"",nil);
    resolution.submenu=[[NSMenu alloc] initWithTitle:@"Display Output"];
    menu_item(resolution.submenu,@"Automatic",@selector(selectResolution:),@"",@0);
    menu_item(resolution.submenu,@"1280 × 720",@selector(selectResolution:),@"",@720);
    menu_item(resolution.submenu,@"1920 × 1080",@selector(selectResolution:),@"",@1080);
    NSMenuItem *window=[[NSMenuItem alloc] initWithTitle:@"Window" action:NULL keyEquivalent:@""];[bar addItem:window];window.submenu=[[NSMenu alloc] initWithTitle:@"Window"];
    NSMenuItem *minimize=menu_item(window.submenu,@"Minimize",@selector(performMiniaturize:),@"m",nil);minimize.target=game_window;
    NSApp.windowsMenu=window.submenu;
}

void *front_metal_layer(void) {return (__bridge void *)game_layer;}
int native_front_init(void) {
    native_settings_init();
    if(!getenv("DM_WINDOW"))return 0;
    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    game_delegate=[GameDelegate new];NSApp.delegate=game_delegate;
    game_window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,960,540)
        styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskMiniaturizable|NSWindowStyleMaskResizable
        backing:NSBackingStoreBuffered defer:NO];
    game_window.title=@"nsp-dawrin";game_window.collectionBehavior=NSWindowCollectionBehaviorFullScreenPrimary;
    game_window.contentAspectRatio=NSMakeSize(16,9);game_window.delegate=game_delegate;
    GameView *view=[[GameView alloc] initWithFrame:NSMakeRect(0,0,960,540)];
    game_layer=[CAMetalLayer layer];game_layer.device=MTLCreateSystemDefaultDevice();
    game_layer.pixelFormat=MTLPixelFormatBGRA8Unorm;game_layer.framebufferOnly=YES;
    view.wantsLayer=YES;[view.layer addSublayer:game_layer];game_window.contentView=view;update_surface();
    [game_window center];[game_window makeKeyAndOrderFront:nil];[game_window makeFirstResponder:view];
    native_controller_start();build_menu();
    [NSNotificationCenter.defaultCenter addObserverForName:NativeSettingsChanged object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) { [game_delegate applySettings]; }];
    [NSNotificationCenter.defaultCenter addObserverForName:NSMenuDidBeginTrackingNotification object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) { release_input(); }];
    [NSApp activate];[game_delegate applySettings];return 1;
}
void native_front_loop(void) {[NSApp run];}

// The control server uses the same main-thread settings actions as the menus.
char *native_front_settings(const char *command) {
    if (!game_window) return strdup("{\"error\":\"Window settings are unavailable in headless mode\"}");
    NSString *request=@(command);
    __block NSString *reply;
    void (^work)(void)=^{
        NSError *error=nil;BOOL ok=YES;
        if ([request isEqual:@"show"]) [game_delegate showSettings:nil];
        else if ([request hasPrefix:@"controller "]) ok=native_controller_choose([request substringFromIndex:11],&error);
        else if (request.length) {
            id patch=[NSJSONSerialization JSONObjectWithData:[request dataUsingEncoding:NSUTF8StringEncoding] options:0 error:&error];
            ok=patch && native_settings_update(patch,&error);
        }
        NSMutableDictionary *response=[native_settings_snapshot() mutableCopy];
        response[@"active_mode"]=native_settings_handheld() ? @"handheld":@"console";
        response[@"actual_fullscreen"]=@((game_window.styleMask & NSWindowStyleMaskFullScreen)!=0);
        response[@"output_size"]=@[@(game_layer.drawableSize.width),@(game_layer.drawableSize.height)];
        response[@"devices"]=native_controller_devices();response[@"selected_controller"]=native_controller_selection();
        if (!ok) response=@{@"error":error.localizedDescription ?: @"Invalid settings"}.mutableCopy;
        NSData *data=[NSJSONSerialization dataWithJSONObject:response options:0 error:nil];
        reply=[[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    };
    if (NSThread.isMainThread) work(); else dispatch_sync(dispatch_get_main_queue(),work);
    return strdup(reply.UTF8String);
}
