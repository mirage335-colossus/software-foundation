// SPDX-License-Identifier: CC0-1.0
#pragma once

#include "engine_primary_application_policy.hpp"
#include "appended_document_controller.hpp"
#include "native_engine_document_composition.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <thread>

namespace foundation::ui {

// One semantic presenter over the existing4083 Forms/Broker/Owner/Driver. The
// compiled and HTML pages are application layout, not a second DOM or engine.
// The web-only selection forwards the original terminal composition unchanged.
namespace semantic_primary_detail {
class State final {
    static constexpr std::string_view compiled_tab = "foundation.semantic.compiled";
    static constexpr std::string_view document_tab = "foundation.semantic.document";
    static constexpr std::string_view content_clip = "foundation.semantic.content.clip";
    static constexpr std::string_view waiting_label = "foundation.semantic.waiting";
    struct Guard { bool& value; explicit Guard(bool& v) : value(v) { value = true; } ~Guard() { value = false; } };
    struct Scene {
        gui::Snapshot view, document;
        std::optional<EngineRegionComposition> compiled;
        bool compiled_active{}, masked{};
        std::uint64_t facts_version{};
        gui::Snapshot safe;
        double origin_y{};
        std::uint64_t source_revision{};
    };
    struct Bridge final : gui::Adapter {
        State& root;
        explicit Bridge(State& value) : root(value) {}
        void present(gui::Snapshot value) override { root.present_document(std::move(value)); }
        gui::Size measure_text(const gui::TextMeasureRequest& r) const override { return root.actual_.measure_text(r); }
        gui::Availability resolved_availability(const gui::WidgetKey& k) const override { return root.actual_.resolved_availability(k); }
        std::optional<gui::WidgetKey> focused() const override {
            const auto key = root.actual_.focused();
            if (!root.compiled_) return key;
            return key && gui::find_widget(root.document_source_, *key) ? key : std::nullopt;
        }
        bool focus(std::optional<gui::WidgetKey> key) override {
            if (root.compiled_ && key && !gui::find_widget(root.document_source_, *key)) return false;
            return root.actual_.focus(std::move(key));
        }
        bool focus_next(bool reverse) override { return root.actual_.focus_next(reverse); }
        void scroll(const gui::WidgetKey& k, gui::Point p) override { root.actual_.scroll(k, p); }
        gui::Point scroll_offset(const gui::WidgetKey& k) const override { return root.actual_.scroll_offset(k); }
        gui::TextSelection text_selection(const gui::WidgetKey& k) const override { return root.actual_.text_selection(k); }
        void text_selection(const gui::WidgetKey& k, gui::TextSelection v) override { root.actual_.text_selection(k, v); }
        bool open_popup(const gui::WidgetKey& k) override { return root.actual_.open_popup(k); }
        void close_popup(const gui::WidgetKey& k) override { root.actual_.close_popup(k); }
        void invalidate(const gui::WidgetKey& key, gui::PixelRect rectangle) override {
            if (!root.compiled_) { root.actual_.invalidate(key, rectangle); return; }
            // The sole terminal scene is republished normally; source pixels
            // are never mapped into a physical/bitmap qualification claim.
            root.dirty_ = true;
        }
        bool closed() const override { return root.closing_ || root.actual_.closed(); }
        void close() override { root.closing_ = true; if (!root.compiled_) root.actual_.close(); }
    };

public:
    using Clock = NativeEngineDocumentComposition::Clock;
    State(gui::Adapter& actual,
            std::shared_ptr<appended::EngineOwner> owner, appended::NativeEngineDriver& driver,
            NativeEngineDocumentComposition::PostOwnerWake wake = {})
        : actual_(actual), owner_(std::move(owner)),
          compiled_(EnginePrimaryApplicationPolicy::initial_region(owner_)), wake_(std::move(wake)),
          desired_compiled_(compiled_.has_value()), pane_hold_(compiled_.has_value()),
          policy_(owner_, {
              [this] { auto result = std::move(intent_); intent_.reset(); return result; },
              [this](EngineRegionComposition value) { return stage_compiled(std::move(value)); },
              [this] { return published_ && published_->compiled_active && !published_->masked ? published_->source_revision : 0; },
              [this] { return service_hold_ && !pending_ && published_ && published_->masked && document_.owned_service_ready(); },
              [this](bool value) { service_hold_ = value; intent_.reset(); changed(); apply_document_hold(); }
          }), bridge_(*this), document_(bridge_, owner_, driver, wake_) {
        // All policy hooks are armed only after the same facade is fully alive.
        if (pane_hold_) document_.set_owned_service_active(true);
    }

