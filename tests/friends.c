#include "../src/host/hle_friends.c"
#include <assert.h>
static int user;
int hle_account_is_local_uid(const void *uid){return uid==&user;}
int main(void){
    int count=42;uint8_t untouched[32];memset(untouched,0xa5,sizeof untouched);
    assert(!friends_list(&count,untouched,&user,0,1,NULL)&&count==0);
    for(unsigned i=0;i<sizeof untouched;i++)assert(untouched[i]==0xa5);
    assert(!friends_ids(&count,NULL,&user,100,0,NULL)&&count==0);
    assert(friends_list(&count,NULL,&user,0,1,NULL));
    assert(friends_list(&count,untouched,&user,-1,1,NULL));
    assert(friends_ids(&count,untouched,&user,0,-1,NULL));
    assert(friends_list(&count,untouched,NULL,0,1,NULL)&&count==0);
    assert(friends_list(NULL,untouched,&user,0,1,NULL));
    puts("PASS: local contact enumeration, pagination, output bounds and invalid users");
}
