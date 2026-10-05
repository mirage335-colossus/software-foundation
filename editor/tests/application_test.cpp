#include "editor/ui/application.hpp"
#include "editor/ui/canvas.hpp"
#include "editor/model/project.hpp"
#include "editor/self/generated/visual/forms.hpp"
#include "editor/self/generated/visual/events.hpp"
#include "gui/host/framebuffer.hpp"
#include <gui/framebuffer.hpp>
#include <gui/memory_adapter.hpp>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>

using namespace foundation::editor;
static_assert(foundation::host::Application<Application>);
static_assert(foundation::host::BezelApplication<Application>);

namespace {
void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}
std::string read(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("Cannot read fixture " + path.string());
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
void write(const std::filesystem::path& path, std::string_view bytes) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream stream(path, std::ios::binary);
    stream.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!stream) throw std::runtime_error("Cannot write fixture " + path.string());
}
struct Temporary {
    std::filesystem::path root = std::filesystem::temp_directory_path() /
        ("foundation editor application fixture " +
         std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    Temporary() { require(std::filesystem::create_directory(root), "Fixture directory collision"); }
    ~Temporary() {
        configure_launch();
        std::error_code error;
        std::filesystem::remove_all(root, error);
    }
};
struct WorkingDirectory {
    std::filesystem::path previous = std::filesystem::current_path();
    explicit WorkingDirectory(const std::filesystem::path& path) { std::filesystem::current_path(path); }
    ~WorkingDirectory() {
        std::error_code error;
        std::filesystem::current_path(previous, error);
    }
};
const gui::Widget* find(const gui::Snapshot& snapshot, std::string_view id) {
    const auto item = std::find_if(snapshot.widgets.begin(), snapshot.widgets.end(),
        [&](const auto& widget) { return widget.spec.key.id == id; });
    return item == snapshot.widgets.end() ? nullptr : &*item;
}
const gui::Widget& widget(const gui::Snapshot& snapshot, std::string_view id) {
    const auto* value = find(snapshot, id);
    if (!value) throw std::runtime_error("Missing editor control " + std::string(id));
    return *value;
}
std::map<std::string, std::string> inventory(const std::filesystem::path& root) {
    std::map<std::string, std::string> result;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(root))
        if (entry.is_regular_file()) result.emplace(entry.path().lexically_relative(root).generic_string(), read(entry.path()));
    return result;
}
void capture(const gui::Snapshot& snapshot, const std::filesystem::path& directory, std::string_view name) {
    if (directory.empty()) return;
    std::filesystem::create_directories(directory);
    gui::FramebufferAdapter adapter;
    adapter.present(snapshot);
    const auto image = adapter.frame();
    require(image.pixels && image.width && image.height, "Editor capture contains no frame");
    const auto path = directory / (std::string(name) + ".ppm");
    std::ofstream stream(path, std::ios::binary);
    stream << "P6\n" << image.width << ' ' << image.height << "\n255\n";
    for (unsigned y = 0; y < image.height; ++y)
        stream.write(reinterpret_cast<const char*>(image.pixels->data() + y * image.stride_bytes),
                     static_cast<std::streamsize>(image.width * 3));
    require(bool(stream), "Editor capture could not be saved");
}
struct Session {
    gui::FramebufferAdapter metrics;
    gui::MemoryAdapter adapter{[this](const gui::Event& event) { application->handle(event); },
                              64 * 1024 * 1024,
                              [this](const gui::TextMeasureRequest& request) { return metrics.measure_text(request); }};
    std::unique_ptr<Application> application;
    explicit Session(const std::filesystem::path& project = {}, const std::filesystem::path& root = {},
                     const std::filesystem::path& executable = {}) {
        configure_launch(project, root, executable);
        application = std::make_unique<Application>(adapter);
        healthy("initial presentation");
    }
    const gui::Snapshot& view() const { return application->view(); }
    void healthy(std::string_view step) const {
        require(!application->presentation_pending(), std::string(step) + ": presentation pending");
        require(adapter.snapshot().revision == view().revision, std::string(step) + ": adapter has an obsolete snapshot");
        const auto& status = widget(view(), "editor.status");
        require(status.state.font.tone != gui::Tone::error,
                std::string(step) + ": " + status.state.text + "\n" + widget(view(), "editor.diagnostics").state.text);
    }
    void send(std::string_view id, gui::Input input, bool expect_success = true) {
        const auto target = widget(view(), id).spec.key;
        require(adapter.send(gui::WidgetEvent{target, std::move(input)}) == gui::Delivery::delivered,
                "Adapter rejected " + std::string(id));
        if (expect_success) healthy(id);
    }
    void activate(std::string_view id, bool expect_success = true) { send(id, gui::Activate{}, expect_success); }
    void choose(std::string_view id, std::string value) { send(id, gui::ChooseOption{std::move(value)}); }
    void edit(std::string_view id, std::string value) {
        send(id, gui::EditText{std::move(value), widget(view(), id).state.text});
    }
    void select(std::string value) { send("editor.objects", gui::SelectRecord{std::move(value)}); }
    void pointer(gui::Point position, gui::PointerKind kind = gui::PointerKind::click) {
        gui::PointerInput input; input.kind = kind; input.position = position;
        send("canvas.surface", input);
    }
    std::size_t objects() const { return widget(view(), "editor.objects").state.records.size(); }
};
Project initial_project() {
    auto project = empty_project("Application integration fixture");
    Form form; form.id = "main"; form.label = "Main panel";
    Control start; start.id = "start"; start.label = "Start"; start.layout = {24, 24, 120, 32}; start.binding = "on_start";
    form.controls.push_back(start);
    project.forms.push_back(form);
    project.flows.push_back({"main_flow", "Processing chain"});
    project.bindings.push_back({"on_start", "activate", "src/handlers.hpp", "fixture::on_start", "on_start", "src/handlers.hpp"});
    return project;
}
Project saved_project(const std::filesystem::path& root) {
    auto parsed = parse_project(read(root / "design/project.json"));
    require(bool(parsed), "Saved design could not be parsed");
    return std::move(*parsed.project);
}
void self_toolbar(Session& session) {
    const auto toolbar = self_generated::snapshot("editor.chrome", 1);
    for (const auto& expected : toolbar.widgets) {
        const auto& actual = widget(session.view(), expected.spec.key.id);
        require(actual.spec.kind == expected.spec.kind && actual.state.bounds == expected.state.bounds &&
                actual.state.label == expected.state.label, "Actual toolbar differs from retained self-generated forms");
    }
    struct Actions {
        std::string last;
        void invoke(std::string_view action) { last = action; }
    } actions;
    unsigned handlers = 0;
    for (const auto& binding : self_generated::event_bindings()) {
        gui::WidgetEvent event{{binding.widget_id, 1}, gui::Activate{}};
        require(self_generated::dispatch_handler(actions, actions, event), "Self-generated toolbar omitted a dispatch");
        require(actions.last == binding.widget_id, "Ordinary self-host handler invoked the wrong editor action");
        ++handlers;
    }
    require(handlers >= 10, "Self-host toolbar has no ordinary action bindings");
}
void source_and_forms(Session& session, const std::filesystem::path& root, const std::filesystem::path& captures) {
    require(session.objects() == 1, "Project launch did not load its form");
    self_toolbar(session);
    capture(session.view(), captures, "editor-initial");
    const auto unchanged = inventory(root);
    session.activate("editor.add");
    require(session.objects() == 2, "Add-widget command did not alter the form");
    session.activate("editor.undo");
    require(session.objects() == 1, "Generated Undo action did not restore the form");
    session.activate("editor.redo");
    require(session.objects() == 2, "Generated Redo action did not restore the added widget");
    session.select("start");
    require(widget(session.view(), "editor.objects").state.selected == "start", "Element list failed to select a widget");
    session.pointer({234, 154}, gui::PointerKind::double_click);
    require(session.view().modal_root.has_value(), "Double-click did not open a source window");
    const auto original = read(root / "src/handlers.hpp");
    require(widget(session.view(), "code.text").state.text == original, "Code window did not open the ordinary bound file");
    require(inventory(root) == unchanged, "Opening an existing source file changed project files");
    capture(session.view(), captures, "editor-code");
    const auto amended = original + "\n// Edited through the ordinary GUI source buffer: caf\xc3\xa9.\n";
    session.edit("code.text", amended);
    session.activate("code.undo");
    require(widget(session.view(), "code.text").state.text == original, "Source Undo did not restore source bytes");
    session.activate("code.redo");
    require(widget(session.view(), "code.text").state.text == amended, "Source Redo did not restore source bytes");
    session.activate("code.save");
    require(read(root / "src/handlers.hpp") == amended, "Source Save did not publish the ordinary file");
    const auto local = amended + "// Local unsaved change\n";
    session.edit("code.text", local);
    const std::string external = "// An independent editor changed this ordinary source file.\n";
    write(root / "src/handlers.hpp", external);
    session.activate("code.save", false);
    require(widget(session.view(), "editor.status").state.font.tone == gui::Tone::error, "Conflicting source save reported success");
    require(read(root / "src/handlers.hpp") == external, "Conflicting source save overwrote the external edit");
    require(widget(session.view(), "code.text").state.text == local, "Conflicting source save lost local code");
    session.activate("code.discard");
    session.select("start");
    session.activate("editor.preview");
    const auto& preview = widget(session.view(), "canvas.preview.start");
    require(!preview.state.enabled && !widget(session.view(), "canvas.surface").spec.pointer_input,
            "Preview left project controls or design gestures live");
    const auto before_preview = inventory(root);
    require(session.adapter.send(gui::WidgetEvent{preview.spec.key, gui::Activate{}}) == gui::Delivery::ignored,
            "Inert preview dispatched application code");
    capture(session.view(), captures, "editor-preview");
    session.activate("editor.preview");
    require(inventory(root) == before_preview, "Preview changed project source files");
    session.activate("editor.save");
    const auto design = saved_project(root);
    require(design.forms.at(0).controls.size() == 2, "Design Save did not retain form edits");
    require(read(root / "src/handlers.hpp") == external, "Design Save rewrote ordinary handler source");
    require(std::filesystem::is_regular_file(root / "generated/visual/forms.hpp"), "Design Save did not retain generated layouts");
    // Existing Rust files are editable text and need no Rust compiler or SDK.
    session.choose("editor.mode", "files");
    session.send("editor.objects", gui::ActivateRecord{"src/bridge.rs"});
    const auto rust = read(root / "src/bridge.rs");
    require(widget(session.view(), "code.text").state.text == rust, "Files workspace did not open ordinary Rust source");
    session.edit("code.text", rust + "// Rust remains project-owned source.\n");
    session.activate("code.save");
    require(read(root / "src/bridge.rs") == rust + "// Rust remains project-owned source.\n", "Rust text save changed the source bytes");
    session.activate("code.close");
}
gui::Point port_position(const Project& project, const Session& session, std::string_view block,
                         std::string_view port, PortDirection direction) {
    Canvas canvas; CanvasOptions options;
    options.mode = CanvasMode::flows; options.document = "main_flow";
    options.viewport = widget(session.view(), "canvas.viewport").state.bounds;
    options.measure_text = [&](const gui::TextMeasureRequest& request) { return session.adapter.measure_text(request); };
    (void)canvas.render(project, options);
    const auto position = canvas.port_position(block, port, direction);
    require(position.has_value(), "Canvas omitted an arbitrary named port");
    return *position;
}
void flows(Session& session, const std::filesystem::path& root, const std::filesystem::path& captures) {
    session.choose("editor.mode", "flows");
    session.activate("editor.add");
    require(session.objects() == 1, "Add-block command did not create a block");
    session.edit("property.label", "Source");
    session.edit("property.position", "24, 32");
    session.activate("editor.apply");
    session.activate("editor.details");
    session.edit("detail.inputs", "sample : float\nmode : int\nextra : double\n");
    session.edit("detail.outputs", "out : float\nphase : int\n");
    session.edit("detail.params", "gain = 2\nnote = arbitrary project object\n");
    session.activate("detail.apply");
    // A draft without a factory is saveable; code generation waits for the
    // ordinary source factory created by the explicit double-click gesture.
    session.activate("editor.save", false);
    require(widget(session.view(), "editor.status").state.font.tone == gui::Tone::error,
            "Incomplete block factory did not leave an actionable draft diagnostic");
    require(saved_project(root).blocks.size() == 1, "Incomplete flow draft could not be saved");
    session.pointer({232, 162}, gui::PointerKind::double_click);
    require(session.view().modal_root.has_value(), "Source block double-click did not open ordinary factory code");
    session.activate("code.close");
    session.activate("editor.add");
    session.edit("property.label", "Sink");
    session.edit("property.position", "390, 100");
    session.activate("editor.apply");
    session.activate("editor.details");
    session.edit("detail.inputs", "in : float\nstate : int\n");
    session.edit("detail.outputs", "result : double\n");
    session.activate("detail.apply");
    session.pointer({598, 230}, gui::PointerKind::double_click);
    require(session.view().modal_root.has_value(), "Sink block double-click did not open ordinary factory code");
    session.activate("code.close");
    session.activate("editor.save", false);
    require(widget(session.view(), "editor.status").state.font.tone == gui::Tone::error,
            "Unconnected required MIMO ports lost their draft diagnostic");
    auto design = saved_project(root);
    require(design.blocks.size() == 2, "Saved flow did not retain arbitrary blocks");
    const auto& source = design.blocks.at(0);
    const auto& sink = design.blocks.at(1);
    require(source.inputs.size() == 3 && source.outputs.size() == 2 &&
            sink.inputs.size() == 2 && sink.outputs.size() == 1,
            "Block Details constrained the arbitrary MIMO port lists");
    require(source.params.at("gain") == "2", "Block Details lost a project-owned parameter");
    const auto source_id = source.id, sink_id = sink.id;
    session.pointer(port_position(design, session, source_id, "out", PortDirection::output));
    session.pointer(port_position(design, session, sink_id, "in", PortDirection::input));
    require(session.objects() == 3, "Pointer port gesture did not create an edge");
    session.activate("editor.save", false);
    require(widget(session.view(), "editor.status").state.font.tone == gui::Tone::error,
            "Partly connected MIMO draft incorrectly reported runnable generation");
    design = saved_project(root);
    require(design.edges.size() == 1 && design.edges.front().from_block == source_id &&
            design.edges.front().from_port == "out" && design.edges.front().to_block == sink_id &&
            design.edges.front().to_port == "in", "Saved connection differs from the visually selected ports");
    capture(session.view(), captures, "editor-flows");
    // Selecting an element retains the useful unresolved draft diagnostic.
    session.send("editor.objects", gui::SelectRecord{source_id}, false);
    session.pointer({232, 162}, gui::PointerKind::double_click);
    require(session.view().modal_root.has_value(), "Double-click did not open the block source file");
    const auto source_path = root / design.blocks.front().file;
    require(std::filesystem::is_regular_file(source_path), "Double-click did not create ordinary block code");
    require(widget(session.view(), "code.text").state.text == read(source_path), "Block code window is not the ordinary source buffer");
    require(read(source_path).find(design.blocks.front().factory) != std::string::npos,
            "Block source has no editable factory declaration");
    session.activate("code.close");
}
void editing_regressions(const std::filesystem::path& root) {
    auto project = empty_project("Editing regressions");
    Form form; form.id = "main"; form.label = "Input";
    Control input; input.id = "input"; input.kind = "text"; input.label = "Input";
    input.multiline = true; input.layout = {24, 24, 280, 64};
    input.event_bindings = {{"text_changed", "text"}, {"submit", "submit"}};
    Control choice; choice.id = "choice"; choice.kind = "choice"; choice.layout = {24, 120, 280, 32};
    choice.options = {{"disabled", "Unavailable", "a", false}, {"enabled", "Available", "b", true}};
    Control punctuated; punctuated.id = "a-b"; punctuated.label = "Hyphen"; punctuated.layout = {24, 180, 120, 32};
    Control underscored; underscored.id = "a_b"; underscored.label = "Underscore"; underscored.layout = {170, 180, 120, 32};
    Control alias_map; alias_map.id = "alias_map"; alias_map.kind = "text"; alias_map.label = "Mapped alias";
    alias_map.layout = {24, 300, 280, 32}; alias_map.event_bindings = {{"edit", "alias.map.binding"}};
    Control alias_legacy; alias_legacy.id = "alias_legacy"; alias_legacy.kind = "text"; alias_legacy.label = "Legacy alias";
    alias_legacy.layout = {24, 360, 280, 32}; alias_legacy.binding = "alias.legacy.binding";
    Control legacy; legacy.id = "legacy"; legacy.label = "Legacy event"; legacy.layout = {24, 240, 160, 32}; legacy.binding = "legacy.binding";
    form.controls = {input, choice, punctuated, underscored, alias_map, alias_legacy, legacy}; project.forms.push_back(form);
    project.bindings = {{"text", "text_changed", "src/text.hpp", "fixture::on_text", "on_text", "src/text.hpp"},
                        {"submit", "submit", "src/submit.hpp", "fixture::on_submit", "on_submit", "src/submit.hpp"},
                        {"legacy.binding", "activate", "src/legacy.hpp", "fixture::on_legacy", "on_legacy", "src/legacy.hpp"},
                        {"alias.map.binding", "text_changed", "src/alias_map.hpp", "fixture::on_map", "on_map", "src/alias_map.hpp"},
                        {"alias.legacy.binding", "change", "src/alias_legacy.hpp", "fixture::on_alias", "on_alias", "src/alias_legacy.hpp"}};
    project.flows.push_back({"main_flow", "Optional ports"});
    Block block; block.id = "optional"; block.flow = "main_flow"; block.label = "Optional ports";
    block.factory = "fixture::make_optional"; block.header = "src/block.hpp"; block.file = block.header;
    block.inputs = {{"in", "float", false}}; block.outputs = {{"out", "int", false}};
    project.blocks.push_back(block);
    write(root / "design/project.json", write_project(project));
    write(root / "src/text.hpp", "#pragma once\n// Ordinary on_text source.\n");
    write(root / "src/submit.hpp", "#pragma once\n// Ordinary on_submit source.\n");
    write(root / "src/legacy.hpp", "#pragma once\n// Ordinary on_legacy default activation source.\n");
    write(root / "src/alias_map.hpp", "#pragma once\n// Original on_map handler bound through the edit alias.\n");
    write(root / "src/alias_legacy.hpp", "#pragma once\n// Original on_alias handler using legacy change event.\n");
    write(root / "src/block.hpp", "#pragma once\n// Ordinary make_optional factory.\n");
    Session session(root / "design/project.json", root);
    session.select("input");
    session.choose("editor.event", "submit");
    session.pointer({234, 154}, gui::PointerKind::double_click);
    require(widget(session.view(), "code.text").state.text == read(root / "src/submit.hpp"),
            "Double-click reset the explicitly chosen nondefault widget event");
    const auto original = read(root / "src/submit.hpp");
    const auto local = original + "// Unsaved source survives a cancelled host close.\n";
    session.edit("code.text", local);
    bool reopen_rejected = false;
    try { session.application->invoke("editor.code"); }
    catch (const std::exception&) { reopen_rejected = true; }
    require(reopen_rejected && widget(session.view(), "code.text").state.text == local,
            "Reopening replaced an unsaved ordinary source buffer");
    require(session.adapter.send(gui::CloseEvent{}) == gui::Delivery::delivered, "Host close was not delivered");
    require(find(session.view(), "unsaved.cancel"), "Dirty source host close omitted the unsaved prompt");
    session.activate("unsaved.cancel");
    require(session.view().modal_root && find(session.view(), "code.text") &&
            widget(session.view(), "code.text").state.text == local,
            "Cancelling host close lost the open dirty source window");
    require(read(root / "src/submit.hpp") == original, "Cancelled host close published unsaved source");
    session.activate("code.discard");
    session.select("alias_map");
    session.pointer({234, 430}, gui::PointerKind::double_click);
    require(widget(session.view(), "code.text").state.text == read(root / "src/alias_map.hpp"),
            "Canonical text event double-click did not reuse an edit-alias event map binding");
    session.activate("code.close");
    session.select("alias_legacy");
    session.pointer({234, 490}, gui::PointerKind::double_click);
    require(widget(session.view(), "code.text").state.text == read(root / "src/alias_legacy.hpp"),
            "Canonical text event double-click did not reuse a legacy change-event binding");
    session.activate("code.close"); session.activate("editor.save");
    require(saved_project(root).bindings.size() == project.bindings.size(),
            "Navigating accepted event aliases created replacement handler bindings");
    session.select("choice");
    session.activate("editor.details");
    session.activate("detail.apply");
    session.choose("editor.mode", "flows");
    session.select("optional");
    session.activate("editor.details");
    session.activate("detail.apply");
    session.activate("editor.save");
    const auto saved = saved_project(root);
    const auto& options = saved.forms.front().controls.at(1).options;
    require(options.size() == 2 && !options.front().enabled && options.back().enabled,
            "Unchanged Details Apply re-enabled a disabled dropdown option");
    require(saved.blocks.front().inputs.size() == 1 && !saved.blocks.front().inputs.front().required &&
            saved.blocks.front().outputs.size() == 1 && !saved.blocks.front().outputs.front().required,
            "Unchanged Details Apply converted project-owned optional ports to required ports");
    session.choose("editor.mode", "forms");
    session.select("a-b"); session.activate("editor.code"); session.activate("code.close");
    session.select("a_b"); session.activate("editor.code"); session.activate("code.close");
    session.activate("editor.save");
    const auto collision = saved_project(root);
    const auto binding_for = [&](std::string_view control_id) -> const Binding& {
        for (const auto& control : collision.forms.front().controls) if (control.id == control_id)
            for (const auto& binding : collision.bindings) if (control.event_bindings.at("activate") == binding.id) return binding;
        throw std::runtime_error("Created ordinary handler has no retained binding");
    };
    const auto& left = binding_for("a-b"); const auto& right = binding_for("a_b");
    require(left.file != right.file && left.symbol != right.symbol &&
            std::filesystem::is_regular_file(root / left.file) && std::filesystem::is_regular_file(root / right.file),
            "Punctuated widget identities collided in ordinary handler filenames or C++ symbols");
    session.select("legacy");
    session.activate("editor.details");
    require(widget(session.view(), "detail.file").state.text == "src/legacy.hpp",
            "Details did not resolve the same-event legacy handler");
    session.activate("detail.apply"); session.activate("editor.save");
    const auto same_event = saved_project(root);
    require(same_event.bindings.size() == collision.bindings.size(), "Same-event Details Apply duplicated a legacy binding");
    const auto legacy_bytes = read(root / "src/legacy.hpp");
    session.choose("editor.event", "pointer");
    session.pointer({234, 370}, gui::PointerKind::double_click);
    require(widget(session.view(), "code.text").state.text != legacy_bytes,
            "Unbound event double-click reopened the unrelated legacy default handler");
    session.activate("code.close"); session.activate("editor.save");
    const auto other_event = saved_project(root);
    const auto& legacy_control = other_event.forms.front().controls.back();
    require(legacy_control.binding == "legacy.binding" && legacy_control.event_bindings.contains("pointer"),
            "New event handler replaced the legacy default event binding");
    const auto new_binding = std::find_if(other_event.bindings.begin(), other_event.bindings.end(), [&](const auto& binding) {
        return binding.id == legacy_control.event_bindings.at("pointer");
    });
    require(new_binding != other_event.bindings.end() && new_binding->event == "pointer" &&
            new_binding->file != "src/legacy.hpp" && read(root / "src/legacy.hpp") == legacy_bytes,
            "New event source is not independent of the retained legacy handler");
}
void path_prompt_regressions(const std::filesystem::path& root, const std::filesystem::path& captures) {
    write(root / "design/project.json", write_project(initial_project()));
    write(root / "src/handlers.hpp", "#pragma once\n// Existing ordinary source.\n");
    const auto before = inventory(root);
    Session session(root / "design/project.json", root);
    session.activate("editor.open");
    require(session.view().modal_root && session.view().modal_root->id == "modal.root" &&
            find(session.view(), "prompt.value") && find(session.view(), "prompt.accept") &&
            find(session.view(), "prompt.cancel"), "Open did not use the editor's same-window prompt");
    require(!session.application->next_service(), "Open queued a native prompt that can block the host window manager");
    capture(session.view(), captures, "editor-open-prompt");
    const auto add_key = widget(session.view(), "editor.add").spec.key;
    require(session.adapter.send(gui::WidgetEvent{add_key, gui::Activate{}}) == gui::Delivery::ignored,
            "Same-window prompt left background project editing active");
    session.activate("prompt.cancel");
    require(!session.view().modal_root && session.objects() == 1 && inventory(root) == before,
            "Cancelling Open changed the current project or source files");
    session.activate("editor.open");
    const auto invalid = (root / "does-not-exist/project.json").string();
    session.edit("prompt.value", invalid);
    session.activate("prompt.accept", false);
    require(find(session.view(), "prompt.value") && widget(session.view(), "prompt.value").state.text == invalid &&
            session.view().modal_root && inventory(root) == before,
            "Invalid Open path closed the prompt, lost its input or changed project files");
    session.activate("prompt.cancel");
    session.activate("editor.new");
    require(find(session.view(), "prompt.value") && !session.application->next_service(),
            "New project did not use the same-window path prompt");
    session.edit("prompt.value", (root / "cancelled-new").string());
    session.activate("prompt.cancel");
    require(session.objects() == 1 && inventory(root) == before && !std::filesystem::exists(root / "cancelled-new"),
            "Cancelling New replaced the open project or created a directory");
    session.activate("editor.open");
    session.edit("prompt.value", root.string());
    session.activate("prompt.accept");
    require(!session.view().modal_root && session.objects() == 1 && inventory(root) == before,
            "Open did not accept a project directory without modifying ordinary files");
    {
        Session unsaved;
        unsaved.activate("editor.save");
        require(find(unsaved.view(), "prompt.value") && !unsaved.application->next_service(),
                "Save-as queued a native path prompt");
        const auto destination = root / "saved-new";
        unsaved.edit("prompt.value", destination.string());
        unsaved.activate("prompt.accept");
        require(!unsaved.view().modal_root && std::filesystem::is_regular_file(destination / "design/project.json"),
                "Same-window Save-as did not persist the new project");
    }
    {
        Session unsaved;
        unsaved.activate("editor.document.new"); unsaved.edit("prompt.value", "Unsaved memory form"); unsaved.activate("prompt.accept");
        unsaved.activate("editor.open"); unsaved.activate("unsaved.save");
        const auto destination = root / "saved-before-open";
        unsaved.edit("prompt.value", destination.string()); unsaved.activate("prompt.accept");
        require(find(unsaved.view(), "prompt.value") && !unsaved.application->next_service() &&
                std::filesystem::is_regular_file(destination / "design/project.json"),
                "Saving an unsaved design did not resume its pending Open prompt");
        unsaved.edit("prompt.value", root.string()); unsaved.activate("prompt.accept");
        require(!unsaved.view().modal_root && unsaved.objects() == 1 &&
                widget(unsaved.view(), "editor.document").state.selected == "main" &&
                saved_project(destination).forms.front().label == "Unsaved memory form",
                "Resumed Open prompt lost its action or failed to retain the saved memory form");
    }
}
void document_name_regressions(const std::filesystem::path& root, const std::filesystem::path& captures) {
    auto project = initial_project();
    Block source; source.id = "source"; source.label = "Source"; source.flow = "main_flow";
    source.factory = "fixture::source"; source.header = "src/blocks.hpp"; source.file = source.header;
    source.outputs = {{"out", "float", true}};
    Block sink; sink.id = "sink"; sink.label = "Sink"; sink.flow = "main_flow";
    sink.factory = "fixture::sink"; sink.header = "src/blocks.hpp"; sink.file = sink.header;
    sink.inputs = {{"in", "float", true}};
    project.blocks = {source, sink}; project.edges.push_back({"samples", "source", "out", "sink", "in", 16, 0});
    write(root / "design/project.json", write_project(project));
    write(root / "src/handlers.hpp", "#pragma once\n// on_start remains ordinary source.\n");
    write(root / "src/blocks.hpp", "#pragma once\n// source and sink remain ordinary source.\n");
    const auto handler_bytes = read(root / "src/handlers.hpp");
    const auto block_bytes = read(root / "src/blocks.hpp");
    std::string new_form_id, new_flow_id;
    {
        Session session(root / "design/project.json", root);
        session.activate("editor.document.new");
        require(widget(session.view(), "prompt.value").state.text == "New form" && !session.application->next_service(),
                "New form omitted its editable name prompt");
        session.activate("prompt.cancel");
        require(widget(session.view(), "editor.document").state.options.size() == 1,
                "Cancelled form-name prompt created a form");
        session.activate("editor.document.new");
        session.edit("prompt.value", "  "); session.activate("prompt.accept", false);
        require(find(session.view(), "prompt.value") && widget(session.view(), "prompt.value").state.text == "  " &&
                widget(session.view(), "editor.document").state.options.size() == 1,
                "Empty form name closed the prompt, lost input or created a form");
        session.send("prompt.value", gui::EditText{"Device settings", "  "}, false);
        session.send("prompt.value", gui::SubmitText{});
        new_form_id = widget(session.view(), "editor.document").state.selected.value_or("");
        require(!new_form_id.empty() && new_form_id != "main" && session.objects() == 0,
                "Named form creation did not select a new stable identity");
        session.activate("editor.undo");
        require(widget(session.view(), "editor.document").state.options.size() == 1 &&
                widget(session.view(), "editor.document").state.selected == "main",
                "Undo of form creation did not restore a valid selected document");
        session.activate("editor.redo"); session.choose("editor.document", new_form_id);
        session.activate("editor.document.rename");
        require(widget(session.view(), "prompt.value").state.text == "Device settings",
                "Rename form did not prefill the selected form's name");
        capture(session.view(), captures, "editor-name-prompt");
        session.edit("prompt.value", "Device controls"); session.activate("prompt.accept");
        require(widget(session.view(), "editor.document").state.selected == new_form_id,
                "Renaming a form changed its stable identity");
        session.activate("editor.undo"); session.activate("editor.document.rename");
        require(widget(session.view(), "prompt.value").state.text == "Device settings", "Undo did not restore the form name");
        session.activate("prompt.cancel"); session.activate("editor.redo");
        session.activate("editor.document.rename");
        require(widget(session.view(), "prompt.value").state.text == "Device controls", "Redo did not restore the form name");
        session.activate("prompt.cancel");
        session.choose("editor.document", "main"); session.activate("editor.document.rename");
        session.edit("prompt.value", "Primary controls"); session.activate("prompt.accept");
        session.choose("editor.mode", "flows");
        session.activate("editor.document.new");
        require(widget(session.view(), "prompt.value").state.text == "New flow", "New flow omitted its editable name prompt");
        session.edit("prompt.value", "Capture processing"); session.activate("prompt.accept");
        new_flow_id = widget(session.view(), "editor.document").state.selected.value_or("");
        require(!new_flow_id.empty() && new_flow_id != "main_flow", "Named flow creation did not select a stable identity");
        session.activate("editor.undo");
        require(widget(session.view(), "editor.document").state.options.size() == 1 &&
                widget(session.view(), "editor.document").state.selected == "main_flow",
                "Undo of flow creation did not restore a valid selected document");
        session.activate("editor.redo"); session.choose("editor.document", new_flow_id);
        session.activate("editor.document.rename"); session.edit("prompt.value", "Filtered capture"); session.activate("prompt.accept");
        session.activate("editor.undo"); session.activate("editor.document.rename");
        require(widget(session.view(), "prompt.value").state.text == "Capture processing", "Undo did not restore the flow name");
        session.activate("prompt.cancel"); session.activate("editor.redo");
        session.activate("editor.document.rename");
        require(widget(session.view(), "prompt.value").state.text == "Filtered capture" &&
                widget(session.view(), "editor.document").state.selected == new_flow_id,
                "Redo lost the renamed flow or its stable identity");
        session.activate("prompt.cancel");
        session.choose("editor.document", "main_flow"); session.activate("editor.document.rename");
        session.edit("prompt.value", "Main sample processing"); session.activate("prompt.accept");
        require(session.objects() == 3, "Renaming a populated flow lost its blocks or edge");
        session.activate("editor.save");
    }
    const auto saved = saved_project(root);
    require(saved.forms.size() == 2 && saved.forms.at(0).id == "main" && saved.forms.at(0).label == "Primary controls" &&
            saved.forms.at(0).controls.at(0).id == "start" && saved.forms.at(0).controls.at(0).binding == "on_start" &&
            saved.bindings.at(0).file == "src/handlers.hpp" && saved.forms.at(1).id == new_form_id &&
            saved.forms.at(1).label == "Device controls", "Saving renamed forms changed control/binding identities or lost names");
    require(saved.flows.size() == 2 && saved.flows.at(0).id == "main_flow" && saved.flows.at(0).label == "Main sample processing" &&
            saved.flows.at(1).id == new_flow_id && saved.flows.at(1).label == "Filtered capture" &&
            saved.blocks.size() == 2 && saved.blocks.at(0).flow == "main_flow" && saved.blocks.at(1).flow == "main_flow" &&
            saved.edges.size() == 1 && saved.edges.at(0).id == "samples" && saved.edges.at(0).from_block == "source" &&
            saved.edges.at(0).to_block == "sink", "Saving renamed flows changed graph identities or lost names");
    require(read(root / "src/handlers.hpp") == handler_bytes && read(root / "src/blocks.hpp") == block_bytes,
            "Document naming rewrote ordinary source files");
    Session reloaded(root / "design/project.json", root);
    reloaded.choose("editor.document", new_form_id); reloaded.activate("editor.document.rename");
    require(widget(reloaded.view(), "prompt.value").state.text == "Device controls", "Reload lost a named form");
    reloaded.activate("prompt.cancel"); reloaded.choose("editor.mode", "flows");
    reloaded.choose("editor.document", new_flow_id); reloaded.activate("editor.document.rename");
    require(widget(reloaded.view(), "prompt.value").state.text == "Filtered capture", "Reload lost a named flow");
    reloaded.activate("prompt.cancel");
}
void example_regressions(const std::filesystem::path& root, const std::filesystem::path& captures) {
    // Discovery must work when the editor is launched outside the repository,
    // using its executable's ancestors rather than the process working directory.
    const auto original_demo = std::filesystem::path(__FILE__).parent_path().parent_path() / "examples/demo";
    const auto bundle = root / "bundle";
    const auto demo = bundle / "editor/examples/demo";
    std::filesystem::create_directories(demo.parent_path());
    std::filesystem::copy(original_demo, demo, std::filesystem::copy_options::recursive);
    const auto executable = bundle / "build/editor-fixture/foundation-editor-fixture";
    write(executable, "Executable location fixture.\n");
    const auto current = root / "unrelated-project";
    write(current / "design/project.json", write_project(initial_project()));
    write(current / "src/handlers.hpp", "#pragma once\n// Existing on_start current-project handler.\n");
    const auto original = inventory(root);
    WorkingDirectory outside_repository(current);
    Session session(current / "design/project.json", current, executable);
    session.activate("editor.add"); const auto dirty_objects = session.objects();
    session.activate("editor.example");
    require(find(session.view(), "unsaved.cancel"), "Example bypassed the current design's unsaved-changes prompt");
    session.activate("unsaved.cancel");
    require(session.objects() == dirty_objects && inventory(root) == original, "Cancelling Example lost unsaved project work");
    session.activate("editor.undo"); session.select("start"); session.activate("editor.code");
    const auto source = widget(session.view(), "code.text").state.text;
    session.edit("code.text", source + "// Unsaved ordinary code.\n");
    session.application->invoke("editor.example");
    // Ordinary generated handlers invoke actions inside handle(). This direct
    // facade probe needs a harmless host event to publish the changed snapshot.
    require(session.adapter.send(gui::ResizeEvent{session.view().client_size, session.view().display_scale}) == gui::Delivery::delivered,
            "Example facade probe could not present the unsaved prompt");
    session.healthy("Example requested from an open source buffer");
    require(find(session.view(), "unsaved.cancel"), "Example bypassed dirty ordinary source");
    session.activate("unsaved.cancel");
    require(find(session.view(), "code.text") && widget(session.view(), "code.text").state.text == source + "// Unsaved ordinary code.\n",
            "Cancelling Example discarded the ordinary source buffer");
    session.activate("code.discard");
    session.activate("editor.example");
    const auto demo_project = parse_project(read(demo / "project.json"));
    require(bool(demo_project) && !demo_project.project->forms.empty() && !demo_project.project->flows.empty(),
            "Retained example omits a form or flow");
    const auto& form = demo_project.project->forms.front();
    require(widget(session.view(), "editor.mode").state.selected == "forms" &&
            widget(session.view(), "editor.document").state.selected == form.id && session.objects() == form.controls.size(),
            "Example did not open its form through the normal editor workspace");
    capture(session.view(), captures, "editor-example-form");
    const auto bound = std::find_if(form.controls.begin(), form.controls.end(), [](const auto& control) { return !control.binding.empty(); });
    require(bound != form.controls.end(), "Example form has no ordinary event binding");
    const auto binding = std::find_if(demo_project.project->bindings.begin(), demo_project.project->bindings.end(),
        [&](const auto& value) { return value.id == bound->binding; });
    require(binding != demo_project.project->bindings.end(), "Example event has no source reference");
    session.select(bound->id); session.activate("editor.code");
    require(widget(session.view(), "code.text").state.text == read(demo / binding->file), "Example event did not open ordinary source");
    session.activate("code.close"); session.choose("editor.mode", "flows");
    const auto& flow = demo_project.project->flows.front();
    require(widget(session.view(), "editor.document").state.selected == flow.id && session.objects() >= 3,
            "Example did not expose an editable connected flow");
    capture(session.view(), captures, "editor-example-flow");
    const auto block = std::find_if(demo_project.project->blocks.begin(), demo_project.project->blocks.end(),
        [&](const auto& value) { return value.flow == flow.id && !value.file.empty(); });
    require(block != demo_project.project->blocks.end(), "Example flow has no ordinary processing source");
    session.select(block->id); session.activate("editor.code");
    require(widget(session.view(), "code.text").state.text == read(demo / block->file), "Example block did not open ordinary processing source");
    session.activate("code.close");
    require(inventory(root) == original, "Opening the Example or its source wrote files or ran a project recipe");
}
#if defined(__linux__)
template<class Predicate> void await(Session& session, Predicate&& finished) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (std::chrono::steady_clock::now() < deadline) {
        session.application->tick();
        if (finished()) return;
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    throw std::runtime_error("Editor recipe did not reach its expected result within five seconds");
}
void recipe_regressions(const std::filesystem::path& root, const std::filesystem::path& executable) {
    auto project = initial_project();
    project.recipes = {{"build", "Build", {executable.string(), "--recipe-child", "build.cwd"}, "."},
                       {"run", "Run", {executable.string(), "--recipe-child", "run.cwd"}, "nested"}};
    write(root / "design/project.json", write_project(project));
    write(root / "src/handlers.hpp", "#pragma once\n// on_start fixture.\n");
    std::filesystem::create_directory(root / "nested");
    {
        Session session(root / "design/project.json", root);
        session.activate("editor.build");
        await(session, [&] { return !widget(session.view(), "editor.stop").state.enabled; });
        session.healthy("Build recipe completed");
        require(read(root / "build.cwd") == root.generic_string() + "\n", "Build recipe did not use the project-root working directory");
        require(!std::filesystem::exists(root / "nested/run.cwd"), "Build command unexpectedly ran the application recipe");
        std::filesystem::remove(root / "build.cwd");
        session.activate("editor.run");
        await(session, [&] {
            return std::filesystem::exists(root / "nested/run.cwd") && !widget(session.view(), "editor.stop").state.enabled;
        });
        session.healthy("Build-and-run recipes completed");
        require(read(root / "build.cwd") == root.generic_string() + "\n", "Run command omitted its preceding project-root build");
        require(read(root / "nested/run.cwd") == (root / "nested").generic_string() + "\n", "Run recipe did not use its nested working directory");
    }
    project.recipes.front().argv = {"no-such-foundation-editor-fixture-executable"};
    write(root / "design/project.json", write_project(project));
    std::filesystem::remove(root / "nested/run.cwd");
    Session failure(root / "design/project.json", root);
    failure.activate("editor.run", false);
    await(failure, [&] { return widget(failure.view(), "editor.status").state.font.tone == gui::Tone::error; });
    require(!widget(failure.view(), "editor.stop").state.enabled, "Failed executable left the editor's owned process running");
    require(!std::filesystem::exists(root / "nested/run.cwd"), "Failed build still launched the run recipe");
}
#endif
void smoke_without_writes(const std::filesystem::path& root) {
    configure_launch(root / "design/project.json", root);
    const auto before = inventory(root);
    foundation::host::FramebufferHost<Application> host;
    unsigned presentations = 0;
    host.application().qualify([&] {
        host.application().tick();
        const auto frame = host.adapter().frame();
        require(frame.pixels && frame.width && frame.height, "Generic framebuffer host presented no editor pixels");
        ++presentations;
    });
    require(presentations >= 6, "Native editor smoke omitted toolbar interactions");
    require(!host.application().presentation_pending(), "Native smoke has a failed editor presentation");
    require(inventory(root) == before, "Native editor smoke wrote to the opened project");
}
}
int main(int argc, char** argv) {
#if defined(__linux__)
    if (argc == 3 && std::string_view(argv[1]) == "--recipe-child") {
        write(std::filesystem::current_path() / argv[2], std::filesystem::current_path().generic_string() + "\n");
        std::cout << "Fast recipe completed\n";
        return 0;
    }
#endif
    try {
        std::filesystem::path captures;
        if (argc == 3 && std::string_view(argv[1]) == "--capture-dir") captures = std::filesystem::absolute(argv[2]);
        else require(argc == 1, "Usage: foundation-editor-application_test [--capture-dir PATH]");
        Temporary temporary;
        const auto root = temporary.root;
        write(root / "design/project.json", write_project(initial_project()));
        write(root / "src/handlers.hpp", "#pragma once\nnamespace fixture { void on_start(); }\n");
        write(root / "src/bridge.rs", "#[no_mangle]\npub extern \"C\" fn fixture_value() -> i32 { 7 }\n");
        {
            Session session(root / "design/project.json", root);
            source_and_forms(session, root, captures);
            flows(session, root, captures);
        }
        smoke_without_writes(root);
        editing_regressions(root / "editing-regressions");
        path_prompt_regressions(root / "path-prompt-regressions", captures);
        document_name_regressions(root / "document-name-regressions", captures);
        example_regressions(root / "example-regressions", captures);
#if defined(__linux__)
        recipe_regressions(root / "recipe-regressions", std::filesystem::canonical(argv[0]));
#endif
        std::cout << "editor application: shell, same-window prompts, document names, editable example, generated dispatch, forms, ordinary source, conflicts, arbitrary MIMO, preview, native smoke: ok\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
