#pragma once
#include <stddef.h>
#include <stdint.h>

typedef struct NspVideoDecoder NspVideoDecoder;
typedef struct { uint32_t width, height, profile, full_range; } NspVideoInfo;
typedef struct {
    const uint8_t *i420;
    uint32_t width, height, picture_id, key_frame;
} NspVideoFrame;
enum { NSP_VIDEO_ERROR = -1, NSP_VIDEO_CONSUMED = 1, NSP_VIDEO_FRAME = 3, NSP_VIDEO_FORMAT = 4 };
NspVideoDecoder *nsp_video_decoder_create(const char *mime, int no_reordering);
void nsp_video_decoder_destroy(NspVideoDecoder *decoder);
int nsp_video_decoder_reset(NspVideoDecoder *decoder);
int nsp_video_decoder_feed(NspVideoDecoder *decoder, const uint8_t *data, size_t size,
                           uint32_t picture_id, size_t *consumed);
int nsp_video_decoder_feed_timed(NspVideoDecoder *decoder, const uint8_t *data, size_t size,
                                 uint32_t picture_id, int64_t presentation_us, size_t *consumed);
int nsp_video_decoder_info(NspVideoDecoder *decoder, NspVideoInfo *info);
// Frame storage belongs to the decoder until the next pop or destruction.
int nsp_video_decoder_pop(NspVideoDecoder *decoder, NspVideoFrame *frame, int drain);
