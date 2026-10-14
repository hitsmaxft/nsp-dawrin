#import "../src/gfx/nvn/nvn_refl.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int parse(NSString *kind, int slot, char *error) {
    NSDictionary *json = @{@"route": @"B", @"bindings": @[
        @{@"kind": kind, @"reg": @(slot), @"arg_id": @0,
          @"msl_type": @"texture3d<float, access::write>"}]};
    nvn_refl reflection;
    return nvn_refl_from_json(json, &reflection, error, 256);
}
int main(void) {
    @autoreleasepool {
        char error[256];
        for (NSString *kind in @[@"img", @"cbuf", @"sbuf", @"ubo_ptr", @"tex", @"samp", @"samp_tex", @"tbuf"]) {
            int limit = [kind isEqual:@"img"] ? 32 :
                ([@[@"cbuf", @"sbuf", @"ubo_ptr"] containsObject:kind] ? 16 : 128);
            assert(!parse(kind, 0, error));
            assert(!parse(kind, limit - 1, error));
            assert(parse(kind, limit, error));
            assert(strstr(error, "exceeds"));
            assert(parse(kind, -1, error));
        }
        puts("PASS: reflection rejects out-of-range resources before replay");
    }
}
