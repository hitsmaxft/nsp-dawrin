#include "../src/macos/keyboard.c"
#include <assert.h>
int main(void){
    uint8_t held[128]={0};KeyboardState state={0};
    keyboard_initialize();assert(!keyboard_states(&state,0));assert(!keyboard_states(NULL,1));
    held[0]=held[56]=held[123]=1;native_keyboard_publish(held);
    assert(keyboard_states(&state,1)==1&&state.sampling==1&&state.modifiers==2);
    assert(state.keys[0]==(1ull<<4));assert(state.keys[1]==(1ull<<(80-64)));assert(state.keys[3]==(1ull<<(225-192)));
    held[0]=0;native_keyboard_publish(held);keyboard_states(&state,1);assert(!state.keys[0]&&state.sampling==2);
    memset(held,0,sizeof held);native_keyboard_publish(held);keyboard_states(&state,1);
    assert(!state.modifiers&&!state.keys[0]&&!state.keys[1]&&!state.keys[2]&&!state.keys[3]);
    puts("PASS: raw keyboard ABI, physical key positions, modifiers, sampling and focus release");
}
