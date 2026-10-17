// SPDX-License-Identifier: CC0-1.0
// PRIVATE DISABLED CANDIDATE. No WebCore/JSC compilation or runtime claim.
#pragma once
#include <stdint.h>

#ifndef BIB_FOUNDATION_SERVICES
#define BIB_FOUNDATION_SERVICES 0
#endif

namespace WebCore {
class DOMWrapperWorld;
class Document;
class LocalFrame;
}

namespace BIB {

// Declare before all JSC locks and other objects whose destructors can enter
// JavaScript. Test the guard before doing engine work. A host callback may wake
// its owner, but may not enter another engine turn synchronously.
class FoundationServiceEngineCall final {
public:
#if BIB_FOUNDATION_SERVICES
    FoundationServiceEngineCall();
    ~FoundationServiceEngineCall();
    // Required immediately before a no-unwind live-runtime handoff. Call only
    // after startup JSC objects/locks have gone out of scope. Idempotent.
    void finish();
#else
    FoundationServiceEngineCall() = default;
    ~FoundationServiceEngineCall() = default;
    void finish() { }
#endif
    explicit operator bool() const { return m_entered; }
    FoundationServiceEngineCall(const FoundationServiceEngineCall&) = delete;
    FoundationServiceEngineCall& operator=(const FoundationServiceEngineCall&) = delete;

private:
    bool m_entered { true };
#if BIB_FOUNDATION_SERVICES
    bool m_hostEntered { false };
#endif
};

#if BIB_FOUNDATION_SERVICES
// Composition selects this exact current main-frame document after writer.begin
// and before author bytes are parsed. Selection injects immediately; ordinary
// navigation does not grant the replacement document native services.
void foundationServicesSelectApplicationDocument(WebCore::LocalFrame&);
// Combined composition uses the exact newly-created Document, never a stale
// frame.document() from an earlier/provisional lifecycle. Zero means no fully
// ready generation after locks/turn destructors and their checkpoints return.
uint64_t foundationServicesSelectApplicationDocumentChecked(WebCore::LocalFrame&, WebCore::Document&);
uint64_t foundationServicesResetApplicationDocumentChecked(WebCore::LocalFrame&, WebCore::Document&);
uint64_t foundationServicesReadyGeneration(WebCore::LocalFrame&, const WebCore::Document&);
void foundationServicesRetireCompositionDocument(WebCore::LocalFrame&, const WebCore::Document&, uint64_t expectedGeneration);
void foundationServicesDidClearWindowObject(WebCore::LocalFrame&, WebCore::DOMWrapperWorld&);
// Loader mutation hooks only close/retire state; they do not execute disposal.
void foundationServicesWillChangeMainDocument(WebCore::LocalFrame&);
void foundationServicesDidExplicitOpen(WebCore::LocalFrame&);
// Invalidate before frame/client destruction. The host subsequently disposes
// saved retired controllers through the private C ABI on a safe owner turn.
void foundationServicesWillDestroyEngine();
#else
inline void foundationServicesSelectApplicationDocument(WebCore::LocalFrame&) { }
inline uint64_t foundationServicesSelectApplicationDocumentChecked(WebCore::LocalFrame&, WebCore::Document&) { return 0; }
inline uint64_t foundationServicesResetApplicationDocumentChecked(WebCore::LocalFrame&, WebCore::Document&) { return 0; }
inline uint64_t foundationServicesReadyGeneration(WebCore::LocalFrame&, const WebCore::Document&) { return 0; }
inline void foundationServicesRetireCompositionDocument(WebCore::LocalFrame&, const WebCore::Document&, uint64_t) { }
inline void foundationServicesDidClearWindowObject(WebCore::LocalFrame&, WebCore::DOMWrapperWorld&) { }
inline void foundationServicesWillChangeMainDocument(WebCore::LocalFrame&) { }
inline void foundationServicesDidExplicitOpen(WebCore::LocalFrame&) { }
inline void foundationServicesWillDestroyEngine() { }
#endif

} // namespace BIB
