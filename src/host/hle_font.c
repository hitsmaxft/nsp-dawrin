#include "hle.h"
#include "../macos/shared_font.h"
static const void *shared_font(int type,size_t *size){
    if(size)*size=0;
    return type>=0&&type<6?native_shared_font(size):NULL;
}
HLE_FORCE("_ZN2nn2pl22GetSharedFontLoadStateENS0_14SharedFontTypeE","Query installed host font availability",int,font_state,int type){return shared_font(type,NULL)?1:0;}
HLE_FORCE("_ZN2nn2pl21RequestSharedFontLoadENS0_14SharedFontTypeE","Load an installed host font",void,font_load,int type){(void)shared_font(type,NULL);}
HLE_FORCE("_ZN2nn2pl20GetSharedFontAddressENS0_14SharedFontTypeE","Read installed host font bytes",const void *,font_address,int type){return shared_font(type,NULL);}
HLE_FORCE("_ZN2nn2pl17GetSharedFontSizeENS0_14SharedFontTypeE","Read installed host font byte count",size_t,font_size,int type){size_t size;shared_font(type,&size);return size;}
