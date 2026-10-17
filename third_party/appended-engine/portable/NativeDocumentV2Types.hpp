// SOURCE CANDIDATE ONLY. No negotiated operation, capability or provider ABI.
#pragma once
#include <foundation/appended/document_forms.hpp>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace BIB::NativeDocumentV2 {
namespace F = foundation::appended;
inline constexpr std::size_t maxNodes = 2048, maxControls = 2048, maxOptions = 2048;
inline constexpr std::size_t maxFieldUnits = 2048, maxSectionUnits = 65536;
inline constexpr std::size_t maxTraversal = 8192, maxEvidence = 4096, maxDepth = 256;
inline constexpr std::size_t maxReplyBytes = 1024 * 1024;
inline constexpr std::size_t serviceReplyBytes = 1024 * 1024; // distinct existing service ceiling
inline constexpr std::uint64_t maxConsumerInteger = 9007199254740991ULL;
inline constexpr std::size_t maxEncodedCompletionBytes =
    8 + 40 + 4 + 145 + maxNodes * 42 + maxNodes * 20 + maxControls * 82 +
    maxOptions * 13 + 3 * maxSectionUnits * 3;
static_assert(maxEncodedCompletionBytes == 911557);
static_assert(maxEncodedCompletionBytes <= maxReplyBytes);

struct Identity {
    std::uint64_t application_instance{0}, service_generation{0}, document_sequence{0};
    bool operator==(const Identity&) const = default;
};
enum class NodeKind : std::uint8_t { element = 1, text = 2 };
struct Node {
    std::uint64_t id{0}, parent{0};
    NodeKind kind{NodeKind::element};
    // ACTUAL native direct child count, including omitted/unpublished children.
    // Producer must bound the native walk before obtaining this value.
    std::uint32_t native_child_count{0};
    bool masked{false}, omitted{false};
    bool disabled{false}, editable{false};
    std::string tag, text, name, value, href;
    bool operator==(const Node&) const = default;
};
struct Metadata {
    std::uint64_t node{0};
    std::string role, display, white_space;
    bool operator==(const Metadata&) const = default;
};
enum class EndpointKind : std::uint8_t { text_utf16 = 1, element_child = 2 };
struct Endpoint {
    std::uint64_t node{0};
    EndpointKind kind{EndpointKind::text_utf16};
    std::uint32_t offset{0};
    bool operator==(const Endpoint&) const = default;
};
struct Rect {
    double x{0}, y{0}, width{0}, height{0};
    bool operator==(const Rect&) const = default;
};
struct NativeSelection {
    Endpoint anchor, focus;
    std::optional<Rect> rect;
    bool operator==(const NativeSelection&) const = default;
};
struct EditorState {
    std::uint64_t revision{0}, active_node{0};
    // canEdit=1, hasComposition=2, canUndo=4, canRedo=8, inputMethodEnabled=16.
    // The last requires authoritative native EditorClient state; unavailable
    // state rejects the native publication, never substitutes false.
    std::uint32_t flags{0};
    bool operator==(const EditorState&) const = default;
};
struct OwnedPublication {
    Identity identity;
    F::FormVersion version;
    std::vector<Node> nodes;
    std::vector<Metadata> metadata;
    std::optional<NativeSelection> selection;
    EditorState editor;
    F::DocumentFormsSnapshot forms;
    bool truncated{false};
    // author shadow, frames, generated content, unavailable selection,
    // unavailable label prefix, unknown style, unsupported whitespace.
    std::uint32_t degradation{0};
};
using Publication = OwnedPublication;
struct Query {
    Identity identity;
    // Nested DocumentController token: nonzero for query/reply; reserved ZERO
    // for action/completion, which have no document request token.
    std::uint64_t outer_sequence{0}, document_request_id{0};
    bool operator==(const Query&) const = default;
};
struct ActionRequest { Query request; F::FormAction action; };
struct Reply { Query request; OwnedPublication publication; };
enum class CompletionCode : std::uint8_t {
    ok, busy, unavailable, stale_document, stale_control, invalid_action,
    unsupported, limit, readback_failed
};
struct Completion {
    Query request;
    F::FormDraftOutcome outcome{F::FormDraftOutcome::rejected};
    CompletionCode code{CompletionCode::unavailable};
    bool effects_entered{false}, popup_opened{false};
    std::optional<OwnedPublication> publication;
};

// All throwing validators reject via invalid_argument; no mutation/callback.
std::size_t utf16Units(std::string_view); // strict scalar UTF8, no NUL, <=2048 units
std::string utf16ToUtf8(std::u16string_view);
std::u16string utf8ToUtf16(std::string_view);
bool scalarBoundary(std::string_view, std::uint32_t utf16Offset);
void validatePublication(const OwnedPublication&);
void validateQuery(const Query&);
void validateActionPrefix(const Query&);
void validateActionRequest(const ActionRequest&);
void validateCompletion(const Completion&);
// Explicit downstream compatibility gate; codec and producer preserve full64.
void validateConsumerRepresentability(const Reply&);

// Subtraction based budgets. Charge source UTF16 lengths BEFORE copying/getters;
// validation after copying cannot establish a secure getter nonread guarantee.
enum class TextSection { body, metadata, forms, private_capture };
class ReadBudget {
public:
    void chargeString(TextSection, std::size_t utf16Units);
    void chargeNode();
    void chargeControl();
    void chargeOption();
    void chargeTraversal(std::size_t count = 1);
    void chargeEvidence(std::size_t count = 1);
    void checkDepth(std::size_t) const;
    std::size_t remaining(TextSection) const noexcept;
    void chargeBody(std::size_t n) { chargeString(TextSection::body, n); }
    void chargeMetadata(std::size_t n) { chargeString(TextSection::metadata, n); }
    void chargeForms(std::size_t n) { chargeString(TextSection::forms, n); }
    void chargePrivate(std::size_t n) { chargeString(TextSection::private_capture, n); }
    void visitRaw(std::size_t depth) { checkDepth(depth); chargeTraversal(); }
    void evidence(std::size_t n = 1) { chargeEvidence(n); }
    void control() { chargeControl(); }
    void option() { chargeOption(); }
private:
    std::size_t text_[4]{maxSectionUnits,maxSectionUnits,maxSectionUnits,maxSectionUnits};
    std::size_t nodes_{maxNodes}, controls_{maxControls}, options_{maxOptions};
    std::size_t traversal_{maxTraversal}, evidence_{maxEvidence};
};
class Counter {
public:
    explicit Counter(std::uint64_t highWater = 0) noexcept : high_(highWater) {}
    // Reservations burn on failed staging; overflow permanently retires counter.
    std::optional<std::uint64_t> reserve() noexcept;
    std::uint64_t highWater() const noexcept { return high_; }
    bool retired() const noexcept { return retired_; }
private:
    std::uint64_t high_{0};
    bool retired_{false};
};
using Budget = ReadBudget;
using MonotonicCounter = Counter;
} // namespace BIB::NativeDocumentV2
