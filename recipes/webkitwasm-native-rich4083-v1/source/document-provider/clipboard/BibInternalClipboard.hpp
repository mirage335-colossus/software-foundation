// SPDX-License-Identifier: CC0-1.0
// Private selected rich-engine CPP seam; existing WebCore headers are unchanged.
#pragma once
#include "BibClipboardStore.hpp"
#include "BibEngineUiOwner.hpp"
#include <optional>
namespace WebCore { class Pasteboard; class PasteboardCustomData; class Document; }
namespace BIB::Clipboard {
enum class BatchResult { not_internal, committed, rejected };
bool isInternal(const WebCore::Pasteboard&) noexcept;
BatchResult commitPublicData(WebCore::Pasteboard&, const WebCore::PasteboardCustomData&, bool includeCustomStrings) noexcept;
class CutWriteScope {
public:
    CutWriteScope(const WebCore::Pasteboard&, const WebCore::Document&) noexcept;
    CutWriteScope(const CutWriteScope&) = delete;
    CutWriteScope& operator=(const CutWriteScope&) = delete;
    bool valid() const noexcept { return attempt_ && attempt_->valid(); }
    // Call once, after all editor callbacks and exact source-selection checks.
    bool consume() noexcept;
private:
    const WebCore::Pasteboard* pasteboard_{};
    EngineUI::Snapshot snapshot_{};
    std::optional<WriteAttempt> attempt_{};
    bool consumed_{};
};
} // namespace BIB::Clipboard
