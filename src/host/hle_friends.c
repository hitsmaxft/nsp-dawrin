// The local profile has an empty contact list. No network account or remote
// session is created for local contact enumeration.
#include "hle.h"
static Result local_friends(int *count,void *output,const void *uid,int offset,int capacity) {
    if(count)*count=0;
    if(!count||!hle_account_is_local_uid(uid)||offset<0||capacity<0||(capacity&&!output))return RES_FAIL;
    return RES_OK;
}
HLE_FORCE("_ZN2nn7friends13GetFriendListEPiPNS0_6FriendERKNS_7account3UidEiiRKNS0_12FriendFilterE","Enumerate local profile contacts",Result,friends_list,int *count,void *output,const void *uid,int offset,int capacity,const void *filter) {
    (void)filter;return local_friends(count,output,uid,offset,capacity);
}
HLE_FORCE("_ZN2nn7friends13GetFriendListEPiPNS_7account23NetworkServiceAccountIdERKNS2_3UidEiiRKNS0_12FriendFilterE","Enumerate local profile contact identifiers",Result,friends_ids,int *count,void *output,const void *uid,int offset,int capacity,const void *filter) {
    (void)filter;return local_friends(count,output,uid,offset,capacity);
}
