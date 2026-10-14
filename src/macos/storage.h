#pragma once
#include <stdint.h>

/* Return an errno value; all SDK bindings share these host operations. */
int native_save_ensure(void);
int native_save_sizes(int64_t *data, int64_t *journal);
int native_save_extend(int64_t data, int64_t journal);
int native_storage_space(const char *path, int64_t *free_bytes, int64_t *total_bytes);
