#include "services.h"
#include <string.h>
#define BAD_REQUEST 0xf001u
#define UNSUPPORTED 0x2a2u
static uint32_t u32(const void *p){uint32_t value;memcpy(&value,p,4);return value;}
static void put32(void *p,uint32_t value){memcpy(p,&value,4);}
static const char *languages[]={"ja","en-US","fr","de","it","es","zh-CN","ko","nl","pt","ru","zh-TW","en-GB","fr-CA","es-419","zh-Hans","zh-Hant","pt-BR"};
static uint64_t language(unsigned index){uint64_t code=0;if(index<sizeof languages/sizeof *languages)memcpy(&code,languages[index],strlen(languages[index]));return code;}
uint32_t compat_settings_service(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
    uint64_t code;uint32_t count=sizeof languages/sizeof *languages;
    switch(command){
        case 0:code=language(15);memcpy(reply->data,&code,8);reply->size=8;return 0;
        case 2:if(size<4 || u32(input)>=count)return BAD_REQUEST;code=language(u32(input));memcpy(reply->data,&code,8);reply->size=8;return 0;
        case 3:case 6:put32(reply->data,count);reply->size=4;return 0;
        case 1:case 5:
            if(output.size && !output.data)return BAD_REQUEST;
            if(count>output.size/8)count=output.size/8;
            uint64_t codes[18];for(unsigned i=0;i<count;i++)codes[i]=language(i);
            uint32_t result=native_ipc_write(output,codes,count*8);if(result)return result;
            put32(reply->data,count);reply->size=4;return 0;
        default:return UNSUPPORTED;
    }
}
