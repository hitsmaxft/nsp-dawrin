#pragma once
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static inline int64_t dm_directory_entry_count(DIR *directory, const char *path, int mode) {
    (void)path;
    // A separate open file description preserves the caller's directory cursor.
    int fd = openat(dirfd(directory), ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) return -1;
    DIR *scan = fdopendir(fd);
    if (!scan) { close(fd); return -1; }
    int64_t count = 0;
    struct dirent *entry;
    for (;;) {
        errno = 0;
        entry = readdir(scan);
        if (!entry) { if (errno) count = -1; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        size_t length = strlen(entry->d_name);
        if (length > 6 && !strcmp(entry->d_name + length - 6, ".holes")) continue;
        struct stat status;
        if (fstatat(fd, entry->d_name, &status, 0)) { count = -1; break; }
        if (mode & (S_ISDIR(status.st_mode) ? 1 : 2)) count++;
    }
    closedir(scan);
    return count;
}
