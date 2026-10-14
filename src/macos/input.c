#include "hle.h"
#include <stdatomic.h>
#include "controller.h"
// A host controller. The eventual window frontend can set buttons atomically.
_Atomic uint64_t native_buttons;
_Atomic uint64_t native_keyboard_buttons;
_Atomic uint64_t native_touch_samples;
_Atomic uint64_t native_touch_contacts;
static _Atomic uint64_t sampling;
static uint32_t supported=1;
static pthread_mutex_t touch_lock=PTHREAD_MUTEX_INITIALIZER;
static uint32_t touch_x,touch_y;static int touch_down,touch_previous;
void native_touch(int down,int x,int y) {
    pthread_mutex_lock(&touch_lock);touch_down=down;touch_x=x;touch_y=y;pthread_mutex_unlock(&touch_lock);
}
typedef struct {uint64_t delta;uint32_t attributes,id,x,y,dx,dy,angle,reserved;} Touch;
_Static_assert(sizeof(Touch)==40,"Horizon touch ABI");
static void fill_touch(void *out,size_t size) {
    ++native_touch_samples;
    memset(out,0,size);*(uint64_t*)out=++sampling;
    pthread_mutex_lock(&touch_lock);
    if(touch_down||touch_previous) {
        ++native_touch_contacts;
        *(uint32_t*)((char*)out+8)=1;
        Touch *t=(Touch*)((char*)out+16);
        *t=(Touch){.delta=16666667,.attributes=touch_down?(touch_previous?0:1):2,.x=touch_x,.y=touch_y,.dx=8,.dy=8};
    }
    touch_previous=touch_down;pthread_mutex_unlock(&touch_lock);
}
typedef struct {double seconds;uint64_t buttons;} InputStep;
static InputStep input_steps[128];static int input_count;
static pthread_once_t input_once=PTHREAD_ONCE_INIT;
static void parse_input_script(void) {
    const char *e=getenv("DM_INPUT_SCRIPT");if(!e)return;
    char *copy=strdup(e),*save=NULL;
    for(char *p=strtok_r(copy,",",&save);p;p=strtok_r(NULL,",",&save)) {
        char *end;double seconds=strtod(p,&end);
        if(*end!=':'||seconds<0||input_count==128)die("Invalid DM_INPUT_SCRIPT");
        uint64_t buttons=strtoull(end+1,&end,0);
        if(*end||(input_count&&seconds<input_steps[input_count-1].seconds))die("Unsorted DM_INPUT_SCRIPT");
        input_steps[input_count++]=(InputStep){seconds,buttons};
    }
    free(copy);
}
typedef struct {uint64_t sampling,buttons;int32_t lx,ly,rx,ry;uint32_t attributes,pad;} State;
_Static_assert(sizeof(State)==0x28,"NpadState ABI");
static void fill(State *s,const uint32_t *id,uint32_t style) {
    memset(s,0,sizeof *s);s->sampling=++sampling;
    if (*id==0 && style==1) {
        NativePad pad=native_controller_read();
        uint64_t keys=atomic_load(&native_keyboard_buttons)|atomic_load(&native_buttons);
        s->attributes=1;s->buttons=keys | pad.buttons;
        s->lx=pad.lx;s->ly=pad.ly;s->rx=pad.rx;s->ry=pad.ry;
        if (!s->lx) s->lx=32767*((int)((keys>>18)&1)-(int)((keys>>16)&1));
        if (!s->ly) s->ly=32767*((int)((keys>>17)&1)-(int)((keys>>19)&1));
        if (!s->rx) s->rx=32767*((int)((keys>>22)&1)-(int)((keys>>20)&1));
        if (!s->ry) s->ry=32767*((int)((keys>>21)&1)-(int)((keys>>23)&1));
        pthread_once(&input_once,parse_input_script);
        double seconds=(now_ns()-g_t0_ns)/1e9;
        for(int i=0;i<input_count&&input_steps[i].seconds<=seconds;i++)s->buttons=input_steps[i].buttons;
    }
}
HLE_FORCE("_ZN2nn3hid14InitializeNpadEv","Host input state",void,hid_init,void) {}
HLE_FORCE("_ZN2nn3hid21InitializeTouchScreenEv","Mac has no touchscreen",void,hid_touch_init,void) {}
HLE_FORCE("_ZN2nn3hid17InitializeGestureEv","Mac has no Switch gesture service",void,hid_gesture_init,void) {}
HLE_FORCE("_ZN2nn3hid22SetSupportedNpadIdTypeEPKjm","One host controller at index zero",void,hid_ids,const uint32_t *ids,uint64_t n) {(void)ids;(void)n;}
HLE_FORCE("_ZN2nn3hid24SetSupportedNpadStyleSetENS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE","Store supported styles",void,hid_styles,uint32_t styles) {supported=styles;}
HLE_FORCE("_ZN2nn3hid24GetSupportedNpadStyleSetEv","Supported styles",uint32_t,hid_get_styles,void) {return supported;}
HLE_FORCE("_ZN2nn3hid15GetNpadStyleSetERKj","Host full controller",uint32_t,hid_style,const uint32_t *id) {return *id==0?(supported&1):0;}
#define STATE(kind,code,style) \
HLE_FORCE("_ZN2nn3hid12GetNpadStateEPNS0_" kind "ERKj","Host controller sample",void,hid_state_##code,State *s,const uint32_t *id) {fill(s,id,style);} \
HLE_FORCE("_ZN2nn3hid13GetNpadStatesEPNS0_" kind "EiRKj","Latest host controller sample",int,hid_states_##code,State *s,int n,const uint32_t *id) {if(n<1)return 0;fill(s,id,style);return 1;}
STATE("16NpadFullKeyState",full,1)
STATE("17NpadHandheldState",handheld,2)
STATE("16NpadJoyDualState",dual,4)
STATE("16NpadJoyLeftState",left,8)
STATE("17NpadJoyRightState",right,16)
HLE_FORCE("_ZN2nn3hid29SetNpadHandheldActivationModeENS0_26NpadHandheldActivationModeE","Docked mode",void,hid_handheld,int mode) {(void)mode;}
HLE_FORCE("_ZN2nn3hid18SetNpadJoyHoldTypeENS0_15NpadJoyHoldTypeE","No detachable JoyCons",void,hid_hold,int mode) {(void)mode;}
HLE_FORCE("_ZN2nn3hid20IsVibrationPermittedEv","No vibration device",int,hid_vibration,void) {return 0;}
HLE_FORCE("_ZN2nn3hid25GetVibrationDeviceHandlesEPNS0_21VibrationDeviceHandleEiRKjNS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE","No vibration device",int,hid_vib_handles,void *out,int n,const uint32_t *id,uint32_t style) {(void)out;(void)n;(void)id;(void)style;return 0;}
HLE_FORCE("_ZN2nn3hid19GetTouchScreenStateILm16EEEvPNS0_16TouchScreenStateIXT_EEE","Host pointer contacts",void,hid_touch,void *out) {fill_touch(out,0x290);}
HLE_FORCE("_ZN2nn3hid19GetTouchScreenStateILm5EEEvPNS0_16TouchScreenStateIXT_EEE","Host pointer contacts",void,hid_touch5,void *out) {fill_touch(out,0xd8);}
HLE_FORCE("_ZN2nn3hid23GetSixAxisSensorHandlesEPNS0_19SixAxisSensorHandleEiRKjNS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE","Mac keyboard controller has no motion sensor",int,hid_motion_handles,void *out,int n,const uint32_t *id,uint32_t style) {(void)out;(void)n;(void)id;(void)style;return 0;}