    void drawable_cells(std::int64_t columns, std::int64_t rows) {
        check_owner();
        if (columns < 1 || columns > 500 || rows < 1 || rows > 200) cells_.reset();
        else cells_ = DocumentViewport{static_cast<std::size_t>(columns), static_cast<std::size_t>(rows)};
        const auto chrome = compiled_ ? 2 : 0;
        document_.drawable_cells(columns, rows > chrome ? rows - chrome : 0);
        intent_.reset(); changed();
    }
    void foreground(bool value) {
        check_owner();
        if (foreground_ == value) return;
        foreground_ = value; document_.foreground(value);
        intent_.reset(); changed();
    }
    void handle(gui::Event event) {
        check_owner();
        if (std::holds_alternative<gui::CloseEvent>(event)) { shutdown(); return; }
        if (busy_ || closing_ || pending_ || dirty_ || service_hold_ || !foreground_ || !cells_ || owner_->native_effect()) return;
        if (!compiled_) { document_.handle(std::move(event)); return; }
        if (!published_ || published_->masked) return;
        Guard guard(busy_);
        if (compiled_region_event_charge(event) > 512 * 1024) return;
        const auto clip_offset = actual_.scroll_offset({std::string(content_clip), 1});
        if (clip_offset.x != 0 || clip_offset.y != 0) return;
        auto raw = event;
        if (!gui::normalize_event(published_->view, event,
                [this](const gui::WidgetKey& key) { return actual_.scroll_offset(key); })) return;
        if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
            if ((widget->target.id == compiled_tab || widget->target.id == document_tab) &&
                std::holds_alternative<gui::Activate>(widget->input)) {
                desired_compiled_ = widget->target.id == compiled_tab;
                if (desired_compiled_) { pane_hold_ = true; apply_document_hold(); }
                else visible_compiled_ = false; // Publish the held/redacted HTML pane first.
                intent_.reset(); changed(); return;
            }
        }
        inverse_origin(raw, published_->origin_y);
        inverse_origin(event, published_->origin_y);
        if (!published_->compiled_active) {
            document_.handle(std::move(raw)); return;
        }
        if (intent_ || !published_->compiled || !document_.owned_service_ready()) return;
        const auto& source = published_->compiled->compiled();
        if (const auto* widget = std::get_if<gui::WidgetEvent>(&event)) {
            if (!gui::find_widget(source, widget->target) && !gui::find_command(source, widget->target)) return;
        } else if (const auto* page = std::get_if<gui::PageEvent>(&event)) {
            if (std::none_of(source.pages.begin(), source.pages.end(), [&](const auto& p) { return p.id == page->id; })) return;
        }
        CompiledRegionEvent value;
        value.revision = published_->source_revision;
        value.event = std::move(event); value.raw_event = std::move(raw);
        // Facts use original Module groups and IDs. The semantic clip is not
        // invented as a guest scroll owner, and its extent cannot scroll.
        const auto model = owner_->binary_view();
        const auto& facts_source = model && model->snapshot().revision == value.revision ? model->snapshot() : source;
        value.focused = actual_.focused();
        if (value.focused && !gui::find_widget(facts_source, *value.focused)) value.focused.reset();
        for (const auto& widget : facts_source.widgets) if (widget.spec.kind == gui::Kind::group) {
            if (value.scroll_offsets.size() == 256) throw std::invalid_argument("Semantic event has too many owned scroll facts");
            const auto offset = actual_.scroll_offset(widget.spec.key);
            if (!std::isfinite(offset.x) || !std::isfinite(offset.y)) throw std::invalid_argument("Semantic scroll fact is not finite");
            value.scroll_offsets.emplace_back(widget.spec.key, offset);
        }
        value.retained_bytes = sizeof(value);
        const auto charge = [&](std::size_t amount) {
            if (amount > 1024 * 1024 - value.retained_bytes) return false;
            value.retained_bytes += amount; return true;
        };
        if (!charge(compiled_region_event_charge(value.event)) || !charge(compiled_region_event_charge(value.raw_event))) return;
        if (value.focused && !charge(value.focused->id.capacity())) return;
        for (const auto& fact : value.scroll_offsets) if (!charge(sizeof(fact) + fact.first.id.capacity())) return;
        intent_ = std::move(value);
    }

