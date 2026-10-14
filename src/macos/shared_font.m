#include "shared_font.h"
#import <CoreText/CoreText.h>
#include <pthread.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static pthread_once_t font_once=PTHREAD_ONCE_INIT;
static const void *font_data;
static size_t font_size;
static void load_font(void){
    char path[4096];const char *override=getenv("NSP_SYSTEM_FONT");
    if(override&&*override){if(strlen(override)>=sizeof path)return;strcpy(path,override);}
    else {
        CTFontRef font=CTFontCreateWithName(CFSTR("ArialUnicodeMS"),12,NULL);
        CFURLRef url=font?(CFURLRef)CTFontCopyAttribute(font,kCTFontURLAttribute):NULL;
        int ok=url&&CFGetTypeID(url)==CFURLGetTypeID()&&CFURLGetFileSystemRepresentation(url,true,(UInt8 *)path,sizeof path);
        if(url)CFRelease(url);if(font)CFRelease(font);if(!ok)return;
    }
    int fd=open(path,O_RDONLY);if(fd<0)return;
    struct stat st;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size<12||st.st_size>128*1024*1024){close(fd);return;}
    void *data=mmap(NULL,(size_t)st.st_size,PROT_READ,MAP_PRIVATE,fd,0);close(fd);
    if(data==MAP_FAILED)return;
    const unsigned char *bytes=data;
    if(memcmp(bytes,"OTTO",4)&&memcmp(bytes,"ttcf",4)&&memcmp(bytes,"\0\1\0\0",4)){munmap(data,(size_t)st.st_size);return;}
    font_data=data;font_size=(size_t)st.st_size;
}
const void *native_shared_font(size_t *size){
    pthread_once(&font_once,load_font);if(size)*size=font_size;return font_data;
}
