// Service layer initialization called by nninitInitializeSdkModule: on the real device each connects to a Horizon system service (IPC), the host has no such service processes.
// Native takeover: create no session, return directly; each service's later interfaces are taken over one by one as host implementations when they come into use (see hle_*.c in the same directory).
// nn::os::InitializeVirtualAddressMemory belongs to the SDK's os layer and is not taken over; fs::SetLocalApplicationAccessLog /
// SetResultHandledByApplication only write SDK-internal switches and are not taken over.
#include "hle.h"

static void once(const char *what) { LOG("Host service initialization: %s (no IPC session)", what); }

HLE_FORCE("nndiagStartup", "Host diagnostics replace the logging service", void, h_nndiagStartup, void) { once("nndiagStartup"); }
HLE_FORCE("_ZN2nn2oe10InitializeEv", "Host execution environment", void, h_oe_Initialize, void) { once("oe::Initialize"); }
HLE_FORCE("_ZN2nn3err26InitializeContextWriterApiEv", "No remote error reporting", void, h_err_InitCtx, void) { once("err::InitializeContextWriterApi"); }
HLE_FORCE("_ZN2nn2fs24InitializeForApplicationEv", "Host filesystem and indexed package resources", void, h_fs_InitApp, void) { once("fs::InitializeForApplication"); }
HLE_FORCE("_ZN2nn4pctl10InitializeEv", "No parental control service", void, h_pctl_Initialize, void) { once("pctl::Initialize"); }
HLE_FORCE("_ZN2nn4diag34InitializeApplicationAbortObserverEv", "Host signal handler reports native faults", void, h_diag_AbortObs, void) { once("diag::InitializeApplicationAbortObserver"); }
