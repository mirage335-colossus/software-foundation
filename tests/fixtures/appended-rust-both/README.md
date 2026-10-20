# Portable Rust calculator and provider fixture

This `no_std` application shares its four-widget calculator across GUI and terminal
hosts. It discovers `foundation.view` from the real initialization context. When
`foundation.providers` is available it also registers `org.example.increment`;
when that optional gateway is absent it remains a view-only calculator. Absence
is successful only after discovery is acknowledged. Every ACK failure is fatal.
BOTH qualification still requires actual provider discovery and invocation.

Compile only the small module with the supported entry point and a pinned
retained Rust guest SDK; keep outputs outside the source directory:

```sh
./build.sh appended compile --source tests/fixtures/appended-rust-both/src \
  --entry lib.rs --language rust --sdk /absolute/path/to/retained-rust-guest-sdk.json \
  --output /tmp/appended-rust-calculator.wasm \
  --receipt /tmp/appended-rust-calculator.compile.json
node tests/fixtures/appended-rust-both/run.mjs /tmp/appended-rust-calculator.wasm
for scenario in wrong-target-type wrong-revision-field optional-missing \
  optional-ack-not-found optional-missing-ack-not-found optional-unavailable \
  optional-missing-payload; do
  node tests/fixtures/appended-rust-both/run.mjs /tmp/appended-rust-calculator.wasm --"$scenario"
done
```

The real Wasm fixture checks 12 complete view goldens, 38 typed calls, resize,
Enter, invalid input and overflow, plus the two original rejection cases. Five
optional-gateway cases distinguish absence from failed ACK and malformed replies.
The old application fails the ACK-NOT_FOUND counterexample; the corrected one
passes all eight groups. A real retained Linux terminal renders actual keys
17 + 25 → 42 and exits naturally with terminal settings restored. Its module
compile took 1.950 seconds; packaging took 0.138 seconds. This is one measured
sample, not an inclusive-loop or cross-platform qualification.

Historical source/module identities and failures remain in ignored NC558 evidence.
The earlier required-gateway module separately passed Foundation's complete
private partial-BOTH runtime and independent readback (`ad701520…`). That receipt
belongs to its exact older module; it is not relabelled as a browser pass for this
optional-gateway successor. Full Foundation and ordinary public rich-browser
qualification, native GUI and the integrated viewer remain pending. No retained
kernel, engine or SDK maintenance belongs to application editing.
