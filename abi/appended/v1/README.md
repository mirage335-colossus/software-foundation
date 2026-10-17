# Appended ABI v1

This directory owns the initial transport and kernel bootstrap contracts. These
contracts implement host-side byte codecs, discovery, replay and result retention;
they do not establish portable guest execution or rich-document qualification.
The public C constants are in
[`abi.h`](../../../include/foundation/appended/abi.h), and host values and dispatch
are in [`registry.hpp`](../../../include/foundation/appended/registry.hpp).

[`transport.json`](transport.json) fixes offsets, numeric statuses, scalar export
signatures, canonical record encoding and limits. [`bootstrap.json`](bootstrap.json)
fixes control operation and initialization field IDs. Its exact UTF-8 file bytes,
including the final newline, are SHA-256 hashed into the bootstrap schema identity
in `abi.h`. Regenerate that constant deliberately whenever its contract changes.
[`golden.json`](golden.json) supplies independent byte vectors for guest codecs.
No compiler struct layout is a serialized representation.

Native endpoints register an exact namespaced name, major, minor, schema identity,
maximum reply size and synchronous handler. Every supported older contract needs
its own explicit registration. Discovery selects the highest minor in the requested
range matching an optional exact schema. Duplicate name/version registration is a
conflict, regardless of whether the hash matches. A failed registration leaves the
previous provider in place; startup owners must treat conflicts as startup errors.
Service and result handles share one monotonic allocation domain and are scoped
to the nonzero instance generation. They are never persisted or reused.

Before invoking a service, the gateway checks current guest-memory ranges,
nonoverlap, a complete fixed reply header, envelope validity, generation, replay
identity and bounded outcome/result capacity. It copies input and reserves the
provider's maximum result size and outcome storage before any handler effect.
The guest memory lease must stay stable until this synchronous call returns; a
runtime adapter obtains it again after every guest call or memory growth.
Handlers must not call guest code or the registry recursively. Exceptions produce
a recorded uncertain outcome; callers must resolve the external state explicitly.
Errors and invalid handler replies have no result payload.

All admitted requests have strictly increasing nonzero sequences. An identical
live retry uses its recorded outcome; changed bytes return a transport replay
error. Capacity failures do not admit the sequence, so capacity recovery permits
a retry. Older gaps and acknowledged sequences expire without running providers.
Control operation 5 acknowledges completed outcomes through a previously admitted
highest sequence and closes intervening unused gaps. Its own sequence must be
newer. A full ledger can accept an acknowledgment that frees enough space for its
own outcome. Retention requires at least two request slots. The synchronous core
has no unfinished asynchronous outcomes; a future queued implementation must not
advance acknowledgments past unfinished requests.

A reply that cannot fit returns `RESULT_AVAILABLE` and its result handle in the
header correlation field, with no payload. The provider runs once. Read selected
ranges with operation 2 and release with operation 3. A read count must fit its
reply buffer; reads do not create nested result handles. Acknowledging the
originating outcome keeps an exposed result alive until release. Unexposed
results retire with their outcome. Release invalidates all live outcomes referring
to that result, whose subsequent replay reports expired. Actual reserved storage
remains charged while a live outcome still references it; acknowledge those
outcomes to recover the budget. A returned inline payload also reserves retention
until acknowledgment, allowing a smaller-buffer retry to receive a retained handle.

Counter overflow never wraps. The highest generation/sequence may be used once;
subsequent new IDs cannot be admitted. Shutdown closes the registry, releases
resources and rejects ordinary work. Scheduling, cancellation, provider events,
job handles and platform device implementations are not supplied by this core.
