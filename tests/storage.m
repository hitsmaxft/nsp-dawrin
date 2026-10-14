#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "storage.h"
#include "content.h"

int main(int argc,char **argv) {
    int64_t data,journal,available,total;
    assert(argc==2);
    assert(native_save_ensure()==0);
    assert(native_save_sizes(&data,&journal)==0);
    if(!strcmp(argv[1],"extend")) {
        assert(data==4096 && journal==4096);
        assert(native_save_extend(8192,4096)==0);
        assert(native_save_extend(4096,4096)==EINVAL);
        assert(native_save_extend(-1,0)==EINVAL);
    } else assert(data==8192 && journal==4096);
    assert(native_storage_space("/tmp",&available,&total)==0 && total>=available);
    assert(native_content_count()==1);
    int index=-1;assert(native_content_list(&index,1,0)==1 && index==1);
    assert(native_content_list(&index,1,1)==0);
    assert(native_content_list(NULL,1,0)==-1);
    char root[1024];assert(native_content_root(1,root,sizeof root));
    assert(!native_content_root(2,root,sizeof root));
    puts("PASS: content enumeration, save allocation persistence and storage bounds");
}
