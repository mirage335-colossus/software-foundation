// SPDX-License-Identifier: CC0-1.0
#include "BibClipboardStore.hpp"
#include <new>

namespace BIB::Clipboard {
namespace {
char16_t* allocateUnits(void*, std::size_t count) noexcept { return new (std::nothrow) char16_t[count]; }
void freeUnits(void*, char16_t* data, std::size_t) noexcept { delete[] data; }
Input inputFor(const Record& record) noexcept {
    return {{record.plain.present(), record.plain.view()}, {record.html.present(), record.html.view()}};
}
}
Allocator defaultAllocator() noexcept { return {nullptr, allocateUnits, freeUnits}; }
Format formatForMime(std::string_view type) noexcept {
    const auto equal = [&](std::string_view expected) noexcept {
        if (type.size() != expected.size()) return false;
        for (std::size_t index = 0; index < type.size(); ++index) {
            const auto unit = type[index];
            const auto lower = unit >= 'A' && unit <= 'Z' ? static_cast<char>(unit + ('a' - 'A')) : unit;
            if (lower != expected[index]) return false;
        }
        return true;
    };
    if (equal("text/plain") || equal("text/plain;charset=utf-8")) return Format::plain;
    if (equal("text/html")) return Format::html;
    return Format::unsupported;
}
OwnedText::~OwnedText() { reset(); }
void OwnedText::reset() noexcept {
    if (data_ && allocator_.deallocate) allocator_.deallocate(allocator_.context, data_, length_);
    data_ = nullptr; length_ = 0; present_ = false; allocator_ = {};
}
OwnedText::OwnedText(OwnedText&& other) noexcept { *this = std::move(other); }
OwnedText& OwnedText::operator=(OwnedText&& other) noexcept {
    if (this == &other) return *this;
    reset(); data_ = std::exchange(other.data_, nullptr); length_ = std::exchange(other.length_, 0);
    present_ = std::exchange(other.present_, false); allocator_ = std::exchange(other.allocator_, {});
    return *this;
}
Store::Store(Allocator allocator, std::uint64_t initial_revision) noexcept
    : allocator_(allocator), revision_(initial_revision) { }
bool Store::bind(OwnerKey owner) noexcept {
    if (!owner || !allocator_.allocate || !allocator_.deallocate) return false;
    if (owner_ != owner) { retire(); owner_ = owner; }
    return true;
}
void Store::retire() noexcept { record_ = {}; owner_ = {}; }
const Record* Store::current(OwnerKey owner) const noexcept {
    return owner && owner == owner_ ? &record_ : nullptr;
}
Status Store::prepare(const Input& input, Record& output) const noexcept {
    const auto length = [](const ValueInput& value) { return value.present ? value.text.length : 0; };
    if ((input.plain.present && !input.plain.text.valid()) || (input.html.present && !input.html.text.valid()))
        return Status::invalid;
    const auto plain = length(input.plain), html = length(input.html);
    if (plain > max_units || html > max_units - plain) return Status::limit;
    Record candidate;
    const auto copy = [&](const ValueInput& source, OwnedText& target) noexcept {
        if (!source.present) return true;
        target.present_ = true; target.length_ = source.text.length; target.allocator_ = allocator_;
        if (!target.length_) return true;
        target.data_ = allocator_.allocate(allocator_.context, target.length_);
        if (!target.data_) return false;
        for (std::size_t index = 0; index < target.length_; ++index)
            target.data_[index] = source.text.units ? source.text.units[index] : source.text.latin1[index];
        return true;
    };
    if (!copy(input.plain, candidate.plain) || !copy(input.html, candidate.html)) return Status::allocation_failure;
    output = std::move(candidate); return Status::ok;
}
Status Store::snapshot(OwnerKey owner, Record& output) const noexcept {
    if (!current(owner)) return Status::unavailable;
    Record candidate;
    const auto status = prepare(inputFor(record_), candidate);
    if (status != Status::ok) return status;
    candidate.revision = record_.revision; output = std::move(candidate); return Status::ok;
}
WriteResult Store::replace(OwnerKey owner, const Input& input) noexcept {
    if (!current(owner)) return {Status::unavailable, 0};
    if (revision_ == std::numeric_limits<std::uint64_t>::max()) return {Status::exhausted, 0};
    Record candidate;
    const auto status = prepare(input, candidate);
    if (status != Status::ok) return {status, 0};
    candidate.revision = ++revision_; const auto revision = candidate.revision;
    record_ = std::move(candidate); return {Status::ok, revision};
}
WriteResult Store::set(OwnerKey owner, Format format, TextInput text) noexcept {
    if (format == Format::unsupported) return {Status::unsupported, 0};
    if (!current(owner)) return {Status::unavailable, 0};
    auto input = inputFor(record_);
    (format == Format::plain ? input.plain : input.html) = {true, text};
    return replace(owner, input);
}
WriteResult Store::erase(OwnerKey owner, Format format) noexcept {
    if (format == Format::unsupported) return {Status::unsupported, 0};
    if (!current(owner)) return {Status::unavailable, 0};
    auto input = inputFor(record_); (format == Format::plain ? input.plain : input.html) = {};
    return replace(owner, input);
}
WriteResult Store::clear(OwnerKey owner) noexcept { return replace(owner, {}); }
WriteAttempt::WriteAttempt(ReceiptBook& book, const void* object, OwnerKey owner) noexcept
    : book_(&book), object_(object), owner_(owner) { book.enter(*this); }
WriteAttempt::~WriteAttempt() { if (book_) book_->leave(*this); }
bool WriteAttempt::consume(OwnerKey owner, std::uint64_t revision, bool matches) noexcept {
    if (consumed_) return false;
    consumed_ = true;
    return book_ && !book_->broken_ && id_ && owner == owner_ && matches && committed_
        && revision_ && revision == revision_;
}
void ReceiptBook::enter(WriteAttempt& attempt) noexcept {
    if (broken_ || !attempt.object_ || !attempt.owner_ || depth_ == 64
        || attempts_ == std::numeric_limits<std::uint64_t>::max()) return;
    attempt.id_ = ++attempts_; attempt.previous_ = top_; top_ = &attempt; ++depth_;
}
void ReceiptBook::leave(WriteAttempt& attempt) noexcept {
    if (!attempt.id_) return;
    if (top_ == &attempt) { top_ = attempt.previous_; --depth_; return; }
    broken_ = true;
    for (auto* current = top_; current; current = current->previous_) {
        if (current->previous_ == &attempt) { current->previous_ = attempt.previous_; --depth_; return; }
    }
}
WriteToken ReceiptBook::beginWrite(const void* object, OwnerKey owner) noexcept {
    return reserveWrite(object, owner).token;
}
WriteReservation ReceiptBook::reserveWrite(const void* object, OwnerKey owner) noexcept {
    if (broken_) return {{}, Status::unavailable};
    for (auto* attempt = top_; attempt; attempt = attempt->previous_) {
        if (attempt->object_ != object || attempt->owner_ != owner) continue;
        attempt->committed_ = false; attempt->revision_ = 0; attempt->write_ = 0;
        if (attempt->consumed_) return {{}, Status::unavailable};
        if (writes_ == std::numeric_limits<std::uint64_t>::max()) return {{}, Status::exhausted};
        attempt->write_ = ++writes_;
        return {{object, owner, attempt->id_, attempt->write_}, Status::ok};
    }
    return {};
}
void ReceiptBook::complete(const WriteToken& token, WriteResult result) noexcept {
    if (!token || broken_) return;
    for (auto* attempt = top_; attempt; attempt = attempt->previous_) {
        if (attempt->id_ != token.attempt || attempt->object_ != token.object || attempt->owner_ != token.owner
            || attempt->write_ != token.write || attempt->consumed_) continue;
        attempt->committed_ = result.status == Status::ok && result.revision;
        attempt->revision_ = attempt->committed_ ? result.revision : 0; return;
    }
}
void ReceiptBook::fail(const void* object) noexcept {
    for (auto* attempt = top_; attempt; attempt = attempt->previous_)
        if (attempt->object_ == object) { attempt->committed_ = false; attempt->revision_ = 0; attempt->write_ = 0; }
}
void ReceiptBook::retire() noexcept {
    broken_ = true;
    for (auto* attempt = top_; attempt; attempt = attempt->previous_) {
        attempt->committed_ = false; attempt->revision_ = 0; attempt->write_ = 0;
    }
}
KeyCommand commandForKey(KeyFacts key) noexcept {
    if (!key.raw_down || key.prevented || key.handled || key.alt || key.system || key.control == key.meta) return KeyCommand::none;
    switch (key.key) {
    case 'c': case 'C': return key.shift ? KeyCommand::none : KeyCommand::copy;
    case 'x': case 'X': return key.shift ? KeyCommand::none : KeyCommand::cut;
    case 'v': case 'V': return key.shift ? KeyCommand::paste_plain : KeyCommand::paste;
    default: return KeyCommand::none;
    }
}
const char* commandName(KeyCommand command) noexcept {
    switch (command) {
    case KeyCommand::copy: return "Copy";
    case KeyCommand::cut: return "Cut";
    case KeyCommand::paste: return "Paste";
    case KeyCommand::paste_plain: return "PasteAsPlainText";
    case KeyCommand::none: return "";
    }
    return "";
}
} // namespace BIB::Clipboard
