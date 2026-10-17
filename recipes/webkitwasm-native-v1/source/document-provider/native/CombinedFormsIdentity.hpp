// Exact native identity adapter. No URL, author number or resource epoch rebasing.
#pragma once
#include "NativeFormsV2Combined.hpp"
#include "BibAppResources.h"
#include <WebCore/LocalFrameInlines.h>

namespace BIB::FormsV2Combined {
inline std::optional<Context> contextFromAppDocument(WebCore::LocalFrame& frame,
    WebCore::Document& document, uint64_t revision)
{
    if (!revision || frame.document() != &document) return std::nullopt;
    BibAppDocumentIdentityV1 identity { };
    identity.size = sizeof(identity);
    identity.version = BIB_APP_DOCUMENT_IDENTITY_VERSION;
    if (!BIB::appResourcesDocumentIdentity(frame, document, identity)
        || identity.size != sizeof(identity) || identity.version != BIB_APP_DOCUMENT_IDENTITY_VERSION
        || !identity.application_instance || !identity.service_generation || !identity.document_sequence
        || !identity.resource_epoch) return std::nullopt;
    return Context { { identity.application_instance, identity.service_generation, revision },
        identity.document_sequence, identity.resource_epoch, &document, &frame };
}
inline N::Identity wireIdentity(const Context& context)
{
    return { context.version.generation, context.version.epoch, context.documentSequence };
}
} // namespace BIB::FormsV2Combined
