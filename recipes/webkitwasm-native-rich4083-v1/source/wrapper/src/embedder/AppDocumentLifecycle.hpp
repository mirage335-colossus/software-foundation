// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <utility>

namespace foundation::appended::candidate {

// Serialized composition metadata only: this class neither owns an engine
// object/epoch nor runs an engine, native-service or author callback. The owner
// must keep the engine objects represented by physical IDs alive while using
// them, and must retire returned resource/native identities itself.
class AppDocumentLifecycle final {
public:
    using AppInstance = std::uint64_t; // Remains 64 bits on Wasm32.
    using PhysicalId = std::uintptr_t;
    using Token = std::uint64_t;
    using ResourceEpoch = std::uint64_t;
    using ServiceGeneration = std::uint64_t;

    struct Active final {
        AppInstance app_instance{};
        Token token{};
        PhysicalId frame{};
        PhysicalId loader{};
        PhysicalId document{};
        ResourceEpoch resource_epoch{};
        ServiceGeneration service_generation{};
        friend bool operator==(const Active&, const Active&) = default;
    };

    // An allocation-free copy safe to retain across reentrant callbacks. A
    // nonzero selected_document means begin_selection already consumed the
    // record's one permitted selection attempt.
    struct PendingIdentity {
        AppInstance app_instance{};
        Token token{};
        PhysicalId frame{};
        PhysicalId loader{};
        ResourceEpoch resource_epoch{};
        PhysicalId predecessor_document{};
        PhysicalId selected_document{};
        friend bool operator==(const PendingIdentity&, const PendingIdentity&) = default;
    };

    struct Pending final : PendingIdentity {
        std::string expected_url;
        bool callback_registered{};
        bool selecting{};
    };

    struct Retired final {
        std::optional<Active> active;
        std::optional<PendingIdentity> pending;
    };

    static constexpr std::size_t max_expected_url_bytes = 4096;

    explicit AppDocumentLifecycle(AppInstance app_instance) noexcept
        : app_instance_(app_instance) { }
    AppDocumentLifecycle(const AppDocumentLifecycle&) = delete;
    AppDocumentLifecycle& operator=(const AppDocumentLifecycle&) = delete;
    AppDocumentLifecycle(AppDocumentLifecycle&&) = delete;
    AppDocumentLifecycle& operator=(AppDocumentLifecycle&&) = delete;

    // Reserve the canonical document sequence BEFORE the owner calls the
    // external resource host. The pending epoch remains zero until attachment;
    // a reservation alone can never register, select or activate a document.
    // Existing pending state must be explicitly discarded before replacement.
    // Invalid/occupied/exhausted reservations return zero without mutation.
    // URL allocation may throw without mutation. A successful reservation burns
    // its sequence once even if later resource admission/attachment fails.
    [[nodiscard]] Token reserve_pending(PhysicalId frame, PhysicalId loader,
        PhysicalId predecessor_document, std::string_view expected_url)
    {
        if (!app_instance_ || !frame || !loader || pending_ || !next_token_ ||
            expected_url.empty() || expected_url.size() > max_expected_url_bytes ||
            expected_url.find('\0') != std::string_view::npos)
            return 0;

        const auto token = next_token_;
        // Allocate before publishing any identity/counter changes. Moving this
        // standard-allocator string into optional storage cannot allocate.
        Pending next{PendingIdentity{app_instance_, token, frame, loader,
            0, predecessor_document, 0}, std::string(expected_url), false, false};
        pending_.emplace(std::move(next));
        next_token_ = token == std::numeric_limits<Token>::max() ? 0 : token + 1;
        return token;
    }

    // Attach only the exact still-current reservation, once. The private resource
    // epoch must be fresh, nonzero and monotonic independently of the canonical
    // document sequence. Failure leaves metadata untouched; the owner must retire
    // any externally admitted epoch and discard only its captured token. Neither
    // this helper nor cancellation owns an external host resource context.
    [[nodiscard]] bool attach_resource_epoch(Token token,
        ResourceEpoch resource_epoch) noexcept
    {
        if (!pending_ || !token || pending_->token != token ||
            pending_->resource_epoch || !resource_epoch ||
            resource_epoch <= highest_resource_epoch_)
            return false;
        pending_->resource_epoch = resource_epoch;
        highest_resource_epoch_ = resource_epoch;
        return true;
    }

    // Compatibility entry point for owners which already hold an admitted
    // resource epoch. Its invalid-epoch rejection retains the old no-mutation
    // behavior; new owners use reserve_pending before invoking their host.
    // Catch URL allocation failure and retire the externally admitted epoch.
    [[nodiscard]] Token begin_pending(PhysicalId frame, PhysicalId loader,
        ResourceEpoch resource_epoch, PhysicalId predecessor_document,
        std::string_view expected_url)
    {
        if (!resource_epoch || resource_epoch <= highest_resource_epoch_)
            return 0;
        const auto token = reserve_pending(frame, loader, predecessor_document,
            expected_url);
        if (!token)
            return 0;
        if (!attach_resource_epoch(token, resource_epoch)) {
            (void)discard_pending(token);
            return 0;
        }
        return token;
    }

    // Mark registration before installing whenDocumentIsCreated on the exact
    // loader. A failed/throwing engine registration discards this token; retrying
    // registration against the same pending record is deliberately impossible.
    [[nodiscard]] bool register_callback(Token token, PhysicalId loader) noexcept
    {
        if (!pending_ || !token || pending_->token != token || !loader ||
            pending_->loader != loader || !pending_->resource_epoch ||
            pending_->callback_registered)
            return false;
        pending_->callback_registered = true;
        return true;
    }

