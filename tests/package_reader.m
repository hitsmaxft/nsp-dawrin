#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <assert.h>
#include <errno.h>
extern void dm_package_note_fd(int, const char *);
extern void dm_package_forget_fd(int);
extern ssize_t dm_package_pread(int, void *, size_t, off_t);

int main(int argc, char **argv) {
    assert(argc == 4);
    int fd = open(argv[1], O_RDONLY); assert(fd >= 0);
    dm_package_note_fd(fd, argv[1]);
    size_t size = strtoull(argv[3], NULL, 10);
    unsigned char *buffer = malloc(size ? size : 1); assert(buffer);
    ssize_t n = dm_package_pread(fd, buffer, size, strtoll(argv[2], NULL, 10));
    if (n < 0) { perror("packed read"); return 1; }
    assert(fwrite(buffer, 1, n, stdout) == n);
    dm_package_forget_fd(fd);
    assert(dm_package_pread(fd, buffer, size, 0) == -2);
    free(buffer); close(fd);
}
