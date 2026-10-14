// Use the host random generator instead of a guest IPC service session.
#include "hle.h"
HLE_FORCE("_ZN2nn6crypto15InitializeCsrngEv", "Host random generator needs no guest service session", void,
          h_crypto_InitializeCsrng, void) {}
HLE_FORCE("_ZN2nn6crypto36GenerateCryptographicallyRandomBytesEPvm", "Host cryptographic random bytes", void,
          h_crypto_GenerateRandomBytes, void *output, size_t length) {
    if (length) arc4random_buf(output, length);
}
