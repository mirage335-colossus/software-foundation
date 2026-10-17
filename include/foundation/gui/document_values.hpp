// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <foundation/appended/document_forms.hpp>
#include <gui/contract.hpp>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace foundation::ui {

// Disposable values exported by the SAME running document. This utility does
// not parse HTML, execute scripts, own form state, or implement an HTML engine.
struct DocumentVersion {
    std::uint64_t generation = 0, epoch = 0, revision = 0;
    bool operator==(const DocumentVersion&) const = default;
};
enum class DocumentNodeKind { element, text };
enum class DocumentWhiteSpace { normal, pre, pre_wrap };
struct DocumentNode {
    std::uint64_t id = 0, parent = 0;
    DocumentNodeKind kind = DocumentNodeKind::element;
    std::string tag, text, name, value, href;
    // Computed style on elements; text nodes inherit their parent's policy.
    DocumentWhiteSpace white_space = DocumentWhiteSpace::normal;
    // Presentation hints do not remove nodes or stop their scripts. disabled
    // reflects the producer's observed flag, not full browser focus semantics.
    bool omitted = false, masked = false, disabled = false, editable = false;
    bool operator==(const DocumentNode&) const = default;
};
struct DocumentPoint {
    std::uint64_t node = 0;
    std::uint32_t utf16_offset = 0;
    bool operator==(const DocumentPoint&) const = default;
};
struct DocumentSelection {
    DocumentPoint anchor, focus;
    bool operator==(const DocumentSelection&) const = default;
};
struct DocumentSnapshot {
    DocumentVersion version;
    // Visibility/omission filtering can yield no nodes or an element-rooted
    // forest. Keep actual IDs and absent parents; never synthesize a DOM root.
    std::vector<DocumentNode> nodes;
    std::optional<std::uint64_t> active_node;
    std::optional<DocumentSelection> selection;
    bool truncated = false;
    bool operator==(const DocumentSnapshot&) const = default;
};
struct DocumentEditorState {
    std::uint32_t revision = 0, flags = 0;
};
struct DocumentNodeMetadata {
    std::uint64_t node = 0;
    std::string role, display, white_space;
    bool read_only = false, checked = false;
};
enum class DocumentNativeOffsetKind { text_utf16, element_child_index };
struct DocumentNativePoint {
    std::uint64_t node = 0;
    std::uint32_t offset = 0;
    DocumentNativeOffsetKind kind = DocumentNativeOffsetKind::text_utf16;
    bool operator==(const DocumentNativePoint&) const = default;
};
struct DocumentNativeSelection {
    DocumentNativePoint anchor, focus;
    bool operator==(const DocumentNativeSelection&) const = default;
};
struct DocumentWireSelection {
    DocumentNativeSelection endpoints;
    // Finite engine coordinates; consumers must map/check their GUI range.
    gui::Rect focus_rect;
};
struct DocumentDecodeDegradation {
    bool whitespace = false;
    bool element_selection = false;
    bool truncated_selection = false;
};
struct DocumentSemanticReply {
    std::uint64_t request_id = 0, epoch = 0;
    // A producer error is explicit and has no snapshot or editor state.
    std::string error_code;
    std::optional<DocumentSnapshot> snapshot;
    std::optional<DocumentEditorState> editor_state;
    std::vector<DocumentNodeMetadata> metadata;
    // Retain original endpoints/geometry even when the narrow text selection
    // cannot represent them. Never invent a valid text-node caret or offset.
    std::optional<DocumentWireSelection> original_selection;
    DocumentDecodeDegradation degraded;
};

// Produced ONLY by the native-v2 adapter from one immutable publication and
// native node registry. A legacy v1 reply plus coincident numeric IDs is not a
// valid join. Current controller representability limits are checked exactly.
struct NativeFormsDocumentObservation {
    std::uint32_t protocol{appended::document_forms_version};
    appended::FormVersion publication;
    DocumentSemanticReply body;
    appended::DocumentFormsSnapshot forms;
};
} // namespace foundation::ui
