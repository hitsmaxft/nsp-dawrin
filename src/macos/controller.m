#import <Cocoa/Cocoa.h>
#import <GameController/GameController.h>
#include "controller.h"
#include <math.h>
#include <pthread.h>

static GCController *selected;
static pthread_mutex_t pad_lock = PTHREAD_MUTEX_INITIALIZER;
static NativePad state;
static BOOL focused = YES;

static int32_t axis(float value) {
    const float deadzone = 0.15f;
    if (!isfinite(value) || fabsf(value) <= deadzone) return 0;
    float normalized = (fminf(fabsf(value), 1) - deadzone) / (1 - deadzone);
    return (int32_t)lrintf(copysignf(normalized * 32767, value));
}

// The framework defines face buttons by position: A south, B east, X west, Y north.
// The guest layout uses A east, B south, X north, Y west on every controller.
NativePad native_controller_map(GCExtendedGamepad *p) {
    NativePad s = {.connected = p != nil};
    GCControllerButtonInput *buttons[] = {
        p.buttonB, p.buttonA, p.buttonY, p.buttonX,
        p.leftThumbstickButton, p.rightThumbstickButton,
        p.leftShoulder, p.rightShoulder, p.leftTrigger, p.rightTrigger,
        p.buttonMenu, p.buttonOptions, p.dpad.left, p.dpad.up,
        p.dpad.right, p.dpad.down
    };
    for (unsigned i = 0; i < 16; i++) if (buttons[i].pressed) s.buttons |= 1ull << i;
    s.lx = axis(p.leftThumbstick.xAxis.value); s.ly = axis(p.leftThumbstick.yAxis.value);
    s.rx = axis(p.rightThumbstick.xAxis.value); s.ry = axis(p.rightThumbstick.yAxis.value);
    if (s.lx < -16383) s.buttons |= 1ull << 16;
    if (s.ly > 16383) s.buttons |= 1ull << 17;
    if (s.lx > 16383) s.buttons |= 1ull << 18;
    if (s.ly < -16383) s.buttons |= 1ull << 19;
    if (s.rx < -16383) s.buttons |= 1ull << 20;
    if (s.ry > 16383) s.buttons |= 1ull << 21;
    if (s.rx > 16383) s.buttons |= 1ull << 22;
    if (s.ry < -16383) s.buttons |= 1ull << 23;
    return s;
}

static void publish(void) {
    NativePad next = native_controller_map(selected.extendedGamepad);
    if (!focused) next = (NativePad){.connected = next.connected};
    pthread_mutex_lock(&pad_lock); state = next; pthread_mutex_unlock(&pad_lock);
}

NativePad native_controller_read(void) {
    pthread_mutex_lock(&pad_lock); NativePad copy = state; pthread_mutex_unlock(&pad_lock);
    return copy;
}

void native_controller_focus(int active) { focused = !!active; publish(); }

static void select_controller(GCController *controller) {
    selected.extendedGamepad.valueChangedHandler = nil;
    selected = controller;
    selected.handlerQueue = dispatch_get_main_queue();
    selected.playerIndex = GCControllerPlayerIndex1;
    selected.extendedGamepad.valueChangedHandler = ^(GCExtendedGamepad *pad, GCControllerElement *element) {
        (void)pad; (void)element; publish();
    };
    publish();
}

void native_controller_start(void) {
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    [center addObserverForName:GCControllerDidConnectNotification object:nil queue:NSOperationQueue.mainQueue
                   usingBlock:^(NSNotification *note) {
        GCController *controller = note.object;
        if (!selected && controller.extendedGamepad) select_controller(controller);
    }];
    [center addObserverForName:GCControllerDidDisconnectNotification object:nil queue:NSOperationQueue.mainQueue
                   usingBlock:^(NSNotification *note) {
        if (note.object != selected) return;
        select_controller(nil);
        for (GCController *controller in GCController.controllers)
            if (controller != note.object && controller.extendedGamepad) { select_controller(controller); break; }
    }];
    for (GCController *controller in GCController.controllers)
        if (controller.extendedGamepad) { select_controller(controller); break; }
}
