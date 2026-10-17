// SPDX-License-Identifier: CC0-1.0
// Private application-local clipboard values. No DOM, platform or public ABI.
#pragma once
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string_view>
#include <utility>

namespace BIB::Clipboard {
struct OwnerKey {
    std::uint64_t runtime_generation{}, worker{}, application{};
    friend bool operator==(const OwnerKey&, const OwnerKey&) = default;
    explicit operator bool() const noexcept { return runtime_generation && worker && application; }
};
enum class Format { plain, html, unsupported };
Format formatForMime(std::string_view) noexcept;
enum class Status { ok, unavailable, unsupported, limit, allocation_failure, exhausted, invalid };
struct Allocator {
    void* context{};
    char16_t* (*allocate)(void*, std::size_t) noexcept{};
    void (*deallocate)(void*, char16_t*, std::size_t) noexcept{};
};
Allocator defaultAllocator() noexcept;
struct TextInput {
    const char16_t* units{};
    const unsigned char* latin1{};
    std::size_t length{};
    bool valid() const noexcept { return !length || (!!units != !!latin1); }
};
struct ValueInput { bool present{}; TextInput text{}; };
struct Input { ValueInput plain{}, html{}; };
class OwnedText {
public:
    OwnedText() noexcept = default;
    ~OwnedText();
    OwnedText(const OwnedText&) = delete;
    OwnedText& operator=(const OwnedText&) = delete;
    OwnedText(OwnedText&&) noexcept;
    OwnedText& operator=(OwnedText&&) noexcept;
    const char16_t* data() const noexcept { return data_; }
    std::size_t size() const noexcept { return length_; }
    bool present() const noexcept { return present_; }
    TextInput view() const noexcept { return {data_, nullptr, length_}; }
private:
    friend class Store;
    void reset() noexcept;
    char16_t* data_{};
    std::size_t length_{};
    bool present_{};
    Allocator allocator_{};
};
struct Record {
    OwnedText plain{}, html{};
    std::uint64_t revision{};
    bool hasData() const noexcept { return plain.present() || html.present(); }
};
struct WriteResult { Status status{Status::unavailable}; std::uint64_t revision{}; };
class Store {
public:
    static constexpr std::size_t max_units = 32768;
    explicit Store(Allocator = defaultAllocator(), std::uint64_t initial_revision = 0) noexcept;
    Store(const Store&) = delete;
    Store& operator=(const Store&) = delete;
    bool bind(OwnerKey) noexcept;
    void retire() noexcept;
    OwnerKey owner() const noexcept { return owner_; }
    const Record* current(OwnerKey) const noexcept;
    Status snapshot(OwnerKey, Record&) const noexcept;
    WriteResult replace(OwnerKey, const Input&) noexcept;
    WriteResult set(OwnerKey, Format, TextInput) noexcept;
    WriteResult erase(OwnerKey, Format) noexcept;
    WriteResult clear(OwnerKey) noexcept;
private:
    Status prepare(const Input&, Record&) const noexcept;
    Allocator allocator_{};
    OwnerKey owner_{};
    Record record_{};
    std::uint64_t revision_{};
};

// Stack-owned exact default-Cut write receipts. This is not a Page registry.
class ReceiptBook;
struct WriteToken {
    const void* object{};
    OwnerKey owner{};
    std::uint64_t attempt{}, write{};
    explicit operator bool() const noexcept { return object && attempt && write; }
};
struct WriteReservation { WriteToken token{}; Status status{Status::ok}; };
class WriteAttempt {
public:
    WriteAttempt(ReceiptBook&, const void* exact_object, OwnerKey) noexcept;
    ~WriteAttempt();
    WriteAttempt(const WriteAttempt&) = delete;
    WriteAttempt& operator=(const WriteAttempt&) = delete;
    bool valid() const noexcept { return id_ != 0; }
    bool consume(OwnerKey, std::uint64_t current_record_revision, bool source_fence_matches) noexcept;
private:
    friend class ReceiptBook;
    ReceiptBook* book_{};
    WriteAttempt* previous_{};
    const void* object_{};
    OwnerKey owner_{};
    std::uint64_t id_{}, write_{}, revision_{};
    bool committed_{}, consumed_{};
};
class ReceiptBook {
public:
    explicit ReceiptBook(std::uint64_t attempts = 0, std::uint64_t writes = 0) noexcept
        : attempts_(attempts), writes_(writes) { }
    ReceiptBook(const ReceiptBook&) = delete;
    ReceiptBook& operator=(const ReceiptBook&) = delete;
    WriteToken beginWrite(const void*, OwnerKey) noexcept;
    WriteReservation reserveWrite(const void*, OwnerKey) noexcept;
    void complete(const WriteToken&, WriteResult) noexcept;
    void fail(const void*) noexcept;
    void retire() noexcept;
private:
    friend class WriteAttempt;
    void enter(WriteAttempt&) noexcept;
    void leave(WriteAttempt&) noexcept;
    WriteAttempt* top_{};
    std::uint64_t attempts_{}, writes_{};
    std::size_t depth_{};
    bool broken_{};
};

enum class KeyCommand { none, copy, cut, paste, paste_plain };
struct KeyFacts {
    bool raw_down{}, prevented{}, handled{}, control{}, meta{}, alt{}, shift{}, system{};
    char key{}; // Actual platform logical key, ASCII C/X/V only.
};
KeyCommand commandForKey(KeyFacts) noexcept;
const char* commandName(KeyCommand) noexcept;
} // namespace BIB::Clipboard
