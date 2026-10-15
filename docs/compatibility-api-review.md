# Compatibility API review

Reviewed LASRecomp at
[`ffa37e0430e68379436a7eaedd8a2a9a9d7fda61`](https://github.com/peiikai/LASRecomp/tree/ffa37e0430e68379436a7eaedd8a2a9a9d7fda61).
Its service-object approach is useful across SDK revisions. Several handlers also
return unconditional success, fixed title metadata or empty results. Those are
not a general compatibility contract and have not been imported.

| Upstream area | Existing local coverage / change | Remaining boundary |
| --- | --- | --- |
| `services/acc.c` | Local user, selection, nickname and generated profile image already have SDK bindings | Account IPC objects and network authentication |
| `services/time.c` | Added user/local clock, steady clock and host-calendar IPC objects; SDK bindings share the same source identity and correlation | Shared-memory clock mapping, network clock and explicit guest timezone-rule decoding |
| `services/am.c` | Existing mode/settings bindings; transport now supports child objects and cloned domain sessions | Applet proxy hierarchy, message events and storage objects |
| `services/hid_set.c` | Existing input/keyboard bindings and bounded language service | HID shared-memory layouts and multi-controller lifecycle |
| `services/misc.c` | Existing DLC inventory derives IDs from loaded content | Do not adopt a hard-coded title ID or report absent DLC as universally empty |
| `platform/*` | Added independently implemented macOS/Windows/Linux service backends | Full non-macOS execution, presentation and graphics |

## New transport contract

A successful handler may return one stateless child interface in
`NativeIpcReply.object`. Ordinary sessions return a moved handle. Domains return
an object ID after the CMIF payload. Domain clones share one reference-counted
namespace; copying a domain object out creates an independent session. Closing
an object invalidates its ID across clones, while closing the root leaves child
objects usable. IDs do not recycle in a live namespace. Limits are 255 sessions,
64 live objects per namespace and 32 service registrations.

Input objects, stateful service resources, input descriptors, multiple output
buffers, shared-memory/event handle replies and asynchronous IPC are not yet
supported. Unsupported operations return errors. Stateless interfaces are enough
for the new read-only clocks; filesystem/storage extensions need explicit
per-instance ownership instead of global state hidden behind handlers.

## Time commands

`time:u`, `time:a`, and `time:s` expose the same read-only local capabilities.
Command IDs/layouts were checked against libnx at the revision in
[dependencies](DEPENDENCIES.md), including its CMIF object response layout.

| Interface | Commands |
| --- | --- |
| Root | 0 user clock, 2 steady clock, 3 timezone, 4 local clock |
| System clock | 0 current POSIX seconds, 2 stable system-clock context |
| Steady clock | 0 current point with the same source ID as the system context |
| Timezone | 101 calendar conversion using the host timezone |

The wall clock follows the host; the steady clock is monotonic. A context retains
its initial wall/steady correlation. Calendar outputs validate the guest year
range and initialize padding. `DM_FIXED_TIME` is parsed once under the clock
lock for deterministic tests. Unknown commands, short requests, explicit guest
rules and shared-memory clock requests fail visibly. Clients that require the
shared-memory or network-clock path still need implementation; the new services
do not establish that those clients can initialize successfully.
