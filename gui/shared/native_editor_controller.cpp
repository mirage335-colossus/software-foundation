// SPDX-License-Identifier: CC0-1.0
#include "native_editor_controller.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <stdexcept>
#include <utility>

namespace foundation::ui::native_editor {
namespace {
constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();

// Validate scalar UTF-8 and the independent UTF-16/UTF-8 observation join.
bool text(const std::string& value, std::size_t bound, const TextObservation* observed = nullptr) {
    if (value.size() > bound) return false;
    std::size_t position = 0, units = 0;
    ByteRange joined{std::numeric_limits<std::size_t>::max(), std::numeric_limits<std::size_t>::max()};
    while (true) {
        if (observed) {
            if (units == observed->selection_start) joined.begin = position;
            if (units == observed->selection_end) joined.end = position;
        }
        if (position == value.size()) break;
        const auto lead = static_cast<unsigned char>(value[position]);
        std::size_t count = 0;
        std::uint32_t point = 0, minimum = 0;
        if (lead > 0 && lead < 0x80) { count = 1; point = lead; }
        else if (lead >= 0xc2 && lead <= 0xdf) { count = 2; point = lead & 31u; minimum = 0x80; }
        else if (lead >= 0xe0 && lead <= 0xef) { count = 3; point = lead & 15u; minimum = 0x800; }
        else if (lead >= 0xf0 && lead <= 0xf4) { count = 4; point = lead & 7u; minimum = 0x10000; }
        else return false;
        if (count > value.size() - position) return false;
        for (std::size_t index = 1; index < count; ++index) {
            const auto byte = static_cast<unsigned char>(value[position + index]);
            if ((byte & 0xc0u) != 0x80u) return false;
            point = (point << 6u) | (byte & 63u);
        }
        if (point < minimum || point > 0x10ffff || (point >= 0xd800 && point <= 0xdfff)) return false;
        position += count;
        units += point > 0xffff ? 2 : 1;
    }
    if (!observed) return true;
    return observed->selection_start <= observed->selection_end && joined.begin <= value.size() &&
        joined.end <= value.size() && joined == observed->selection &&
        observed->byte_length == value.size() &&
        (observed->selection_direction == Direction::none || observed->selection_direction == Direction::forward ||
         observed->selection_direction == Direction::backward);
}
bool boundary(const std::string& value, std::size_t offset) {
    return offset <= value.size() && (offset == value.size() ||
        (static_cast<unsigned char>(value[offset]) & 0xc0u) != 0x80u);
}
bool range(const std::string& value, ByteRange selection) {
    return selection.begin <= selection.end && boundary(value, selection.begin) && boundary(value, selection.end);
}
bool identity(const Identity& value) {
    return !value.owner.id.empty() && text(value.owner.id, 128) && value.owner.generation &&
        value.presentation_revision && value.generation && value.epoch && value.context;
}
bool retire_material(const NativeRetireMaterial& value) {
    return value.token && value.mapping_id && value.input_context;
}
bool retirement_matches(const NativeRetireMaterial& value, const NativeProjection& target) {
    return retire_material(value) && value.mapping_id == target.mapping_id &&
        value.input_context == target.identity.context && value.composition == target.composition;
}
bool projection(const NativeProjection& value) {
    const auto bounded = [](double number) { return std::isfinite(number) && std::abs(number) <= 1000000; };
    return value.readback_attested && identity(value.identity) && value.editor_revision && value.mapping_id &&
        value.frame_id && text(value.surrounding, Controller::max_text_bytes) && range(value.surrounding, value.selection) &&
        bounded(value.caret.x) && bounded(value.caret.y) && bounded(value.caret.width) && bounded(value.caret.height) &&
        value.caret.width >= 0 && value.caret.height >= 0 && text(value.input_purpose, 128) &&
        (!value.retire || retirement_matches(*value.retire, value));
}
bool same_context(Identity a, Identity b) {
    a.presentation_revision = b.presentation_revision;
    return a == b;
}
bool same_owner(const Identity& a, const Identity& b) {
    return a.owner == b.owner && a.generation == b.generation && a.epoch == b.epoch;
}
bool result_matches(const NativeResult& result, const NativeProjection& target) {
    const bool explicit_readback = result.readback_attested || result.observation_revision ||
        result.readback_identity != Identity{};
    if (explicit_readback && (!result.readback_attested || !result.observation_revision ||
        !identity(result.readback_identity) || !same_context(result.readback_identity, target.identity))) return false;
    return (!result.retire || (retirement_matches(*result.retire, target) &&
        (!target.retire || result.retire == target.retire)));
}
bool same_projection(NativeProjection a, NativeProjection b) {
    a.identity.presentation_revision = b.identity.presentation_revision;
    return a == b;
}
bool same_basis(Basis a, Basis b) {
    a.identity.presentation_revision = b.identity.presentation_revision;
    return a == b;
}
Basis basis(const NativeProjection& value, std::uint64_t token) {
    return {token, value.identity, value.editor_revision, value.surrounding, value.selection,
            value.backward, value.composition};
}
bool observation_text(const TextObservation& value) {
    return text(value.value, Controller::max_text_bytes, &value);
}
bool before_matches(const TextObservation& before, const NativeProjection& actual) {
    return before.value == actual.surrounding && before.selection == actual.selection &&
        (before.selection_direction == Direction::backward) == actual.backward;
}
bool key(const KeyData& value) {
    const auto& transition = value.transition;
    return (transition.phase == gui_surface::KeyPhase::down || transition.phase == gui_surface::KeyPhase::up) &&
        !transition.key.empty() && text(transition.key, 64) && transition.code.size() <= 64 &&
        std::all_of(transition.code.begin(), transition.code.end(), [](unsigned char c) { return c >= 0x21 && c <= 0x7e; }) &&
        transition.location <= 3 && !(transition.modifiers & ~gui_surface::known_modifiers) &&
        !(transition.phase == gui_surface::KeyPhase::up && transition.repeat);
}
bool same_key(const KeyData& a, const KeyData& b) {
    return a.transition.location == b.transition.location &&
        (a.transition.code.empty() && b.transition.code.empty() ? a.transition.key == b.transition.key :
         !a.transition.code.empty() && a.transition.code == b.transition.code);
}
const std::vector<std::uint64_t>& source_groups(const Observation& value) {
    static const std::vector<std::uint64_t> empty;
    if (const auto* item = std::get_if<TextData>(&value.data)) return item->source_groups;
    if (const auto* item = std::get_if<CompositionData>(&value.data)) return item->source_groups;
    return empty;
}
bool observation(const Observation& value) {
    if (!value.id || (value.predecessor && !*value.predecessor) || (value.group && !*value.group) ||
        !observation_text(value.before) || (value.after && !observation_text(*value.after)) ||
        source_groups(value).size() > Controller::max_dependencies) return false;
    if (value.kind != Kind::composition && value.transaction) return false;
    if (value.kind == Kind::key) {
        const auto* data = std::get_if<KeyData>(&value.data);
        return data && key(*data) && value.authority == Authority::native &&
            (!value.after || *value.after == value.before);
    }
    if (value.kind == Kind::selection) {
        const auto* data = std::get_if<SelectionData>(&value.data);
        return data && value.authority == Authority::range && value.after && value.after->value == value.before.value &&
            data->selection == value.after->selection && data->backward == (value.after->selection_direction == Direction::backward);
    }
    if (value.kind == Kind::text) {
        const auto* data = std::get_if<TextData>(&value.data);
        if (!data || !value.after || (value.authority != Authority::range && value.authority != Authority::default_action) ||
            data->input_type.empty() || !text(data->input_type, 64) || !text(data->text, Controller::max_text_bytes) ||
            data->replacement != value.before.selection) return false;
        return value.after->value == value.before.value.substr(0, data->replacement.begin) + data->text +
            value.before.value.substr(data->replacement.end);
    }
    if (value.kind != Kind::composition) return false;
    const auto* data = std::get_if<CompositionData>(&value.data);
    if (!data || !value.transaction || !text(data->text, Controller::max_text_bytes) || !range(data->text, data->selection)) return false;
    switch (data->operation) {
    case gui_surface::CompositionOperation::begin:
        return (value.authority == Authority::range || value.authority == Authority::default_action) &&
            data->replacement == value.before.selection;
    case gui_surface::CompositionOperation::update:
    case gui_surface::CompositionOperation::commit:
    case gui_surface::CompositionOperation::cancel:
        return value.authority == Authority::composition && !data->replacement;
    }
    return false;
}
Receipt correlate(const Packet& packet) {
    Receipt result;
    result.session = packet.session; result.id = packet.observation.id;
    result.predecessor = packet.observation.predecessor; result.submitted_token = packet.basis.token;
    return result;
}
}

struct Controller::Impl {
    explicit Impl(Backend* input) : backend(input) {}
    struct DefaultFact { DefaultDependency dependency; std::uint64_t source = 0; NativeProjection projection; };
    Backend* backend;
    enum class Stage { idle, projection, effect };
    Stage stage = Stage::idle;
    std::uint64_t dispatches = 0, ticket = 0;
    bool revocation_flight = false;
    std::optional<NativeRequest> prepared_request;
    std::optional<NativeProjection> resolved;
    std::vector<KeyData> pending_held;
    std::map<std::uint64_t, DefaultFact> retained_defaults;
    std::vector<std::uint64_t> pending_groups;
    State state = State::detached;
    bool processing = false, usable = false, revoked = false;
    std::uint64_t tokens = 0;
    std::optional<std::uint64_t> session, predecessor;
    std::optional<NativeProjection> current;
    std::optional<NativeProjection> retirement_obligation;
    std::uint64_t retirement_transaction = 0;
    std::optional<std::uint64_t> external_retired_token;
    std::optional<RetirementReadback> external_retirement;
    std::optional<Basis> published;
    std::map<std::uint64_t, DefaultFact> defaults;
    std::vector<KeyData> held;
    std::optional<CompositionFact> composition;
    std::optional<Packet> packet;
    std::optional<Receipt> receipt;
    std::optional<Revocation> revocation;
    std::string error;

