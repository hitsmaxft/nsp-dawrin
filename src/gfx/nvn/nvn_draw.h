#pragma once
#import <Metal/Metal.h>
#include "nvn_obj.h"

// Shared by the command replay and the offscreen rendering regression test.
static inline void nvn_encode_array_draw(id encoder,
                                         MTLPrimitiveType primitive, const p_draw *draw) {
    if (draw->count <= 0 || draw->instances <= 0) return;
    [encoder drawPrimitives:primitive vertexStart:draw->first vertexCount:draw->count
             instanceCount:draw->instances baseInstance:draw->base_instance];
}
