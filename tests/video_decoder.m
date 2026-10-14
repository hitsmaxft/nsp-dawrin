#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#include "../src/macos/video_decoder.h"
#include <assert.h>

typedef struct { NspVideoDecoder *decoder; unsigned frames, formats, total; int reorder, previous_encoded, saw_reordering; } Test;
static void receive_frames(Test *test, int drain) {
    NspVideoFrame frame;
    int result;
    while ((result=nsp_video_decoder_pop(test->decoder,&frame,drain))==1) {
        assert(frame.width==64&&frame.height==48&&frame.picture_id<test->total);
        unsigned long sum=0;for(unsigned i=0;i<64*48;i++)sum+=frame.i420[i];
        double expected=32+(test->reorder?2:64)*frame.picture_id;
        assert(frame.picture_id==test->frames);
        if(!test->reorder)assert(frame.key_frame);
        assert(fabs((double)sum/(64*48)-expected)<4);
        unsigned long u=0,v=0;for(unsigned i=0;i<64*48/4;i++){u+=frame.i420[64*48+i];v+=frame.i420[64*48*5/4+i];}
        assert(fabs((double)u/(64*48/4)-(96+frame.picture_id))<4);
        assert(fabs((double)v/(64*48/4)-(160-frame.picture_id))<4);
        test->frames++;
    }
    assert(result==0);
}
static void feed(Test *test, const uint8_t *data, size_t size, uint32_t id) {
    while(size) {
        size_t consumed=0;int result=nsp_video_decoder_feed_timed(test->decoder,data,size,id,(int64_t)id*1000000/30,&consumed);
        assert(result>0&&consumed>0&&consumed<=size);
        if(result==NSP_VIDEO_FORMAT) {
            NspVideoInfo info;assert(!nsp_video_decoder_info(test->decoder,&info));
            assert(info.width==64&&info.height==48&&info.profile==100);test->formats++;
        }
        data+=consumed;size-=consumed;receive_frames(test,0);
    }
}
static void encoded(void *context,void *source,OSStatus status,VTEncodeInfoFlags flags,CMSampleBufferRef sample) {
    (void)flags;assert(!status&&sample);Test *test=context;uint32_t id=(uint32_t)(uintptr_t)source;
    if((int)id<test->previous_encoded)test->saw_reordering=1;test->previous_encoded=id;
    CMFormatDescriptionRef format=CMSampleBufferGetFormatDescription(sample);
    NSMutableData *annex=[NSMutableData data];const uint8_t prefix[]={0,0,0,1};
    for(size_t i=0;i<2;i++) {
        const uint8_t *parameter;size_t size;
        assert(!CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format,i,&parameter,&size,NULL,NULL));
        [annex appendBytes:prefix length:4];[annex appendBytes:parameter length:size];
    }
    CMBlockBufferRef block=CMSampleBufferGetDataBuffer(sample);size_t size=CMBlockBufferGetDataLength(block);
    uint8_t *bytes=malloc(size);assert(bytes&&!CMBlockBufferCopyDataBytes(block,0,size,bytes));
    for(size_t offset=0;offset<size;) {
        assert(size-offset>=4);uint32_t length;memcpy(&length,bytes+offset,4);length=CFSwapInt32BigToHost(length);offset+=4;
        assert(length&&length<=size-offset);[annex appendBytes:prefix length:4];[annex appendBytes:bytes+offset length:length];offset+=length;
    }
    feed(test,annex.bytes,annex.length,id);free(bytes);
}
static void run(int reorder) { @autoreleasepool {
    assert(!nsp_video_decoder_create("invalid",0));
    Test test={.decoder=nsp_video_decoder_create("video/avc",!reorder),.total=reorder?64:3,.reorder=reorder,.previous_encoded=-1};assert(test.decoder);
    NspVideoInfo info;assert(nsp_video_decoder_info(test.decoder,&info)<0);
    size_t consumed=9;assert(nsp_video_decoder_feed(test.decoder,NULL,0,0,&consumed)<0&&consumed==0);
    VTCompressionSessionRef encoder=NULL;
    assert(!VTCompressionSessionCreate(kCFAllocatorDefault,64,48,kCMVideoCodecType_H264,NULL,NULL,NULL,encoded,&test,&encoder));
    assert(!VTSessionSetProperty(encoder,kVTCompressionPropertyKey_ProfileLevel,kVTProfileLevel_H264_High_AutoLevel));
    assert(!VTSessionSetProperty(encoder,kVTCompressionPropertyKey_AllowFrameReordering,reorder?kCFBooleanTrue:kCFBooleanFalse));
    assert(!VTCompressionSessionPrepareToEncodeFrames(encoder));
    for(unsigned i=0;i<test.total;i++) {
        CVPixelBufferRef image=NULL;
        NSDictionary *attributes=@{(id)kCVPixelBufferIOSurfacePropertiesKey:@{}};
        assert(!CVPixelBufferCreate(kCFAllocatorDefault,64,48,kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,(__bridge CFDictionaryRef)attributes,&image));
        assert(!CVPixelBufferLockBaseAddress(image,0));
        for(size_t row=0;row<48;row++)memset((uint8_t *)CVPixelBufferGetBaseAddressOfPlane(image,0)+row*CVPixelBufferGetBytesPerRowOfPlane(image,0),32+(reorder?2:64)*i,64);
        for(size_t row=0;row<24;row++)for(size_t col=0;col<32;col++){
            uint8_t *uv=(uint8_t *)CVPixelBufferGetBaseAddressOfPlane(image,1)+row*CVPixelBufferGetBytesPerRowOfPlane(image,1)+col*2;
            uv[0]=96+i;uv[1]=160-i;
        }
        CVPixelBufferUnlockBaseAddress(image,0);
        NSDictionary *options=reorder?nil:@{(id)kVTEncodeFrameOptionKey_ForceKeyFrame:@YES};
        assert(!VTCompressionSessionEncodeFrame(encoder,image,CMTimeMake(i,30),CMTimeMake(1,30),(__bridge CFDictionaryRef)options,(void *)(uintptr_t)i,NULL));
        CVPixelBufferRelease(image);
    }
    assert(!VTCompressionSessionCompleteFrames(encoder,kCMTimeInvalid));
    receive_frames(&test,1);assert(test.frames==test.total&&test.formats==1);
    VTCompressionSessionInvalidate(encoder);CFRelease(encoder);nsp_video_decoder_destroy(test.decoder);
    printf("PASS: native AVC pixels, frame identity and drain; frames=%u reordered_input=%d\n",test.frames,test.saw_reordering);
    if(reorder)assert(test.saw_reordering);
} }

int main(void){run(0);run(1);}
