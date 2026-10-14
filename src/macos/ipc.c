// Bounded HIPC/CMIF transport; layouts checked against libnx (ISC notice retained).
#include "ipc.h"
#include <pthread.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>

#define BAD_HANDLE 0xe401u
#define BAD_REQUEST 0xf001u
#define UNSUPPORTED 0x2a2u
#define HANDLE_BASE 0x60000000u
#define MAX_SESSIONS 256
#define MAX_SERVICES 32
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static struct {char name[9];NativeServiceHandler handler;} services[MAX_SERVICES];
static struct {unsigned service;int active,domain,closed;uint32_t generation;} sessions[MAX_SESSIONS];
static unsigned service_count;
static pthread_once_t once=PTHREAD_ONCE_INIT;
static uint32_t u32(const void *p){uint32_t value;memcpy(&value,p,4);return value;}
static void put32(void *p,uint32_t value){memcpy(p,&value,4);}
static const char *languages[]={"ja","en-US","fr","de","it","es","zh-CN","ko","nl","pt","ru","zh-TW","en-GB","fr-CA","es-419","zh-Hans","zh-Hant","pt-BR"};
static uint64_t language(unsigned index){uint64_t code=0;if(index<sizeof languages/sizeof *languages)memcpy(&code,languages[index],strlen(languages[index]));return code;}
uint32_t native_ipc_write(NativeIpcBuffer output,const void *data,size_t size) {
    if(size>output.size || size>UINT32_MAX || (size && (!output.data || !data)))return BAD_REQUEST;
    if(!size)return 0;
    return mach_vm_write(mach_task_self(),(mach_vm_address_t)output.data,(vm_offset_t)data,(mach_msg_type_number_t)size)==KERN_SUCCESS?0:BAD_REQUEST;
}
static uint32_t settings(uint32_t command,const void *input,size_t size,NativeIpcBuffer output,NativeIpcReply *reply) {
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
static void initialize(void) {
    strcpy(services[0].name,"sm:");strcpy(services[1].name,"set");services[1].handler=settings;service_count=2;
}
int native_ipc_register(const char *name,NativeServiceHandler handler) {
    if(!name || !handler || !*name || strlen(name)>8)return 0;
    pthread_once(&once,initialize);pthread_mutex_lock(&mutex);int okay=service_count<MAX_SERVICES;
    for(unsigned i=0;i<service_count;i++)if(!strcmp(name,services[i].name))okay=0;
    if(okay){strcpy(services[service_count].name,name);services[service_count++].handler=handler;}
    pthread_mutex_unlock(&mutex);return okay;
}
static uint32_t allocate(unsigned service) {
    for(unsigned i=1;i<MAX_SESSIONS;i++)if(!sessions[i].active){
        sessions[i].active=1;sessions[i].domain=0;sessions[i].closed=0;sessions[i].service=service;
        sessions[i].generation=(sessions[i].generation+1)&0xfffff;
        return HANDLE_BASE|(sessions[i].generation<<8)|i;
    }
    return 0;
}
int native_ipc_owns(uint32_t handle){return (handle&0xf0000000u)==HANDLE_BASE;}
static int lookup(uint32_t handle) {
    unsigned index=handle&255;
    return native_ipc_owns(handle) && index && sessions[index].active && sessions[index].generation==((handle>>8)&0xfffff)?(int)index:-1;
}
uint32_t native_ipc_connect(const char *name,uint32_t *handle) {
    if(!name || !handle)return BAD_REQUEST;pthread_once(&once,initialize);pthread_mutex_lock(&mutex);
    uint32_t result=UNSUPPORTED;
    for(unsigned i=0;i<service_count;i++)if(!strcmp(name,services[i].name)){
        *handle=allocate(i);result=*handle?0:BAD_REQUEST;break;
    }
    if(result)fprintf(stderr,"[dm] Unsupported IPC service: %.8s\n",name);
    pthread_mutex_unlock(&mutex);return result;
}
uint32_t native_ipc_close(uint32_t handle) {
    pthread_once(&once,initialize);pthread_mutex_lock(&mutex);int index=lookup(handle);
    if(index>=0)sessions[index].active=0;
    pthread_mutex_unlock(&mutex);return index>=0?0:BAD_HANDLE;
}
static uint32_t transact(unsigned index,unsigned char *buffer,size_t size) {
    if(size<64 || size>0x1000 || sessions[index].closed)return BAD_REQUEST;
    uint32_t h0=u32(buffer),h1=u32(buffer+4),type=h0&65535;
    if(type==2){sessions[index].closed=1;return 0;}
    if(type!=4 && type!=5 && type!=6 && type!=7)return BAD_REQUEST;
    size_t cursor=8;
    if(h1>>31){
        uint32_t special=u32(buffer+cursor);cursor+=4;
        cursor+=(special&1)?8:0;cursor+=4*((special>>1&15)+(special>>5&15));
    }
    unsigned statics=h0>>16&15,send=h0>>20&15,receive=h0>>24&15,exchange=h0>>28&15;
    size_t descriptors=statics*8+(send+receive+exchange)*12;
    if(cursor>size || descriptors>size-cursor)return BAD_REQUEST;
    NativeIpcBuffer output={0};
    if(receive){
        const unsigned char *p=buffer+cursor+statics*8+send*12;uint32_t packed=u32(p+8);
        output.data=(void *)(uintptr_t)((uint64_t)u32(p+4)|((uint64_t)(packed>>28)<<32)|((uint64_t)(packed>>2&0x3fffff)<<36));
        output.size=(uint64_t)u32(p)|((uint64_t)(packed>>24&15)<<32);
    }
    cursor+=descriptors;size_t raw_size=(h1&1023)*4,raw=cursor,aligned=(cursor+15)&~(size_t)15;
    if(raw_size>size-raw || aligned+16>raw+raw_size)return BAD_REQUEST;
    unsigned receive_mode=h1>>10&15;
    if(!receive && receive_mode>=2 && raw+raw_size+8<=size){
        const unsigned char *p=buffer+raw+raw_size;uint32_t hi=u32(p+4);
        output.data=(void *)(uintptr_t)((uint64_t)u32(p)|((uint64_t)(hi&65535)<<32));output.size=hi>>16;
    }
    int control=type==5 || type==7,domain=sessions[index].domain && !control;
    size_t payload=aligned;
    size_t payload_end=raw+raw_size;
    if(domain){
        if(buffer[payload]==2 && u32(buffer+payload+4)==1){sessions[index].closed=1;memset(buffer,0,size);return 0;}
        if(buffer[payload]!=1 || buffer[payload+1] || u32(buffer+payload+4)!=1)return BAD_REQUEST;
        unsigned length=(unsigned)buffer[payload+2]|((unsigned)buffer[payload+3]<<8);
        payload+=16;if(length<16 || length>payload_end-payload)return BAD_REQUEST;
        payload_end=payload+length;
    }
    if(u32(buffer+payload)!=0x49434653)return BAD_REQUEST;
    uint32_t command=u32(buffer+payload+8),token=u32(buffer+payload+12),result=0,moved=0;
    const void *input=buffer+payload+16;size_t input_size=payload_end-payload-16;
    NativeIpcReply reply={0};unsigned service=sessions[index].service;
    if(control){
        switch(command){
            case 0:sessions[index].domain=1;put32(reply.data,1);reply.size=4;break;
            case 2:case 4:moved=allocate(service);if(!moved)result=BAD_REQUEST;break;
            case 3:put32(reply.data,0);reply.size=2;break;
            default:result=UNSUPPORTED;
        }
    } else if(service==0){
        if(command==0)result=0;
        else if(command==1 && input_size>=8){
            char name[9]={0};memcpy(name,input,8);result=UNSUPPORTED;
            for(unsigned i=1;i<service_count;i++)if(!strcmp(name,services[i].name)){moved=allocate(i);result=moved?0:BAD_REQUEST;break;}
            if(result)fprintf(stderr,"[dm] Unsupported IPC service: %.8s\n",name);
        } else result=UNSUPPORTED;
    } else result=services[service].handler(command,input,input_size,output,&reply);
    if(result==UNSUPPORTED)fprintf(stderr,"[dm] Unsupported IPC command: %s:%u\n",services[service].name,command);
    if(reply.size>sizeof reply.data)return BAD_REQUEST;
    size_t words=(16+(domain?16:0)+16+reply.size+3)/4;
    if(16+words*4>size)return BAD_REQUEST;
    memset(buffer,0,size);put32(buffer+4,(uint32_t)words|(moved?0x80000000u:0));
    if(moved){put32(buffer+8,1u<<5);put32(buffer+12,moved);}
    size_t out=16;if(domain)out+=16;
    put32(buffer+out,0x4f434653);put32(buffer+out+8,result);put32(buffer+out+12,token);
    memcpy(buffer+out+16,reply.data,reply.size);return 0;
}
uint32_t native_ipc_transact(uint32_t handle,void *buffer,size_t size) {
    if(!buffer)return BAD_REQUEST;pthread_once(&once,initialize);pthread_mutex_lock(&mutex);
    int index=lookup(handle);uint32_t result=index<0?BAD_HANDLE:transact(index,buffer,size);
    pthread_mutex_unlock(&mutex);return result;
}
