// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <gui/web.hpp>
#include <foundation/gui/surface.hpp>
#include <algorithm>
#include <charconv>
#include <cmath>
#include <initializer_list>
#include <stdexcept>
#include <string_view>

namespace foundation::host::surface_web {

using Json = gui::web_detail::Json;
enum class Profile { legacy, mouse_v1, editor_v1 };
inline constexpr gui_surface::Features basic_supported =
    gui_surface::feature(gui_surface::Feature::raw_keys) |
    gui_surface::feature(gui_surface::Feature::focus) |
    gui_surface::feature(gui_surface::Feature::raw_pointer);
inline constexpr gui_surface::Features successor_supported =
    gui_surface::feature(gui_surface::Feature::raw_keys) |
    gui_surface::feature(gui_surface::Feature::focus) |
    gui_surface::feature(gui_surface::Feature::mouse_input);
inline constexpr gui_surface::Features editor_supported = successor_supported |
    gui_surface::feature(gui_surface::Feature::committed_text) |
    gui_surface::feature(gui_surface::Feature::composition) |
    gui_surface::feature(gui_surface::Feature::surrounding_text) |
    gui_surface::feature(gui_surface::Feature::selection);
inline constexpr std::uint32_t editor_protocol_version = 2;

// A closed vocabulary keeps browser input from acquiring native service or
// future editor authority merely by supplying additional object properties.
inline bool exact_shape(const Json& value, std::initializer_list<std::string_view> fields) {
    const auto* object = std::get_if<Json::Object>(&value.value);
    return object && object->size() == fields.size() &&
        std::all_of(object->begin(), object->end(), [&](const auto& member) {
            return std::find(fields.begin(), fields.end(), member.first) != fields.end();
        });
}
inline void require_shape(const Json& value, std::initializer_list<std::string_view> fields) {
    if (!exact_shape(value, fields)) throw std::invalid_argument("Invalid browser surface object shape");
}

namespace detail {
[[noreturn]] inline void invalid() { throw std::invalid_argument("Invalid browser surface value"); }
inline gui_surface::Features supported(Profile profile) {
    switch (profile) {
        case Profile::legacy: return basic_supported;
        case Profile::mouse_v1: return successor_supported;
        case Profile::editor_v1: return editor_supported;
    }
    invalid();
}
inline const std::string& text(const Json& value, std::size_t maximum, bool empty = true) {
    const auto* result = std::get_if<std::string>(&value.value);
    if (!result || result->size() > maximum || (!empty && result->empty()) || !gui_surface::valid_text(*result)) invalid();
    return *result;
}
inline bool boolean(const Json& value) {
    const auto* result = std::get_if<bool>(&value.value);
    if (!result) invalid();
    return *result;
}
inline double finite(const Json& value, double maximum) {
    const auto* result = std::get_if<double>(&value.value);
    if (!result || !std::isfinite(*result) || std::abs(*result) > maximum) invalid();
    return *result;
}
inline unsigned integer(const Json& value, unsigned maximum) {
    const auto result = finite(value, maximum);
    if (result < 0 || std::floor(result) != result) invalid();
    return static_cast<unsigned>(result);
}
inline std::uint64_t decimal(const Json& value, bool nonzero = false) {
    const auto& spelling = text(value, 20, false);
    std::uint64_t result = 0;
    const auto [end, error] = std::from_chars(spelling.data(), spelling.data() + spelling.size(), result);
    if (error != std::errc{} || end != spelling.data() + spelling.size() ||
        (spelling.size() > 1 && spelling.front() == '0') || (nonzero && !result)) invalid();
    return result;
}
inline gui_surface::Identity identity(const Json& value) {
    require_shape(value, {"owner", "presentationRevision", "generation", "epoch", "context"});
    const auto& owner = value.at("owner");
    require_shape(owner, {"id", "generation"});
    return {{text(owner.at("id"), 128, false), decimal(owner.at("generation"), true)},
        decimal(value.at("presentationRevision"), true), decimal(value.at("generation"), true),
        decimal(value.at("epoch"), true), decimal(value.at("context"), true)};
}
inline Json identity(const gui_surface::Identity& value) {
    return Json::Object{{"owner", Json::Object{{"id", value.owner.id}, {"generation", std::to_string(value.owner.generation)}}},
        {"presentationRevision", std::to_string(value.presentation_revision)}, {"generation", std::to_string(value.generation)},
        {"epoch", std::to_string(value.epoch)}, {"context", std::to_string(value.context)}};
}
inline Json rect(const gui_surface::Rect& value) {
    return Json::Array{value.x, value.y, value.width, value.height};
}
inline const char* capture(gui_surface::Capture value) {
    switch (value) {
        case gui_surface::Capture::pass: return "pass";
        case gui_surface::Capture::capture: return "capture";
    }
    invalid();
}
inline gui_surface::KeyTransition key(const Json& value) {
    require_shape(value, {"kind", "phase", "key", "code", "location", "modifiers", "repeat"});
    gui_surface::KeyTransition result;
    const auto& phase = text(value.at("phase"), 4, false);
    if (phase == "down") result.phase = gui_surface::KeyPhase::down;
    else if (phase == "up") result.phase = gui_surface::KeyPhase::up;
    else invalid();
    result.key = text(value.at("key"), 64, false);
    result.code = text(value.at("code"), 64);
    if (!std::all_of(result.code.begin(), result.code.end(), [](unsigned char c) { return c >= 33 && c <= 126; })) invalid();
    result.location = integer(value.at("location"), 3);
    result.modifiers = integer(value.at("modifiers"), gui_surface::known_modifiers);
    result.repeat = boolean(value.at("repeat"));
    if (result.phase == gui_surface::KeyPhase::up && result.repeat) invalid();
    return result;
}
inline gui_surface::FocusChange focus(const Json& value) {
    require_shape(value, {"kind", "focused", "active", "cause"});
    gui_surface::FocusChange result;
    result.focused = boolean(value.at("focused"));
    result.active = boolean(value.at("active"));
    const auto& cause = text(value.at("cause"), 8, false);
    if (cause == "direct") result.cause = gui_surface::FocusCause::direct;
    else if (cause == "external") result.cause = gui_surface::FocusCause::external;
    else invalid(); // Owned popup/service causes require the trusted host.
    return result;
}
inline gui_surface::PointerTransition pointer(const Json& value) {
    require_shape(value, {"kind", "phase", "pointer", "x", "y", "wheelX", "wheelY", "button", "buttons", "clicks", "modifiers"});
    gui_surface::PointerTransition result;
    const auto& phase = text(value.at("phase"), 7, false);
    if (phase == "move") result.phase = gui_surface::PointerPhase::move;
    else if (phase == "down") result.phase = gui_surface::PointerPhase::down;
    else if (phase == "up") result.phase = gui_surface::PointerPhase::up;
    else if (phase == "cancel") result.phase = gui_surface::PointerPhase::cancel;
    else if (phase == "wheel") result.phase = gui_surface::PointerPhase::wheel;
    else if (phase == "context") result.phase = gui_surface::PointerPhase::context;
    else invalid();
    result.pointer = decimal(value.at("pointer"));
    result.x = finite(value.at("x"), 1000000);
    result.y = finite(value.at("y"), 1000000);
    result.wheel_x = finite(value.at("wheelX"), 1000000);
    result.wheel_y = finite(value.at("wheelY"), 1000000);
    result.button = integer(value.at("button"), 4);
    result.buttons = integer(value.at("buttons"), 31);
    result.clicks = integer(value.at("clicks"), 3);
    result.modifiers = integer(value.at("modifiers"), gui_surface::known_modifiers);
    if (!result.clicks || ((result.phase == gui_surface::PointerPhase::down || result.phase == gui_surface::PointerPhase::up ||
        result.phase == gui_surface::PointerPhase::cancel) && !result.pointer)) invalid();
    if (result.phase == gui_surface::PointerPhase::wheel) {
        if (!result.wheel_x && !result.wheel_y) invalid();
    } else if (result.wheel_x || result.wheel_y) invalid();
    return result;
}
inline gui_surface::MouseTransition mouse(const Json& value) {
    require_shape(value, {"kind", "version", "phase", "captureToken", "x", "y", "wheelX", "wheelY", "button", "buttons", "clicks", "modifiers", "contextOrigin"});
    gui_surface::MouseTransition result;
    result.version = integer(value.at("version"), gui_surface::mouse_input_version);
    if (result.version != gui_surface::mouse_input_version) invalid();
    const auto& phase = text(value.at("phase"), 7, false);
    if (phase == "move") result.phase = gui_surface::MousePhase::move;
    else if (phase == "down") result.phase = gui_surface::MousePhase::down;
    else if (phase == "up") result.phase = gui_surface::MousePhase::up;
    else if (phase == "wheel") result.phase = gui_surface::MousePhase::wheel;
    else if (phase == "cancel") result.phase = gui_surface::MousePhase::cancel;
    else if (phase == "context") result.phase = gui_surface::MousePhase::context;
    else invalid();
    result.capture_token = decimal(value.at("captureToken"));
    result.x = finite(value.at("x"), 1000000);
    result.y = finite(value.at("y"), 1000000);
    result.wheel_x = finite(value.at("wheelX"), 1000000);
    result.wheel_y = finite(value.at("wheelY"), 1000000);
    result.button = integer(value.at("button"), 4);
    result.buttons = integer(value.at("buttons"), 31);
    result.clicks = integer(value.at("clicks"), 3);
    result.modifiers = integer(value.at("modifiers"), gui_surface::known_modifiers);
    const auto& origin = text(value.at("contextOrigin"), 8, false);
    if (origin == "pointer") result.context_origin = gui_surface::ContextOrigin::pointer;
    else if (origin == "keyboard") result.context_origin = gui_surface::ContextOrigin::keyboard;
    else invalid();
    const bool edge = result.phase == gui_surface::MousePhase::down || result.phase == gui_surface::MousePhase::up;
    if (edge) {
        if (!result.capture_token || ((result.buttons & gui_surface::mouse_button_bit(result.button)) != 0) !=
            (result.phase == gui_surface::MousePhase::down)) invalid();
    } else if (result.button || result.clicks) invalid();
    if (result.phase == gui_surface::MousePhase::wheel) {
        if ((!result.wheel_x && !result.wheel_y) ||
            double(float(result.wheel_x)) != result.wheel_x || double(float(result.wheel_y)) != result.wheel_y) invalid();
    } else if (result.wheel_x || result.wheel_y) invalid();
    if (result.phase == gui_surface::MousePhase::cancel) {
        if (!result.capture_token || result.x || result.y || result.buttons || result.modifiers) invalid();
    } else if (!result.capture_token && result.buttons) invalid();
    if (result.context_origin == gui_surface::ContextOrigin::keyboard) {
        if (result.phase != gui_surface::MousePhase::context || result.x || result.y || result.modifiers) invalid();
    }
    return result;
}
inline gui_surface::ByteRange range(const Json& value) {
    const auto* values = std::get_if<Json::Array>(&value.value);
    if (!values || values->size() != 2) invalid();
    gui_surface::ByteRange result{integer((*values)[0], 65536), integer((*values)[1], 65536)};
    if (result.begin > result.end) invalid();
    return result;
}
inline Json range(gui_surface::ByteRange value) {
    return Json::Array{double(value.begin), double(value.end)};
}
inline std::optional<gui_surface::ByteRange> replacement(const Json& value) {
    if (std::holds_alternative<std::nullptr_t>(value.value)) return std::nullopt;
    return range(value);
}
inline gui_surface::TextCommit committed_text(const Json& value) {
    require_shape(value, {"kind", "transaction", "editorRevision", "text", "replacement"});
    gui_surface::TextCommit result{decimal(value.at("transaction"), true), decimal(value.at("editorRevision"), true),
        text(value.at("text"), 65536), replacement(value.at("replacement"))};
    if (result.text.empty() && result.replacement && result.replacement->begin == result.replacement->end) invalid();
    return result;
}
inline gui_surface::CompositionEdit composition(const Json& value) {
    require_shape(value, {"kind", "operation", "transaction", "editorRevision", "text", "selection", "replacement"});
    gui_surface::CompositionEdit result;
    const auto& operation = text(value.at("operation"), 6, false);
    if (operation == "begin") result.operation = gui_surface::CompositionOperation::begin;
    else if (operation == "update") result.operation = gui_surface::CompositionOperation::update;
    else if (operation == "commit") result.operation = gui_surface::CompositionOperation::commit;
    else if (operation == "cancel") result.operation = gui_surface::CompositionOperation::cancel;
    else invalid();
    result.transaction = decimal(value.at("transaction"), true);
    result.editor_revision = decimal(value.at("editorRevision"), true);
    result.text = text(value.at("text"), 65536);
    result.selection = range(value.at("selection"));
    result.replacement = replacement(value.at("replacement"));
    if (!gui_surface::valid_range(result.text, result.selection) ||
        (result.operation != gui_surface::CompositionOperation::begin && result.replacement) ||
        (result.operation == gui_surface::CompositionOperation::cancel && (!result.text.empty() || result.selection != gui_surface::ByteRange{}))) invalid();
    return result;
}
inline gui_surface::SelectionChange selection(const Json& value) {
    require_shape(value, {"kind", "editorRevision", "selection", "backward"});
    return {decimal(value.at("editorRevision"), true), range(value.at("selection")), boolean(value.at("backward"))};
}
inline void validate_presentation(const gui_surface::Presentation& value, const gui_surface::Capabilities& capabilities,
                                  Profile profile, std::optional<std::uint64_t> composition) {
    if (value.clipboard || value.popup || (value.editor && profile != Profile::editor_v1)) invalid();
    if (composition && (!*composition || profile != Profile::editor_v1 ||
        !(capabilities.supported & gui_surface::feature(gui_surface::Feature::composition)) ||
        !value.editor || !value.editor->editable)) invalid();
    if (value.editor && value.editor->composition_transaction &&
        (!composition || value.editor->composition_transaction != *composition)) invalid();
    // A fresh Policy has no live native composition. Validate declaration values
    // on a copy; the explicit live transaction above is supplied by the owner,
    // never invented by this serializer to satisfy a temporary validator.
    auto validation = value;
    if (validation.editor) validation.editor->composition_transaction = 0;
    gui_surface::Policy validator(capabilities, value.identity.generation);
    const auto prepared = validator.prepare(validation);
    if (prepared.status != gui_surface::Status::ok) invalid();
}
inline Json editor(const gui_surface::EditorContext& value) {
    return Json::Object{{"revision", std::to_string(value.revision)},
        {"compositionTransaction", std::to_string(value.composition_transaction)}, {"surrounding", value.surrounding},
        {"selection", range(value.selection)}, {"selectionBackward", value.selection_backward}, {"caret", rect(value.caret)},
        {"editable", value.editable}, {"inputPurpose", value.input_purpose}};
}
} // namespace detail

inline Json json_capabilities(const gui_surface::Capabilities& value, Profile profile = Profile::legacy) {
    if (gui_surface::validate_capabilities(value) != gui_surface::Status::ok || (value.supported & ~detail::supported(profile))) detail::invalid();
    const auto& limits = value.limits;
    Json::Object result{{"version", int(value.version)}, {"supported", std::to_string(value.supported)},
        {"limits", Json::Object{{"textBytes", double(limits.text_bytes)}, {"clipboardBytes", double(limits.clipboard_bytes)},
            {"popupItems", double(limits.popup_items)}, {"popupTextBytes", double(limits.popup_text_bytes)},
            {"captureRules", double(limits.capture_rules)}, {"heldKeys", double(limits.held_keys)}, {"popupDepth", double(limits.popup_depth)}}}};
    if (value.supported & gui_surface::feature(gui_surface::Feature::mouse_input)) result.emplace("mouseInputVersion", int(value.mouse_input_version));
    return result;
}

inline Json json_presentation(const gui_surface::Presentation& value, Profile profile,
                              std::optional<std::uint64_t> composition) {
    // Reuse the shared validation, including capture-rule and coordinate limits,
    // without depending on or mutating the live owner's Policy.
    gui_surface::Capabilities capabilities;
    capabilities.supported = detail::supported(profile);
    if (capabilities.supported & gui_surface::feature(gui_surface::Feature::mouse_input)) capabilities.mouse_input_version = gui_surface::mouse_input_version;
    detail::validate_presentation(value, capabilities, profile, composition);
    Json::Array rules;
    rules.reserve(value.keys.rules.size());
    for (const auto& rule : value.keys.rules) rules.emplace_back(Json::Object{
        {"key", rule.key}, {"code", rule.code}, {"requiredModifiers", double(rule.required_modifiers)},
        {"forbiddenModifiers", double(rule.forbidden_modifiers)}, {"down", rule.down}, {"up", rule.up},
        {"disposition", detail::capture(rule.disposition)}});
    return Json::Object{{"identity", detail::identity(value.identity)}, {"required", std::to_string(value.required)},
        {"bounds", detail::rect(value.bounds)}, {"clip", detail::rect(value.clip)}, {"displayScale", value.display_scale},
        {"available", value.available}, {"keys", Json::Object{{"fallback", detail::capture(value.keys.fallback)}, {"rules", std::move(rules)}}},
        {"editor", value.editor ? detail::editor(*value.editor) : Json{}}, {"clipboard", nullptr}, {"popup", nullptr}};
}
inline Json json_presentation(const gui_surface::Presentation& value, Profile profile = Profile::legacy) {
    // The editor profile requires the caller's actual live composition state,
    // including an explicitly supplied null transaction.
    if (profile == Profile::editor_v1) detail::invalid();
    return json_presentation(value, profile, std::nullopt);
}

inline Json json_state(const gui_surface::Capabilities& capabilities, const gui_surface::Presentation* presentation,
                       bool focused, bool active, std::optional<std::uint64_t> composition,
                       std::uint64_t last_sequence, bool service_active, Profile profile = Profile::legacy) {
    auto encoded_capabilities = json_capabilities(capabilities, profile);
    if (!presentation && composition) detail::invalid();
    if (composition && (!presentation->available || !focused || !active || service_active)) detail::invalid();
    Json declaration;
    if (presentation) {
        detail::validate_presentation(*presentation, capabilities, profile, composition);
        declaration = json_presentation(*presentation, profile, composition);
    }
    Json::Object result{{"version", profile == Profile::editor_v1 ? int(editor_protocol_version) : int(gui_surface::protocol_version)},
        {"capabilities", std::move(encoded_capabilities)}, {"presentation", std::move(declaration)},
        {"focused", focused}, {"active", active}, {"composition", composition ? Json{std::to_string(*composition)} : Json{}},
        {"lastSequence", std::to_string(last_sequence)}, {"serviceActive", service_active}};
    if (profile == Profile::editor_v1) result.emplace("profile", "editor_v1");
    return result;
}

inline gui_surface::Capabilities parse_connect(const Json& value, Profile profile = Profile::legacy) {
    const auto allowed = detail::supported(profile);
    if (profile == Profile::editor_v1) {
        if (!exact_shape(value, {"type", "version", "profile", "supported"}) &&
            !exact_shape(value, {"type", "version", "profile", "supported", "mouseInputVersion"})) detail::invalid();
        if (detail::text(value.at("type"), 14, false) != "surfaceConnect" ||
            detail::integer(value.at("version"), editor_protocol_version) != editor_protocol_version ||
            detail::text(value.at("profile"), 9, false) != "editor_v1") detail::invalid();
        gui_surface::Capabilities result;
        result.supported = detail::decimal(value.at("supported"));
        if (result.supported & ~allowed) detail::invalid();
        if (result.supported & gui_surface::feature(gui_surface::Feature::mouse_input)) {
            require_shape(value, {"type", "version", "profile", "supported", "mouseInputVersion"});
            result.mouse_input_version = detail::integer(value.at("mouseInputVersion"), gui_surface::mouse_input_version);
            if (result.mouse_input_version != gui_surface::mouse_input_version) detail::invalid();
        } else require_shape(value, {"type", "version", "profile", "supported"});
        return result;
    }
    if (!exact_shape(value, {"type", "version", "supported"}) &&
        !(profile == Profile::mouse_v1 && exact_shape(value, {"type", "version", "supported", "mouseInputVersion"}))) detail::invalid();
    if (detail::text(value.at("type"), 14, false) != "surfaceConnect" ||
        detail::integer(value.at("version"), gui_surface::protocol_version) != gui_surface::protocol_version) detail::invalid();
    gui_surface::Capabilities result;
    result.supported = detail::decimal(value.at("supported"));
    if (result.supported & ~allowed) detail::invalid();
    if (result.supported & gui_surface::feature(gui_surface::Feature::mouse_input)) {
        require_shape(value, {"type", "version", "supported", "mouseInputVersion"});
        result.mouse_input_version = detail::integer(value.at("mouseInputVersion"), gui_surface::mouse_input_version);
        if (result.mouse_input_version != gui_surface::mouse_input_version) detail::invalid();
    } else require_shape(value, {"type", "version", "supported"});
    return result;
}

inline gui_surface::Event parse_event(const Json& value, Profile profile = Profile::legacy) {
    detail::supported(profile);
    require_shape(value, {"type", "identity", "sequence", "input"});
    if (detail::text(value.at("type"), 12, false) != "surfaceInput") detail::invalid();
    gui_surface::Event result;
    result.identity = detail::identity(value.at("identity"));
    result.sequence = detail::decimal(value.at("sequence"), true);
    const auto& input = value.at("input");
    const auto* object = std::get_if<Json::Object>(&input.value);
    if (!object) detail::invalid();
    const auto kind = object->find("kind");
    if (kind == object->end()) detail::invalid();
    const auto& name = detail::text(kind->second, profile == Profile::editor_v1 ? 11 : 7, false);
    if (name == "key") result.input = detail::key(input);
    else if (name == "focus") result.input = detail::focus(input);
    else if (name == "pointer" && profile == Profile::legacy) result.input = detail::pointer(input);
    else if (name == "mouse" && (profile == Profile::mouse_v1 || profile == Profile::editor_v1)) result.input = detail::mouse(input);
    else if (name == "text" && profile == Profile::editor_v1) result.input = detail::committed_text(input);
    else if (name == "composition" && profile == Profile::editor_v1) result.input = detail::composition(input);
    else if (name == "selection" && profile == Profile::editor_v1) result.input = detail::selection(input);
    else detail::invalid();
    return result;
}

} // namespace foundation::host::surface_web
