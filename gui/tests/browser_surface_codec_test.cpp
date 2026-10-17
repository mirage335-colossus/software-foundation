// SPDX-License-Identifier: CC0-1.0
#include "host/browser_surface_codec.hpp"
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
namespace codec = foundation::host::surface_web;
namespace surface = foundation::gui_surface;
using Json = codec::Json;

void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class Function> void rejected(Function&& function, const char* message) {
    try { function(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error(message);
}
Json::Object& object(Json& value) { return std::get<Json::Object>(value.value); }
Json& member(Json& value, const char* name) { return object(value).at(name); }
surface::Presentation presentation() {
    surface::Presentation result;
    result.identity = {{"surface/\xc3\xa9", 2}, 9007199254740993ull, 3, 4, 5};
    result.required = codec::basic_supported;
    result.bounds = {10, 20, 200, 100}; result.clip = {20, 30, 100, 50};
    result.display_scale = 1.5;
    result.keys.rules.push_back({"z", "KeyZ", surface::control, surface::alt, true, false, surface::Capture::capture});
    return result;
}
Json identity() { return codec::json_presentation(presentation()).at("identity"); }
Json event(Json input) {
    return Json::Object{{"type", "surfaceInput"}, {"identity", identity()}, {"sequence", "18446744073709551615"}, {"input", std::move(input)}};
}
Json key() {
    return Json::Object{{"kind", "key"}, {"phase", "down"}, {"key", "\xf0\x9f\x98\x80"}, {"code", "KeyZ"},
        {"location", 3}, {"modifiers", 31}, {"repeat", false}};
}
Json focus() { return Json::Object{{"kind", "focus"}, {"focused", true}, {"active", true}, {"cause", "direct"}}; }
Json pointer() {
    return Json::Object{{"kind", "pointer"}, {"phase", "down"}, {"pointer", "9007199254740993"},
        {"x", 12.5}, {"y", -20.5}, {"wheelX", 0}, {"wheelY", 0},
        {"button", 4}, {"buttons", 31}, {"clicks", 3}, {"modifiers", 31}};
}
Json mouse() {
    return Json::Object{{"kind", "mouse"}, {"version", 1}, {"phase", "down"}, {"captureToken", "9007199254740993"},
        {"x", 12.5}, {"y", -20.5}, {"wheelX", 0}, {"wheelY", 0},
        {"button", 4}, {"buttons", 16}, {"clicks", 0}, {"modifiers", 31}, {"contextOrigin", "pointer"}};
}
void capabilities_and_output() {
    const Json connection = Json::Object{{"type", "surfaceConnect"}, {"version", 1}, {"supported", "97"}};
    auto capabilities = codec::parse_connect(connection);
    check(capabilities.supported == codec::basic_supported && capabilities.limits == surface::Limits{}, "Connection capabilities changed");
    const auto encoded = codec::json_capabilities(capabilities);
    check(codec::exact_shape(encoded, {"version", "supported", "limits"}) && encoded.at("supported").str() == "97", "Capability wire shape changed");
    check(encoded.at("limits").at("textBytes").number() == 65536 && encoded.at("limits").at("popupDepth").number() == 8, "Capability ceilings changed");
    auto zero = connection; member(zero, "supported") = "0";
    check(codec::parse_connect(zero).supported == 0, "Empty capability intersection was rejected");
    for (const Json& bad : {Json{97}, Json{"097"}, Json{"98"}, Json{"18446744073709551616"}}) {
        auto value = connection; member(value, "supported") = bad;
        rejected([&] { codec::parse_connect(value); }, "Invalid connection feature value accepted");
    }
    for (const Json& bad : {Json{true}, Json{"1"}, Json{1.5}, Json{0}, Json{2}}) {
        auto value = connection; member(value, "version") = bad;
        rejected([&] { codec::parse_connect(value); }, "Invalid connection version accepted");
    }
    auto extra = connection; object(extra).emplace("limits", Json::Object{});
    rejected([&] { codec::parse_connect(extra); }, "Untrusted connection supplied limits");
    capabilities.supported |= surface::feature(surface::Feature::composition);
    rejected([&] { codec::json_capabilities(capabilities); }, "Unimplemented physical capability advertised");
    capabilities.supported = 0; capabilities.limits.capture_rules = 65;
    rejected([&] { codec::json_capabilities(capabilities); }, "Excessive capability ceiling advertised");

    const auto source = presentation();
    const auto output = codec::json_presentation(source);
    check(codec::exact_shape(output, {"identity", "required", "bounds", "clip", "displayScale", "available", "keys", "editor", "clipboard", "popup"}), "Presentation shape changed");
    check(output.at("identity").at("presentationRevision").str() == "9007199254740993" && output.at("required").str() == "97", "64-bit presentation identity lost precision");
    check(output.at("identity").at("owner").at("id").str() == source.identity.owner.id &&
        output.at("keys").at("rules").array()[0].at("requiredModifiers").number() == double(surface::control), "Capture or scalar owner metadata changed");
    check(std::holds_alternative<std::nullptr_t>(output.at("editor").value) &&
        std::holds_alternative<std::nullptr_t>(output.at("clipboard").value) &&
        std::holds_alternative<std::nullptr_t>(output.at("popup").value), "Unsupported editor authority was emitted");
    const auto round_trip = gui::web_detail::Parser(gui::web_detail::encode(output)).parse();
    check(round_trip.at("identity").at("presentationRevision").str() == "9007199254740993", "Wire serialization rounded identity");
    for (const auto& change : std::vector<std::function<void(surface::Presentation&)>>{
        [](auto& value) { value.editor.emplace(); }, [](auto& value) { value.clipboard.emplace(); }, [](auto& value) { value.popup.emplace(); },
        [](auto& value) { value.required |= surface::feature(surface::Feature::committed_text); },
        [](auto& value) { value.identity.owner.id = std::string("a\0b", 3); },
        [](auto& value) { value.clip = {0, 0, 1000, 1000}; },
        [](auto& value) { value.display_scale = std::numeric_limits<double>::infinity(); },
        [](auto& value) { value.keys.rules.resize(65); }}) {
        auto value = source; change(value);
        rejected([&] { codec::json_presentation(value); }, "Invalid or unsupported presentation encoded");
    }
}
void valid_inputs_and_policy() {
    const auto key_event = codec::parse_event(event(key()));
    check(key_event.identity == presentation().identity && key_event.sequence == std::numeric_limits<std::uint64_t>::max(), "Event identity lost 64-bit precision");
    const auto& stroke = std::get<surface::KeyTransition>(key_event.input);
    check(stroke.key == "\xf0\x9f\x98\x80" && stroke.location == 3 && stroke.modifiers == 31 && !stroke.repeat, "Physical key metadata changed");
    auto released = key(); member(released, "phase") = "up";
    check(std::get<surface::KeyTransition>(codec::parse_event(event(released)).input).phase == surface::KeyPhase::up, "Key release was lost");
    auto blurred = focus(); member(blurred, "cause") = "external"; member(blurred, "focused") = false;
    check(std::get<surface::FocusChange>(codec::parse_event(event(blurred)).input) == surface::FocusChange{false, true, surface::FocusCause::external}, "External focus transition changed");
    for (const char* phase : {"move", "down", "up", "cancel", "wheel", "context"}) {
        auto input = pointer(); member(input, "phase") = phase;
        if (std::string_view(phase) == "wheel") member(input, "wheelY") = -100.5;
        const auto parsed = std::get<surface::PointerTransition>(codec::parse_event(event(input)).input);
        check(parsed.pointer == 9007199254740993ull && parsed.x == 12.5 && parsed.y == -20.5 &&
            parsed.button == 4 && parsed.buttons == 31 && parsed.clicks == 3 && parsed.modifiers == 31, "Pointer metadata changed");
    }
    for (const char* phase : {"move", "wheel", "context"}) {
        auto input = pointer(); member(input, "phase") = phase; member(input, "pointer") = "0";
        if (std::string_view(phase) == "wheel") member(input, "wheelX") = 1;
        check(std::get<surface::PointerTransition>(codec::parse_event(event(input)).input).pointer == 0,
            "Valid pointer phase incorrectly required capture ownership");
    }
    surface::Capabilities capabilities; capabilities.supported = codec::basic_supported;
    surface::Policy policy(capabilities, 3);
    auto prepared = policy.prepare(presentation());
    check(prepared.status == surface::Status::ok && policy.commit(std::move(prepared.prepared), presentation().identity.presentation_revision).status == surface::Status::ok, "Policy fixture did not commit");
    auto focused = event(focus()); member(focused, "sequence") = "1";
    check(policy.accept(codec::parse_event(focused)).status == surface::Status::ok, "Parsed focus was not accepted by Policy");
    auto pressed = event(key()); member(pressed, "sequence") = "2";
    check(policy.accept(codec::parse_event(pressed)).status == surface::Status::ok &&
        policy.accept(codec::parse_event(pressed)).status == surface::Status::duplicate, "Parsed event bypassed Policy replay rejection");
    auto stale = event(pointer()); member(stale, "sequence") = "3"; member(member(stale, "identity"), "context") = "6";
    check(policy.accept(codec::parse_event(stale)).status == surface::Status::stale_identity, "Parsed stale identity bypassed Policy");
}
void malformed_inputs() {
    for (const Json& bad : {Json{1}, Json{true}, Json{nullptr}, Json{""}, Json{"0"}, Json{"01"}, Json{"+1"}, Json{"-1"}, Json{"1.0"}, Json{" 1"}, Json{"18446744073709551616"}}) {
        auto value = event(key()); member(value, "sequence") = bad;
        rejected([&] { codec::parse_event(value); }, "Malformed sequence accepted");
    }
    for (const char* field : {"owner", "presentationRevision", "generation", "epoch", "context"}) {
        auto value = event(key()); object(member(value, "identity")).erase(field);
        rejected([&] { codec::parse_event(value); }, "Incomplete identity accepted");
    }
    for (const auto& bad : std::vector<std::string>{"", std::string(129, 'x'), std::string("a\0b", 3), "\xed\xa0\x80", "\xc0\xaf", "\xf4\x90\x80\x80"}) {
        auto value = event(key()); member(member(member(value, "identity"), "owner"), "id") = bad;
        rejected([&] { codec::parse_event(value); }, "Invalid scalar owner accepted");
    }
    for (const char* cause : {"owned_service", "owned_popup", "unknown"}) {
        auto value = focus(); member(value, "cause") = cause;
        rejected([&] { codec::parse_event(event(value)); }, "Untrusted input acquired owned focus authority");
    }
    for (const char* kind : {"text", "composition", "selection", "clipboard", "popup", "service", "unknown"}) {
        auto value = key(); member(value, "kind") = kind;
        rejected([&] { codec::parse_event(event(value)); }, "Undelegated input kind accepted");
    }
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& value) { member(value, "location") = 1.5; }, [](auto& value) { member(value, "location") = 4; },
        [](auto& value) { member(value, "modifiers") = 32; }, [](auto& value) { member(value, "repeat") = 1; },
        [](auto& value) { member(value, "key") = std::string(65, 'x'); }, [](auto& value) { member(value, "key") = "\xed\xa0\x80"; },
        [](auto& value) { member(value, "key") = std::string("x\0y", 3); }, [](auto& value) { member(value, "code") = "Key Z"; },
        [](auto& value) { member(value, "phase") = "press"; },
        [](auto& value) { member(value, "phase") = "up"; member(value, "repeat") = true; },
        [](auto& value) { object(value).emplace("service", "forged"); }, [](auto& value) { object(value).erase("code"); }}) {
        auto value = key(); change(value);
        rejected([&] { codec::parse_event(event(value)); }, "Malformed key input accepted");
    }
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& value) { member(value, "x") = std::numeric_limits<double>::quiet_NaN(); },
        [](auto& value) { member(value, "y") = std::numeric_limits<double>::infinity(); },
        [](auto& value) { member(value, "wheelX") = 1; }, [](auto& value) { member(value, "x") = 1000001; },
        [](auto& value) { member(value, "button") = -1; }, [](auto& value) { member(value, "buttons") = 32; },
        [](auto& value) { member(value, "clicks") = 0; }, [](auto& value) { member(value, "clicks") = 1.5; },
        [](auto& value) { member(value, "pointer") = "0"; }, [](auto& value) { member(value, "pointer") = 1; },
        [](auto& value) { member(value, "phase") = "wheel"; }, [](auto& value) { member(value, "phase") = "invalid"; }}) {
        auto value = pointer(); change(value);
        rejected([&] { codec::parse_event(event(value)); }, "Malformed pointer input accepted");
    }
    auto value = event(key()); object(value).emplace("operation", "service");
    rejected([&] { codec::parse_event(value); }, "Extra outer operation accepted");
    check(!codec::exact_shape(Json::Object{{"a", 1}, {"b", 2}}, {"a", "a"}) &&
        !codec::exact_shape(Json::Array{}, {}), "Exact-shape helper accepted unknown keys or non-object");
    rejected([&] { codec::parse_event(Json::Array{}); }, "Non-object event accepted");
    rejected([&] { gui::web_detail::Parser("{\"type\":\"surfaceInput\",\"type\":\"surfaceInput\"}").parse(); }, "Duplicate wire property accepted");
}
void successor_profile() {
    constexpr auto profile = codec::Profile::mouse_v1;
    static_assert(codec::basic_supported == 97 && codec::successor_supported == 8225);
    const Json connection = Json::Object{{"type", "surfaceConnect"}, {"version", 1}, {"supported", "8225"}, {"mouseInputVersion", 1}};
    const auto capabilities = codec::parse_connect(connection, profile);
    check(capabilities.supported == codec::successor_supported && capabilities.mouse_input_version == 1, "Successor negotiation lost its version");
    const auto output = codec::json_capabilities(capabilities, profile);
    check(codec::exact_shape(output, {"version", "supported", "limits", "mouseInputVersion"}) &&
        output.at("supported").str() == "8225" && output.at("mouseInputVersion").number() == 1, "Successor capability shape changed");
    rejected([&] { codec::parse_connect(connection); }, "Legacy connection accepted mouse feature");
    rejected([&] { codec::json_capabilities(capabilities); }, "Legacy writer advertised mouse feature");
    for (const char* supported : {"0", "1", "32", "33"}) {
        auto value = connection; member(value, "supported") = supported;
        rejected([&] { codec::parse_connect(value, profile); }, "Absent feature accepted a version marker");
        object(value).erase("mouseInputVersion");
        const auto parsed = codec::parse_connect(value, profile);
        check(!parsed.mouse_input_version && codec::exact_shape(codec::json_capabilities(parsed, profile), {"version", "supported", "limits"}),
            "Mouse-free successor changed the old capability shape");
    }
    auto without_marker = connection; object(without_marker).erase("mouseInputVersion");
    rejected([&] { codec::parse_connect(without_marker, profile); }, "Mouse feature accepted without version marker");
    for (const Json& bad : {Json{0}, Json{2}, Json{true}, Json{"1"}, Json{1.5}}) {
        auto value = connection; member(value, "mouseInputVersion") = bad;
        rejected([&] { codec::parse_connect(value, profile); }, "Invalid successor version accepted");
    }
    auto pointer_connection = connection; member(pointer_connection, "supported") = "8289";
    rejected([&] { codec::parse_connect(pointer_connection, profile); }, "Successor reader acquired legacy multi-pointer feature");
    auto inconsistent = capabilities; inconsistent.mouse_input_version = 0;
    rejected([&] { codec::json_capabilities(inconsistent, profile); }, "Mouse writer omitted version authority");
    inconsistent = {}; inconsistent.mouse_input_version = 1;
    rejected([&] { codec::json_capabilities(inconsistent, profile); }, "Mouse-free writer emitted version authority");
    auto source = presentation(); source.required = codec::successor_supported;
    check(codec::json_presentation(source, profile).at("required").str() == "8225", "Successor presentation was not encoded");
    rejected([&] { codec::json_presentation(source); }, "Legacy presentation accepted mouse requirement");
    rejected([&] { codec::json_presentation(presentation(), profile); }, "Successor presentation acquired legacy pointer requirement");
    rejected([&] { codec::parse_event(event(pointer()), profile); }, "Successor aliased legacy pointer input");
    rejected([&] { codec::parse_event(event(mouse())); }, "Legacy reader accepted mouse input");
    const auto parsed = std::get<surface::MouseTransition>(codec::parse_event(event(mouse()), profile).input);
    check(parsed.version == 1 && parsed.capture_token == 9007199254740993ull && parsed.phase == surface::MousePhase::down &&
        parsed.context_origin == surface::ContextOrigin::pointer && parsed.clicks == 0 && parsed.buttons == 16 && parsed.modifiers == 31,
        "Successor mouse metadata changed");
    for (unsigned button = 0; button != 5; ++button) {
        for (unsigned clicks = 0; clicks != 4; ++clicks) {
            auto value = mouse(); member(value, "button") = int(button); member(value, "clicks") = int(clicks);
            member(value, "buttons") = int(surface::mouse_button_bit(button));
            check(std::get<surface::MouseTransition>(codec::parse_event(event(value), profile).input).button == button, "Mouse ordinal mapping changed");
            member(value, "phase") = "up"; member(value, "buttons") = 0;
            check(std::get<surface::MouseTransition>(codec::parse_event(event(value), profile).input).phase == surface::MousePhase::up, "Mouse release rejected");
        }
    }
    for (const char* phase : {"move", "wheel", "context", "cancel"}) {
        auto value = mouse(); member(value, "phase") = phase; member(value, "button") = 0;
        if (std::string_view(phase) == "wheel") member(value, "wheelY") = -100.5;
        if (std::string_view(phase) == "cancel") {
            member(value, "x") = 0; member(value, "y") = 0; member(value, "buttons") = 0; member(value, "modifiers") = 0;
        }
        check(std::get<surface::MouseTransition>(codec::parse_event(event(value), profile).input).capture_token == parsed.capture_token,
            "Mouse phase retired or rounded token during decoding");
        if (std::string_view(phase) != "cancel") {
            member(value, "captureToken") = "0"; member(value, "buttons") = 0;
            codec::parse_event(event(value), profile);
        }
    }
    auto context = mouse(); member(context, "phase") = "context"; member(context, "button") = 0;
    member(context, "contextOrigin") = "keyboard"; member(context, "x") = 0; member(context, "y") = 0; member(context, "modifiers") = 0;
    const auto held_context = std::get<surface::MouseTransition>(codec::parse_event(event(context), profile).input);
    check(held_context.capture_token == parsed.capture_token && held_context.buttons == 16 &&
        held_context.context_origin == surface::ContextOrigin::keyboard, "Held keyboard context lost its retained capture");
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& value) { member(value, "version") = 0; }, [](auto& value) { member(value, "version") = 2; },
        [](auto& value) { member(value, "version") = true; }, [](auto& value) { member(value, "captureToken") = "01"; },
        [](auto& value) { member(value, "captureToken") = 1; }, [](auto& value) { member(value, "captureToken") = "18446744073709551616"; },
        [](auto& value) { member(value, "captureToken") = "0"; }, [](auto& value) { member(value, "buttons") = 0; },
        [](auto& value) { member(value, "phase") = "up"; }, [](auto& value) { member(value, "buttons") = 32; },
        [](auto& value) { member(value, "button") = 5; }, [](auto& value) { member(value, "clicks") = 4; },
        [](auto& value) { member(value, "modifiers") = 32; }, [](auto& value) { member(value, "x") = 1000001; },
        [](auto& value) { member(value, "y") = std::numeric_limits<double>::infinity(); },
        [](auto& value) { member(value, "wheelX") = 1; }, [](auto& value) { member(value, "contextOrigin") = "keyboard"; },
        [](auto& value) { member(value, "contextOrigin") = "unknown"; },
        [](auto& value) { object(value).emplace("pointer", "1"); }, [](auto& value) { member(value, "phase") = "press"; }}) {
        auto value = mouse(); change(value);
        rejected([&] { codec::parse_event(event(value), profile); }, "Malformed mouse input accepted");
    }
    for (const char* field : {"kind", "version", "phase", "captureToken", "x", "y", "wheelX", "wheelY", "button", "buttons", "clicks", "modifiers", "contextOrigin"}) {
        auto value = mouse(); object(value).erase(field);
        rejected([&] { codec::parse_event(event(value), profile); }, "Incomplete mouse shape accepted");
    }
    auto value = mouse(); member(value, "phase") = "move";
    rejected([&] { codec::parse_event(event(value), profile); }, "Move supplied unused button");
    member(value, "button") = 0; member(value, "captureToken") = "0";
    rejected([&] { codec::parse_event(event(value), profile); }, "Idle move claimed held buttons");
    member(value, "captureToken") = "18446744073709551615"; member(value, "phase") = "wheel"; member(value, "wheelY") = 0.1;
    rejected([&] { codec::parse_event(event(value), profile); }, "Wheel accepted noncanonical float precision");
    member(value, "wheelY") = double(float(0.1));
    check(std::get<surface::MouseTransition>(codec::parse_event(event(value), profile).input).capture_token == std::numeric_limits<std::uint64_t>::max(),
        "Maximum mouse token rounded");
    member(value, "phase") = "cancel"; member(value, "wheelY") = 0;
    rejected([&] { codec::parse_event(event(value), profile); }, "Cancel accepted physical payload instead of canonical zeros");
    const auto invalid_profile = static_cast<codec::Profile>(99);
    rejected([&] { codec::parse_connect(connection, invalid_profile); }, "Unknown reader profile accepted");
    rejected([&] { codec::parse_event(event(key()), invalid_profile); }, "Unknown input profile accepted");
}
surface::Presentation editor_presentation() {
    auto value = presentation(); value.required = codec::editor_supported;
    value.editor = surface::EditorContext{9007199254740993ull, 0, "A\xc3\xa9\xf0\x9f\x99\x82Z", {1, 3}, true,
        {20, 30, 1, 16}, true, "text"};
    return value;
}
Json editor_connection(std::uint64_t supported = codec::editor_supported) {
    Json::Object value{{"type", "surfaceConnect"}, {"version", 2}, {"profile", "editor_v1"}, {"supported", std::to_string(supported)}};
    if (supported & surface::feature(surface::Feature::mouse_input)) value.emplace("mouseInputVersion", 1);
    return value;
}
Json text_input() {
    return Json::Object{{"kind", "text"}, {"transaction", "18446744073709551615"}, {"editorRevision", "9007199254740993"},
        {"text", "\xf0\x9f\x99\x82"}, {"replacement", Json::Array{1, 3}}};
}
Json composition_input(const char* operation = "begin") {
    return Json::Object{{"kind", "composition"}, {"operation", operation}, {"transaction", "9007199254740995"},
        {"editorRevision", "9007199254740993"}, {"text", "\xc3\xa9\xf0\x9f\x99\x82"}, {"selection", Json::Array{2, 6}},
        {"replacement", nullptr}};
}
Json selection_input() {
    return Json::Object{{"kind", "selection"}, {"editorRevision", "9007199254740993"},
        {"selection", Json::Array{1, 7}}, {"backward", true}};
}
void editor_negotiation_and_output() {
    constexpr auto profile = codec::Profile::editor_v1;
    static_assert(codec::editor_supported == 8255);
    const auto capabilities = codec::parse_connect(editor_connection(), profile);
    check(capabilities.version == 1 && capabilities.supported == 8255 && capabilities.mouse_input_version == 1,
        "Editor envelope changed shared capability version or mask");
    for (unsigned subset = 0; subset != 128; ++subset) {
        const std::uint64_t supported = (subset & 63) | ((subset & 64) ? 8192 : 0);
        const auto parsed = codec::parse_connect(editor_connection(supported), profile);
        check(parsed.supported == supported && parsed.mouse_input_version == ((subset & 64) ? 1u : 0u),
            "Editor profile rejected a valid capability subset");
        check(codec::json_capabilities(parsed, profile).at("version").number() == 1, "Editor capability version changed");
    }
    for (const auto old_profile : {codec::Profile::legacy, codec::Profile::mouse_v1}) {
        rejected([&] { codec::parse_connect(editor_connection(), old_profile); }, "Old reader accepted editor connection");
        auto old = editor_connection(); member(old, "version") = 1;
        rejected([&] { codec::parse_connect(old, profile); }, "Editor reader accepted old envelope version");
    }
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& v) { member(v, "version") = true; }, [](auto& v) { member(v, "version") = "2"; },
        [](auto& v) { member(v, "version") = 2.5; }, [](auto& v) { member(v, "version") = 3; },
        [](auto& v) { member(v, "profile") = "mouse_v1"; }, [](auto& v) { object(v).erase("profile"); },
        [](auto& v) { member(v, "supported") = "8319"; }, [](auto& v) { member(v, "supported") = "8383"; },
        [](auto& v) { member(v, "supported") = 8255; }, [](auto& v) { member(v, "supported") = "08255"; },
        [](auto& v) { object(v).erase("mouseInputVersion"); }, [](auto& v) { member(v, "mouseInputVersion") = "1"; },
        [](auto& v) { object(v).emplace("limits", Json::Object{}); }}) {
        auto value = editor_connection(); change(value);
        rejected([&] { codec::parse_connect(value, profile); }, "Malformed editor connection accepted");
    }
    auto without_mouse = editor_connection(63); object(without_mouse).emplace("mouseInputVersion", 1);
    rejected([&] { codec::parse_connect(without_mouse, profile); }, "Mouse-free editor connection supplied version marker");
    auto source = editor_presentation();
    rejected([&] { codec::json_presentation(source, profile); }, "Editor writer guessed a live composition argument");
    const auto encoded = codec::json_presentation(source, profile, std::nullopt);
    const auto& editor = encoded.at("editor");
    check(codec::exact_shape(editor, {"revision", "compositionTransaction", "surrounding", "selection", "selectionBackward", "caret", "editable", "inputPurpose"}) &&
        editor.at("revision").str() == "9007199254740993" && editor.at("compositionTransaction").str() == "0" &&
        editor.at("surrounding").str() == source.editor->surrounding && editor.at("selection").array()[1].number() == 3 &&
        editor.at("selectionBackward").boolean(), "Editor output lost its exact basis");
    const auto state = codec::json_state(capabilities, &source, true, true, std::nullopt,
        std::numeric_limits<std::uint64_t>::max(), false, profile);
    check(codec::exact_shape(state, {"version", "profile", "capabilities", "presentation", "focused", "active", "composition", "lastSequence", "serviceActive"}) &&
        state.at("version").number() == 2 && state.at("profile").str() == "editor_v1" &&
        state.at("capabilities").at("version").number() == 1 && state.at("lastSequence").str() == "18446744073709551615" &&
        std::holds_alternative<std::nullptr_t>(state.at("composition").value), "Editor state envelope/version changed");
    const auto live = std::optional<std::uint64_t>{9007199254740995ull};
    check(codec::json_state(capabilities, &source, true, true, live, 2, false, profile).at("composition").str() == "9007199254740995",
        "Pending native attestation was not serializable");
    source.editor->composition_transaction = *live;
    check(codec::json_presentation(source, profile, live).at("editor").at("compositionTransaction").str() == "9007199254740995",
        "Explicit native composition attestation changed");
    rejected([&] { codec::json_state(capabilities, &source, true, true, std::nullopt, 2, false, profile); },
        "Nonzero native attestation accepted without actual live composition");
    rejected([&] { codec::json_presentation(source, profile, *live + 1); }, "Mismatched native composition attestation accepted");
    source.editor->composition_transaction = 0;
    rejected([&] { codec::json_state(capabilities, &source, true, true, 0, 2, false, profile); }, "Explicit zero composition accepted");
    rejected([&] { codec::json_state(capabilities, nullptr, true, true, live, 2, false, profile); }, "Composition without presentation accepted");
    auto no_editor = source; no_editor.editor.reset();
    rejected([&] { codec::json_state(capabilities, &no_editor, true, true, live, 2, false, profile); }, "Composition without editor accepted");
    auto readonly = source; readonly.editor->editable = false;
    rejected([&] { codec::json_state(capabilities, &readonly, true, true, live, 2, false, profile); }, "Readonly live composition accepted");
    auto unavailable = source; unavailable.available = false;
    rejected([&] { codec::json_state(capabilities, &unavailable, true, true, live, 2, false, profile); }, "Unavailable live composition accepted");
    rejected([&] { codec::json_state(capabilities, &source, false, true, live, 2, false, profile); }, "Unfocused live composition accepted");
    rejected([&] { codec::json_state(capabilities, &source, true, false, live, 2, false, profile); }, "Inactive live composition accepted");
    rejected([&] { codec::json_state(capabilities, &source, true, true, live, 2, true, profile); }, "Service-owned live composition accepted");
    auto limited = capabilities; limited.supported &= ~surface::feature(surface::Feature::composition);
    auto less_required = source; less_required.required = limited.supported;
    rejected([&] { codec::json_state(limited, &less_required, true, true, live, 2, false, profile); }, "Unsupported live composition accepted");
    limited = capabilities; limited.limits.text_bytes = 7;
    rejected([&] { codec::json_state(limited, &source, true, true, std::nullopt, 2, false, profile); }, "Negotiated text limit ignored");
    limited = capabilities; limited.limits.capture_rules = 1;
    auto many_rules = source; many_rules.keys.rules.push_back(many_rules.keys.rules.front());
    rejected([&] { codec::json_state(limited, &many_rules, true, true, std::nullopt, 2, false, profile); }, "Negotiated capture limit ignored");
    limited = capabilities; limited.supported = 63; limited.mouse_input_version = 0;
    rejected([&] { codec::json_state(limited, &source, true, true, std::nullopt, 2, false, profile); }, "Required features escaped negotiated mask");
    for (const auto& change : std::vector<std::function<void(surface::Presentation&)>>{
        [](auto& v) { v.editor->revision = 0; }, [](auto& v) { v.editor->selection = {2, 3}; },
        [](auto& v) { v.editor->selection = {0, 9}; }, [](auto& v) { v.editor->surrounding = "\xed\xa0\x80"; },
        [](auto& v) { v.editor->surrounding = std::string(65537, 'x'); },
        [](auto& v) { v.editor->input_purpose = std::string(65, 'x'); },
        [](auto& v) { v.editor->caret.width = -1; }, [](auto& v) { v.clipboard.emplace(); }, [](auto& v) { v.popup.emplace(); }}) {
        auto value = source; change(value);
        rejected([&] { codec::json_presentation(value, profile, std::nullopt); }, "Malformed editor declaration encoded");
    }
    const auto empty = codec::json_state(surface::Capabilities{}, nullptr, false, true, std::nullopt, 0, false, profile);
    check(empty.at("capabilities").at("supported").str() == "0" && std::holds_alternative<std::nullptr_t>(empty.at("presentation").value),
        "Empty editor state rejected");
    // Preserve the original capability wire bytes, including conditional markers.
    for (const auto old_profile : {codec::Profile::legacy, codec::Profile::mouse_v1}) {
        surface::Capabilities old; old.supported = old_profile == codec::Profile::legacy ? 97 : 8225;
        old.mouse_input_version = old_profile == codec::Profile::mouse_v1 ? 1 : 0;
        const std::string expected = old_profile == codec::Profile::legacy ?
            R"({"limits":{"captureRules":64,"clipboardBytes":65536,"heldKeys":64,"popupDepth":8,"popupItems":1024,"popupTextBytes":65536,"textBytes":65536},"supported":"97","version":1})" :
            R"({"limits":{"captureRules":64,"clipboardBytes":65536,"heldKeys":64,"popupDepth":8,"popupItems":1024,"popupTextBytes":65536,"textBytes":65536},"mouseInputVersion":1,"supported":"8225","version":1})";
        check(gui::web_detail::encode(codec::json_capabilities(old, old_profile)) == expected, "Old capability wire bytes changed");
        const auto old_state = codec::json_state(old, nullptr, false, true, std::nullopt, 0, false, old_profile);
        check(codec::exact_shape(old_state, {"version", "capabilities", "presentation", "focused", "active", "composition", "lastSequence", "serviceActive"}) &&
            old_state.at("version").number() == 1, "Old state shape changed");
        rejected([&] { codec::json_presentation(source, old_profile); }, "Old profile emitted editor authority");
    }
}
void editor_inputs_and_policy() {
    constexpr auto profile = codec::Profile::editor_v1;
    const auto parsed = std::get<surface::TextCommit>(codec::parse_event(event(text_input()), profile).input);
    check(parsed.transaction == std::numeric_limits<std::uint64_t>::max() && parsed.editor_revision == 9007199254740993ull &&
        parsed.replacement == surface::ByteRange{1, 3} && parsed.text == "\xf0\x9f\x99\x82", "Text metadata rounded or changed");
    auto deletion = text_input(); member(deletion, "text") = "";
    check(std::get<surface::TextCommit>(codec::parse_event(event(deletion), profile).input).text.empty(), "Explicit deletion rejected");
    member(deletion, "replacement") = nullptr; codec::parse_event(event(deletion), profile);
    auto ceiling = text_input(); member(ceiling, "text") = std::string(65536, 'x');
    codec::parse_event(event(ceiling), profile);
    for (const char* operation : {"begin", "update", "commit", "cancel"}) {
        auto input = composition_input(operation);
        if (std::string_view(operation) == "begin") member(input, "replacement") = Json::Array{1, 7};
        if (std::string_view(operation) == "cancel") { member(input, "text") = ""; member(input, "selection") = Json::Array{0, 0}; }
        check(std::get<surface::CompositionEdit>(codec::parse_event(event(input), profile).input).transaction == 9007199254740995ull,
            "Composition transaction changed");
    }
    const auto selected = std::get<surface::SelectionChange>(codec::parse_event(event(selection_input()), profile).input);
    check(selected.editor_revision == parsed.editor_revision && selected.selection == surface::ByteRange{1, 7} && selected.backward,
        "Selection basis or direction changed");
    codec::parse_event(event(key()), profile); codec::parse_event(event(focus()), profile); codec::parse_event(event(mouse()), profile);
    rejected([&] { codec::parse_event(event(pointer()), profile); }, "Editor profile acquired legacy pointer input");
    for (const auto old_profile : {codec::Profile::legacy, codec::Profile::mouse_v1})
        for (const auto& input : {text_input(), composition_input(), selection_input()})
            rejected([&] { codec::parse_event(event(input), old_profile); }, "Old profile acquired editor input");
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& v) { member(v, "transaction") = "0"; }, [](auto& v) { member(v, "transaction") = "01"; },
        [](auto& v) { member(v, "transaction") = "18446744073709551616"; }, [](auto& v) { member(v, "transaction") = 1; },
        [](auto& v) { member(v, "editorRevision") = "0"; }, [](auto& v) { member(v, "editorRevision") = true; },
        [](auto& v) { member(v, "text") = std::string(65537, 'x'); }, [](auto& v) { member(v, "text") = "\xc0\xaf"; },
        [](auto& v) { member(v, "text") = std::string("a\0b", 3); }, [](auto& v) { member(v, "text") = "\xed\xa0\x80"; },
        [](auto& v) { member(v, "replacement") = Json::Array{3, 1}; }, [](auto& v) { member(v, "replacement") = Json::Array{0, 65537}; },
        [](auto& v) { member(v, "replacement") = Json::Array{0, 1.5}; }, [](auto& v) { member(v, "replacement") = Json::Array{"0", 1}; },
        [](auto& v) { member(v, "replacement") = Json::Array{1}; }, [](auto& v) { member(v, "replacement") = false; },
        [](auto& v) { member(v, "text") = ""; member(v, "replacement") = Json::Array{3, 3}; },
        [](auto& v) { object(v).emplace("sourceKeySequence", "1"); }, [](auto& v) { object(v).erase("replacement"); }}) {
        auto value = text_input(); change(value);
        rejected([&] { codec::parse_event(event(value), profile); }, "Malformed text input accepted");
    }
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& v) { member(v, "operation") = "replace"; }, [](auto& v) { member(v, "operation") = 1; },
        [](auto& v) { member(v, "selection") = Json::Array{1, 6}; }, [](auto& v) { member(v, "selection") = Json::Array{2, 7}; },
        [](auto& v) { member(v, "selection") = Json::Array{2, 2, 6}; },
        [](auto& v) { member(v, "operation") = "update"; member(v, "replacement") = Json::Array{0, 0}; },
        [](auto& v) { member(v, "operation") = "cancel"; }, [](auto& v) { object(v).erase("selection"); },
        [](auto& v) { object(v).emplace("backward", true); }}) {
        auto value = composition_input(); change(value);
        rejected([&] { codec::parse_event(event(value), profile); }, "Malformed composition input accepted");
    }
    for (const auto& change : std::vector<std::function<void(Json&)>>{
        [](auto& v) { member(v, "backward") = 1; }, [](auto& v) { member(v, "editorRevision") = "0"; },
        [](auto& v) { member(v, "selection") = Json::Array{-1, 1}; }, [](auto& v) { member(v, "selection") = Json::Array{7, 1}; },
        [](auto& v) { object(v).erase("backward"); }, [](auto& v) { object(v).emplace("replacement", nullptr); }}) {
        auto value = selection_input(); change(value);
        rejected([&] { codec::parse_event(event(value), profile); }, "Malformed selection input accepted");
    }
    for (const char* kind : {"clipboard", "popup", "service"}) {
        auto value = text_input(); member(value, "kind") = kind;
        rejected([&] { codec::parse_event(event(value), profile); }, "Editor acquired undelegated input authority");
    }
    const auto capabilities = codec::parse_connect(editor_connection(), profile);
    surface::Policy policy(capabilities, 3); const auto source = editor_presentation();
    auto prepared = policy.prepare(source);
    check(prepared.status == surface::Status::ok && policy.commit(std::move(prepared.prepared), source.identity.presentation_revision).status == surface::Status::ok,
        "Editor Policy fixture did not publish");
    std::uint64_t sequence = 0;
    const auto accept = [&](Json input) {
        auto packet = event(std::move(input)); member(packet, "sequence") = std::to_string(++sequence);
        return policy.accept(codec::parse_event(packet, profile)).status;
    };
    check(accept(focus()) == surface::Status::ok, "Editor focus failed");
    auto stale = text_input(); member(stale, "editorRevision") = "9007199254740992";
    check(accept(stale) == surface::Status::stale_revision, "Codec bypassed stale editor revision");
    auto interior = text_input(); member(interior, "replacement") = Json::Array{2, 3};
    check(accept(interior) == surface::Status::invalid_value, "Codec bypassed native surrounding scalar boundary");
    auto selected_input = selection_input(); member(selected_input, "selection") = Json::Array{4, 7};
    check(accept(selected_input) == surface::Status::invalid_value, "Codec bypassed selection scalar boundary");
    check(accept(composition_input()) == surface::Status::ok && policy.composition() == 9007199254740995ull,
        "Decoded composition did not begin");
    check(accept(text_input()) == surface::Status::invalid_transaction, "Text input bypassed active composition");
    auto ended = composition_input("cancel"); member(ended, "text") = ""; member(ended, "selection") = Json::Array{0, 0};
    check(accept(ended) == surface::Status::ok && !policy.composition(), "Decoded composition did not cancel");
    check(accept(text_input()) == surface::Status::ok, "Decoded text was not accepted after composition");

    surface::Policy attested_policy(capabilities, 3);
    auto initial = attested_policy.prepare(source);
    check(attested_policy.commit(std::move(initial.prepared), source.identity.presentation_revision).status == surface::Status::ok,
        "Attestation fixture did not publish");
    check(attested_policy.accept({source.identity, 1, surface::FocusChange{true, true, surface::FocusCause::direct}}).status == surface::Status::ok &&
        attested_policy.accept({source.identity, 2, surface::CompositionEdit{surface::CompositionOperation::begin, 9,
            source.editor->revision, "", {}, std::nullopt}}).status == surface::Status::ok, "Attestation fixture did not compose");
    auto attested = source; ++attested.identity.presentation_revision; ++attested.editor->revision;
    attested.editor->composition_transaction = 9;
    auto update = attested_policy.prepare(attested);
    check(update.status == surface::Status::ok && attested_policy.commit(std::move(update.prepared), attested.identity.presentation_revision).status == surface::Status::ok,
        "Native attestation did not publish");
    check(attested_policy.accept({attested.identity, 3, surface::CompositionEdit{surface::CompositionOperation::cancel, 9,
        attested.editor->revision, "", {}, std::nullopt}}).status == surface::Status::ok, "Attested composition did not retire");
    // Policy retains its last native declaration until readback. The serializer
    // deliberately refuses this stale attestation rather than inventing readback.
    rejected([&] { codec::json_state(capabilities, attested_policy.accepted(), true, true,
        attested_policy.composition(), attested_policy.last_sequence(), false, profile); }, "Retired native attestation was silently normalized");
}
Json editor_fixtures() {
    constexpr auto profile = codec::Profile::editor_v1;
    const auto capabilities = codec::parse_connect(editor_connection(), profile);
    auto source = editor_presentation();
    const Json snapshot = Json::Object{{"revision", std::to_string(source.identity.presentation_revision)}, {"scale", source.display_scale}, {"closed", false},
        {"widgets", Json::Array{Json::Object{{"key", Json::Object{{"id", source.identity.owner.id}, {"generation", std::to_string(source.identity.owner.generation)}}},
            {"bounds", Json::Array{10, 20, 200, 100}}, {"clip", Json::Array{20, 30, 100, 50}},
            {"visible", true}, {"enabled", true}, {"inModal", true}}}}};
    Json::Array cases;
    const auto append = [&](std::optional<std::uint64_t> live, Json::Array inputs) {
        std::uint64_t sequence = 2;
        for (auto& input : inputs) {
            auto operation = event(std::move(input)); member(operation, "sequence") = std::to_string(++sequence);
            (void)codec::parse_event(operation, profile);
            cases.emplace_back(Json::Object{{"snapshot", snapshot},
                {"surface", codec::json_state(capabilities, &source, true, true, live, 2, false, profile)}, {"operation", std::move(operation)}});
        }
    };
    append(std::nullopt, {key(), focus(), mouse(), text_input(), selection_input(), composition_input()});
    const auto live = std::optional<std::uint64_t>{9007199254740995ull};
    auto cancelled = composition_input("cancel"); member(cancelled, "text") = ""; member(cancelled, "selection") = Json::Array{0, 0};
    append(live, {composition_input("update"), composition_input("commit"), cancelled});
    source.editor->composition_transaction = *live;
    append(live, {composition_input("update"), composition_input("commit"), cancelled});
    return cases;
}
} // namespace

int main(int argc, char** argv) {
    try {
        capabilities_and_output(); valid_inputs_and_policy(); malformed_inputs(); successor_profile();
        editor_negotiation_and_output(); editor_inputs_and_policy();
        if (argc == 2 && std::string_view(argv[1]) == "--emit-editor-fixtures") {
            std::cout << gui::web_detail::encode(editor_fixtures()) << '\n'; return 0;
        }
        if (argc != 1) throw std::invalid_argument("Unknown browser surface codec test argument");
        std::cout << "Browser surface codec capability, scalar, identity, exact-shape, authority and Policy checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
