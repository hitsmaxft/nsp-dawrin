#import <Cocoa/Cocoa.h>
#import <GameController/GameController.h>
#include "controller.h"
#import "settings.h"
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

NSString *const NativeControllersChanged = @"NativeControllersChanged";
static NSArray<GCController *> *devices;
static NSMapTable<GCController *, NSString *> *identifiers;
static NSString *wanted_identifier;

static NSDictionary *descriptor(GCController *controller) {
    return @{@"vendor":controller.vendorName ?: @"Controller", @"category":controller.productCategory ?: @"Gamepad"};
}
static void select_controller(GCController *controller) {
    if (selected != controller) {
        selected.extendedGamepad.valueChangedHandler = nil;
        selected.playerIndex = GCControllerPlayerIndexUnset;
        selected = controller;
        selected.handlerQueue = dispatch_get_main_queue();
        selected.playerIndex = GCControllerPlayerIndex1;
        selected.extendedGamepad.valueChangedHandler = ^(GCExtendedGamepad *pad, GCControllerElement *element) {
            (void)pad; (void)element; publish();
        };
    }
    publish();
}
static void apply_selection(void) {
    id preference=native_settings_snapshot()[@"controller"];
    GCController *match=nil;
    if ([preference isEqual:@"auto"]) match=[devices containsObject:selected] ? selected : devices.firstObject;
    else if (![preference isEqual:@"none"]) {
        for (GCController *device in devices) {
            if (wanted_identifier && [[identifiers objectForKey:device] isEqual:wanted_identifier] && [descriptor(device) isEqual:preference]) { match=device; break; }
            if (!wanted_identifier && !match && [descriptor(device) isEqual:preference]) match=device;
        }
    }
    select_controller(match);
    [NSNotificationCenter.defaultCenter postNotificationName:NativeControllersChanged object:nil];
}
// Refresh from the framework's device list; also usable with framework virtual controllers.
void native_controller_refresh(NSArray<GCController *> *connected) {
    if (!identifiers) identifiers=[NSMapTable weakToStrongObjectsMapTable];
    NSMutableArray *supported=[NSMutableArray array];
    for (GCController *controller in connected) if (controller.extendedGamepad) {
        [supported addObject:controller];
        if (![identifiers objectForKey:controller]) [identifiers setObject:NSUUID.UUID.UUIDString forKey:controller];
    }
    id preference=native_settings_snapshot()[@"controller"];
    BOOL wantedPresent=NO;
    for (GCController *device in supported) if ([[identifiers objectForKey:device] isEqual:wanted_identifier]) wantedPresent=YES;
    if (!wantedPresent && [preference isKindOfClass:NSDictionary.class])
        for (GCController *device in supported)
            if (![devices containsObject:device] && [descriptor(device) isEqual:preference]) {
                wanted_identifier=[identifiers objectForKey:device];break;
            }
    devices=[supported copy];
    apply_selection();
}
NSArray<NSDictionary *> *native_controller_devices(void) {
    NSMutableArray *result=[NSMutableArray array];
    NSUInteger index=0;
    for (GCController *device in devices) {
        NSDictionary *model=descriptor(device);
        [result addObject:@{@"id":[identifiers objectForKey:device],
            @"name":[NSString stringWithFormat:@"%@ — %@ (%lu)",model[@"vendor"],model[@"category"],(unsigned long)++index],
            @"selected":@(device==selected)}];
    }
    return result;
}
NSString *native_controller_selection(void) {
    id preference=native_settings_snapshot()[@"controller"];
    if ([preference isKindOfClass:NSString.class]) return preference;
    return selected ? [identifiers objectForKey:selected] : @"unavailable";
}
BOOL native_controller_choose(NSString *identifier, NSError **error) {
    id preference=identifier;
    if (![@[@"auto",@"none"] containsObject:identifier]) {
        preference=nil;
        for (GCController *device in devices)
            if ([[identifiers objectForKey:device] isEqual:identifier]) { preference=descriptor(device); break; }
        if (!preference) {
            if (error) *error=[NSError errorWithDomain:@"nsp-dawrin.controller" code:1 userInfo:@{NSLocalizedDescriptionKey:@"Controller is no longer connected"}];
            return NO;
        }
    }
    NSString *previous=wanted_identifier;
    wanted_identifier=identifier;
    if (!native_settings_update(@{@"controller":preference},error)) { wanted_identifier=previous; return NO; }
    apply_selection();
    return YES;
}
void native_controller_start(void) {
    static BOOL started=NO;
    if (started) return;
    started=YES;
    NSNotificationCenter *center=NSNotificationCenter.defaultCenter;
    [center addObserverForName:GCControllerDidConnectNotification object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) { (void)note; native_controller_refresh(GCController.controllers); }];
    [center addObserverForName:GCControllerDidDisconnectNotification object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) {
            NSMutableArray *remaining=[GCController.controllers mutableCopy];
            [remaining removeObject:note.object];
            native_controller_refresh(remaining);
        }];
    [center addObserverForName:NativeSettingsChanged object:nil queue:NSOperationQueue.mainQueue
        usingBlock:^(NSNotification *note) { (void)note; apply_selection(); }];
    native_controller_refresh(GCController.controllers);
}
