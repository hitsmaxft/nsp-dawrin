#include "keyboard.h"
#include "hle.h"
#include <pthread.h>
#include <stdatomic.h>
typedef struct {uint64_t sampling,modifiers,keys[4];} KeyboardState;
_Static_assert(sizeof(KeyboardState)==48,"Keyboard state ABI");
static pthread_mutex_t keyboard_lock=PTHREAD_MUTEX_INITIALIZER;
static KeyboardState keyboard;
// macOS virtual key positions to USB HID keyboard usages.
static const uint8_t usages[128]={
    [0]=4,[1]=22,[2]=7,[3]=9,[4]=11,[5]=10,[6]=29,[7]=27,[8]=6,[9]=25,[11]=5,
    [12]=20,[13]=26,[14]=8,[15]=21,[16]=28,[17]=23,[18]=30,[19]=31,[20]=32,[21]=33,
    [22]=35,[23]=34,[24]=46,[25]=38,[26]=36,[27]=45,[28]=37,[29]=39,[30]=48,
    [31]=18,[32]=24,[33]=47,[34]=12,[35]=19,[36]=40,[37]=15,[38]=13,[39]=52,[40]=14,
    [41]=51,[42]=49,[43]=54,[44]=56,[45]=17,[46]=16,[47]=55,[48]=43,[49]=44,[50]=53,
    [51]=42,[53]=41,[54]=231,[55]=227,[56]=225,[58]=226,[59]=224,[60]=229,[61]=230,[62]=228,
    [64]=108,[65]=99,[67]=85,[69]=87,[71]=83,[75]=84,[76]=88,[78]=86,[79]=109,[80]=110,
    [81]=103,[82]=98,[83]=89,[84]=90,[85]=91,[86]=92,[87]=93,[88]=94,[89]=95,[90]=111,[91]=96,[92]=97,
    [96]=62,[97]=63,[98]=64,[99]=60,[100]=65,[101]=66,[103]=68,[105]=104,[106]=107,[107]=105,
    [109]=67,[111]=69,[113]=106,[114]=73,[115]=74,[116]=75,[117]=76,[118]=61,[119]=77,[120]=59,[121]=78,
    [122]=58,[123]=80,[124]=79,[125]=81,[126]=82
};
void native_keyboard_publish(const uint8_t held[128]){
    KeyboardState next={0};
    for(unsigned i=0;i<128;i++)if(held[i]&&usages[i])next.keys[usages[i]/64]|=1ull<<(usages[i]%64);
    next.modifiers=((held[59]||held[62])?1:0)|((held[56]||held[60])?2:0)|(held[58]?4:0)|(held[61]?8:0)|((held[54]||held[55])?16:0)|(held[57]?256:0);
    pthread_mutex_lock(&keyboard_lock);next.sampling=keyboard.sampling;keyboard=next;pthread_mutex_unlock(&keyboard_lock);
}
HLE_FORCE("_ZN2nn3hid18InitializeKeyboardEv","Use focused native keyboard events",void,keyboard_initialize,void){}
HLE_FORCE("_ZN2nn3hid17GetKeyboardStatesEPNS0_13KeyboardStateEi","Read physical keyboard state",int,keyboard_states,KeyboardState *out,int capacity){
    if(!out||capacity<=0)return 0;
    pthread_mutex_lock(&keyboard_lock);keyboard.sampling++;*out=keyboard;pthread_mutex_unlock(&keyboard_lock);return 1;
}
