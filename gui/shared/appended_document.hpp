#pragma once

#include <foundation/gui/document_values.hpp>

#include <gui/contract.hpp>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::ui {

struct DocumentSourceSpan {
    // UTF-8 byte offsets in the displayed row; points remain DOM UTF-16 offsets.
    std::size_t begin = 0, end = 0;
    DocumentPoint first, last;
};
struct DocumentRow {
    std::string id, text;
    std::vector<DocumentSourceSpan> sources;
    std::optional<std::uint64_t> node;
    bool activatable = false;
};
struct DocumentProjection {
    DocumentVersion version;
    gui::Snapshot view;
    std::vector<DocumentRow> rows;
    std::optional<std::uint64_t> active_node;
    std::optional<DocumentSelection> selection;
    bool incomplete = false;
};
enum class DocumentAction { focus, activate, select };
struct DocumentIntent {
    DocumentVersion version;
    DocumentAction action = DocumentAction::focus;
    std::uint64_t node = 0;
    std::optional<DocumentSelection> selection;
};

class AppendedDocument {
public:
    static constexpr std::size_t max_nodes = 2048;
    // Aggregate text/name/value/href units; tag names retain only the field cap.
    static constexpr std::size_t max_text_units = 65536;
    static constexpr std::size_t max_field_units = 2048;
    static constexpr std::size_t max_rows = 8192;
    // Repeated line measurement has a work bound even when valid combining or
    // joining text has zero advance. Final row measurement is linear in output.
    static constexpr std::size_t max_reflow_measure_bytes = 64 * 1024 * 1024;
    // Invalid or older input throws std::invalid_argument and leaves the prior
    // snapshot intact. Empty exports and element-rooted forests are valid.
    // Equal versions are accepted only for identical values.
    void accept(DocumentSnapshot snapshot);
    const DocumentSnapshot* snapshot() const noexcept;
    // Explicit viewport columns avoid assuming a minimum GUI canvas is the
    // actual terminal width. measure is the public adapter's text measurement;
    // no concrete renderer or Unicode library is required by this utility.
    DocumentProjection project(std::size_t columns, std::size_t rows,
                               const gui::TextMeasure& measure) const;
    // Create an intent after the adapter callback returns. These methods never
    // invoke the engine, mutate its DOM, or replay a failed/uncertain action.
    std::optional<DocumentIntent> intent(const DocumentProjection& projection,
        std::string_view row, DocumentAction action) const;
    std::optional<DocumentIntent> select(const DocumentProjection& projection,
        DocumentSelection selection) const;
    bool current(const DocumentIntent& intent) const noexcept;

private:
    std::optional<DocumentSnapshot> snapshot_;
};

} // namespace foundation::ui
