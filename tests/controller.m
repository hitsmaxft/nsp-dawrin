#import <GameController/GameController.h>
#include "controller.h"
#include <assert.h>
extern NativePad native_controller_map(GCExtendedGamepad *);

int main(void) {
    @autoreleasepool {
        GCController *controller = [GCController controllerWithExtendedGamepad];
        GCExtendedGamepad *pad = controller.extendedGamepad;
        assert(pad);
        NativePad s = native_controller_map(pad);
        assert(s.connected && !s.buttons && !s.lx && !s.ly);
        [pad.buttonB setValue:1]; s = native_controller_map(pad); assert(s.buttons == 1);
        [pad.buttonB setValue:0]; [pad.buttonA setValue:1];
        s = native_controller_map(pad); assert(s.buttons == 2);
        [pad.buttonA setValue:0]; [pad.buttonY setValue:1];
        s = native_controller_map(pad); assert(s.buttons == 4);
        [pad.buttonY setValue:0]; [pad.buttonX setValue:1];
        s = native_controller_map(pad); assert(s.buttons == 8);
        [pad.buttonX setValue:0];
        [pad.leftThumbstick setValueForXAxis:1 yAxis:-1];
        [pad.rightThumbstick setValueForXAxis:0.10 yAxis:0];
        [pad.leftTrigger setValue:1];
        s = native_controller_map(pad);
        assert(s.lx == 32767 && s.ly == -32767 && s.rx == 0 && s.ry == 0);
        assert(s.buttons == ((1ull<<8)|(1ull<<18)|(1ull<<19)));
        s = native_controller_map(nil); assert(!s.connected && !s.buttons && !s.lx);
        printf("PASS: face layout, trigger, stick range, deadzone, neutral disconnect; physical controllers=%lu\n",
               (unsigned long)GCController.controllers.count);
    }
}
