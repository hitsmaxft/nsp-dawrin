#include "dir_count.h"
#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
int main(void) {
    char path[]="/tmp/nsp-directory-XXXXXX";
    assert(mkdtemp(path));
    char file[256],folder[256],metadata[256];
    snprintf(file,sizeof file,"%s/item",path);fclose(fopen(file,"w"));
    snprintf(folder,sizeof folder,"%s/folder",path);mkdir(folder,0700);
    snprintf(metadata,sizeof metadata,"%s/item.holes",path);fclose(fopen(metadata,"w"));
    DIR *directory=opendir(path);assert(directory);
    readdir(directory);long position=telldir(directory);
    assert(dm_directory_entry_count(directory,path,3)==2);
    assert(dm_directory_entry_count(directory,path,1)==1);
    assert(dm_directory_entry_count(directory,path,2)==1);
    assert(telldir(directory)==position);
    closedir(directory);unlink(file);unlink(metadata);rmdir(folder);rmdir(path);
    puts("Directory count filters and cursor preservation passed");
}
