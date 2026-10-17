// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "appended_engine_owner.hpp"
#include "compiled_region_feature.hpp"
#include <functional>
#include <memory>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>

namespace foundation::ui {

// One startup/Module/service policy shared by bitmap and semantic composition.
// Hooks only take/stage owned application values. The root remains the sole
// presenter and owns its existing Driver turn; this policy creates neither.
class EnginePrimaryApplicationPolicy {
public:
    struct Hooks {
        std::function<std::optional<CompiledRegionEvent>()> take_compiled_event;
        std::function<bool(EngineRegionComposition)> queue_compiled_region;
        std::function<std::uint64_t()> compiled_region_published_revision;
        std::function<bool()> owned_service_ready;
        std::function<void(bool)> set_owned_service_active;
    };

    EnginePrimaryApplicationPolicy(std::shared_ptr<appended::EngineOwner> owner, Hooks hooks)
        : owner_(require_owner(std::move(owner))), primary_(owner_->startup_primary()), hooks_(std::move(hooks)) {
        if (!hooks_.take_compiled_event || !hooks_.queue_compiled_region ||
            !hooks_.compiled_region_published_revision || !hooks_.owned_service_ready ||
            !hooks_.set_owned_service_active)
            throw std::invalid_argument("Primary application policy needs all five owned-value hooks");
        // No hook runs during construction. The root can establish its Base
        // and initial sole publication before callbacks to that root are armed.
        if (primary_ == appended::EngineStartupPrimary::binary) {
            const auto region = initial_region(owner_);
            queued_revision_ = region->revision();
            binary_canvas_ = region->compiled().client_size;
            binary_pane_ = region->pane();
        }
    }

    static std::optional<EngineRegionComposition> initial_region(
            const std::shared_ptr<appended::EngineOwner>& owner) {
        require_owner(owner);
        switch (owner->startup_primary()) {
        case appended::EngineStartupPrimary::web: return {};
        case appended::EngineStartupPrimary::compiled: return CompiledRegionFeature::make_region(1, 0);
        case appended::EngineStartupPrimary::binary:
            if (auto model = owner->binary_view(); model && model->snapshot().revision)
                return EngineRegionComposition::from_binary_view(*model);
            throw std::invalid_argument("Binary primary needs its initialized single-Module view");
        }
        throw std::invalid_argument("Unsupported rich primary selection");
    }

    void tick() {
        check_owner();
        if (owner_->closed() && !closing_) shutdown();
        if (closing_) return; // Only the root's existing checked close drain runs.
        if (primary_ == appended::EngineStartupPrimary::compiled) {
            while (auto intent = hooks_.take_compiled_event()) compiled_.accept(*intent);
            compiled_.stage(*this);
        } else if (primary_ == appended::EngineStartupPrimary::binary) tick_binary();
    }

