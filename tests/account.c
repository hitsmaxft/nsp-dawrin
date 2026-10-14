#include "../src/host/hle_account.c"
#include <assert.h>

void hle_signal_system_event(void *event) { (void)event; }
int main(void) {
    UserHandle user = {0}; Uid uid = {0}, invalid = {0};
    assert(h_acc_TryOpenPre(&user));
    assert(h_acc_GetUserId(&uid, &user) == RES_OK);
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
    puts("PASS: local account profile image binding and invalid-user rejection");
}
