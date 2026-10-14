#ifndef NSP_PROFILE_H
#define NSP_PROFILE_H
#include <stddef.h>
#include <stdbool.h>

// A generated local-user avatar, encoded as JPEG. No application assets are used.
size_t nsp_profile_image_size(void);
bool nsp_profile_image_copy(void *destination, size_t capacity, size_t *written);
#endif
