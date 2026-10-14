#include "../src/host/hle_account.c"
#include <assert.h>

void hle_signal_system_event(void *event) { (void)event; }
int main(void) {
    UserHandle user = {0}; Uid uid = {0}, invalid = {0};
    assert(h_acc_TryOpenPre(&user));
    assert(h_acc_GetUserId(&uid, &user) == RES_OK);
    uint8_t available=1,exists=0;int count=123;
    assert(!account_network_available(&available,&user)&&available==0);
    assert(!account_count(&count)&&count==1);
    Uid list[2]={0};assert(!account_list_all(&count,list,2)&&count==1&&!memcmp(&list[0],&uid,sizeof uid));
    assert(!account_list_qualified(&count,NULL,0)&&count==0);
    assert(account_list_all(&count,NULL,1)&&count==0);
    assert(account_list_all(&count,list,-1));
    assert(!account_exists(&exists,&uid)&&exists==1);
    assert(!account_exists(&exists,&invalid)&&exists==0);
    assert(!account_last_user(&list[1])&&!memcmp(&list[1],&uid,sizeof uid));
    size_t size = nsp_profile_image_size(), written = 123;
    void *buffer = malloc(size);
    assert(h_acc_LoadProfileImage(&written, buffer, size, &invalid) != RES_OK);
    assert(written == 0);
    assert(h_acc_LoadProfileImage(&written, buffer, size - 1, &uid) != RES_OK);
    assert(written == 0);
    assert(h_acc_LoadProfileImage(&written, buffer, size, &uid) == RES_OK);
    assert(written == size);
    free(buffer); h_acc_Close(&user);
    assert(!user.v[2]);
    available=1;assert(account_network_available(&available,&user)&&!available);
    assert(!account_async_done(NULL,&available)&&available);assert(!account_async_cancel(NULL));
    puts("PASS: local account profile image binding and invalid-user rejection");
}