    void set_external_service_active(bool active) {
        check_owner();
        if (closing_ || owner_->closed()) return;
        external_service_held_ = active;
        apply_service_hold();
    }
    bool service_pending() const noexcept {
        return thread_ == std::this_thread::get_id() && service_held_;
    }
    std::optional<gui::ServiceRequest> next_service() {
        check_owner();
        if (closing_ || owner_->closed() || external_service_held_ ||
            primary_ != appended::EngineStartupPrimary::binary || service_sent_) return {};
        if (!service_request_) service_request_ = owner_->begin_binary_view_service();
        if (!service_request_) return {};
        if (!service_held_) { service_held_ = true; apply_service_hold(); }
        if (!hooks_.owned_service_ready()) return {};
        service_sent_ = service_request_->request.id;
        return service_request_->request;
    }
    bool complete_service(gui::ServiceResult result) {
        check_owner();
        if (primary_ != appended::EngineStartupPrimary::binary || !service_sent_ ||
            result.id != *service_sent_ || service_result_staged_) return false;
        // Preserve the ordinary App's outer bound. The actual mutable queue in
        // the one Module binding applies request-specific normalization later.
        if (result.status == gui::ServiceStatus::cancelled) { result.value.clear(); result.error.clear(); }
        else if (result.value.size() > 65536 || result.error.size() > 65536) {
            result.status = gui::ServiceStatus::error;
            result.value.clear(); result.error = "Host service result exceeds the 64 KiB view limit";
        }
        if (closing_ || owner_->closed()) {
            // The offered external UI is actually complete. No obsolete guest
            // entry or guest ACK is invented while releasing its local debt.
            clear_service(); return true;
        }
        const auto encoded = appended::EngineModuleView::encode_service_result(result);
        if (!owner_->stage_binary_view_service_result(encoded)) return false;
        service_result_staged_ = true;
        return true;
    }
    void shutdown() noexcept {
        if (thread_ != std::this_thread::get_id() || closing_) return;
        closing_ = true; intent_.reset();
        // Unoffered work never entered external UI. A staged result already
        // proves that UI completed; only an outstanding offer remains debt.
        if (!service_sent_ || service_result_staged_) clear_service();
    }
    bool debt_complete() const noexcept {
        return thread_ == std::this_thread::get_id() && !service_sent_;
    }
    bool closing() const noexcept {
        return thread_ == std::this_thread::get_id() && closing_;
    }

private:
    friend class CompiledRegionFeature;
    static std::shared_ptr<appended::EngineOwner> require_owner(std::shared_ptr<appended::EngineOwner> owner) {
        if (!owner) throw std::invalid_argument("Primary application policy needs its configured Owner");
        return owner;
    }
    void check_owner() const {
        if (thread_ != std::this_thread::get_id())
            throw std::logic_error("Primary application policy needs its serialized application owner");
    }
    bool queue_compiled_region(EngineRegionComposition region) {
        return hooks_.queue_compiled_region(std::move(region));
    }
    void apply_service_hold() {
        hooks_.set_owned_service_active(external_service_held_ || service_held_);
    }
    void clear_service() noexcept {
        service_sent_.reset(); service_result_staged_ = false;
        service_request_.reset(); service_held_ = false;
    }
    void tick_binary() {
        auto model = owner_->binary_view();
        if (!model) return;
        if (model->pending() && hooks_.compiled_region_published_revision() == model->snapshot().revision)
            (void)owner_->acknowledge_binary_view(model->snapshot().revision);
        if (!service_held_) {
            if (!intent_) intent_ = hooks_.take_compiled_event();
            if (intent_) {
                if (intent_->revision != model->snapshot().revision) intent_.reset();
                else {
                    auto event = intent_->raw_event;
                    appended::EngineModuleView::EventFacts facts{intent_->focused, intent_->scroll_offsets};
                    if (!model->normalize_event(event, facts)) intent_.reset();
                    else {
                        const auto encoded = appended::EngineModuleView::encode_event(event, intent_->revision);
                        if (owner_->stage_binary_view_event(intent_->revision, encoded)) intent_.reset();
                    }
                }
            }
        }
        owner_->tick_binary_view();
        if (service_sent_ && service_result_staged_) {
            const auto active = owner_->current_binary_view_service();
            if (!active || active->request.id != *service_sent_) {
                service_sent_.reset(); service_result_staged_ = false; service_request_.reset();
                // A successor is a new reservation, never a current query.
                service_request_ = owner_->begin_binary_view_service();
                if (!service_request_) { service_held_ = false; apply_service_hold(); }
            }
        }
        model = owner_->binary_view();
        if (model && model->pending() && model->snapshot().revision > queued_revision_) {
            auto region = EngineRegionComposition::from_binary_view(*model);
            if (region.compiled().client_size != binary_canvas_ || region.pane() != binary_pane_)
                throw std::invalid_argument("Binary rich region changed its fixed root layout; a maintained resize successor is required");
            if (queue_compiled_region(std::move(region))) queued_revision_ = model->snapshot().revision;
        }
    }

    const std::thread::id thread_ = std::this_thread::get_id();
    const std::shared_ptr<appended::EngineOwner> owner_;
    const appended::EngineStartupPrimary primary_;
    const Hooks hooks_;
    CompiledRegionFeature compiled_;
    std::optional<CompiledRegionEvent> intent_;
    std::uint64_t queued_revision_{};
    gui::Size binary_canvas_;
    gui::Rect binary_pane_;
    bool closing_{}, external_service_held_{}, service_held_{}, service_result_staged_{};
    std::optional<std::uint64_t> service_sent_;
    std::shared_ptr<const appended::EngineModuleServiceRequest> service_request_;
};

} // namespace foundation::ui