    void clear_flight() noexcept {
        stage = Stage::idle; ticket = 0; prepared_request.reset(); resolved.reset();
        pending_held.clear(); retained_defaults.clear(); pending_groups.clear();
    }
    std::uint64_t begin_flight(bool revoking) {
        if (dispatches == maximum) throw std::overflow_error("Editor dispatch ticket space exhausted");
        ticket = ++dispatches; revocation_flight = revoking; stage = Stage::projection;
        return ticket;
    }
    std::uint64_t issue() {
        if (tokens == maximum) throw std::overflow_error("Editor token space exhausted");
        return ++tokens;
    }
    void stop(const char* detail) noexcept {
        clear_flight();
        usable = false; defaults.clear();
        if (state != State::closed) state = State::terminal_unknown;
        try { error = detail; } catch (...) {}
    }
    DispatchResult unknown(const char* detail, bool packet_failure = true) {
        stop(detail);
        if (packet_failure && packet) receipt = correlate(*packet);
        return {Admission::terminal, packet_failure ? receipt : std::nullopt, error};
    }
    DispatchResult reject(std::string detail, const NativeProjection* checked = nullptr) {
        if (state == State::closed || state == State::terminal_unknown) return {Admission::terminal, {}, error};
        clear_flight();
        state = State::suspended; usable = false; defaults.clear(); error = std::move(detail);
        std::optional<Receipt> result;
        if (packet && packet->session && packet->observation.id && packet->basis.token && published) {
            result = correlate(*packet); result->outcome = Outcome::rejected;
            if (checked && held.empty() && !composition && !checked->composition) {
                current = *checked; published = basis(*checked, issue());
            }
            result->basis = *published;
            result->continuity = !same_context(result->basis->identity, packet->basis.identity)
                ? Continuity::replaced : Continuity::same;
            if (checked && current && checked->composition != current->composition) result.reset();
            else {
                if (composition) result->composition = composition;
                receipt = result;
            }
        }
        return {Admission::rejected, std::move(result), error};
    }
};

bool valid_basis(const Basis& value) noexcept {
    return value.token && identity(value.identity) && value.editor_revision &&
        text(value.surrounding, Controller::max_text_bytes) && range(value.surrounding, value.selection);
}
bool valid_retire_material(const NativeRetireMaterial& value) noexcept { return retire_material(value); }
bool valid_projection(const NativeProjection& value) noexcept { return projection(value); }
bool valid_observation(const Observation& value) noexcept {
    try { return observation(value); } catch (...) { return false; }
}
namespace {
PreparedDispatch prepared_reply(DispatchResult value, std::uint64_t ticket = 0) {
    PreparedDispatch result;
    result.admission = value.admission; result.ticket = ticket;
    result.receipt = std::move(value.receipt); result.detail = std::move(value.detail);
    return result;
}
DispatchResult dispatched_reply(PreparedDispatch value) {
    return {value.admission, std::move(value.receipt), std::move(value.detail)};
}
struct Processing {
    bool& active;
    explicit Processing(bool& value) : active(value) { active = true; }
    ~Processing() { active = false; }
};
}

Controller::Controller() : impl_(std::make_unique<Impl>(nullptr)) {}
Controller::Controller(Backend& backend) : impl_(std::make_unique<Impl>(&backend)) {}
Controller::~Controller() = default;

std::optional<Basis> Controller::activate(NativeProjection next) {
    auto& self = *impl_;
    if (self.processing || self.stage != Impl::Stage::idle || terminal() || self.retirement_obligation ||
        !projection(next) || (self.external_retired_token &&
            (!next.retire || next.retire->token == *self.external_retired_token))) return std::nullopt;
    if (self.state == State::ready && self.current && self.published && same_projection(*self.current, next)) {
        self.current = std::move(next); self.published->identity = self.current->identity;
        return self.published;
    }
    // Native lifecycle ownership must be closed by process_revocation first.
    if ((!self.held.empty() || self.composition) && self.current) return std::nullopt;
    try {
        self.current = std::move(next); self.published = basis(*self.current, self.issue());
        self.session.reset(); self.predecessor.reset(); self.defaults.clear();
        self.external_retirement.reset();
        self.usable = true; self.revoked = false; self.state = State::ready; self.error.clear();
        if (self.current->composition) self.composition = CompositionFact{self.current->composition, CompositionState::live};
        return self.published;
    } catch (...) { self.stop("Editor activation failed"); return std::nullopt; }
}

PreparedDispatch Controller::begin(Packet input) {
    auto& self = *impl_;
    if (self.processing || self.stage != Impl::Stage::idle)
        return prepared_reply({Admission::busy, {}, "Native editor operation is active"});
    if (terminal()) return prepared_reply({Admission::terminal, {}, self.error});
    if (self.state != State::ready || !self.usable)
        return prepared_reply({Admission::unavailable, {}, "No active editor basis"});
    Processing guard(self.processing);
    self.packet = std::move(input); self.receipt.reset();
    const auto& packet = *self.packet;
    const auto& observed = packet.observation;
    try {
        if (!packet.session || !valid_basis(packet.basis) || !observation(observed) || !self.published || !same_basis(packet.basis, *self.published) ||
            (self.session && packet.session != *self.session) || observed.predecessor != self.predecessor ||
            (self.predecessor && observed.id <= *self.predecessor)) return prepared_reply(self.reject("Editor basis or causal predecessor differs"));
        const auto total = packet.basis.surrounding.size() + observed.before.value.size() +
            (observed.after ? observed.after->value.size() : 0);
        if (total > max_packet_bytes) return prepared_reply(self.reject("Editor packet exceeds retained byte limit"));
        PreparedDispatch result;
        result.admission = Admission::awaiting_projection; result.ticket = self.begin_flight(false);
        return result;
    } catch (...) { return prepared_reply(self.unknown("Editor head preparation failed")); }
}

PreparedDispatch Controller::begin_revocation(Revocation input) {
    auto& self = *impl_;
    if (self.processing || self.stage != Impl::Stage::idle)
        return prepared_reply({Admission::busy, {}, "Native editor operation is active"});
    if (terminal()) return prepared_reply({Admission::terminal, {}, self.error});
    Processing guard(self.processing);
    try {
        if (!self.current || !self.published || self.revoked || !input.incarnation || !valid_basis(input.basis) ||
            !same_basis(input.basis, *self.published) || input.composition != (self.composition ? self.composition->transaction : 0) ||
            input.held_keys.size() != self.held.size() || !text(input.reason, 4096))
            return prepared_reply({Admission::rejected, {}, "Native editor revocation ownership differs"});
        auto remaining = self.held;
        for (const auto& item : input.held_keys) {
            const auto found = std::find_if(remaining.begin(), remaining.end(), [&](const KeyData& held) { return same_key(held, item); });
            if (!key(item) || item.transition.phase != gui_surface::KeyPhase::down || found == remaining.end())
                return prepared_reply({Admission::rejected, {}, "Native editor revocation held keys differ"});
            remaining.erase(found);
        }
        self.revocation = std::move(input);
        PreparedDispatch result;
        result.admission = Admission::awaiting_projection; result.ticket = self.begin_flight(true);
        return result;
    } catch (...) { return prepared_reply(self.unknown("Native editor revocation preparation failed", false)); }
}

PreparedDispatch Controller::supply_projection(std::uint64_t ticket, std::optional<NativeProjection> resolved) {
    auto& self = *impl_;
    if (self.processing) return prepared_reply({Admission::busy, {}, "Native editor operation is active"});
    if (terminal()) return prepared_reply({Admission::terminal, {}, self.error});
    if (!ticket || ticket != self.ticket || self.stage != Impl::Stage::projection)
        return prepared_reply({Admission::rejected, {}, "Foreign or duplicate editor projection ticket"});
    Processing guard(self.processing);
    auto reject = [&](std::string detail, const NativeProjection* checked = nullptr) {
        return prepared_reply(self.reject(std::move(detail), checked), ticket);
    };
    try {
        if (self.revocation_flight) {
            if (!resolved || !projection(*resolved) || !same_projection(*resolved, *self.current)) {
                self.clear_flight();
                return prepared_reply({Admission::rejected, {}, "Native editor revocation mapping changed"}, ticket);
            }
            self.resolved = *resolved;
            PreparedDispatch result; result.admission = Admission::prepared;
            result.ticket = ticket; result.revocation = self.revocation;
            self.usable = false; self.defaults.clear(); self.state = State::suspended;
            self.stage = Impl::Stage::effect;
            return result;
        }
        const auto& packet = *self.packet;
        const auto& observed = packet.observation;
        if (self.state != State::ready) return reject("Editor lifecycle changed during projection");
        if (!resolved || !projection(*resolved)) return reject("Native editor mapping is unavailable");
        if (!same_projection(*resolved, *self.current)) return reject("Native editor mapping changed", &*resolved);
        if (observed.authority == Authority::range && !before_matches(observed.before, *resolved))
            return reject("Editor captured-before projection differs");
        const auto* composing = std::get_if<CompositionData>(&observed.data);
        if (composing) {
            const bool begin = composing->operation == gui_surface::CompositionOperation::begin;
            if (begin ? bool(self.composition) : (!self.composition || self.composition->transaction != observed.transaction))
                return reject("Editor composition predecessor differs");
        } else if (self.composition && observed.kind != Kind::key) return reject("Native composition owns editor input");
        auto groups = source_groups(observed);
        if (observed.authority == Authority::default_action) {
            if (!observed.group) return reject("Editor default has no source group");
            if (groups.empty()) groups.push_back(*observed.group);
            if (groups.size() > max_dependencies || groups.back() != *observed.group ||
                packet.default_dependencies.size() != groups.size() || !packet.default_token ||
                *packet.default_token != packet.default_dependencies.back().token)
                return reject("Editor default dependency inventory differs");
            std::uint64_t previous = 0;
            for (std::size_t index = 0; index < groups.size(); ++index) {
                const auto found = self.defaults.find(groups[index]);
                if (!groups[index] || found == self.defaults.end() ||
                    packet.default_dependencies[index] != found->second.dependency ||
                    found->second.source <= previous) return reject("Editor default source is not authorized");
                previous = found->second.source;
                const auto& origin = found->second.projection;
                if (origin.frame_id != resolved->frame_id || origin.identity.owner != resolved->identity.owner ||
                    origin.identity.generation != resolved->identity.generation || origin.identity.epoch != resolved->identity.epoch)
                    return reject("Editor default source belongs to another native owner");
            }
            if (!same_projection(self.defaults.at(groups.back()).projection, *resolved))
                return reject("Editor default mapping changed");
        } else if (!groups.empty() || packet.default_token || !packet.default_dependencies.empty())
            return reject("Unexpected editor default authority");
        auto held = self.held;
        const auto* key_data = std::get_if<KeyData>(&observed.data);
        if (key_data) {
            const auto found = std::find_if(held.begin(), held.end(), [&](const KeyData& item) { return same_key(item, *key_data); });
            if (key_data->transition.phase == gui_surface::KeyPhase::up) {
                if (found == held.end()) return reject("Editor key release has no owned press");
                held.erase(found);
            } else if (key_data->transition.repeat) {
                if (found == held.end()) return reject("Editor key repeat has no owned press");
            } else {
                if (found != held.end() || held.size() >= max_default_groups) return reject("Editor held-key ownership differs");
                held.push_back(*key_data);
            }
            if (observed.group && self.defaults.size() >= max_default_groups && !self.defaults.contains(*observed.group))
                return reject("Editor default group limit");
        }
        NativeRequest request{*resolved, packet};
        self.prepared_request = request; self.resolved = *resolved;
        self.pending_held = std::move(held); self.retained_defaults = self.defaults; self.pending_groups = groups;
        PreparedDispatch result; result.admission = Admission::prepared; result.ticket = ticket;
        result.request = std::move(request);
        // Authority is consumed before returning an effect request to the owner.
        self.usable = false;
        for (auto group : groups) self.defaults.erase(group);
        self.session = packet.session; self.stage = Impl::Stage::effect;
        return result;
    } catch (...) { return prepared_reply(self.unknown("Native editor projection preparation failed", !self.revocation_flight), ticket); }
}

DispatchResult Controller::complete(std::uint64_t ticket, NativeResult result) {
    auto& self = *impl_;
    if (self.processing) return {Admission::busy, {}, "Native editor operation is active"};
    if (terminal()) return {Admission::terminal, {}, self.error};
    if (!ticket || ticket != self.ticket || self.stage != Impl::Stage::effect)
        return {Admission::rejected, {}, "Foreign or duplicate editor completion ticket"};
    Processing guard(self.processing);
    try {
        if (self.revocation_flight) {
            const auto& actual = self.resolved;
            const bool retired_matches = result.retired && actual->retire && result.retired == actual->retire;
            if (result.availability != NativeAvailability::available) {
                if ((result.availability != NativeAvailability::noneditable && result.availability != NativeAvailability::unavailable) ||
                    result.outcome != Outcome::applied || result.projection || result.continuity != Continuity::replaced ||
                    !result.readback_attested || !result.observation_revision || !identity(result.readback_identity) ||
                    !same_owner(result.readback_identity, actual->identity) || !retired_matches || result.allow_default ||
                    (result.composition && (!result.composition_readback_attested ||
                        result.composition->transaction != self.revocation->composition ||
                        result.composition->state != CompositionState::ended)) ||
                    (result.retire && (!retire_material(*result.retire) ||
                        result.retire->input_context != result.readback_identity.context)))
                    return self.unknown("Native owned retirement proof is not attested", false);
                self.current.reset(); self.published.reset(); self.held.clear(); self.composition.reset();
                self.usable = false; self.defaults.clear(); self.revoked = true; self.state = State::suspended;
                self.error.clear(); self.clear_flight();
                return {Admission::completed, {}, {}};
            }
            if (result.outcome != Outcome::applied || !result.projection || !projection(*result.projection) ||
                !result.composition_readback_attested || result.projection->composition ||
                !result_matches(result, *result.projection) ||
                (actual->retire ? !retired_matches : bool(result.retired)))
                return self.unknown("Native editor revocation outcome is not attested", false);
            if ((result.continuity != Continuity::same && result.continuity != Continuity::replaced) ||
                (result.continuity == Continuity::same && (!same_context(actual->identity, result.projection->identity) ||
                    actual->frame_id != result.projection->frame_id)) ||
                (result.composition && (result.composition->transaction != self.revocation->composition ||
                    result.composition->state != CompositionState::ended)))
                return self.unknown("Native editor revocation continuity differs", false);
            if (result.retire && !result.projection->retire) result.projection->retire = result.retire;
            if (result.retired && result.projection->retire &&
                result.projection->retire->token == result.retired->token)
                return self.unknown("Native editor readback reused retired provider authority", false);
            self.current = *result.projection; self.held.clear(); self.composition.reset(); self.revoked = true;
            self.error.clear(); self.clear_flight();
            return {Admission::completed, {}, {}};
        }
        const auto& packet = *self.packet;
        const auto& observed = packet.observation;
        const auto* resolved = &*self.resolved;
        const auto* key_data = std::get_if<KeyData>(&observed.data);
        const auto* composing = std::get_if<CompositionData>(&observed.data);
        const auto& groups = self.pending_groups;
        auto& retained_defaults = self.retained_defaults;
        auto& held = self.pending_held;
        if (self.state != State::ready) return self.unknown("Editor lifecycle changed during native effect");
        if (result.outcome == Outcome::unknown) return self.unknown("Native editor outcome is unknown");
        if (result.outcome != Outcome::applied && result.outcome != Outcome::cancelled && result.outcome != Outcome::rejected)
            return self.unknown("Invalid native editor outcome");
        if (result.retired) {
            const auto* replacement = result.retire ? &*result.retire :
                (result.projection && result.projection->retire ? &*result.projection->retire : nullptr);
            const bool closed = !result.projection && result.availability != NativeAvailability::available &&
                result.continuity == Continuity::replaced && !result.retire;
            const bool transferred = result.projection && projection(*result.projection) &&
                result.availability == NativeAvailability::available &&
                (result.continuity == Continuity::key_retarget || result.continuity == Continuity::replaced) &&
                replacement && retirement_matches(*replacement, *result.projection) &&
                replacement->token != result.retired->token;
            if (!resolved->retire || result.retired != resolved->retire || (!closed && !transferred))
                return self.unknown("Native editor ownership transfer proof differs");
        }
        const auto expected_transaction = composing ? observed.transaction : (self.composition ? self.composition->transaction : 0);
        if (result.availability != NativeAvailability::available) {
            const auto& checked = result.readback_identity;
            const bool closed_owned = resolved->retire && result.retired == resolved->retire &&
                !result.projection && !result.retire && result.continuity == Continuity::replaced;
            if ((result.availability != NativeAvailability::noneditable && result.availability != NativeAvailability::unavailable) ||
                result.projection || (result.outcome == Outcome::applied && !closed_owned) || result.continuity != Continuity::replaced ||
                !result.readback_attested || !result.observation_revision || !identity(checked) ||
                !same_owner(checked, resolved->identity) || result.allow_default ||
                (closed_owned && resolved->retire->composition && !result.composition) ||
                (result.composition && (result.composition->state != CompositionState::ended ||
                    !result.composition_readback_attested || !expected_transaction ||
                    result.composition->transaction != expected_transaction)) ||
                (result.retire && (!retire_material(*result.retire) || result.retire->input_context != checked.context)))
                return self.unknown("Native editor retirement readback is not attested");
            Receipt receipt = correlate(packet); receipt.outcome = result.outcome;
            receipt.continuity = Continuity::replaced;
            if (closed_owned) receipt.composition = result.composition;
            receipt.retirement = RetirementReadback{result.availability, checked,
                result.observation_revision, result.readback_attested, closed_owned};
            if (resolved->retire && !result.retired) {
                self.retirement_obligation = *resolved; self.retirement_transaction = expected_transaction;
            }
            if (closed_owned) self.external_retired_token = result.retired->token;
            self.usable = false; self.defaults.clear(); self.held.clear(); self.composition.reset();
            self.current.reset(); self.published.reset(); self.state = State::suspended;
            self.receipt = receipt; self.error.clear(); self.clear_flight();
            return {Admission::completed, std::move(receipt), {}};
        }
        if (!result.projection || !projection(*result.projection)) return self.unknown("Native editor readback is not attested");
        auto& next = *result.projection;
        if (!result_matches(result, next)) return self.unknown("Native editor readback metadata differs");
        // Preserve explicitly returned provider material even if the backend
        // placed it only on the result envelope rather than its projection.
        if (result.retire && !next.retire) next.retire = result.retire;
        if (resolved->retire && (!next.retire ||
            (next.retire->token != resolved->retire->token && !result.retired)))
            return self.unknown("Native editor ownership changed without retirement proof");
        if (result.continuity == Continuity::same) {
            if (!same_context(resolved->identity, next.identity) || resolved->frame_id != next.frame_id)
                return self.unknown("Native editor context changed without attestation");
        } else if (result.continuity == Continuity::key_retarget) {
            if ((observed.authority != Authority::native && observed.authority != Authority::default_action) ||
                !result.key_retarget_attested || result.changed_focused_frame || resolved->frame_id != next.frame_id ||
                (key_data && !result.key_dispatch_attested)) return self.unknown("Invalid native key retarget attestation");
        } else if (result.continuity != Continuity::replaced) return self.unknown("Invalid native editor continuity");
        if (result.composition) {
            const auto fact = *result.composition;
            if (!expected_transaction || fact.transaction != expected_transaction || !result.composition_readback_attested)
                return self.unknown("Native composition readback is missing");
            if (fact.state == CompositionState::live) {
                if (next.composition != fact.transaction) return self.unknown("Native composition transaction differs");
            } else if (fact.state == CompositionState::pending) {
                if (next.composition || (self.composition && self.composition->state == CompositionState::live &&
                    !(composing && composing->operation == gui_surface::CompositionOperation::update && composing->text.empty())))
                    return self.unknown("Invalid pending native composition");
            } else if (fact.state != CompositionState::ended || next.composition)
                return self.unknown("Invalid ended native composition");
        } else if (next.composition || self.composition || (composing && result.outcome == Outcome::applied))
            return self.unknown("Missing native composition continuity");
        if (composing && result.outcome == Outcome::applied) {
            const bool ending = composing->operation == gui_surface::CompositionOperation::commit ||
                composing->operation == gui_surface::CompositionOperation::cancel;
            if (!result.composition || ending != (result.composition->state == CompositionState::ended))
                return self.unknown("Native composition operation did not settle");
        }
        Receipt receipt = correlate(packet); receipt.outcome = result.outcome;
        receipt.continuity = result.continuity; receipt.composition = result.composition;
        receipt.basis = basis(next, self.issue());
        self.current = next; self.published = receipt.basis; self.predecessor = observed.id; self.held = std::move(held);
        self.composition = result.composition && result.composition->state != CompositionState::ended ? result.composition : std::nullopt;
        if (result.outcome == Outcome::applied && result.continuity != Continuity::replaced) {
            if (observed.authority == Authority::default_action && !observed.group_end) {
                for (auto group : groups) {
                    auto fact = retained_defaults.at(group); fact.projection = next;
                    self.defaults.emplace(group, std::move(fact));
                }
            }
            if (key_data && observed.group) {
                if (observed.group_end) self.defaults.erase(*observed.group);
                else if (key_data->transition.phase == gui_surface::KeyPhase::down && result.key_dispatch_attested &&
                    result.allow_default && !result.default_prevented && !result.default_handled &&
                    !result.changed_focused_frame && !self.composition) {
                    DefaultDependency granted{*observed.group, self.issue()};
                    self.defaults[*observed.group] = {granted, observed.id, next}; receipt.default_token = granted;
                }
            }
            self.usable = true; self.state = State::ready;
        } else { self.defaults.clear(); self.state = State::suspended; }
        self.receipt = receipt; self.error.clear();
        self.clear_flight();
        return {Admission::completed, std::move(receipt), {}};
    } catch (...) { return self.unknown("Native editor completion failed", !self.revocation_flight); }
}

DispatchResult Controller::process(Packet input) {
    auto& self = *impl_;
    if (!self.backend) return {Admission::unavailable, {}, "No synchronous native editor backend"};
    auto pending = begin(std::move(input));
    if (pending.admission != Admission::awaiting_projection) return dispatched_reply(std::move(pending));
    try {
        std::optional<NativeProjection> actual;
        { Processing guard(self.processing); actual = self.backend->project(self.current->mapping_id); }
        auto prepared = supply_projection(pending.ticket, std::move(actual));
        if (prepared.admission != Admission::prepared) return dispatched_reply(std::move(prepared));
        NativeResult result;
        { Processing guard(self.processing); result = self.backend->apply(*prepared.request); }
        return complete(prepared.ticket, std::move(result));
    } catch (...) { return self.unknown("Native editor callback or completion failed"); }
}

DispatchResult Controller::process_revocation(Revocation input) {
    auto& self = *impl_;
    if (!self.backend) return {Admission::unavailable, {}, "No synchronous native editor backend"};
    auto pending = begin_revocation(std::move(input));
    if (pending.admission != Admission::awaiting_projection) return dispatched_reply(std::move(pending));
    try {
        std::optional<NativeProjection> actual;
        { Processing guard(self.processing); actual = self.backend->project(self.current->mapping_id); }
        auto prepared = supply_projection(pending.ticket, std::move(actual));
        if (prepared.admission != Admission::prepared) return dispatched_reply(std::move(prepared));
        NativeResult result;
        { Processing guard(self.processing); result = self.backend->revoke(*prepared.revocation); }
        return complete(prepared.ticket, std::move(result));
    } catch (...) { return self.unknown("Native editor revocation callback failed", false); }
}

DispatchResult Controller::cancel_unentered(std::uint64_t ticket) {
    auto& self = *impl_;
    if (self.processing) return {Admission::busy, {}, "Native editor operation is active"};
    if (terminal()) return {Admission::terminal, {}, self.error};
    if (!ticket || ticket != self.ticket || self.stage == Impl::Stage::idle)
        return {Admission::rejected, {}, "Foreign or duplicate unentered editor ticket"};
    Processing guard(self.processing);
    const bool observation = !self.revocation_flight;
    try {
        if (self.current && self.current->retire) {
            self.retirement_obligation = *self.current;
            self.retirement_transaction = self.composition ? self.composition->transaction : self.current->composition;
        }
        std::optional<Receipt> receipt;
        if (observation) {
            receipt = correlate(*self.packet); receipt->outcome = Outcome::cancelled;
            receipt->continuity = Continuity::replaced;
            self.receipt = receipt;
        }
        self.usable = false; self.defaults.clear(); self.state = State::suspended; self.clear_flight();
        return {Admission::completed, std::move(receipt), {}};
    } catch (...) { return self.unknown("Unentered editor cancellation could not be retained", observation); }
}

bool Controller::complete_external_retirement(const NativeRetireMaterial& expected, const NativeResult& checked) noexcept {
    auto& self = *impl_;
    if (self.processing || self.stage != Impl::Stage::idle || terminal()) return false;
    const auto* owned = self.retirement_obligation ? &*self.retirement_obligation :
        (self.current ? &*self.current : nullptr);
    if (!owned || !owned->retire || *owned->retire != expected || !retire_material(expected)) return false;
    try {
        const auto transaction = self.retirement_obligation ? self.retirement_transaction :
            (self.composition ? self.composition->transaction : expected.composition);
        if (checked.outcome != Outcome::applied || checked.retired != owned->retire ||
            !checked.readback_attested || !checked.observation_revision || !identity(checked.readback_identity) ||
            !same_owner(checked.readback_identity, owned->identity) || checked.allow_default ||
            (checked.continuity != Continuity::same && checked.continuity != Continuity::replaced) ||
            (checked.continuity == Continuity::same && !same_context(checked.readback_identity, owned->identity)) ||
            (checked.composition && (!transaction || checked.composition->transaction != transaction ||
                checked.composition->state != CompositionState::ended || !checked.composition_readback_attested))) return false;
        const auto* renewed = checked.retire ? &*checked.retire :
            (checked.projection && checked.projection->retire ? &*checked.projection->retire : nullptr);
        if (renewed && (!retire_material(*renewed) || renewed->token == expected.token || renewed->composition ||
            renewed->input_context != checked.readback_identity.context)) return false;
        if (checked.availability == NativeAvailability::available) {
            if (!checked.projection || !projection(*checked.projection) || checked.projection->composition ||
                !result_matches(checked, *checked.projection) ||
                (checked.continuity == Continuity::same && owned->frame_id != checked.projection->frame_id)) return false;
        } else if ((checked.availability != NativeAvailability::noneditable &&
                    checked.availability != NativeAvailability::unavailable) || checked.projection) return false;
        RetirementReadback retired{checked.availability, checked.readback_identity,
            checked.observation_revision, checked.readback_attested, true};
        self.external_retirement = std::move(retired); self.external_retired_token = expected.token;
        self.usable = false; self.held.clear(); self.defaults.clear(); self.composition.reset();
        self.current.reset(); self.published.reset(); self.retirement_obligation.reset(); self.retirement_transaction = 0;
        self.revoked = true; self.state = State::suspended;
        return true;
    } catch (...) { return false; }
}

const RetirementReadback* Controller::external_retirement() const noexcept {
    return impl_->external_retirement ? &*impl_->external_retirement : nullptr;
}

void Controller::revoke() noexcept {
    auto& self = *impl_;
    self.usable = false; self.defaults.clear();
    if (!terminal()) self.state = State::suspended;
}
void Controller::close() noexcept { impl_->clear_flight(); impl_->usable = false; impl_->defaults.clear(); impl_->state = State::closed; }
void Controller::notify_publication_failure() noexcept { impl_->stop("Native editor publication failed after consumption"); }
void Controller::notify_transport_failure() noexcept {
    const bool observation_flight = impl_->stage != Impl::Stage::idle && !impl_->revocation_flight;
    impl_->stop("Native editor transport outcome is unknown");
    if (observation_flight && impl_->packet) {
        try { impl_->receipt = correlate(*impl_->packet); } catch (...) {}
    }
}
const Basis* Controller::current_basis() const noexcept { return impl_->usable && !impl_->processing && impl_->stage == Impl::Stage::idle && impl_->published ? &*impl_->published : nullptr; }
const NativeProjection* Controller::current_projection() const noexcept { return impl_->current ? &*impl_->current : nullptr; }
std::optional<CompositionFact> Controller::current_composition() const noexcept { return impl_->composition; }
State Controller::state() const noexcept { return impl_->state; }
bool Controller::terminal() const noexcept { return impl_->state == State::terminal_unknown || impl_->state == State::closed; }
bool Controller::processing() const noexcept { return impl_->processing || impl_->stage != Impl::Stage::idle; }
bool Controller::awaiting_projection() const noexcept { return !terminal() && impl_->stage == Impl::Stage::projection; }
bool Controller::awaiting_result() const noexcept { return !terminal() && impl_->stage == Impl::Stage::effect; }
const Packet* Controller::unresolved() const noexcept { return impl_->packet ? &*impl_->packet : nullptr; }
const Receipt* Controller::last_receipt() const noexcept { return impl_->receipt ? &*impl_->receipt : nullptr; }
const Revocation* Controller::last_revocation() const noexcept { return impl_->revocation ? &*impl_->revocation : nullptr; }
const std::string& Controller::last_error() const noexcept { return impl_->error; }
std::size_t Controller::default_groups() const noexcept { return impl_->defaults.size(); }

} // namespace foundation::ui::native_editor
