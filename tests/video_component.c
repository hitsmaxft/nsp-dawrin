#include "../src/host/hle_video_component.c"
#include <assert.h>

struct NspVideoDecoder { NspVideoFrame frames[32]; unsigned read,write; };
static uint8_t pixels[24];
static unsigned inputs_returned,outputs_returned,errors,ports,destroyed,resets;
static int request_reset;
typedef struct { MediaList input,output; MediaNode in_head,out_head; } TestComponent;
NspVideoDecoder *nsp_video_decoder_create(const char *mime,int reorder){assert(!strcmp(mime,"video/avc"));return calloc(1,sizeof(NspVideoDecoder));}
void nsp_video_decoder_destroy(NspVideoDecoder *d){free(d);}
int nsp_video_decoder_reset(NspVideoDecoder *d){d->read=d->write=0;resets++;return 0;}
int nsp_video_decoder_info(NspVideoDecoder *d,NspVideoInfo *info){*info=(NspVideoInfo){4,4,100,0};return 0;}
int nsp_video_decoder_feed_timed(NspVideoDecoder *d,const uint8_t *bytes,size_t size,uint32_t id,int64_t time,size_t *used){
    assert(size==1);*used=1;if(*bytes==7)return NSP_VIDEO_FORMAT;
    d->frames[d->write++%32]=(NspVideoFrame){pixels,4,4,id,1};return NSP_VIDEO_FRAME;
}
int nsp_video_decoder_pop(NspVideoDecoder *d,NspVideoFrame *frame,int drain){
    if(d->read==d->write)return 0;*frame=d->frames[d->read++%32];return 1;
}
static MediaList *get_queue(void *self,unsigned port){TestComponent *c=self;return port?&c->output:&c->input;}
static void empty_done(void *self,void *header){inputs_returned++;}
static void fill_done(void *self,void *header){outputs_returned++;}
static void notify(void *self,unsigned event,unsigned a,unsigned b,void *data){assert(event==OMX_EventError);errors++;}
static void change(void *self,void *reset,unsigned w,unsigned h,int crop,unsigned fake){assert(w==4&&h==4&&fake==1);*(uint8_t *)reset=request_reset;}
static void copy(void *self,void *out,const void *y,const void *u,const void *v,uint64_t ys,uint64_t us,uint64_t vs){assert(ys==4&&us==2&&vs==2);memcpy(out,y,16);memcpy((char *)out+16,u,4);memcpy((char *)out+20,v,4);}
static void enable(void *self,unsigned port,unsigned on){assert(port==1&&on==1);}
static void init_ports(void *self,unsigned in,unsigned bytes,unsigned out,const char *mime,unsigned ratio){ports=out;}
static void destroy(void *self){assert(!component_state(self,0));destroyed++;}
static void flush(void *self,unsigned port){}
static void reset(void *self){}
void *guest_sym(const char *name){
    if(strstr(name,"getPortQueue"))return get_queue;
    if(!strcmp(name,"_ZdlPv"))return free;
    if(strstr(name,"notifyEmptyBufferDone"))return empty_done;
    if(strstr(name,"notifyFillBufferDone"))return fill_done;
    if(strstr(name,"6notify"))return notify;
    if(strstr(name,"handlePortSettingsChange"))return change;
    if(strstr(name,"copyYV12Frame"))return copy;
    if(strstr(name,"onPortEnableCompleted"))return enable;
    if(strstr(name,"initPorts"))return init_ports;
    if(strstr(name,"SoftAVCD"))return destroy;
    if(strstr(name,"onPortFlushCompleted"))return flush;
    if(strstr(name,"onReset"))return reset;
    abort();
}
static void initialize(TestComponent *c){
    memset(c,0,sizeof *c);c->input.head=&c->in_head;c->output.head=&c->out_head;
    c->in_head.prev=c->in_head.next=&c->in_head;c->out_head.prev=c->out_head.next=&c->out_head;
}
static void enqueue(MediaList *list,MediaBuffer *item){
    MediaNode *node=calloc(1,sizeof *node);*node=(MediaNode){item,list->head->prev,list->head};
    node->prev->next=node;list->head->prev=node;item->owned=1;
}
int main(void){
    TestComponent c;initialize(&c);memset(pixels,123,sizeof pixels);
    uint8_t packets[]={1,2,7,3},out_bytes[4][32]={{0}};
    OMX_BUFFERHEADERTYPE ih[4]={{0}},oh[4]={{0}};MediaBuffer in[4],out[4];
    for(unsigned i=0;i<4;i++){
        ih[i].pBuffer=&packets[i];ih[i].nAllocLen=ih[i].nFilledLen=1;ih[i].nTimeStamp=100+i;
        oh[i].pBuffer=out_bytes[i];oh[i].nAllocLen=32;in[i]=(MediaBuffer){&ih[i],0};out[i]=(MediaBuffer){&oh[i],0};
    }
    video_component_ports(&c,8,4096,2,"video/avc",2);assert(ports==8);
    video_component_ports(&c,8,4096,12,"video/avc",2);assert(ports==12);
    enqueue(&c.input,&in[0]);enqueue(&c.input,&in[1]);enqueue(&c.output,&out[0]);
    video_component_queue(&c,0);
    assert(inputs_returned==1&&outputs_returned==1&&!in[0].owned&&!out[0].owned);
    assert(oh[0].nTimeStamp==100&&oh[0].nFilledLen==24&&!memcmp(out_bytes[0],pixels,24));
    // A consumer still holds the first output. A second independent buffer must
    // make progress without waiting for the entire output pool to be returned.
    enqueue(&c.output,&out[1]);video_component_queue(&c,1);
    assert(inputs_returned==2&&outputs_returned==2&&oh[1].nTimeStamp==101);
    request_reset=1;enqueue(&c.input,&in[2]);enqueue(&c.input,&in[3]);enqueue(&c.output,&out[2]);
    video_component_queue(&c,0);assert(inputs_returned==3&&component_state(&c,0)->waiting);
    video_component_port(&c,1,1);assert(inputs_returned==4&&outputs_returned==3&&oh[2].nTimeStamp==103);
    video_component_flush(&c,0);assert(resets==1);
    ih[0].nFilledLen=0;ih[0].nOffset=0;ih[0].nFlags=OMX_BUFFERFLAG_EOS;
    enqueue(&c.input,&in[0]);enqueue(&c.output,&out[3]);video_component_queue(&c,0);
    assert(outputs_returned==4&&oh[3].nFlags==OMX_BUFFERFLAG_EOS&&!errors);
    video_component_reset(&c);assert(resets==2&&!component_state(&c,0)->eos);
    video_component_destroy(&c);assert(destroyed==1&&!components);
    puts("PASS: video buffer ownership, held-output progress, format reset, timestamps, EOS and teardown");
}
