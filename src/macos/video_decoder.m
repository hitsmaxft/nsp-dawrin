#include "video_decoder.h"
#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#include <pthread.h>

typedef struct VideoFrameNode {
    NspVideoFrame frame;
    uint8_t *pixels;
    int64_t presentation_us;
    struct VideoFrameNode *next;
} VideoFrameNode;
struct NspVideoDecoder {
    VTDecompressionSessionRef session;
    CMVideoFormatDescriptionRef format;
    uint8_t *sps, *pps;
    size_t sps_size, pps_size;
    NspVideoInfo info;
    pthread_mutex_t mutex;
    VideoFrameNode *head, *current;
    size_t queued_bytes;
    unsigned queued_frames;
    int failed, no_reordering, dirty;
};
static void free_frame(VideoFrameNode *frame) { if (frame) { free(frame->pixels); free(frame); } }
static void decoded(void *context, void *source, OSStatus status, VTDecodeInfoFlags flags,
                    CVImageBufferRef image, CMTime pts, CMTime duration) {
    (void)flags; (void)duration;
    NspVideoDecoder *decoder = context;
    if (status || !image) { pthread_mutex_lock(&decoder->mutex); decoder->failed = 1; pthread_mutex_unlock(&decoder->mutex); return; }
    size_t width = CVPixelBufferGetWidth(image), height = CVPixelBufferGetHeight(image);
    size_t cw = (width + 1) / 2, ch = (height + 1) / 2, bytes = width * height + 2 * cw * ch;
    OSType format = CVPixelBufferGetPixelFormatType(image);
    VideoFrameNode *frame = NULL;
    if (!width || !height || width > 8192 || height > 8192 || CVPixelBufferGetPlaneCount(image) != 2 ||
        (format != kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange && format != kCVPixelFormatType_420YpCbCr8BiPlanarFullRange)) goto fail;
    frame = calloc(1, sizeof *frame);
    if (!frame || !(frame->pixels = malloc(bytes))) goto fail;
    if (CVPixelBufferLockBaseAddress(image, kCVPixelBufferLock_ReadOnly)) goto fail;
    const uint8_t *y = CVPixelBufferGetBaseAddressOfPlane(image, 0), *uv = CVPixelBufferGetBaseAddressOfPlane(image, 1);
    size_t ys = CVPixelBufferGetBytesPerRowOfPlane(image, 0), uvs = CVPixelBufferGetBytesPerRowOfPlane(image, 1);
    uint8_t *u = frame->pixels + width * height, *v = u + cw * ch;
    for (size_t row = 0; row < height; row++) memcpy(frame->pixels + row * width, y + row * ys, width);
    for (size_t row = 0; row < ch; row++) for (size_t col = 0; col < cw; col++) {
        u[row * cw + col] = uv[row * uvs + col * 2]; v[row * cw + col] = uv[row * uvs + col * 2 + 1];
    }
    CVPixelBufferUnlockBaseAddress(image, kCVPixelBufferLock_ReadOnly);
    uintptr_t token = (uintptr_t)source;
    frame->presentation_us = CMTimeConvertScale(pts,1000000,kCMTimeRoundingMethod_Default).value;
    frame->frame = (NspVideoFrame){frame->pixels, (uint32_t)width, (uint32_t)height, (uint32_t)(token >> 1), token & 1};
    pthread_mutex_lock(&decoder->mutex);
    if (decoder->queued_bytes + bytes > 256 * 1024 * 1024) { pthread_mutex_unlock(&decoder->mutex); goto fail; }
    VideoFrameNode **link=&decoder->head;
    while(*link&&(decoder->no_reordering||(*link)->presentation_us<=frame->presentation_us))link=&(*link)->next;
    frame->next=*link;*link=frame;decoder->queued_frames++;decoder->queued_bytes+=bytes;
    pthread_mutex_unlock(&decoder->mutex);
    return;
fail:
    free_frame(frame); pthread_mutex_lock(&decoder->mutex); decoder->failed = 1; pthread_mutex_unlock(&decoder->mutex);
}
static void close_session(NspVideoDecoder *decoder) {
    if (decoder->session) {
        VTDecompressionSessionFinishDelayedFrames(decoder->session);
        VTDecompressionSessionWaitForAsynchronousFrames(decoder->session);
        VTDecompressionSessionInvalidate(decoder->session); CFRelease(decoder->session); decoder->session = NULL;
    }
    if (decoder->format) { CFRelease(decoder->format); decoder->format = NULL; }
}
NspVideoDecoder *nsp_video_decoder_create(const char *mime, int no_reordering) {
    if (!mime || strcmp(mime, "video/avc")) return NULL;
    NspVideoDecoder *decoder = calloc(1, sizeof *decoder);
    if (decoder) { pthread_mutex_init(&decoder->mutex, NULL); decoder->no_reordering = !!no_reordering; }
    return decoder;
}
void nsp_video_decoder_destroy(NspVideoDecoder *decoder) {
    if (!decoder) return;
    close_session(decoder);
    while (decoder->head) { VideoFrameNode *next = decoder->head->next; free_frame(decoder->head); decoder->head = next; }
    free_frame(decoder->current); free(decoder->sps); free(decoder->pps);
    pthread_mutex_destroy(&decoder->mutex); free(decoder);
}
static int parameter_set(NspVideoDecoder *decoder, const uint8_t *data, size_t size, int sps) {
    uint8_t **target = sps ? &decoder->sps : &decoder->pps;
    size_t *length = sps ? &decoder->sps_size : &decoder->pps_size;
    if (size > 65536 || size < 2) return -1;
    if (*length == size && !memcmp(*target, data, size)) return 0;
    uint8_t *copy = malloc(size); if (!copy) return -1;
    memcpy(copy, data, size); free(*target); *target = copy; *length = size; decoder->dirty = 1;
    return 0;
}
static int create_session(NspVideoDecoder *decoder) {
    if (!decoder->sps || !decoder->pps || !decoder->dirty) return 0;
    close_session(decoder);
    const uint8_t *sets[] = {decoder->sps, decoder->pps}; size_t sizes[] = {decoder->sps_size, decoder->pps_size};
    OSStatus status = CMVideoFormatDescriptionCreateFromH264ParameterSets(kCFAllocatorDefault, 2, sets, sizes, 4, &decoder->format);
    if (status) return -1;
    CMVideoDimensions dimensions = CMVideoFormatDescriptionGetDimensions(decoder->format);
    if (dimensions.width <= 0 || dimensions.height <= 0 || dimensions.width > 8192 || dimensions.height > 8192) return -1;
    NSDictionary *attributes = @{(id)kCVPixelBufferPixelFormatTypeKey: @(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),
                                (id)kCVPixelBufferIOSurfacePropertiesKey: @{}};
    VTDecompressionOutputCallbackRecord callback = {decoded, decoder};
    status = VTDecompressionSessionCreate(kCFAllocatorDefault, decoder->format, NULL, (__bridge CFDictionaryRef)attributes, &callback, &decoder->session);
    if (status) return -1;
    decoder->info = (NspVideoInfo){dimensions.width, dimensions.height, decoder->sps[1], 0};
    fprintf(stderr,"[video] AVC format %ux%u profile=%u\n",decoder->info.width,decoder->info.height,decoder->info.profile);
    decoder->dirty = 0;
    return 1;
}
int nsp_video_decoder_reset(NspVideoDecoder *decoder) { @autoreleasepool {
    if(!decoder)return -1;
    close_session(decoder);
    while(decoder->head){VideoFrameNode *next=decoder->head->next;free_frame(decoder->head);decoder->head=next;}
    free_frame(decoder->current);decoder->current=NULL;
    decoder->queued_frames=0;decoder->queued_bytes=0;decoder->failed=0;decoder->dirty=1;
    return create_session(decoder)<0?-1:0;
} }
static size_t start_code(const uint8_t *data, size_t size, size_t offset, size_t *prefix) {
    for (size_t i = offset; i + 3 <= size; i++) if (!data[i] && !data[i+1]) {
        if (data[i+2] == 1) { *prefix = 3; return i; }
        if (i + 4 <= size && !data[i+2] && data[i+3] == 1) { *prefix = 4; return i; }
    }
    *prefix = 0; return size;
}
static int feed_internal(NspVideoDecoder *decoder, const uint8_t *data, size_t size, uint32_t picture_id, int64_t presentation_us, size_t *consumed) {
    if (consumed) *consumed = 0;
    if (!decoder || !data || !size || size > 64 * 1024 * 1024 || !consumed) return NSP_VIDEO_ERROR;
    size_t prefix = 0, first = start_code(data, size, 0, &prefix), begin = first < size ? first + prefix : 0;
    if (begin >= size) return NSP_VIDEO_ERROR;
    size_t unused, end = start_code(data, size, begin, &unused);
    unsigned type = data[begin] & 31;
    if (type == 7 || type == 8) {
        if (parameter_set(decoder, data + begin, end - begin, type == 7)) return NSP_VIDEO_ERROR;
        *consumed = end;
        // Recreate only after PPS, so a changed SPS is not paired with stale PPS.
        int changed = type == 8 ? create_session(decoder) : 0;
        return changed < 0 ? NSP_VIDEO_ERROR : changed ? NSP_VIDEO_FORMAT : NSP_VIDEO_CONSUMED;
    }
    if (!decoder->session) { *consumed = end; return NSP_VIDEO_CONSUMED; }
    NSMutableData *sample = [NSMutableData data]; unsigned key = 0, has_picture = 0;
    while (begin < size) {
        end = start_code(data, size, begin, &unused);
        size_t length = end - begin;
        if (!length || length > UINT32_MAX) return NSP_VIDEO_ERROR;
        type = data[begin] & 31; if (type == 5) key = 1; if (type == 1 || type == 5) has_picture = 1;
        uint32_t network_length = CFSwapInt32HostToBig((uint32_t)length);
        [sample appendBytes:&network_length length:4]; [sample appendBytes:data + begin length:length];
        begin = end + unused;
    }
    if (!has_picture) { *consumed = size; return NSP_VIDEO_CONSUMED; }
    CMBlockBufferRef block = NULL; CMSampleBufferRef buffer = NULL;
    OSStatus status = CMBlockBufferCreateWithMemoryBlock(kCFAllocatorDefault, NULL, sample.length, kCFAllocatorDefault, NULL, 0, sample.length, 0, &block);
    if (!status) status = CMBlockBufferReplaceDataBytes(sample.bytes, block, 0, sample.length);
    size_t sample_size = sample.length;
    CMSampleTimingInfo timing = {kCMTimeInvalid, CMTimeMake(presentation_us, 1000000), kCMTimeInvalid};
    if (!status) status = CMSampleBufferCreateReady(kCFAllocatorDefault, block, decoder->format, 1, 1, &timing, 1, &sample_size, &buffer);
    if (!status) status = VTDecompressionSessionDecodeFrame(decoder->session, buffer,
        0,
        (void *)(((uintptr_t)picture_id << 1) | key), NULL);
    if (!status) status = VTDecompressionSessionWaitForAsynchronousFrames(decoder->session);
    if (buffer) CFRelease(buffer); if (block) CFRelease(block);
    *consumed = size;
    pthread_mutex_lock(&decoder->mutex); int failed = decoder->failed; pthread_mutex_unlock(&decoder->mutex);
    if (status || failed) { fprintf(stderr, "[video] AVC decode failed: %d callback=%d\n", (int)status, failed); return NSP_VIDEO_ERROR; }
    return NSP_VIDEO_FRAME;
}
int nsp_video_decoder_feed_timed(NspVideoDecoder *decoder,const uint8_t *data,size_t size,uint32_t id,int64_t pts,size_t *consumed) {
    @autoreleasepool { return feed_internal(decoder,data,size,id,pts,consumed); }
}
int nsp_video_decoder_feed(NspVideoDecoder *decoder,const uint8_t *data,size_t size,uint32_t id,size_t *consumed) {
    return nsp_video_decoder_feed_timed(decoder,data,size,id,id,consumed);
}
int nsp_video_decoder_info(NspVideoDecoder *decoder, NspVideoInfo *info) {
    if (!decoder || !decoder->format || !info) return -1;
    *info = decoder->info; return 0;
}
int nsp_video_decoder_pop(NspVideoDecoder *decoder, NspVideoFrame *out, int drain) {
    if (!decoder || !out) return -1;
    if (drain && decoder->session) { VTDecompressionSessionFinishDelayedFrames(decoder->session); VTDecompressionSessionWaitForAsynchronousFrames(decoder->session); }
    pthread_mutex_lock(&decoder->mutex);
    free_frame(decoder->current); decoder->current = NULL;
    // H.264 bounds its decoded picture buffer at 16 frames. Retaining that
    // window makes timestamp ordering independent of callback arrival order.
    VideoFrameNode *frame = (!drain&&!decoder->no_reordering&&decoder->queued_frames<=16)?NULL:decoder->head;
    if (frame) {
        decoder->head = frame->next;
        decoder->current = frame; *out = frame->frame;decoder->queued_frames--;
        decoder->queued_bytes -= (size_t)out->width * out->height + 2 * ((out->width + 1) / 2) * ((out->height + 1) / 2);
    }
    int result = frame ? 1 : decoder->failed ? -1 : 0;
    pthread_mutex_unlock(&decoder->mutex); return result;
}
