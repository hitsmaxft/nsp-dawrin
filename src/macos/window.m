#import <Cocoa/Cocoa.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>
#include <stdatomic.h>
#include "controller.h"

extern _Atomic uint64_t native_buttons;
extern void native_touch(int,int,int);
static CAMetalLayer *game_layer;
static NSWindow *game_window;

static uint64_t key_button(unsigned short key) {
    switch(key) {
        case 6: case 49: return 1ull<<0; // Z / Space: A
        case 7: case 53: return 1ull<<1; // X / Escape: B
        case 0: return 1ull<<2;         // A: X
        case 1: return 1ull<<3;         // S: Y
        case 36: return 1ull<<10;       // Return: Plus
        case 123: return 1ull<<12;
        case 126: return 1ull<<13;
        case 124: return 1ull<<14;
        case 125: return 1ull<<15;
        default:return 0;
    }
}
@interface GameView : NSView
@end
@implementation GameView
- (BOOL)acceptsFirstResponder {return YES;}
- (void)keyDown:(NSEvent *)event {atomic_fetch_or(&native_buttons,key_button(event.keyCode));}
- (void)keyUp:(NSEvent *)event {atomic_fetch_and(&native_buttons,~key_button(event.keyCode));}
- (void)pointer:(NSEvent *)event down:(int)down {
    NSPoint p=[self convertPoint:event.locationInWindow fromView:nil];
    NSSize size=self.bounds.size;
    if (size.width<=0 || size.height<=0) return;
    int x=MAX(0,MIN(1279,(int)(p.x*1280/size.width)));
    int y=MAX(0,MIN(719,(int)((size.height-p.y)*720/size.height)));
    native_touch(down,x,y);
}
- (void)mouseDown:(NSEvent *)event {[self pointer:event down:1];}
- (void)mouseDragged:(NSEvent *)event {[self pointer:event down:1];}
- (void)mouseUp:(NSEvent *)event {[self pointer:event down:0];}
- (void)setFrameSize:(NSSize)size {
    [super setFrameSize:size];
    CGFloat scale=self.window.backingScaleFactor ?: 1;
    game_layer.contentsScale=scale;
    game_layer.drawableSize=CGSizeMake(size.width*scale,size.height*scale);
}
@end

@interface GameDelegate : NSObject <NSApplicationDelegate,NSWindowDelegate>
@end
@implementation GameDelegate
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app {(void)app;return YES;}
- (void)windowDidResignKey:(NSNotification *)note {(void)note;atomic_store(&native_buttons,0);native_touch(0,0,0);native_controller_focus(0);}
- (void)windowDidBecomeKey:(NSNotification *)note {(void)note;native_controller_focus(1);}
@end
static GameDelegate *game_delegate;

void *front_metal_layer(void) {return (__bridge void *)game_layer;}
int native_front_init(void) {
    if(!getenv("DM_WINDOW"))return 0;
    [NSApplication sharedApplication];
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    game_delegate=[GameDelegate new];NSApp.delegate=game_delegate;
    game_window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,960,540)
        styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskMiniaturizable|NSWindowStyleMaskResizable
        backing:NSBackingStoreBuffered defer:NO];
    game_window.title=@"nsp-dawrin";
    game_window.contentAspectRatio=NSMakeSize(16,9);game_window.delegate=game_delegate;
    GameView *view=[[GameView alloc] initWithFrame:NSMakeRect(0,0,960,540)];
    game_layer=[CAMetalLayer layer];game_layer.device=MTLCreateSystemDefaultDevice();
    game_layer.pixelFormat=MTLPixelFormatBGRA8Unorm;game_layer.framebufferOnly=YES;
    view.wantsLayer=YES;view.layer=game_layer;game_window.contentView=view;
    [view setFrameSize:view.frame.size];
    [game_window center];[game_window makeKeyAndOrderFront:nil];[game_window makeFirstResponder:view];
    native_controller_start();
    [NSApp activateIgnoringOtherApps:YES];return 1;
}
void native_front_loop(void) {[NSApp run];}