    // Consume the one selection attempt BEFORE forcing/initializing the main
    // world's global. Its recursive clear-global/document-created callback then
    // observes selecting and cannot start a second selection. The caller must
    // independently verify live engine ownership, the expected method/URL/MIME
    // and the committed Document. Metadata does not authenticate an engine ID.
    [[nodiscard]] bool begin_selection(Token token, PhysicalId frame,
        PhysicalId loader, PhysicalId document) noexcept
    {
        if (!pending_matches(token, frame, loader) || !document ||
            !pending_->callback_registered || pending_->selecting)
            return false;
        pending_->selected_document = document;
        pending_->selecting = true;
        return true;
    }

    // Invoke only after native selection, then revalidate the actual live
    // frame/loader/document and query the native owner's canonical generation.
    // The same exact pending selection must still exist. No author bytes may be
    // supplied until this succeeds. On false/throw in the surrounding selection,
    // the owner discards this token, retires any partial native generation and
    // cancels the loader before author bytes. An older active record is never
    // silently overwritten: retire it and its epoch/native roots explicitly.
    [[nodiscard]] bool activate(Token token, PhysicalId frame, PhysicalId loader,
        PhysicalId document, ServiceGeneration service_generation) noexcept
    {
        if (active_ || !pending_matches(token, frame, loader) || !document ||
            !pending_->callback_registered || !pending_->selecting ||
            pending_->selected_document != document || !service_generation ||
            service_generation == last_service_generation_)
            return false;

        active_.emplace(Active{app_instance_, token, frame, loader, document,
            pending_->resource_epoch, service_generation});
        last_service_generation_ = service_generation;
        pending_.reset();
        return true;
    }

    // For a synchronous current lifecycle notification. It clears only active
    // state; the successor's pending loader, epoch and one-use token survive.
    // A deferred notification must instead retain/use the full Active overload:
    // document.open can reuse all three physical engine identities.
    [[nodiscard]] std::optional<Active> retire_active(
        PhysicalId frame, PhysicalId document) noexcept
    {
        if (!active_ || !frame || !document || active_->frame != frame ||
            active_->document != document)
            return std::nullopt;
        auto retired = active_;
        active_.reset();
        return retired;
    }

    [[nodiscard]] std::optional<Active> retire_active(const Active& expected) noexcept
    {
        if (!active_ || *active_ != expected)
            return std::nullopt;
        auto retired = active_;
        active_.reset();
        return retired;
    }

    // Idempotent by token: stale cleanup cannot discard a replacement pending
    // load, even if it has exactly the same URL, loader or Document address.
    [[nodiscard]] std::optional<PendingIdentity> discard_pending(Token token) noexcept
    {
        if (!pending_ || !token || pending_->token != token)
            return std::nullopt;
        auto retired = pending_identity();
        pending_.reset();
        return retired;
    }

    [[nodiscard]] bool active_matches(PhysicalId frame, PhysicalId loader,
        PhysicalId document, ServiceGeneration service_generation) const noexcept
    {
        return active_ && frame && loader && document && service_generation &&
            active_->frame == frame && active_->loader == loader &&
            active_->document == document &&
            active_->service_generation == service_generation;
    }

    // Pair resource epoch with canonical native generation from one exact active
    // document. No generation is invented/remapped here. The native owner must
    // supply fresh nonzero generations; the immediately retained last generation
    // is rejected on reuse, but numeric ordering is not part of that C contract.
    [[nodiscard]] std::optional<Active> identity_for(PhysicalId frame,
        PhysicalId loader, PhysicalId document,
        ServiceGeneration service_generation) const noexcept
    {
        return active_matches(frame, loader, document, service_generation)
            ? active_ : std::nullopt;
    }

    [[nodiscard]] std::optional<Active> active_identity() const noexcept { return active_; }

    [[nodiscard]] std::optional<PendingIdentity> pending_identity() const noexcept
    {
        if (!pending_)
            return std::nullopt;
        return static_cast<const PendingIdentity&>(*pending_);
    }

    // Borrowed views expire on the next mutation. Copy an identity before any
    // callback which could discard, replace, activate or retire its record.
    [[nodiscard]] const Active* active() const noexcept
    {
        return active_ ? &*active_ : nullptr;
    }
    [[nodiscard]] const Pending* pending() const noexcept
    {
        return pending_ ? &*pending_ : nullptr;
    }
    [[nodiscard]] AppInstance app_instance() const noexcept { return app_instance_; }

    // Return identities before clearing so the owner can close both separate
    // resource contexts and their native roots. This does not close an engine
    // or reset the application instance, sequence, epoch or generation history.
    [[nodiscard]] Retired retire_all() noexcept
    {
        Retired retired{active_, pending_identity()};
        active_.reset();
        pending_.reset();
        return retired;
    }

private:
    [[nodiscard]] bool pending_matches(Token token, PhysicalId frame,
        PhysicalId loader) const noexcept
    {
        return pending_ && pending_->resource_epoch && token && frame && loader &&
            pending_->token == token &&
            pending_->frame == frame && pending_->loader == loader;
    }

    const AppInstance app_instance_;
    std::optional<Active> active_;
    std::optional<Pending> pending_;
    Token next_token_{1}; // Zero means exhausted; it never wraps/reuses.
    ResourceEpoch highest_resource_epoch_{};
    ServiceGeneration last_service_generation_{};
};

} // namespace foundation::appended::candidate
