#include "shared/appended_document_controller.hpp"

#include <gui/retained_adapter.hpp>
#include <gui/terminal.hpp>
#include <algorithm>
#include <cstdint>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

namespace {
using namespace foundation::ui;
static_assert(std::is_same_v<decltype(std::declval<const AppendedDocumentController&>().candidate_projection()),
    const DocumentProjection*>);
static_assert(noexcept(std::declval<const AppendedDocumentController&>().candidate_projection()));
void check(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
DocumentNode element(std::uint64_t id, std::uint64_t parent, std::string tag) {
    DocumentNode node; node.id = id; node.parent = parent; node.tag = std::move(tag); return node;
}
DocumentNode text(std::uint64_t id, std::uint64_t parent, std::string value) {
    DocumentNode node; node.id = id; node.parent = parent; node.kind = DocumentNodeKind::text;
    node.text = std::move(value); return node;
}
DocumentSnapshot document(std::uint64_t revision = 13, std::uint64_t epoch = 11) {
    auto link = element(4,1,"a"); link.name = "Project guide"; link.href = "guide.html";
    auto button = element(6,1,"button"); button.name = "Run calculation";
    auto disabled = element(8,1,"button"); disabled.name = "Unavailable"; disabled.disabled = true;
    DocumentSnapshot result; result.version = {7,epoch,revision};
    result.nodes = {element(1,0,"body"), element(2,1,"p"), text(3,2,"alpha beta gamma delta epsilon"),
        link, text(5,4,"Project guide"), button, text(7,6,"Run calculation"), disabled};
    result.active_node = 4; return result;
}
const gui::Widget& list(const gui::Snapshot& snapshot) {
    const auto found = std::find_if(snapshot.widgets.begin(),snapshot.widgets.end(),
        [](const gui::Widget& widget) { return widget.spec.kind == gui::Kind::list; });
    check(found != snapshot.widgets.end(),"Document controller presented no navigable list"); return *found;
}
std::string presented_text(const gui::Snapshot& snapshot) {
    std::string result = snapshot.title;
    for (const auto& widget : snapshot.widgets) {
        result += widget.state.text + widget.state.label + widget.state.placeholder;
        for (const auto& row : widget.state.records) {
            result += row.accessible_text;
            for (const auto& cell : row.cells) result += cell.text;
        }
    }
    return result;
}
std::string terminal_cells(gui::TerminalAdapter& terminal) {
    std::string result;
    for (const auto& line : terminal.render()) { result += line; result += '\n'; }
    return result;
}
DocumentSemanticReply reply(const DocumentEngineRequest& request, DocumentSnapshot snapshot = document()) {
    DocumentSemanticReply result; result.request_id = request.token.id; result.epoch = snapshot.version.epoch;
    result.snapshot = std::move(snapshot); result.editor_state = DocumentEditorState{1,0}; return result;
}
DocumentEngineRequest next(AppendedDocumentController& controller, bool action, const char* message) {
    auto request = controller.next_request();
    check(request && request->intent.has_value() == action && request->token.generation == 7 && request->token.id,
        message);
    check(!controller.next_request(),"Controller issued more than one outstanding engine request");
    return *request;
}
void ready(AppendedDocumentController& controller, DocumentSnapshot snapshot = document()) {
    controller.tick();
    const auto initial = next(controller,false,"Initial document request was not a snapshot");
    check(controller.complete_request(initial.token,reply(initial,std::move(snapshot))) && controller.synchronized() &&
        controller.presentation_pending(),"Initial semantic snapshot was not accepted for presentation");
    controller.tick(); check(!controller.presentation_pending(),"Initial presentation did not complete");
}
struct TerminalFixture {
    AppendedDocumentController* current = nullptr;
    unsigned callbacks = 0;
    gui::TerminalAdapter terminal;
    AppendedDocumentController controller;
    explicit TerminalFixture(DocumentViewport viewport = {40,10})
        : terminal([this](const gui::Event& event) { ++callbacks; if (current) current->handle(event); }),
          controller(terminal,7,viewport) {
        current = &controller;
        terminal.terminal_size(static_cast<unsigned>(viewport.columns),static_cast<unsigned>(viewport.drawable_rows + 1));
        ready(controller); callbacks = 0;
    }
};
void activate(AppendedDocumentController& controller, std::string id = "node/4") {
    controller.handle(gui::WidgetEvent{list(controller.view()).spec.key,gui::ActivateRecord{std::move(id)}});
}
void exact(const DocumentEngineRequest& request, DocumentAction action, std::uint64_t node,
           DocumentVersion version = {7,11,13}) {
    check(request.intent && request.intent->version == version && request.intent->action == action &&
        request.intent->node == node,"Engine action was rebased or lost its exact displayed DOM identity");
}
void queue_only_real_terminal_and_exact_action() {
    TerminalFixture fixture;
    auto& controller = fixture.controller; auto& terminal = fixture.terminal;
    const auto initial_epoch = controller.input_epoch(), initial_revision = controller.view().revision;
    const auto key = list(controller.view()).spec.key;
    check(terminal.focus(key),"Real terminal could not focus the document list");
    check(terminal_cells(terminal).find("Project guide") != std::string::npos,
        "Controller projection did not reach real terminal cells");
    terminal.input("\r");
    check(fixture.callbacks == 1 && controller.input_epoch() == initial_epoch &&
        controller.view().revision == initial_revision && !controller.presentation_pending(),
        "Terminal callback performed an engine action or presentation instead of queuing input");
    controller.request_snapshot(); // A queued activation must precede this optional refresh.
    controller.tick();
    const auto action = next(controller,true,"Queued activation was preceded by a speculative snapshot");
    exact(action,DocumentAction::activate,4);
    check(controller.input_epoch() != initial_epoch,"Admitting engine input did not revoke its input epoch");
    auto observed = document(14); observed.active_node = 6; observed.selection = DocumentSelection{{3,0},{3,5}};
    auto completion = reply(action,observed);
    completion.metadata.push_back({4,"link","inline","normal",false,false});
    completion.original_selection = DocumentWireSelection{{{3,0},{3,5}},{0,gui::coordinate_limit + 123,8,16}};
    completion.degraded.whitespace = true;
    check(controller.complete_request(action.token,completion),"Matching action completion was ignored");
    completion.metadata.front().role = "mutated caller storage";
    const auto* accepted = controller.observation();
    check(accepted && accepted->request_id == action.token.id && accepted->metadata.size() == 1 && accepted->metadata.front().role == "link" &&
        accepted->original_selection && accepted->original_selection->endpoints == completion.original_selection->endpoints &&
        accepted->original_selection->endpoints.anchor.kind == DocumentNativeOffsetKind::text_utf16 &&
        accepted->original_selection->endpoints.focus.kind == DocumentNativeOffsetKind::text_utf16 &&
        accepted->original_selection->focus_rect.y == gui::coordinate_limit + 123 &&
        accepted->degraded.whitespace,"Controller discarded or borrowed owned semantic observation metadata");
    check(controller.presentation_pending(),"Accepted action result was not pending presentation");
    controller.tick();
    check(controller.synchronized() && list(controller.view()).state.selected == "node/6" &&
        terminal.snapshot().revision == controller.view().revision &&
        terminal_cells(terminal).find("Run calculation") != std::string::npos,
        "Observed semantic focus/action result did not reach the terminal");
    check(!controller.next_request(),"Successful action scheduled an unnecessary action or snapshot");
}
void local_prose_navigation_and_owned_selection() {
    TerminalFixture fixture; auto& controller = fixture.controller;
    const auto key = list(controller.view()).spec.key;
    const auto& rows = list(controller.view()).state.records;
    const auto prose = std::find_if(rows.begin(),rows.end(),[](const gui::Record& row) {
        return row.accessible_text.find("alpha") != std::string::npos;
    });
    check(prose != rows.end() && !prose->activatable,"Prose fixture became an application action");
    const auto id = prose->id;
    const auto epoch = controller.input_epoch();
    const auto revision = controller.view().revision;
    controller.handle(gui::WidgetEvent{key,gui::SelectRecord{id}});
    check(controller.view().revision == revision,"Prose callback presented synchronously");
    controller.tick();
    check(list(controller.view()).state.selected == id && controller.view().revision > revision &&
        controller.input_epoch() == epoch && !controller.next_request(),
        "Prose navigation mutated the engine or lost its disposable local cursor");
    controller.request_snapshot(); const auto periodic = next(controller,false,"Periodic prose snapshot fixture");
    check(controller.complete_request(periodic.token,reply(periodic,document(14))),"Periodic prose snapshot was ignored");
    controller.tick();
    check(list(controller.view()).state.selected == id && !controller.next_request(),
        "Periodic snapshot reset a selected prose row without an observed DOM focus change");
    check(fixture.terminal.focus(key),"Real terminal could not focus prose list"); fixture.terminal.input("\r");
    controller.tick(); check(!controller.next_request(),"Enter on prose became a DOM activation");
    const DocumentSelection selection{{3,1},{3,5}};
    check(controller.queue_selection(selection),"Composition-owned DOM selection was not queued");
    const auto selected = next(controller,true,"Explicit DOM selection did not produce an engine request");
    exact(selected,DocumentAction::select,0,{7,11,14});
    check(selected.intent->selection == selection,"DOM UTF-16 selection direction/endpoints were changed");
    auto observed = document(15); observed.selection = selection;
    check(controller.complete_request(selected.token,reply(selected,observed)),"Selection completion was ignored");
    controller.tick(); check(!controller.next_request(),"Selection completion replayed input");
    check(!controller.queue_selection({{2,0},{3,1}}) && !controller.queue_selection({{999,0},{3,1}}) &&
        !controller.queue_selection({{3,0},{3,999}}),"Invalid DOM selection acquired engine authority");
    controller.handle(gui::WidgetEvent{key,gui::SelectRecord{"node/6"}});
    const auto focused = next(controller,true,"Selecting a control did not queue observed focus input");
    exact(focused,DocumentAction::focus,6,{7,11,15});
}
void stale_view_and_unknown_outcomes_never_replay() {
    {
        TerminalFixture fixture; auto& controller = fixture.controller;
        activate(controller); activate(controller,"node/6");
        const auto action = next(controller,true,"Stale-view action fixture was not admitted");
        DocumentSemanticReply rejected; rejected.request_id = action.token.id; rejected.epoch = 11;
        rejected.error_code = "stale-view";
        check(controller.complete_request(action.token,std::move(rejected)) && !controller.synchronized() &&
            controller.last_error() == "stale-view","Producer stale-view rejection was treated as success");
        const auto refresh = next(controller,false,"Stale-view action was replayed instead of requesting a snapshot");
        check(refresh.token.id > action.token.id,"Stale-view recovery reused an action request identity");
        check(controller.complete_request(refresh.token,reply(refresh,document(14))),"Stale-view recovery snapshot ignored");
        controller.tick(); check(controller.synchronized() && !controller.next_request(),
            "Stale-view refresh rebased or replayed queued old actions");
    }
    for (const auto failure : {DocumentRequestFailure::known_rejected,DocumentRequestFailure::unknown}) {
        TerminalFixture fixture; auto& controller = fixture.controller;
        activate(controller); activate(controller,"node/6");
        const auto action = next(controller,true,"Transport failure action fixture was not admitted");
        auto foreign = action.token; ++foreign.generation;
        check(!controller.fail_request(foreign,failure) && !controller.next_request(),
            "Foreign transport failure consumed an outstanding action");
        check(controller.fail_request(action.token,failure) && !controller.synchronized() && !controller.last_error().empty(),
            "Failed action retained synchronized input authority");
        check(!controller.complete_request(action.token,reply(action,document(14))),"Late outcome repeated a consumed action");
        const auto refresh = next(controller,false,"Failed action automatically repeated its side effect");
        check(refresh.token.id > action.token.id,"Action failure recovery reused a request identity");
        check(controller.fail_request(refresh.token,DocumentRequestFailure::unknown) && !controller.next_request(),
            "Failed snapshot entered an automatic retry loop");
        controller.request_snapshot();
        const auto explicit_retry = next(controller,false,"Explicit snapshot recovery was not issued");
        check(explicit_retry.token.id > refresh.token.id &&
            controller.complete_request(explicit_retry.token,reply(explicit_retry,document(14))),
            "Explicit snapshot retry did not recover independently");
        controller.tick(); check(controller.synchronized() && !controller.next_request(),
            "Recovery snapshot resurrected an old queued action");
    }
}
void completion_identity_and_atomic_validation() {
    gui::TerminalAdapter terminal;
    AppendedDocumentController initial(terminal,7,{40,10});
    const auto request = next(initial,false,"Initial request identity fixture");
    for (auto token : {DocumentRequestToken{8,request.token.id},DocumentRequestToken{7,request.token.id + 1}}) {
        check(!initial.complete_request(token,reply(request)) && !initial.next_request(),
            "Foreign completion consumed or replaced the outstanding snapshot");
    }
    check(initial.complete_request(request.token,reply(request)),"Correct completion was lost after foreign replies");
    check(!initial.complete_request(request.token,reply(request)),"Duplicate completion replaced accepted state");
    initial.tick(); check(initial.synchronized(),"Correct initial completion was not presented");
    initial.request_snapshot(); const auto pending = next(initial,false,"Pending explicit refresh fixture");
    initial.request_snapshot();
    check(initial.fail_request(pending.token,DocumentRequestFailure::unknown),"Pending snapshot failure was ignored");
    const auto later = next(initial,false,"Snapshot failure discarded a newer explicit refresh request");
    check(later.token.id > pending.token.id && initial.fail_request(later.token,DocumentRequestFailure::known_rejected) &&
        !initial.next_request(),"Explicit pending refresh repeated without another owner request");
    for (unsigned variant = 0; variant < 7; ++variant) {
        TerminalFixture fixture; auto& controller = fixture.controller;
        const auto previous = controller.view();
        controller.request_snapshot(); const auto refresh = next(controller,false,"Validation snapshot request fixture");
        auto invalid = reply(refresh);
        if (variant == 0) ++invalid.request_id;
        if (variant == 1) invalid.snapshot->version.generation = 8;
        if (variant == 2) ++invalid.epoch;
        if (variant == 3) --invalid.snapshot->version.revision;
        if (variant == 4) invalid.snapshot->nodes[2].text = "different bytes under the same semantic version";
        if (variant == 5) invalid.editor_state.reset();
        if (variant == 6) invalid.snapshot->nodes[2].id = 1;
        check(controller.complete_request(refresh.token,std::move(invalid)) && !controller.synchronized() &&
            !controller.last_error().empty(),"Malformed matching completion retained synchronized state");
        controller.tick();
        check(controller.view().revision == previous.revision && presented_text(controller.view()) == presented_text(previous) &&
            !controller.next_request(),"Malformed snapshot partially replaced the prior view or retried automatically");
        controller.request_snapshot(); const auto retry = next(controller,false,"Malformed snapshot explicit retry");
        check(controller.complete_request(retry.token,reply(retry,document(14))),"Fresh snapshot did not recover after rejection");
        controller.tick(); check(controller.synchronized(),"Recovered valid snapshot remained unsynchronized");
    }
}
void consumed_actions_without_publication_require_fresh_observation() {
    for (const auto kind : {DocumentAction::focus,DocumentAction::activate,DocumentAction::select}) {
        TerminalFixture fixture; auto& controller = fixture.controller;
        const auto& initial_rows = list(controller.view()).state.records;
        const auto initial_prose = std::find_if(initial_rows.begin(),initial_rows.end(),[](const gui::Record& row) {
            return row.accessible_text.find("alpha") != std::string::npos;
        });
        check(initial_prose != initial_rows.end(),"Consumed action fixture has no prose row");
        const auto prose_id = initial_prose->id;
        controller.handle(gui::WidgetEvent{list(controller.view()).spec.key,gui::SelectRecord{prose_id}});
        controller.tick();
        check(list(controller.view()).state.selected == prose_id && !controller.next_request(),
            "Consumed action fixture did not establish a local prose cursor");
        const auto prior = controller.view();
        const auto observed = *controller.observation();
        const auto key = list(prior).spec.key;
        if (kind == DocumentAction::focus)
            controller.handle(gui::WidgetEvent{key,gui::SelectRecord{"node/6"}});
        else if (kind == DocumentAction::activate) activate(controller);
        else check(controller.queue_selection({{3,1},{3,5}}),"Consumed selection fixture was not queued");
        // Both semantic and local navigation behind the consumed action must
        // be discarded, even if a subsequent query returns the same version.
        activate(controller,"node/6");
        controller.handle(gui::WidgetEvent{key,gui::SelectRecord{prose_id}});
        const auto action = next(controller,true,"Consumed action fixture was not admitted");
        check(action.intent->action == kind,"Consumed action fixture selected a different intent");
        const auto admitted_epoch = controller.input_epoch();
        for (const auto foreign : {DocumentRequestToken{8,action.token.id},
                                  DocumentRequestToken{7,action.token.id + 1}})
            check(!controller.consume_request_without_publication(foreign) &&
                controller.input_epoch() == admitted_epoch && controller.synchronized() &&
                !controller.next_request(),"Foreign consumed completion changed an outstanding action");
        check(controller.consume_request_without_publication(action.token) &&
            !controller.synchronized() && controller.input_epoch() > admitted_epoch &&
            controller.last_error().empty() && !controller.presentation_pending() &&
            controller.view().revision == prior.revision && fixture.terminal.snapshot().revision == prior.revision &&
            presented_text(controller.view()) == presented_text(prior) &&
            controller.observation() && controller.observation()->request_id == observed.request_id &&
            controller.observation()->snapshot == observed.snapshot && controller.candidate_projection() &&
            controller.candidate_projection()->version == observed.snapshot->version,
            "Consumed action invented an observation/failure, published stale state or retained input");
        const auto consumed_epoch = controller.input_epoch();
        check(!controller.consume_request_without_publication(action.token) &&
            !controller.complete_request(action.token,reply(action,document(14))) &&
            !controller.fail_request(action.token,DocumentRequestFailure::unknown) &&
            controller.input_epoch() == consumed_epoch,
            "Late completion changed or repeated the consumed action");
        activate(controller); controller.tick();
        check(!controller.queue_selection({{3,0},{3,1}}) && !controller.synchronized() &&
            controller.view().revision == prior.revision,
            "Consumed action allowed stale view input before the fresh query");
        const auto refresh = next(controller,false,"Consumed action replayed instead of requesting fresh state");
        check(refresh.token.id > action.token.id &&
            !controller.consume_request_without_publication(refresh.token) && !controller.next_request(),
            "Consumed completion consumed its recovery query or reused action identity");
        check(controller.complete_request(refresh.token,reply(refresh)) && controller.synchronized() &&
            controller.presentation_pending(),"Consumed action recovery snapshot was not accepted");
        activate(controller);
        check(!controller.queue_selection({{3,0},{3,1}}) && !controller.next_request(),
            "Unpublished recovery snapshot armed input");
        controller.tick();
        check(!controller.presentation_pending() && !controller.next_request() &&
            list(controller.view()).state.selected == "node/4",
            "Recovery query replayed queued old input or local navigation");
        activate(controller,"node/6");
        const auto fresh = next(controller,true,"Published fresh observation did not restore input");
        exact(fresh,DocumentAction::activate,6);
    }
}
void consumed_completion_refuses_snapshot_and_closed_states() {
    gui::TerminalAdapter terminal; AppendedDocumentController controller(terminal,7,{40,10});
    const auto initial_epoch = controller.input_epoch();
    check(!controller.consume_request_without_publication({7,1}) && controller.input_epoch() == initial_epoch,
        "Consumed completion changed a controller without outstanding work");
    const auto initial = next(controller,false,"Consumed completion initial snapshot fixture");
    check(!controller.consume_request_without_publication(initial.token) && !controller.next_request() &&
        controller.input_epoch() == initial_epoch && !controller.synchronized(),
        "Consumed completion retired an initial snapshot");
    check(controller.complete_request(initial.token,reply(initial)),"Refused snapshot consumption lost the original request");
    controller.tick(); activate(controller);
    const auto action = next(controller,true,"Consumed completion shutdown action fixture");
    controller.shutdown(); const auto closed_epoch = controller.input_epoch();
    check(!controller.consume_request_without_publication(action.token) && controller.closed() &&
        controller.input_epoch() == closed_epoch && !controller.next_request(),
        "Consumed completion restored a stopped controller");
    TerminalFixture closing;
    activate(closing.controller);
    const auto closed_action = next(closing.controller,true,"Consumed completion closed-adapter fixture");
    closing.terminal.close();
    check(!closing.controller.consume_request_without_publication(closed_action.token) && closing.controller.closed() &&
        !closing.controller.next_request(),"Consumed completion retained authority after adapter closure");
}
void same_publication_action_discards_queued_input_before_refresh() {
    TerminalFixture fixture; auto& controller = fixture.controller;
    activate(controller); activate(controller,"node/6");
    const auto action = next(controller,true,"Same-publication action fixture was not admitted");
    check(controller.complete_request(action.token,reply(action)),"Same-publication action completion was rejected");
    controller.request_snapshot(); controller.tick();
    const auto refresh = next(controller,false,"Same-publication completion replayed queued action ahead of fresh query");
    check(refresh.token.id > action.token.id && controller.complete_request(refresh.token,reply(refresh)),
        "Same-publication refresh was not independent of the consumed action");
    controller.tick();
    check(!controller.next_request(),"Same-publication refresh resurrected stale queued input");
    activate(controller,"node/6");
    const auto fresh = next(controller,true,"Same-publication fresh query did not restore explicit input");
    exact(fresh,DocumentAction::activate,6);
}
class FailingAdapter final : public gui::RetainedAdapter {
    gui::TerminalAdapter metrics_;
public:
    bool fail_next = false;
    std::function<void()> during_measure;
    std::function<void()> during_present;
    unsigned presentations = 0;
    gui::Size measure_text(const gui::TextMeasureRequest& request) const override {
        if (during_measure) during_measure();
        return metrics_.measure_text(request);
    }
    void present(gui::Snapshot snapshot) override {
        ++presentations;
        if (during_present) during_present();
        if (std::exchange(fail_next,false)) throw std::runtime_error("injected document presentation failure");
        gui::RetainedAdapter::present(std::move(snapshot));
    }
};
void candidate_projection_is_readonly_and_publication_is_explicit() {
    FailingAdapter adapter; AppendedDocumentController controller(adapter,7,{40,10});
    const auto& readonly = controller;
    check(!readonly.candidate_projection(),"Unobserved controller invented a document candidate");
    controller.tick();
    check(!readonly.candidate_projection(),"Awaiting-snapshot presentation invented a document projection");
    const auto request = next(controller,false,"Readonly candidate initial snapshot fixture");
    auto accepted = reply(request); accepted.snapshot->nodes[2].text = "owned candidate text";
    check(controller.complete_request(request.token,accepted),"Readonly candidate snapshot was rejected");
    accepted.snapshot->nodes[2].text = "mutated caller storage";
    const auto painted_revision = adapter.snapshot().revision, epoch = controller.input_epoch();
    check(!readonly.candidate_projection() && controller.presentation_pending(),
        "Readonly candidate access built an unprojected accepted snapshot");
    adapter.fail_next = true; bool failed = false;
    try { controller.tick(); } catch (const std::runtime_error&) { failed = true; }
    const auto* candidate = readonly.candidate_projection();
    check(failed && candidate && candidate->version == DocumentVersion{7,11,13} &&
        candidate->view.revision == controller.view().revision && candidate->view.revision > painted_revision &&
        presented_text(candidate->view).find("owned candidate text") != std::string::npos &&
        presented_text(candidate->view).find("mutated caller storage") == std::string::npos &&
        !candidate->rows.empty(),"Readonly access lost the owned pending projection or borrowed caller storage");
    const auto candidate_revision = candidate->view.revision;
    const auto presentations = adapter.presentations;
    check(readonly.candidate_projection() == candidate && controller.input_epoch() == epoch &&
        controller.synchronized() && controller.presentation_pending() &&
        adapter.snapshot().revision == painted_revision && adapter.presentations == presentations &&
        !controller.next_request(),"Reading a pending candidate published it or changed input/request authority");
    controller.retry_presentation();
    candidate = readonly.candidate_projection();
    check(candidate && candidate->view.revision == candidate_revision &&
        adapter.snapshot().revision == candidate_revision && !controller.presentation_pending() &&
        controller.input_epoch() == epoch && !controller.next_request(),
        "Committed candidate access rebuilt the projection or scheduled engine work");
    controller.shutdown();
    check(!readonly.candidate_projection(),"Stopped controller exposed a revoked document candidate");
}
void suspension_refuses_queued_and_outstanding_work_transactionally() {
    TerminalFixture fixture; auto& controller = fixture.controller;
    const auto epoch = controller.input_epoch(), revision = controller.view().revision;
    const auto visible = presented_text(controller.view());
    activate(controller);
    check(!controller.suspend_input() && controller.synchronized() && controller.input_epoch() == epoch &&
        controller.view().revision == revision && presented_text(controller.view()) == visible &&
        !controller.presentation_pending() && !controller.closed(),
        "Refused suspension mutated the committed view or revoked queued input");
    const auto action = next(controller,true,"Refused suspension discarded a queued activation");
    exact(action,DocumentAction::activate,4);
    const auto outstanding_epoch = controller.input_epoch();
    check(!controller.suspend_input() && controller.synchronized() &&
        controller.input_epoch() == outstanding_epoch && controller.view().revision == revision &&
        !controller.next_request(),"Refused suspension forgot an already-returned native effect");
    check(controller.complete_request(action.token,reply(action,document(14))) &&
        !controller.complete_request(action.token,reply(action,document(14))),
        "Suspension refusal consumed an outstanding completion or permitted it twice");
    const auto accepted_epoch = controller.input_epoch();
    check(!controller.suspend_input() && controller.synchronized() &&
        controller.presentation_pending() && controller.input_epoch() == accepted_epoch,
        "Suspension accepted an unbuilt action result or mutated a refused dirty candidate");
    controller.tick();
    check(controller.synchronized() && !controller.presentation_pending() && !controller.next_request(),
        "Refused suspension introduced a snapshot or replay after the original action completed");

    const auto key = list(controller.view()).spec.key;
    const auto& records = list(controller.view()).state.records;
    const auto prose = std::find_if(records.begin(),records.end(),[](const gui::Record& row) {
        return row.accessible_text.find("alpha") != std::string::npos;
    });
    check(prose != records.end(),"Suspension local-navigation fixture has no prose row");
    const auto id = prose->id;
    controller.handle(gui::WidgetEvent{key,gui::SelectRecord{id}});
    check(!controller.suspend_input() && controller.input_epoch() == accepted_epoch,
        "Suspension discarded queued local navigation");
    controller.tick();
    check(list(controller.view()).state.selected == id && !controller.next_request(),
        "Refused suspension lost the original local navigation");
}
void successful_suspension_requires_explicit_fresh_snapshot_resume() {
    TerminalFixture fixture; auto& controller = fixture.controller;
    const auto epoch = controller.input_epoch(), revision = controller.view().revision;
    const auto visible = presented_text(controller.view());
    const auto accepted_request = controller.observation()->request_id;
    controller.request_snapshot(); // An unissued optional refresh is deliberately cancelled by suspension.
    check(controller.suspend_input() && !controller.synchronized() && controller.input_epoch() > epoch &&
        !controller.presentation_pending() && !controller.closed() && controller.last_error().empty() &&
        controller.view().revision == revision && presented_text(controller.view()) == visible &&
        fixture.terminal.snapshot().revision == revision && controller.candidate_projection() &&
        controller.candidate_projection()->version == DocumentVersion{7,11,13} &&
        controller.observation() && controller.observation()->request_id == accepted_request,
        "Successful suspension lost observation/display state or retained synchronized input");
    const auto suspended_epoch = controller.input_epoch();
    check(!controller.suspend_input() && controller.input_epoch() == suspended_epoch,
        "Repeated suspension changed an already suspended controller");
    activate(controller); controller.tick();
    check(!controller.queue_selection({{3,0},{3,1}}) && !controller.next_request() &&
        !controller.synchronized() && controller.view().revision == revision &&
        controller.input_epoch() == suspended_epoch,
        "Suspended input or owner tick silently resumed engine work");
    controller.request_snapshot();
    const auto refresh = next(controller,false,"Suspension did not permit explicit fresh-snapshot resume");
    check(refresh.token.id > accepted_request && !controller.suspend_input() &&
        !controller.synchronized() && controller.input_epoch() == suspended_epoch,
        "Suspension consumed an outstanding explicit resume snapshot");
    check(controller.complete_request(refresh.token,reply(refresh,document(14))) && controller.synchronized() &&
        controller.presentation_pending(),"Fresh resume snapshot did not require real presentation");
    const auto resumed_epoch = controller.input_epoch();
    activate(controller);
    check(!controller.suspend_input() && controller.input_epoch() == resumed_epoch && !controller.next_request(),
        "Uncommitted resume snapshot acquired input or suspension authority");
    controller.tick();
    check(!controller.presentation_pending() && controller.candidate_projection() &&
        controller.candidate_projection()->version == DocumentVersion{7,11,14} && !controller.next_request(),
        "Resume did not commit the fresh snapshot or revived suspended input");
    activate(controller);
    const auto fresh = next(controller,true,"Committed resume snapshot did not restore input authority");
    exact(fresh,DocumentAction::activate,4,{7,11,14});
}
void local_suspension_resume_requires_exact_unchanged_version() {
    TerminalFixture fixture; auto& controller = fixture.controller;
    const auto version = controller.candidate_projection()->version;
    const auto epoch = controller.input_epoch(), revision = controller.view().revision;
    const auto observed = controller.observation()->request_id;
    check(!controller.resume_input(version) && controller.input_epoch() == epoch,
        "Resume changed a controller that was never suspended");
    check(controller.suspend_input(),"Local modal resume fixture could not suspend input");
    const auto suspended_epoch = controller.input_epoch();
    for (const auto foreign : {DocumentVersion{8,version.epoch,version.revision},
                               DocumentVersion{7,version.epoch + 1,version.revision},
                               DocumentVersion{7,version.epoch,version.revision + 1}})
        check(!controller.resume_input(foreign) && !controller.synchronized() &&
            controller.input_epoch() == suspended_epoch && !controller.next_request(),
            "Foreign displayed version resumed suspended input");
    check(controller.resume_input(version) && controller.synchronized() &&
        controller.input_epoch() > suspended_epoch && controller.view().revision == revision &&
        fixture.terminal.snapshot().revision == revision && !controller.presentation_pending() &&
        controller.observation() && controller.observation()->request_id == observed &&
        controller.last_error().empty() && !controller.next_request(),
        "Exact local Cancel resume invented an observation, publication or native work");
    const auto resumed_epoch = controller.input_epoch();
    check(!controller.resume_input(version) && controller.input_epoch() == resumed_epoch,
        "Repeated local Cancel resumed input twice");
    activate(controller); const auto action = next(controller,true,"Exact local Cancel did not restore input");
    exact(action,DocumentAction::activate,4);
    check(!controller.resume_input(version) && !controller.next_request(),
        "Local Cancel consumed outstanding action work");
}
void local_resume_never_bypasses_uncertainty_or_publication() {
    FailingAdapter adapter; AppendedDocumentController controller(adapter,7,{40,10});
    const DocumentVersion version{7,11,13};
    check(!controller.resume_input(version),"Initial controller invented suspended input authority");
    ready(controller);
    check(controller.suspend_input(),"Local uncertainty resume fixture could not suspend input");
    controller.request_snapshot();
    check(!controller.resume_input(version),"Explicit fresh query debt was discarded by local resume");
    const auto failed = next(controller,false,"Local resume refresh fixture was not issued");
    check(!controller.resume_input(version) && !controller.next_request() &&
        controller.fail_request(failed.token,DocumentRequestFailure::unknown) &&
        !controller.resume_input(version) && !controller.next_request(),
        "Failed or outstanding fresh query incorrectly became a reversible local suspension");
    controller.request_snapshot(); const auto recovery = next(controller,false,"Local resume explicit recovery fixture");
    check(controller.complete_request(recovery.token,reply(recovery)) && !controller.resume_input(version),
        "Unpublished recovery snapshot bypassed presentation through local resume");
    controller.tick();
    check(controller.suspend_input(),"Recovered snapshot did not permit an explicit local suspension");
    unsigned callbacks = 0;
    adapter.during_measure = [&] {
        ++callbacks;
        check(!controller.resume_input(version),"Measurement callback resumed local input reentrantly");
    };
    adapter.during_present = [&] {
        ++callbacks;
        check(!controller.resume_input(version),"Presentation callback resumed local input reentrantly");
    };
    controller.viewport({30,8});
    check(!controller.resume_input(version),"Dirty projection bypassed publication through local resume");
    adapter.fail_next = true; bool publication_failed = false;
    try { controller.tick(); } catch (const std::runtime_error&) { publication_failed = true; }
    check(publication_failed && callbacks && !controller.resume_input(version) && controller.presentation_pending(),
        "Failed presentation bypassed publication through local resume");
    adapter.during_measure = {}; adapter.during_present = {};
    controller.retry_presentation();
    check(controller.resume_input(version),"Published same-version reflow lost explicit local suspension");
    activate(controller); const auto action = next(controller,true,"Local resume consumed-action fixture");
    check(controller.consume_request_without_publication(action.token) && !controller.resume_input(version),
        "Consumed action became reversible local suspension without fresh observation");
    controller.shutdown();
    check(!controller.resume_input(version) && !controller.next_request(),"Stopped controller resumed local input");
    TerminalFixture closing;
    check(closing.controller.suspend_input(),"Local resume closed-adapter fixture could not suspend");
    closing.terminal.close();
    check(!closing.controller.resume_input(version),"Closed adapter resumed local input");
}
void suspension_refuses_unpublished_reentrant_and_stopped_states() {
    FailingAdapter adapter; AppendedDocumentController controller(adapter,7,{40,10});
    const auto initial_epoch = controller.input_epoch();
    check(!controller.suspend_input() && controller.input_epoch() == initial_epoch &&
        !controller.synchronized(),"Initial unsynchronized suspension altered input authority");
    ready(controller);
    const auto epoch = controller.input_epoch();
    unsigned measure_callbacks = 0, present_callbacks = 0;
    adapter.during_measure = [&] {
        ++measure_callbacks;
        check(!controller.suspend_input() && controller.input_epoch() == epoch,
            "Suspension changed controller state during projection measurement");
    };
    adapter.during_present = [&] {
        ++present_callbacks;
        check(!controller.suspend_input() && controller.input_epoch() == epoch,
            "Suspension changed controller state during presentation");
    };
    controller.viewport({30,8});
    check(!controller.suspend_input() && controller.input_epoch() == epoch,
        "Suspension accepted a dirty reflow candidate");
    adapter.fail_next = true; bool failed = false;
    try { controller.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && measure_callbacks && present_callbacks == 1 && !controller.suspend_input() &&
        controller.input_epoch() == epoch && controller.synchronized() && controller.presentation_pending(),
        "Suspension accepted or altered a failed unpublished candidate");
    adapter.during_measure = {}; adapter.during_present = {};
    controller.retry_presentation();
    check(controller.suspend_input(),"Committed reflow candidate did not permit suspension");
    controller.shutdown(); const auto stopped_epoch = controller.input_epoch();
    check(!controller.suspend_input() && controller.closed() && controller.input_epoch() == stopped_epoch &&
        !controller.next_request(),"Stopped suspension restored or changed controller input authority");
    TerminalFixture tiny({1,1}); const auto tiny_epoch = tiny.controller.input_epoch();
    check(!tiny.controller.candidate_projection() && !tiny.controller.suspend_input() &&
        tiny.controller.synchronized() && tiny.controller.input_epoch() == tiny_epoch && !tiny.controller.next_request(),
        "Noninteractive viewport invented a committed candidate for suspension");
}
void presentation_retry_and_callback_guards() {
    FailingAdapter adapter; AppendedDocumentController controller(adapter,7,{40,10}); ready(controller);
    activate(controller); const auto action = next(controller,true,"Presentation retry action fixture");
    const auto painted = adapter.snapshot(); auto observed = document(14); observed.nodes[2].text = "accepted engine result";
    check(controller.complete_request(action.token,reply(action,observed)),"Accepted action result was not retained");
    adapter.fail_next = true; bool failed = false;
    try { controller.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && controller.synchronized() && controller.presentation_pending() &&
        controller.view().revision > painted.revision && adapter.snapshot().revision == painted.revision,
        "Failed presentation lost the accepted candidate or claimed it was painted");
    const auto accepted_revision = controller.view().revision, epoch = controller.input_epoch();
    controller.handle(gui::WidgetEvent{list(painted).spec.key,gui::ActivateRecord{"node/4"}});
    check(!controller.queue_selection({{3,0},{3,1}}) && !controller.next_request() && controller.input_epoch() == epoch,
        "Input from an old painted view reached the engine while presentation was pending");
    unsigned guarded_callbacks = 0;
    adapter.during_present = [&] {
        ++guarded_callbacks; bool rejected = false;
        try { (void)controller.next_request(); } catch (const std::logic_error&) { rejected = true; }
        check(rejected,"Presentation callback reentered controller request dispatch");
    };
    controller.retry_presentation(); adapter.during_present = {};
    check(guarded_callbacks == 1 && !controller.presentation_pending() && controller.view().revision == accepted_revision &&
        adapter.snapshot().revision == accepted_revision && presented_text(adapter.snapshot()).find("accepted engine result") != std::string::npos &&
        !controller.complete_request(action.token,reply(action,observed)) && !controller.next_request(),
        "Presentation retry repeated an engine action or rebuilt a different candidate");
    FailingAdapter closing_adapter;
    AppendedDocumentController closing(closing_adapter,7,{40,10});
    closing_adapter.during_present = [&] { closing.shutdown(); };
    closing.tick();
    check(closing.closed() && !closing_adapter.closed() && !closing.next_request(),
        "Shutdown during presentation retained requests or destroyed the composition-owned adapter");
}
void epoch_replacement_queue_limit_and_lifecycle() {
    {
        TerminalFixture fixture; auto& controller = fixture.controller;
        const auto old_key = list(controller.view()).spec.key;
        const auto painted_revision = controller.view().revision, epoch = controller.input_epoch();
        activate(controller); activate(controller,"node/6");
        const auto action = next(controller,true,"Epoch replacement action fixture");
        check(controller.complete_request(action.token,reply(action,document(1,12))),"New document epoch snapshot was rejected");
        controller.tick();
        check(controller.view().revision > painted_revision && controller.input_epoch() != epoch &&
            list(controller.view()).spec.key != old_key && !controller.next_request(),
            "Epoch replacement reused GUI revision or rebased queued old actions");
        controller.handle(gui::WidgetEvent{old_key,gui::ActivateRecord{"node/4"}});
        check(!controller.next_request(),"Obsolete document epoch key authorized a new engine action");
        activate(controller); const auto fresh = next(controller,true,"New epoch activation was not available");
        exact(fresh,DocumentAction::activate,4,{7,12,1});
        controller.handle(gui::CloseEvent{});
        check(controller.closed() && !controller.synchronized() && !fixture.terminal.closed() &&
            !controller.complete_request(fresh.token,reply(fresh,document(2,12))) && !controller.next_request(),
            "Close callback retained completion/input authority or destroyed its adapter");
    }
    {
        TerminalFixture fixture; auto& controller = fixture.controller;
        for (std::size_t n = 0; n < AppendedDocumentController::max_queued_intents; ++n) activate(controller);
        check(!controller.closed(),"Controller closed before its documented queue capacity");
        activate(controller);
        check(controller.closed() && !controller.next_request() && !controller.queue_selection({{3,0},{3,1}}) &&
            !fixture.terminal.closed(),"Queue overflow retained actions or destroyed the adapter");
    }
    {
        TerminalFixture fixture; activate(fixture.controller);
        const auto action = next(fixture.controller,true,"Adapter close action fixture");
        fixture.terminal.close(); fixture.controller.tick();
        check(fixture.controller.closed() && !fixture.controller.next_request() &&
            !fixture.controller.complete_request(action.token,reply(action,document(14))),
            "Closed adapter retained outstanding engine work");
    }
}
void empty_snapshots_and_visibility_pruned_forests() {
    AppendedDocumentController* current = nullptr;
    gui::TerminalAdapter terminal([&](const gui::Event& event) { if (current) current->handle(event); });
    AppendedDocumentController controller(terminal,7,{40,10}); current = &controller;
    terminal.terminal_size(40,11);
    DocumentSnapshot empty; empty.version = {7,11,1}; empty.active_node = 999;
    ready(controller,empty);
    const auto retained_key = list(controller.view()).spec.key;
    const auto check_empty = [&] {
        const auto* observed = controller.observation();
        check(controller.synchronized() && !controller.presentation_pending() && observed && observed->snapshot &&
            observed->snapshot->nodes.empty() && observed->snapshot->active_node == 999 &&
            list(controller.view()).spec.key == retained_key && list(controller.view()).state.visible &&
            !list(controller.view()).state.enabled && !terminal.focus(retained_key) &&
            list(controller.view()).state.records.empty() && !list(controller.view()).state.selected &&
            !controller.queue_selection({{999,0},{999,0}}),
            "Empty semantic snapshot acquired synthetic nodes, focus, selection or enabled actions");
        controller.handle(gui::WidgetEvent{retained_key,gui::SelectRecord{"node/999"}});
        controller.handle(gui::WidgetEvent{retained_key,gui::ActivateRecord{"node/999"}});
        terminal.input("\r");
        controller.tick();
        check(!controller.next_request(),"Empty document row input acquired phantom engine authority");
    };
    check_empty();
    controller.request_snapshot();
    const auto populate = next(controller,false,"Empty document did not allow an explicit semantic refresh");
    check(controller.complete_request(populate.token,reply(populate,document(2))),"Populated snapshot after empty was rejected");
    controller.tick();
    check(list(controller.view()).spec.key == retained_key && list(controller.view()).state.enabled &&
        terminal.focus(retained_key),"Populating an empty document lost its real adapter list lifetime");
    activate(controller); activate(controller,"node/6");
    const auto action = next(controller,true,"Populated-to-empty action fixture was not admitted");
    exact(action,DocumentAction::activate,4,{7,11,2});
    empty.version.revision = 3;
    check(controller.complete_request(action.token,reply(action,empty)),"Empty action result was rejected or replaced with a fake root");
    controller.tick(); check_empty();
    check(!controller.complete_request(action.token,reply(action,document(4))),
        "Duplicate pre-empty completion restored discarded document actions");

    // Visibility pruning may export several actual element roots. The button
    // deliberately reuses a pre-empty queued node ID; its old action must stay
    // revoked even when that producer ID becomes visible again.
    auto button = element(6,0,"button"); button.name = "Visible root action";
    auto link = element(211,0,"a"); link.name = "Visible root link"; link.href = "visible.html";
    DocumentSnapshot forest; forest.version = {7,11,4}; forest.active_node = 211;
    forest.nodes = {button,text(61,6,"Visible root action"),link,text(212,211,"Visible root link"),
        element(307,0,"p"),text(308,307,"Visible prose after a pruned ancestor")};
    controller.request_snapshot(); const auto reveal = next(controller,false,"Empty-to-forest refresh was not issued");
    check(controller.complete_request(reveal.token,reply(reveal,forest)),"Visibility-pruned element forest was rejected");
    controller.tick();
    const auto* observed = controller.observation();
    check(observed && observed->snapshot && *observed->snapshot == forest &&
        list(controller.view()).spec.key == retained_key && list(controller.view()).state.enabled &&
        list(controller.view()).state.selected == "node/211" && !controller.next_request(),
        "Forest projection changed actual roots/ancestry/IDs or revived pre-empty queued input");
    const auto& records = list(controller.view()).state.records;
    check(records.size() == 3 && records[0].id == "node/6" && records[1].id == "node/211" &&
        records[0].activatable && records[1].activatable && !records[2].activatable &&
        terminal_cells(terminal).find("Visible root link") != std::string::npos,
        "Forest root order or real-node action identities were lost in terminal presentation");
    activate(controller,"node/4");
    check(!controller.queue_selection({{3,0},{3,1}}) && !controller.next_request(),
        "Removed pre-empty node acquired focus, selection or activation in the forest");
    controller.handle(gui::WidgetEvent{retained_key,gui::SelectRecord{"node/6"}});
    const auto focus = next(controller,true,"Forest root did not produce a real-node focus request");
    exact(focus,DocumentAction::focus,6,{7,11,4});
    forest.version.revision = 5; forest.active_node = 6;
    check(controller.complete_request(focus.token,reply(focus,forest)),"Forest focus result was rejected");
    controller.tick();
    check(terminal.focus(retained_key),"Forest list could not regain generic terminal focus");
    terminal.input("\r");
    const auto activated = next(controller,true,"Real terminal Enter did not activate the observed forest root");
    exact(activated,DocumentAction::activate,6,{7,11,5});
    forest.version.revision = 6;
    check(controller.complete_request(activated.token,reply(activated,forest)),"Forest activation result was rejected");
    controller.tick();
    check(controller.synchronized() && !controller.next_request() && controller.observation() &&
        controller.observation()->snapshot && *controller.observation()->snapshot == forest,
        "Forest action completion synthesized ancestry or repeated earlier input");
    controller.request_snapshot();
    const auto truncated = next(controller,false,"Truncated empty snapshot refresh was not issued");
    empty.version.revision = 7; empty.truncated = true;
    check(controller.complete_request(truncated.token,reply(truncated,empty)),"Truncated empty snapshot was rejected");
    controller.tick();
    const auto& incomplete = list(controller.view());
    check(controller.synchronized() && !incomplete.state.enabled && !incomplete.state.selected &&
        incomplete.state.records.size() == 1 && !incomplete.state.records.front().activatable &&
        incomplete.state.records.front().accessible_text.find("incomplete") != std::string::npos &&
        terminal_cells(terminal).find("incomplete") != std::string::npos &&
        !controller.queue_selection({{999,0},{999,0}}),
        "Truncated empty document lost its readable notice or granted interactive marker authority");
    const auto marker = incomplete.state.records.front().id;
    controller.handle(gui::WidgetEvent{retained_key,gui::SelectRecord{marker}});
    controller.handle(gui::WidgetEvent{retained_key,gui::ActivateRecord{marker}});
    terminal.input("\r"); controller.tick();
    check(!controller.next_request(),"Incomplete-document notice became a phantom engine action");
}
void tiny_viewports_and_resize_revisions() {
    for (const auto viewport : {DocumentViewport{1,6},DocumentViewport{20,1},DocumentViewport{1,1}}) {
        TerminalFixture fixture(viewport); auto& controller = fixture.controller;
        check(controller.synchronized() && controller.view().widgets.size() == 1 &&
            !list(controller.view()).state.visible && !list(controller.view()).state.enabled &&
            controller.view().title.find("too small") != std::string::npos &&
            controller.view().client_size == gui::Size{double(viewport.columns) * gui::TerminalAdapter::cell_width,
                double(viewport.drawable_rows) * gui::TerminalAdapter::cell_height} &&
            !controller.queue_selection({{3,0},{3,1}}) && !controller.next_request(),
            "Tiny terminal viewport acquired invented geometry or interactive document authority");
        controller.viewport({40,10}); controller.tick();
        check(list(controller.view()).state.visible && list(controller.view()).state.enabled &&
            !list(controller.view()).state.records.empty() && !controller.presentation_pending(),
            "Valid viewport did not restore a readable projection");
    }
    TerminalFixture fixture({40,10}); auto& controller = fixture.controller;
    const auto original_revision = controller.view().revision;
    const auto wide_rows = list(controller.view()).state.records.size();
    controller.handle(gui::ResizeEvent{{640,480},1}); controller.tick();
    check(controller.view().revision == original_revision,"Minimum logical canvas was mistaken for actual terminal size");
    controller.viewport({20,8}); controller.tick();
    check(controller.view().revision > original_revision && controller.view().client_size == gui::Size{160,128} &&
        list(controller.view()).state.records.size() > wide_rows && !controller.next_request(),
        "Actual cell resize failed to reflow or spuriously requested engine work");
    const auto retained_key = list(controller.view()).spec.key;
    activate(controller); // Shrinking revokes already queued engine actions.
    controller.viewport({1,1}); controller.tick();
    check(list(controller.view()).spec.key == retained_key && !list(controller.view()).state.visible &&
        !list(controller.view()).state.enabled && !controller.next_request(),
        "Shrinking to a tiny viewport retired the list lifetime or dispatched old input");
    controller.viewport({20,8}); controller.tick();
    check(list(controller.view()).spec.key == retained_key && list(controller.view()).state.visible &&
        list(controller.view()).state.enabled && !controller.next_request(),
        "Restoring a usable terminal reused a retired widget generation or revived old queued input");
    activate(controller); const auto action = next(controller,true,"Resized document action fixture");
    exact(action,DocumentAction::activate,4); // GUI revision changed; DOM revision did not.
}
} // namespace

int main() {
    try {
        queue_only_real_terminal_and_exact_action(); local_prose_navigation_and_owned_selection();
        stale_view_and_unknown_outcomes_never_replay(); completion_identity_and_atomic_validation();
        consumed_actions_without_publication_require_fresh_observation();
        consumed_completion_refuses_snapshot_and_closed_states();
        same_publication_action_discards_queued_input_before_refresh();
        candidate_projection_is_readonly_and_publication_is_explicit();
        suspension_refuses_queued_and_outstanding_work_transactionally();
        successful_suspension_requires_explicit_fresh_snapshot_resume();
        local_suspension_resume_requires_exact_unchanged_version();
        local_resume_never_bypasses_uncertainty_or_publication();
        suspension_refuses_unpublished_reentrant_and_stopped_states();
        presentation_retry_and_callback_guards(); epoch_replacement_queue_limit_and_lifecycle();
        empty_snapshots_and_visibility_pruned_forests(); tiny_viewports_and_resize_revisions();
        std::cout << "Document controller queue, exact versions, recovery and terminal presentation passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
