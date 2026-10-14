# Content loading

`tools/content.py` separates container indexing, NCA sections, CNMT selection and
virtual resource reads. `ContentSet` implements the same `ResourceReader` used by
shader adapters. The launcher accepts repeated `--update` and `--dlc` options;
`--application-id HEX` selects a base from a compilation container. `--inspect`
reports the selected versions and add-on indexes without creating a cache.

Selection uses CNMT application IDs and content records, not filenames. The
highest supplied update is selected. Add-on content is checked against its base
application and required application version. Duplicate versions and explicitly
supplied unrelated packages are rejected. DLC is mounted separately; its files
do not overwrite base resources.

NSP PFS0 and XCI secure HFS0 containers use bounded reads. NCA3 plain/CTR sections
are supported. BKTR update sections combine the matching base with patch ranges,
splitting at crypto-counter boundaries. The flattened range index allows native
reads across base/patch boundaries without extracting RomFS. Only executable
modules, metadata, private key caches and sparse filesystem entries are prepared.

Version 2 of `package-index.json` has independent `sources` and `mounts`. Each
mount has file offsets into a contiguous virtual address space and sorted
`segments` mapping that space to package offsets and crypto sources. The native
reader validates range bounds, reads in bounded chunks and retains version 1
compatibility. Content is immutable for a running session.

The common host content inventory supplies count/list/prepare operations and
read-only add-on mounts. Host storage operations use allocation sizes from
`control.nacp`, keep allocation metadata beside the save directory, and preserve
existing transactional save data. The current account namespace is single-user.

## Coverage

Synthetic tests cover encrypted NSP and XCI input, version selection, unrelated
content rejection, DLC version prerequisites, cross-source BKTR reads and native
reader equivalence. `tests/storage.m` checks content enumeration and persistent
allocation across processes. Real-package validation is recorded outside source.

Personalized tickets, compressed containers/sections, sparse sections,
multi-program applications, deeper BKTR trees and incremental DLC patch sections
need additional adapters. Unsupported formats fail explicitly. Metadata and
bounds validation do not constitute full signature or IVFC integrity verification.
