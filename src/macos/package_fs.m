// Read indexed resources directly from an encrypted base package.
#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonCryptor.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <stdatomic.h>

static NSDictionary *manifest, *files;
static NSString *root;
static int package_fd = -1;
static uint64_t package_offset;
static unsigned char key[16], prefix[8];
static BOOL encrypted;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct { uint64_t offset, size; int valid; } handles[4096];
_Atomic uint64_t native_package_reads, native_package_bytes;

static void fail(const char *message) {
    fprintf(stderr, "Package reader: %s\n", message); exit(1);
}
static void initialize(void) {
    const char *path = getenv("DM_PACKAGE_INDEX"); if (!path || !*path) return;
    @autoreleasepool {
        NSData *data = [NSData dataWithContentsOfFile:@(path)];
        manifest = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        if (![manifest isKindOfClass:NSDictionary.class] || [manifest[@"version"] intValue] != 1)
            fail("Invalid resource index");
        files = manifest[@"files"]; root = [manifest[@"root"] stringByStandardizingPath];
        package_fd = open([manifest[@"package"] fileSystemRepresentation], O_RDONLY | O_CLOEXEC);
        struct stat st;
        if (package_fd < 0 || fstat(package_fd, &st) || st.st_size != [manifest[@"package_bytes"] longLongValue])
            fail("Original package is unavailable or has changed");
        package_offset = [manifest[@"nca_offset"] unsignedLongLongValue];
        encrypted = [manifest[@"encrypted"] boolValue];
        NSData *secret = [NSData dataWithContentsOfFile:manifest[@"key_file"]];
        if (secret.length != sizeof key) fail("Invalid local key cache");
        memcpy(key, secret.bytes, sizeof key);
        NSString *hex = manifest[@"ctr_prefix"];
        if (hex.length != 16) fail("Invalid counter prefix");
        for (unsigned i = 0; i < 8; i++) {
            unsigned value;
            if (sscanf([[hex substringWithRange:NSMakeRange(i*2, 2)] UTF8String], "%2x", &value) != 1)
                fail("Invalid counter prefix");
            prefix[i] = value;
        }
    }
}

void dm_package_forget_fd(int fd) {
    if (fd < 0 || fd >= 4096) return;
    pthread_mutex_lock(&lock); handles[fd].valid = 0; pthread_mutex_unlock(&lock);
}
void dm_package_note_fd(int fd, const char *path) {
    pthread_once(&once, initialize);
    dm_package_forget_fd(fd);
    if (package_fd < 0 || fd < 0 || fd >= 4096) return;
    @autoreleasepool {
        NSString *host = [@(path) stringByStandardizingPath];
        NSString *base = [root stringByAppendingString:@"/"];
        if (![host hasPrefix:base]) return;
        NSArray *entry = files[[host substringFromIndex:base.length]];
        if (![entry isKindOfClass:NSArray.class] || entry.count != 2) fail("Resource is absent from index");
        uint64_t offset = [entry[0] unsignedLongLongValue], size = [entry[1] unsignedLongLongValue];
        uint64_t total = [manifest[@"package_bytes"] unsignedLongLongValue];
        if (package_offset > total || offset > total - package_offset || size > total - package_offset - offset)
            fail("Resource extends beyond package bounds");
        pthread_mutex_lock(&lock);
        handles[fd].offset = offset; handles[fd].size = size; handles[fd].valid = 1;
        pthread_mutex_unlock(&lock);
    }
}

// -2 means the descriptor belongs to an ordinary host file.
ssize_t dm_package_pread(int fd, void *buffer, size_t length, off_t offset) {
    if (fd < 0 || fd >= 4096) return -2;
    pthread_mutex_lock(&lock); typeof(handles[0]) entry = handles[fd]; pthread_mutex_unlock(&lock);
    if (!entry.valid) return -2;
    if (offset < 0) { errno = EINVAL; return -1; }
    if ((uint64_t)offset >= entry.size || !length) return 0;
    if (length > entry.size - offset) length = entry.size - offset;
    if (length > (size_t)SSIZE_MAX - 32) { errno = EOVERFLOW; return -1; }
    uint64_t position = entry.offset + offset, aligned = position & ~15ull;
    size_t skip = position - aligned, count = (skip + length + 15) & ~(size_t)15;
    unsigned char *data = malloc(count);
    if (!data) { errno = ENOMEM; return -1; }
    size_t got = 0;
    while (got < count) {
        ssize_t n = pread(package_fd, data + got, count - got, package_offset + aligned + got);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { free(data); if (!n) errno = EIO; return -1; }
        got += n;
    }
    if (encrypted) {
        unsigned char iv[16]; memcpy(iv, prefix, 8);
        uint64_t counter = aligned / 16;
        for (unsigned i = 0; i < 8; i++) iv[15-i] = counter >> (8*i);
        CCCryptorRef cryptor = NULL; size_t written = 0;
        CCCryptorStatus result = CCCryptorCreateWithMode(kCCDecrypt, kCCModeCTR, kCCAlgorithmAES,
            ccNoPadding, iv, key, sizeof key, NULL, 0, 0, kCCModeOptionCTR_BE, &cryptor);
        if (result == kCCSuccess) result = CCCryptorUpdate(cryptor, data, count, data, count, &written);
        if (cryptor) CCCryptorRelease(cryptor);
        if (result != kCCSuccess || written != count) { free(data); errno = EIO; return -1; }
    }
    memcpy(buffer, data + skip, length); free(data);
    atomic_fetch_add(&native_package_reads, 1); atomic_fetch_add(&native_package_bytes, length);
    return length;
}
