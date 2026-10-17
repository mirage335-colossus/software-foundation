# Optional engine provider guard

The canonical host contract is
[`engine_provider.h`](../../include/foundation/appended/engine_provider.h). It is
a C interface for an optional retained engine, separate from the portable guest
SDK. The guard and legacy host adapters are implemented here. The actual WebCore
binding, native DSO and browser composition are unfinished.

The default getter returns `UNSUPPORTED` and publishes no callable table until
the engine composition explicitly installs a real private implementation.
Private test backends cannot qualify an engine SDK or advertise runtime support.

The canonical Document authority is exactly three `uint64_t` fields:
`application_instance`, `document_sequence`, and the actual ready
`service_generation`. Resource bootstrap metadata projects these same fields
without remapping; its resource epoch remains private. Never use a resource epoch
as a service, editor, surface, form or popup authority.

`enter_engine` returns the existing ServiceStatus domain: **0 admits, every
nonzero status rejects**. The legacy adapter forwards checked statuses;
exceptions/invalid statuses become uncertain (14), never accidental success.
ACK callbacks stage a control operation and return `UNAVAILABLE` until the actual
owner performs ACK outside engine/pump and supplies the cached receipt.

The guard validates complete known prefixes, reserved fields, capabilities,
actual pointer width/target, layout and header identity before retention. It
copies bounded catalogs/configuration/requests. Outer appended tails are ignored
and private prefix sizes normalized; embedded Build/Limits structures have exact
sizes. All successful output sizes name only initialized bytes.

Startup is one-shot and process-lived. Before retention, validation failure can
return `NOT_RETAINED`. After callbacks/configuration are retained, even startup
failure is `PROCESS_COMMITTED` and requires process exit. Successful startup is
`READY`; another start is rejected. No reusable destroy/reset/unload exists.
The callback shell, captured owners and code module must remain alive through
engine workers and process lifetime. Document disposal does not shut down the
engine. Handler/host exceptions and explicit process-exit status poison the guard.

Commands require a selected capability, exact schema/document, nonzero monotonic
sequence and full reply capacity before effects. The sequence burns before
dispatch; handled=false and uncertain effects are never automatically replayed.
Replies use bounded scratch storage. Queries require exact captured document
identity and a post-capture recheck; no mutable size-query/retry path is supplied.
Engine callbacks only copy/queue or perform immutable resource/lifecycle work.
Actual Registry/ModuleProviders pump ends before completion delivery reenters.

`LegacyHostAdapters` constructs the exact private service/resource host tables.
It preserves staged ACK receipts; at most two resource contexts; separate
nonreused adapter epochs/leases; immediate producer retirement; and exactly-once
release of nonzero leases, including malformed or rejected responses. Explicit
service retention bounds are constructor inputs because the v1 table omits them.
The raw host lease budget is separate from the real engine's copied-body budget.

The future private engine target needs these two sources, its private include
directory and the repository's public include directory:

- `src/ProviderGuard.cpp`
- `src/LegacyHostAdapters.cpp`

They use exception-enabled C++20 and threads internally. The engine producer must
compile them with its separately qualified private toolchain/runtime and
source-specific exception support, retaining WebCore/JSC object flags. Its
default visibility should hide private C++ symbols; only the C provider entry is
exported. This is not a request to change Foundation's MSVC/C++20 or existing
engine flags. No CMake target, baseline source graph or default build is changed.

`EnginePrivate.hpp` is only for the engine composition. Application owners must
include the C contract, never private WebCore, STL or private implementation
types across the DSO boundary. The actual private preflight still must validate
the complete canonical URL and immutable package entry. This guard checks bounded
shape/digest; it implements no resource loader or fallback.

Focused checks live in the three new `tests/appended_engine_provider_*` files.
They compile only dependency-free helpers and fake owners. They do not configure,
compile, link or execute WebCore. Current Linux C11/C++20 layout/behavior evidence
cannot establish Windows, ARM64, Wasm ABI, runtime imports, actual application
routing, same-engine service behavior or safe shutdown. Native DSO qualification
and actual copied/same-artifact Wasm binding remain separate work.
