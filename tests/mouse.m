#import <Cocoa/Cocoa.h>
#include <stdatomic.h>
#include <assert.h>
_Atomic uint64_t native_buttons, native_keyboard_buttons;
static int contact, tx, ty;
void native_touch(int down, int x, int y) { contact=down;tx=x;ty=y; }
extern int native_front_init(void);
static NSEvent *event(NSWindow *window, NSEventType type, CGFloat x, CGFloat y) {
    return [NSEvent mouseEventWithType:type location:NSMakePoint(x,y) modifierFlags:0 timestamp:0
        windowNumber:window.windowNumber context:nil eventNumber:1 clickCount:1 pressure:1];
}
int main(void) {
    @autoreleasepool {
        setenv("DM_WINDOW","1",1); assert(native_front_init());
        NSWindow *window=NSApp.windows.firstObject; NSView *view=window.contentView;
        [view mouseDown:event(window,NSEventTypeLeftMouseDown,480,270)];
        assert(contact==1 && tx==640 && ty==360);
        [view mouseDragged:event(window,NSEventTypeLeftMouseDragged,960,0)];
        assert(contact==1 && tx==1279 && ty==719);
        [view mouseUp:event(window,NSEventTypeLeftMouseUp,0,540)];
        assert(contact==0 && tx==0 && ty==0);
        [view setFrameSize:NSMakeSize(1920,1080)];
        [view mouseDown:event(window,NSEventTypeLeftMouseDown,960,540)];
        assert(contact==1 && tx==640 && ty==360);
        [(id)window.delegate windowDidResignKey:[NSNotification notificationWithName:NSWindowDidResignKeyNotification object:window]];
        assert(!contact && !atomic_load(&native_buttons));
        [window orderOut:nil];
        puts("PASS: mouse press, drag, release, resize coordinates, focus release");
    }
}
