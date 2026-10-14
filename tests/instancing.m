#import <Foundation/Foundation.h>
#include <assert.h>
#include "../src/gfx/nvn/nvn_draw.h"

int main(void) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        assert(device);
        NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct V { float4 p [[position]]; float size [[point_size]]; };\n"
            "vertex V vs(uint v [[vertex_id]], uint i [[instance_id]]) {\n"
            "  V o; o.p=float4((float(v)+.5)/4.-1.,1.-(float(i)+.5)/4.,0,1); o.size=1; return o; }\n"
            "fragment float4 fs() { return float4(1,0,0,1); }\n";
        NSError *error = nil;
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        assert(library && !error);
        MTLRenderPipelineDescriptor *pipeline = [MTLRenderPipelineDescriptor new];
        pipeline.vertexFunction = [library newFunctionWithName:@"vs"];
        pipeline.fragmentFunction = [library newFunctionWithName:@"fs"];
        pipeline.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> state = [device newRenderPipelineStateWithDescriptor:pipeline error:&error];
        assert(state && !error);
        MTLTextureDescriptor *description = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:8 height:8 mipmapped:NO];
        description.usage = MTLTextureUsageRenderTarget;
        description.storageMode = MTLStorageModeShared;
        id<MTLTexture> texture = [device newTextureWithDescriptor:description];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        const p_draw cases[] = {{0,2,3,0,1}, {0,2,3,1,2}, {0,2,3,1,0}, {0,2,0,1,2}};
        for (unsigned test = 0; test < sizeof cases / sizeof *cases; test++) {
            const p_draw *draw = &cases[test];
            MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
            pass.colorAttachments[0].texture = texture;
            pass.colorAttachments[0].loadAction = MTLLoadActionClear;
            pass.colorAttachments[0].storeAction = MTLStoreActionStore;
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
            [encoder setRenderPipelineState:state];
            nvn_encode_array_draw(encoder, MTLPrimitiveTypePoint, draw);
            [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
            assert(command.status == MTLCommandBufferStatusCompleted && !command.error);
            unsigned char pixels[8 * 8 * 4];
            [texture getBytes:pixels bytesPerRow:32 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
            for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) {
                bool expected = x >= draw->first && x < draw->first + draw->count &&
                                y >= draw->base_instance && y < draw->base_instance + draw->instances;
                assert(pixels[(y * 8 + x) * 4] == (expected ? 255 : 0));
                assert(pixels[(y * 8 + x) * 4 + 1] == 0 && pixels[(y * 8 + x) * 4 + 2] == 0);
            }
        }
        puts("PASS: array draw vertex offset, instance count, base instance and empty draws on Metal");
    }
}
