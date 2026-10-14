#include "../src/macos/input.c"
#include <assert.h>
static NativePad pad;
uint64_t g_t0_ns;
uint64_t now_ns(void){return 0;}
NativePad native_controller_read(void){return pad;}
int main(void) {
    State state;uint32_t id=0;
    atomic_store(&native_buttons,1ull<<18);fill(&state,&id,1);assert(state.lx==32767 && state.buttons==(1ull<<18));
    atomic_store(&native_keyboard_buttons,1ull<<16);fill(&state,&id,1);assert(state.lx==0);
    atomic_store(&native_buttons,0);fill(&state,&id,1);assert(state.lx==-32767);
    pad.lx=1234;fill(&state,&id,1);assert(state.lx==1234);
    id=1;fill(&state,&id,1);assert(!state.buttons && !state.attributes && !state.lx);
    uint8_t args[7]={0,4,1,1,1,0,0};SupportResult result;
    assert(!hid_support(&result,args) && result.count==1 && result.selected==0);
    args[0]=2;assert(hid_support(&result,args) && !result.count);
    args[5]=1;assert(!hid_support(&result,args) && result.count==1);
    supported=2;assert(hid_support(&result,args));supported=1;
    hid_hold_set(1);assert(hid_hold_get()==1);hid_hold_set(99);assert(hid_hold_get()==1);
    puts("PASS: CLI stick directions, opposite inputs and controller axis precedence");
}
