// SPDX-License-Identifier: CC0-1.0
// Private combined source candidate; no live engine/support claim.
#pragma once
#include "BibAppResourceHost.h"
#ifndef BIB_APP_RESOURCES
#define BIB_APP_RESOURCES 0
#endif
#ifdef __cplusplus
extern "C" {
#endif
enum { BIB_APP_DOCUMENT_IDENTITY_VERSION = 1 };
typedef struct BibAppDocumentIdentityV1 {
    uint32_t size;
    uint32_t version;
    uint64_t application_instance;
    uint64_t document_sequence;
    uint64_t resource_epoch;     // Private resource ownership, never native authority.
    uint64_t service_generation; // Canonical native/ACK/forms lease identity.
} BibAppDocumentIdentityV1;
// Install once on the engine owner before Page creation. No C++ object crosses
// this boundary. Root selects the package/application, never a URL alone.
int bib_app_resources_install_bundle(const BibAppResourceBundleHostV1*,
    const uint8_t* entry_url, uint32_t length, uint64_t application_instance);
int bib_app_resources_close_all(void);
int bib_app_resources_current_identity(BibAppDocumentIdentityV1*);
int bib_app_resources_strict_profile(void);
// Core-only opaque engine identity hooks. They compare objects inside this
// engine; no WebCore object is delivered to a native service or page script.
int bib_app_resources_requires_document_fence(const void* frame);
int bib_app_resources_allow_author_bytes(const void* loader, const void* document);
int bib_app_resources_will_explicit_open(const void* frame, const void* loader, const void* document);
#ifdef __cplusplus
}
#include <memory>
#include <wtf/Forward.h>
namespace WebCore {
class Document; class DocumentLoader; class DOMWrapperWorld; class LocalFrame; class FrameLoader;
class ResourceLoader; class ResourceRequest; class ResourceResponse; class ResourceError;
}
namespace BIB {
class AppResourceContext;
using AppResourceBinding = std::shared_ptr<AppResourceContext>;
#if BIB_APP_RESOURCES
bool appResourcesStrict();
void appResourcesInitializeScheme();
bool appResourcesStartApplicationLoad(WebCore::LocalFrame&);
bool appResourcesNavigationAllowed(WebCore::LocalFrame&, const WebCore::ResourceRequest&);
bool appResourcesCheckResponse(WebCore::LocalFrame&, const WebCore::ResourceResponse&, const WebCore::ResourceRequest&);
AppResourceBinding appResourcesBind(WebCore::LocalFrame&, bool mainResource, const WebCore::ResourceRequest&);
void appResourcesSchedule(WebCore::ResourceLoader&, AppResourceBinding);
void appResourcesCreationFailed(AppResourceBinding);
bool appResourcesRemove(WebCore::ResourceLoader*);
bool appResourcesContains(WebCore::ResourceLoader*);
void appResourcesSetDefersLoading(WebCore::ResourceLoader&, bool);
void appResourcesLoadSynchronously(WebCore::FrameLoader&, const WebCore::ResourceRequest&, WebCore::ResourceError&, WebCore::ResourceResponse&, Vector<uint8_t>&);
void appResourcesWillChangeMainDocument(WebCore::LocalFrame&);
void appResourcesDidExplicitOpen(WebCore::LocalFrame&);
void appResourcesDidClearWindowObject(WebCore::LocalFrame&, WebCore::DOMWrapperWorld&);
void appResourcesWillDestroyEngine();
// Exact current Document and actual ready service generation are mandatory.
bool appResourcesDocumentIdentity(WebCore::LocalFrame&, const WebCore::Document&, BibAppDocumentIdentityV1&);
// Always-linked profile shim dispatches these only in the enabled wrapper TU.
bool appResourcesRequiresDocumentFence(const void* frame);
bool appResourcesAllowAuthorBytes(const void* loader, const void* document);
bool appResourcesWillExplicitOpen(const void* frame, const void* loader, const void* document);
#else
inline bool appResourcesStrict() { return false; }
inline void appResourcesInitializeScheme() { }
inline bool appResourcesStartApplicationLoad(WebCore::LocalFrame&) { return false; }
inline bool appResourcesNavigationAllowed(WebCore::LocalFrame&, const WebCore::ResourceRequest&) { return true; }
inline bool appResourcesCheckResponse(WebCore::LocalFrame&, const WebCore::ResourceResponse&, const WebCore::ResourceRequest&) { return true; }
inline AppResourceBinding appResourcesBind(WebCore::LocalFrame&, bool, const WebCore::ResourceRequest&) { return {}; }
inline void appResourcesSchedule(WebCore::ResourceLoader&, AppResourceBinding) { }
inline void appResourcesCreationFailed(AppResourceBinding) { }
inline bool appResourcesRemove(WebCore::ResourceLoader*) { return false; }
inline bool appResourcesContains(WebCore::ResourceLoader*) { return false; }
inline void appResourcesSetDefersLoading(WebCore::ResourceLoader&, bool) { }
inline void appResourcesLoadSynchronously(WebCore::FrameLoader&, const WebCore::ResourceRequest&, WebCore::ResourceError&, WebCore::ResourceResponse&, Vector<uint8_t>&) { }
inline void appResourcesWillChangeMainDocument(WebCore::LocalFrame&) { }
inline void appResourcesDidExplicitOpen(WebCore::LocalFrame&) { }
inline void appResourcesDidClearWindowObject(WebCore::LocalFrame&, WebCore::DOMWrapperWorld&) { }
inline void appResourcesWillDestroyEngine() { }
inline bool appResourcesDocumentIdentity(WebCore::LocalFrame&, const WebCore::Document&, BibAppDocumentIdentityV1&) { return false; }
inline bool appResourcesRequiresDocumentFence(const void*) { return false; }
inline bool appResourcesAllowAuthorBytes(const void*, const void*) { return true; }
inline bool appResourcesWillExplicitOpen(const void*, const void*, const void*) { return true; }
#endif
}
#endif
