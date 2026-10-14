#pragma once
#include <stddef.h>
#include <stdint.h>

/* Immutable content inventory selected before launching guest threads. */
int native_content_count(void);
int native_content_list(int *out, int capacity, int offset);
int native_content_root(int index, char *out, size_t size);

int native_content_save_sizes(int64_t *data, int64_t *journal);
