#include "foundation/store.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace foundation {

Store::Store(std::size_t capacity) : capacity_(capacity) {
    if (capacity == 0 || capacity > max_capacity) {
        throw std::invalid_argument("capacity must be 1..4096");
    }
}

void Store::validate(std::string_view text) {
    if (text.empty() || text.size() > max_text_bytes) {
        throw std::invalid_argument("text must contain 1..256 bytes");
    }
    for (const unsigned char byte : text) {
        if (byte < 32 || byte > 126) {
            throw std::invalid_argument("text must contain printable ASCII only");
        }
    }
}

RecordId Store::add(std::string_view text) {
    validate(text);
    if (records_.size() == capacity_) {
        throw std::length_error("collection is full");
    }
    if (next_id_ == std::numeric_limits<RecordId>::max()) {
        throw std::overflow_error("record identifiers exhausted");
    }
    const auto id = next_id_;
    records_.push_back({id, std::string(text)});
    ++next_id_;
    return id;
}

bool Store::update(RecordId id, std::string_view text) {
    validate(text);
    const auto found = std::find_if(records_.begin(), records_.end(),
        [id](const Record& row) { return row.id == id; });
    if (found == records_.end()) return false;
    std::string replacement(text);
    found->text.swap(replacement);
    return true;
}

bool Store::erase(RecordId id) {
    const auto found = std::find_if(records_.begin(), records_.end(),
        [id](const Record& row) { return row.id == id; });
    if (found == records_.end()) return false;
    records_.erase(found);
    return true;
}

std::optional<Record> Store::get(RecordId id) const {
    const auto found = std::find_if(records_.begin(), records_.end(),
        [id](const Record& row) { return row.id == id; });
    if (found == records_.end()) return std::nullopt;
    return *found;
}

std::vector<Record> Store::snapshot() const { return records_; }
std::size_t Store::size() const noexcept { return records_.size(); }

} // namespace foundation
