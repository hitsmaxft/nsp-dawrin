// SDK bindings delegate to the immutable launcher-selected content inventory.
#include "hle.h"
#include "../macos/content.h"

HLE_FORCE("_ZN2nn3aoc10InitializeEv", "Use local content inventory", void, h_aoc_Init, void) {}
HLE_FORCE("_ZN2nn3aoc8FinalizeEv", "Inventory lifetime belongs to the session", void, h_aoc_Finalize, void) {}
HLE_FORCE("_ZN2nn3aoc17CountAddOnContentEv", "Count selected compatible add-on content", int,
    h_aoc_Count, void) {return native_content_count();}
HLE_FORCE("_ZN2nn3aoc16ListAddOnContentEPiii", "Enumerate selected add-on content indexes", int,
    h_aoc_List, int *out, int offset, int count) {return native_content_list(out,count,offset);}
HLE_FORCE("_ZN2nn3aoc19PrepareAddOnContentEi", "Validate selected add-on content", Result,
    h_aoc_Prepare, int index) {char path[1024];return native_content_root(index,path,sizeof path)?RES_OK:RES_FAIL;}