    void tick(Clock::time_point now = Clock::now()) {
        check_owner();
        if (busy_) return;
        Guard guard(busy_);
        if (owner_->native_effect()) intent_.reset();
        if (closing_ || owner_->closed()) {
            closing_ = true; policy_.shutdown(); document_.shutdown();
        }
        if (pending_) commit_pending();
        if (cells_) {
            const auto measure = actual_.measure_text({"M", {}, 1024, 1, gui::TextWrap::none});
            if (!std::isfinite(measure.width) || !std::isfinite(measure.height) || measure.width <= 0 || measure.height <= 0)
                throw std::invalid_argument("Terminal cell measurement is not positive and finite");
            cell_ = measure;
            if (desired_compiled_ && !visible_compiled_ && document_.owned_service_ready()) {
                visible_compiled_ = true; changed();
            }
            if (!closing_ && (!compiled_ || compiled_started_) && !owner_->native_effect() &&
                    (!pane_hold_ || document_.owned_service_ready())) policy_.tick();
            if (compiled_ && published_ && published_->masked && !service_hold_ && foreground_ && !closing_ &&
                    !owner_->native_effect() && (!pane_hold_ || document_.owned_service_ready())) changed();
            if (compiled_ && dirty_ && !pending_) publish_scene(document_source_);
        }
        // An actual external offer is cleared only by complete_service for its
        // exact sent ID. Preparation remains free to drain the real4083 debt.
        document_.tick(now);
        if (desired_compiled_ && !visible_compiled_ && document_.owned_service_ready()) {
            visible_compiled_ = true; changed();
        }
        if (document_.closed() && !closing_) { closing_ = true; policy_.shutdown(); }
        if (closing_ && shutdown_complete()) actual_.close();
    }
    void wake() noexcept { document_.wake(); }
    void retry_presentation() {
        check_owner();
        if (busy_) return;
        Guard guard(busy_);
        if (pending_) commit_pending();
        document_.retry_presentation();
    }
    void qualify(const std::function<void()>& present) { retry_presentation(); if (present) present(); }
    void shutdown() noexcept {
        if (thread_ != std::this_thread::get_id()) return;
        closing_ = true; intent_.reset(); policy_.shutdown(); document_.shutdown();
    }
    bool shutdown_complete() const noexcept {
        return thread_ == std::this_thread::get_id() && !pending_ && policy_.debt_complete() &&
            document_.native_state() == appended::NativeEngineState::detached;
    }
    std::optional<gui::ServiceRequest> next_service() {
        check_owner();
        if (busy_ || closing_ || !foreground_ || !cells_ || (compiled_ && !compiled_started_)) return {};
        auto value = policy_.next_service();
        if (value) document_.set_owned_service_offered(true);
        return value;
    }
    bool complete_service(gui::ServiceResult result) {
        check_owner();
        if (busy_ || !policy_.complete_service(std::move(result))) return false;
        // A true result matched the one real offer. Completion only stages
        // owned bytes; the next policy turn consumes/normalizes in the Module.
        document_.set_owned_service_offered(false); return true;
    }
    bool queue_selection(DocumentSelection value) {
        check_owner();
        return !busy_ && !closing_ && !pending_ && !service_hold_ &&
            (!compiled_ || (published_ && !published_->compiled_active)) && document_.queue_selection(std::move(value));
    }
    const gui::Snapshot& view() const noexcept {
        if (thread_ != std::this_thread::get_id()) return empty_view_;
        if (compiled_ && published_) return (service_hold_ || !foreground_ || !cells_ || closing_ || owner_->native_effect() || (pane_hold_ && !visible_compiled_ && desired_compiled_)) ? published_->safe : published_->view;
        return document_.view();
    }
    std::uint64_t input_epoch() const noexcept { return thread_ == std::this_thread::get_id() ? (compiled_ ? epoch_ : document_.input_epoch()) : 0; }
    bool closed() const noexcept { return thread_ != std::this_thread::get_id() || closing_ || document_.closed(); }
    bool presentation_pending() const noexcept { return thread_ == std::this_thread::get_id() && (pending_.has_value() || dirty_ || document_.presentation_pending()); }
    bool body_ready() const noexcept { return thread_ == std::this_thread::get_id() && !pending_ && (!compiled_ || (published_ && !published_->compiled_active && !published_->masked)) && document_.body_ready(); }
    bool modal_open() const noexcept { return thread_ == std::this_thread::get_id() && document_.modal_open(); }
    const std::string& last_error() const noexcept { return thread_ == std::this_thread::get_id() ? document_.last_error() : empty_error_; }
    appended::NativeEngineState native_state() const noexcept { return thread_ == std::this_thread::get_id() ? document_.native_state() : appended::NativeEngineState::blocked; }
    std::optional<Clock::time_point> deadline() const noexcept { return thread_ == std::this_thread::get_id() ? document_.deadline() : std::nullopt; }

private:
    void check_owner() const {
        if (thread_ != std::this_thread::get_id()) throw std::logic_error("Semantic primary requires its serialized owner");
    }
    void advance_epoch() {
        if (epoch_ == std::numeric_limits<std::uint64_t>::max()) { shutdown(); throw std::overflow_error("Semantic input epoch exhausted"); }
        ++epoch_;
    }
    void changed() {
        if (facts_version_ == std::numeric_limits<std::uint64_t>::max()) { shutdown(); throw std::overflow_error("Semantic layout facts exhausted"); }
        ++facts_version_; dirty_ = true; advance_epoch();
        if (wake_) { try { wake_(); } catch (...) {} } // Schedule only, never recursively pump.
    }
    void apply_document_hold() { document_.set_owned_service_active(pane_hold_ || service_hold_); }
    static void inverse_origin(gui::Event& event, double y) {
        if (auto* widget = std::get_if<gui::WidgetEvent>(&event))
            if (auto* pointer = std::get_if<gui::PointerInput>(&widget->input)) pointer->position.y -= y;
    }
    bool stage_compiled(EngineRegionComposition value) {
        if (closing_ || pending_ || document_.modal_open()) return false;
        if (!compiled_ || !compiled_->same_layout(value)) throw std::invalid_argument("Semantic compiled layout changed");
        compiled_ = std::move(value); changed(); return true;
    }
    static void mask_widget(gui::Widget& widget) {
        const auto bounds = widget.state.bounds;
        const auto extent = widget.state.content_size;
        const auto clip = widget.state.content_clip;
        widget.state = {}; widget.state.bounds = bounds;
        widget.state.content_size = extent; widget.state.content_clip = clip;
        widget.state.visible = false; widget.state.enabled = false;
    }
    Scene compose(gui::Snapshot document) {
        if (!cells_ || !compiled_) throw std::logic_error("Semantic scene needs actual cells and its compiled source");
        if (revision_ == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("Semantic publication revision exhausted");
        Scene result;
        result.document = std::move(document); result.compiled = compiled_;
        result.compiled_active = visible_compiled_;
        result.facts_version = facts_version_;
        const auto& compiled = compiled_->compiled();
        if (compiled.modal_root && result.document.modal_root) throw std::invalid_argument("Semantic sources have competing modals");
        if (compiled.modal_root && result.compiled_active) result.compiled_active = true;
        if (result.document.modal_root && !result.compiled_active) result.compiled_active = false;
        result.masked = service_hold_ || !foreground_ || closing_ || owner_->native_effect().has_value() ||
            (pane_hold_ && !document_.owned_service_ready() && (visible_compiled_ || desired_compiled_));
        result.origin_y = 2 * cell_.height;
        result.source_revision = compiled_->revision();
        auto& view = result.view;
        view.revision = revision_ + 1; view.title = "Foundation application and HTML document";
        view.client_size = {cells_->columns * cell_.width, cells_->drawable_rows * cell_.height};
        if (result.compiled_active) {
            // Preserve source logical geometry. The actual TerminalAdapter's
            // 8x16-cell viewport/reveal pans to focused controls and carets.
            // HTML instead keeps its exact actual-cell canvas, which clamps
            // any previous global pan back to zero when its page is selected.
            view.client_size.width = std::max(view.client_size.width, compiled.client_size.width);
            view.client_size.height = std::max(view.client_size.height, compiled.client_size.height + result.origin_y);
        }
        view.display_scale = 1;
        gui::Widget clip;
        clip.spec.key = {std::string(content_clip), 1}; clip.spec.kind = gui::Kind::group;
        clip.state.bounds = {0, result.origin_y, view.client_size.width, std::max(0.0, view.client_size.height - result.origin_y)};
        clip.state.content_size = {clip.state.bounds.width, clip.state.bounds.height};
        view.widgets.push_back(std::move(clip));
        std::set<std::string> ids{std::string(content_clip), std::string(compiled_tab), std::string(document_tab), std::string(waiting_label)};
        std::set<std::string> pages;
        const auto append = [&](const gui::Snapshot& source, bool active) {
            for (const auto& original : source.widgets) {
                if (!ids.insert(original.spec.key.id).second) throw std::invalid_argument("Semantic source widget ID collision");
                auto widget = original;
                widget.state.bounds.y += result.origin_y;
                if (widget.spec.parent.empty()) widget.spec.parent = std::string(content_clip);
                // Hidden native text is cleared, including options/records and
                // callable bitmap state. It is not exported as invisible data.
                if (!active || result.masked) mask_widget(widget);
                view.widgets.push_back(std::move(widget));
            }
            for (auto command : source.commands) {
                if (!ids.insert(command.key.id).second) throw std::invalid_argument("Semantic source command ID collision");
                if (!active || result.masked) command.enabled = false;
                view.commands.push_back(std::move(command));
            }
            for (auto page : source.pages) {
                if (!pages.insert(page.id).second) throw std::invalid_argument("Semantic source page ID collision");
                if (!active || result.masked) { page.label.clear(); page.visible = false; page.enabled = false; }
                view.pages.push_back(std::move(page));
            }
            if (active && !result.masked) {
                view.active_page = source.active_page;
                view.page_bar = source.page_bar; view.page_bar.y += result.origin_y;
                view.modal_root = source.modal_root; view.key_bindings = source.key_bindings;
                view.palette = source.palette;
            }
        };
        append(compiled, result.compiled_active);
        append(result.document, !result.compiled_active);
        for (unsigned n = 0; n != 2; ++n) {
            gui::Widget button;
            button.spec.key = {std::string(n ? document_tab : compiled_tab), 1}; button.spec.kind = gui::Kind::button;
            button.state.bounds = {n * view.client_size.width / 2, 0, view.client_size.width / 2, result.origin_y};
            button.state.text = n ? "HTML document" : "Application";
            button.state.enabled = !result.masked && !view.modal_root;
            view.widgets.push_back(std::move(button));
        }
        gui::validate_snapshot(view);
        result.safe = view;
        for (auto& widget : result.safe.widgets) mask_widget(widget);
        for (auto& page : result.safe.pages) { page.label.clear(); page.visible = false; page.enabled = false; }
        for (auto& command : result.safe.commands) command.enabled = false;
        result.safe.modal_root.reset(); result.safe.active_page.reset(); result.safe.key_bindings.clear();
        return result;
    }
    void publish_scene(gui::Snapshot document) {
        if (pending_) throw std::logic_error("Semantic publication retry must settle first");
        if (!cells_ && published_) {
            // With no current drawable cells, redact the previous logical
            // scene only. No larger/current viewport is invented for Forms.
            if (revision_ == std::numeric_limits<std::uint64_t>::max()) throw std::overflow_error("Semantic publication revision exhausted");
            pending_ = *published_; pending_->document = std::move(document);
            pending_->view = pending_->safe; pending_->view.revision = revision_ + 1;
            pending_->safe.revision = pending_->view.revision; pending_->masked = true;
            pending_->facts_version = facts_version_;
        } else pending_ = compose(std::move(document));
        commit_pending();
    }
    void commit_pending() {
        if (!pending_) return;
        actual_.present(pending_->view); // Throw preserves this exact combined candidate.
        // This causal record, not numerical revision equality, proves which
        // original semantic candidate reached the sole actual presenter.
        document_source_ = pending_->document;
        revision_ = pending_->view.revision;
        const bool switched = published_ && published_->compiled_active != pending_->compiled_active;
        const auto applied_facts = pending_->facts_version;
        published_ = std::move(pending_); pending_.reset(); dirty_ = facts_version_ != applied_facts;
        if (published_->compiled_active && !published_->masked) compiled_started_ = true;
        advance_epoch();
        if (!published_->compiled_active && !desired_compiled_ && pane_hold_) {
            // The actual HTML page is visible with its held/redacted scene.
            // Now request the original fresh observation before any HTML input.
            pane_hold_ = false; apply_document_hold();
        }
        if (switched) { intent_.reset(); (void)actual_.focus(std::nullopt); }
    }
    void present_document(gui::Snapshot value) {
        if (!compiled_) {
            actual_.present(value); document_source_ = std::move(value); dirty_ = false; return;
        }
        if (pending_) {
            if (pending_->document.revision != value.revision)
                throw std::logic_error("A prior combined presentation still needs exact retry");
            commit_pending(); return;
        }
        if (published_ && published_->document.revision == value.revision) {
            // A root-owned exact retry may already have published this origin;
            // return its retained actual-publication receipt to the inner App.
            return;
        }
        if (value.revision < document_source_.revision) throw std::invalid_argument("Semantic document origin went backwards");
        publish_scene(std::move(value));
    }

    gui::Adapter& actual_;
    const std::shared_ptr<appended::EngineOwner> owner_;
    const std::thread::id thread_ = std::this_thread::get_id();
    std::optional<EngineRegionComposition> compiled_;
    const NativeEngineDocumentComposition::PostOwnerWake wake_;
    bool compiled_started_{}, desired_compiled_{}, pane_hold_{}, visible_compiled_{}, foreground_ = true, closing_{}, busy_{}, service_hold_{}, dirty_ = true;
    std::optional<DocumentViewport> cells_;
    gui::Size cell_{1, 1};
    std::uint64_t revision_{}, epoch_ = 1, facts_version_ = 1;
    gui::Snapshot document_source_;
    std::optional<Scene> pending_, published_;
    std::optional<CompiledRegionEvent> intent_;
    const gui::Snapshot empty_view_;
    const std::string empty_error_;
    EnginePrimaryApplicationPolicy policy_;
    Bridge bridge_;
    NativeEngineDocumentComposition document_;
};
} // namespace semantic_primary_detail

// Keep the complete Adapter bridge and policy alive on unresolved close, just
// as the existing native composition retains its Forms/Broker/Owner evidence.
class SemanticPrimaryDocumentApplication final {
public:
    using Clock = semantic_primary_detail::State::Clock;
    template<class... Args> explicit SemanticPrimaryDocumentApplication(Args&&... args)
        : state_(std::make_unique<semantic_primary_detail::State>(std::forward<Args>(args)...)) {}
    ~SemanticPrimaryDocumentApplication() {
        if (!state_) return;
        state_->shutdown();
        if (!state_->shutdown_complete()) (void)state_.release();
    }
    void handle(gui::Event value) { state_->handle(std::move(value)); }
    void tick(Clock::time_point now = Clock::now()) { state_->tick(now); }
    void drawable_cells(std::int64_t columns, std::int64_t rows) { state_->drawable_cells(columns, rows); }
    void foreground(bool value) { state_->foreground(value); }
    void wake() noexcept { state_->wake(); }
    void retry_presentation() { state_->retry_presentation(); }
    void qualify(const std::function<void()>& present) { state_->qualify(present); }
    void shutdown() noexcept { state_->shutdown(); }
    bool shutdown_complete() const noexcept { return state_->shutdown_complete(); }
    std::optional<gui::ServiceRequest> next_service() { return state_->next_service(); }
    bool complete_service(gui::ServiceResult value) { return state_->complete_service(std::move(value)); }
    bool queue_selection(DocumentSelection value) { return state_->queue_selection(std::move(value)); }
    const gui::Snapshot& view() const noexcept { return state_->view(); }
    std::uint64_t input_epoch() const noexcept { return state_->input_epoch(); }
    bool closed() const noexcept { return state_->closed(); }
    bool presentation_pending() const noexcept { return state_->presentation_pending(); }
    bool body_ready() const noexcept { return state_->body_ready(); }
    bool modal_open() const noexcept { return state_->modal_open(); }
    const std::string& last_error() const noexcept { return state_->last_error(); }
    appended::NativeEngineState native_state() const noexcept { return state_->native_state(); }
    std::optional<Clock::time_point> deadline() const noexcept { return state_->deadline(); }
private:
    std::unique_ptr<semantic_primary_detail::State> state_;
};

} // namespace foundation::ui
