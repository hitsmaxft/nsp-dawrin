#include "nvn_commands.h"
#include "nvn_obj.h"
#include <stdlib.h>
#include <string.h>

enum { COPY_LIMIT = 128 * 1024 * 1024, COPY_STEPS = 1024 * 1024 };
typedef struct { uint8_t *data; size_t size, capacity; unsigned steps; } Snapshot;
static int collect(Snapshot *copy, const uint8_t *cursor, unsigned depth) {
    if (depth >= 16) return -1;
    for (;;) {
        if (!cursor || ((uintptr_t)cursor & 7) || !copy->steps--) return -1;
        op_hdr header; memcpy(&header,cursor,sizeof header);
        if (header.op >= OP_COUNT_ || header.size < 8 || (header.size & 7) || header.size > COPY_LIMIT) return -1;
        if (header.op == OP_END) return header.size == 8 ? 0 : -1;
        if (header.op == OP_JUMP || header.op == OP_CALL) {
            if (header.size != 16) return -1;
            const uint8_t *target; memcpy(&target,cursor+8,sizeof target);
            if (header.op == OP_JUMP) { cursor=target; continue; }
            if (collect(copy,target,depth+1)) return -1;
        } else if (header.op != OP_BEGIN) {
            if (copy->size > COPY_LIMIT-header.size) return -1;
            size_t needed=copy->size+header.size;
            if (needed > copy->capacity) {
                size_t capacity=copy->capacity ? copy->capacity : 4096;
                while (capacity < needed) capacity*=2;
                void *data=realloc(copy->data,capacity); if (!data) return -1;
                copy->data=data; copy->capacity=capacity;
            }
            memcpy(copy->data+copy->size,cursor,header.size); copy->size=needed;
        } else if (header.size != 8) return -1;
        cursor+=header.size;
    }
}
int nvn_copy_commands(int count,const uint64_t *handles,void *context,NvnCommandAllocate allocate) {
    if (count < 0 || (count && !handles) || !allocate) return -1;
    Snapshot copy={.steps=COPY_STEPS}; int result=-1;
    for (int i=0;i<count;i++) if (collect(&copy,(const uint8_t *)handles[i],0)) goto done;
    for (size_t offset=0;offset<copy.size;) {
        op_hdr header;memcpy(&header,copy.data+offset,sizeof header);
        void *destination=allocate(context,header.size);if (!destination) goto done;
        memcpy(destination,copy.data+offset,header.size);offset+=header.size;
    }
    result=0;
done:
    free(copy.data);return result;
}
