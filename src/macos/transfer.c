#include "transfer.h"
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <pthread.h>
#include <stdio.h>
#define BASE 0x50000000u
#define BAD_HANDLE 0xe401u
#define INVALID 0xd401u
#define LIMIT 256
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static struct {uintptr_t address,mapped;size_t size;unsigned permission,generation;int active,isolated_copy;} ranges[LIMIT];
static int lookup(uint32_t handle) {
    unsigned slot=handle&255;
    return native_transfer_owns(handle) && slot && ranges[slot].active && ranges[slot].generation==((handle>>8)&0xfffff)?(int)slot:0;
}
int native_transfer_owns(uint32_t handle){return (handle&0xf0000000u)==BASE;}
uint32_t native_transfer_create(uintptr_t address,size_t size,unsigned permission,uint32_t *handle) {
    if(!handle || !address || !size || ((address|size)&4095) || size>UINTPTR_MAX-address || (permission!=0 && permission!=1 && permission!=3))return INVALID;
    mach_vm_address_t cursor=address,end=address+size;
    while(cursor<end) {
        mach_vm_address_t start=cursor;mach_vm_size_t length=0;mach_port_t object=MACH_PORT_NULL;
        vm_region_basic_info_data_64_t info;mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;
        kern_return_t result=mach_vm_region(mach_task_self(),&start,&length,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
        if(object)mach_port_deallocate(mach_task_self(),object);
        if(result!=KERN_SUCCESS || start>cursor || !(info.protection&VM_PROT_READ) || !(info.protection&VM_PROT_WRITE) || !length)return INVALID;
        cursor=start+length;
    }
    pthread_mutex_lock(&lock);unsigned slot=0;
    for(unsigned i=1;i<LIMIT;i++) {
        if(!ranges[i].active){if(!slot)slot=i;continue;}
        if(address<ranges[i].address+ranges[i].size && ranges[i].address<end){pthread_mutex_unlock(&lock);return INVALID;}
    }
    if(!slot){pthread_mutex_unlock(&lock);return 0xce01u;}
    ranges[slot].address=address;ranges[slot].size=size;ranges[slot].permission=permission;ranges[slot].active=1;ranges[slot].isolated_copy=0;
    ranges[slot].generation=(ranges[slot].generation+1)&0xfffff;
    *handle=BASE|(ranges[slot].generation<<8)|slot;
    pthread_mutex_unlock(&lock);return 0;
}
uint32_t native_transfer_close(uint32_t handle) {
    unsigned slot=handle&255;pthread_mutex_lock(&lock);
    int valid=lookup(handle) && !ranges[slot].mapped;
    if(valid)ranges[slot].active=0;
    pthread_mutex_unlock(&lock);return valid?0:BAD_HANDLE;
}
uint32_t native_transfer_map(uint32_t handle,uintptr_t destination,size_t size,unsigned permission) {
    pthread_mutex_lock(&lock);int slot=lookup(handle);uint32_t result=BAD_HANDLE;
    if(!slot)goto done;
    result=INVALID;
    if(ranges[slot].mapped || size!=ranges[slot].size || permission!=ranges[slot].permission || !destination || (destination&4095) || size>UINTPTR_MAX-destination-vm_page_size)goto done;
    uintptr_t mask=vm_page_size-1,source=ranges[slot].address;
    int isolated_copy=(destination&mask)!=(source&mask);
    if(isolated_copy && permission!=0) {
        fprintf(stderr,"[dm] Transfer memory subpage alignment differs: source=%#lx destination=%#lx\n",source,destination);goto done;
    }
    uintptr_t base=destination&~mask;size_t length=(size+(destination&mask)+mask)&~mask;
    mach_vm_address_t cursor=base,end=base+length;
    while(cursor<end) {
        mach_vm_address_t start=cursor;mach_vm_size_t span=0;mach_port_t object=MACH_PORT_NULL;
        vm_region_basic_info_data_64_t info;mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;
        kern_return_t rc=mach_vm_region(mach_task_self(),&start,&span,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
        if(object)mach_port_deallocate(mach_task_self(),object);
        if(rc!=KERN_SUCCESS || start>cursor || info.protection!=VM_PROT_NONE || !span)goto done;
        cursor=start+span;
    }
    mach_vm_address_t target=base;vm_prot_t current,maximum;
    if(isolated_copy) {
        // Permission None transfers exclusive ownership: the source is not
        // accessible to its guest owner until unmapping. For 4 KiB subpages on
        // a 16 KiB host, move contents at the two ownership boundaries.
        mach_vm_size_t copied=0;
        if(mach_vm_allocate(mach_task_self(),&target,length,VM_FLAGS_FIXED|VM_FLAGS_OVERWRITE)!=KERN_SUCCESS)goto done;
        if(mach_vm_read_overwrite(mach_task_self(),source,size,destination,&copied)!=KERN_SUCCESS || copied!=size) {
            mach_vm_protect(mach_task_self(),base,length,FALSE,VM_PROT_NONE);goto done;
        }
    } else if(mach_vm_remap(mach_task_self(),&target,length,0,VM_FLAGS_FIXED|VM_FLAGS_OVERWRITE,mach_task_self(),source&~mask,FALSE,&current,&maximum,VM_INHERIT_NONE)!=KERN_SUCCESS)goto done;
    ranges[slot].isolated_copy=isolated_copy;ranges[slot].mapped=destination;result=0;
done:pthread_mutex_unlock(&lock);return result;
}
uint32_t native_transfer_unmap(uint32_t handle,uintptr_t destination,size_t size) {
    pthread_mutex_lock(&lock);int slot=lookup(handle);uint32_t result=BAD_HANDLE;
    if(slot && destination && ranges[slot].mapped==destination && ranges[slot].size==size) {
        uintptr_t mask=vm_page_size-1;mach_vm_address_t base=destination&~mask;
        size_t length=(size+(destination&mask)+mask)&~mask;
        result=INVALID;
        if(ranges[slot].isolated_copy) {
            mach_vm_size_t copied=0;
            if(mach_vm_read_overwrite(mach_task_self(),destination,size,ranges[slot].address,&copied)!=KERN_SUCCESS || copied!=size)goto done;
        }
        if(mach_vm_allocate(mach_task_self(),&base,length,VM_FLAGS_FIXED|VM_FLAGS_OVERWRITE)==KERN_SUCCESS &&
           mach_vm_protect(mach_task_self(),base,length,FALSE,VM_PROT_NONE)==KERN_SUCCESS){ranges[slot].mapped=0;result=0;}
    }
done:pthread_mutex_unlock(&lock);return result;
}
