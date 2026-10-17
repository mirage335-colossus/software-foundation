// SPDX-License-Identifier: CC0-1.0
// Always linked by this private wrapper overlay. No WebCore-wide compile flag.
#include "config.h"
#include "BibAppResources.h"

// Core edits call these narrow functions unconditionally. The disabled wrapper
// uses header stubs: false strict/fence, true author/open, with no resource TU
// reference. Enabling the profile defines BIB_APP_RESOURCES only for this shim
// and its specific wrapper consumers; generated unified WebCore flags stay put.
extern "C" int bib_app_resources_strict_profile(void)
{ return BIB::appResourcesStrict() ? 1 : 0; }
extern "C" int bib_app_resources_requires_document_fence(const void* frame)
{ return BIB::appResourcesRequiresDocumentFence(frame) ? 1 : 0; }
extern "C" int bib_app_resources_allow_author_bytes(const void* loader, const void* document)
{ return BIB::appResourcesAllowAuthorBytes(loader, document) ? 1 : 0; }
extern "C" int bib_app_resources_will_explicit_open(const void* frame, const void* loader, const void* document)
{ return BIB::appResourcesWillExplicitOpen(frame, loader, document) ? 1 : 0; }
