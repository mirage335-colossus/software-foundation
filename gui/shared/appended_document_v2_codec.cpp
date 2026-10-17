#include "appended_document_v2_codec.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <string_view>
#include <type_traits>

namespace foundation::ui {
namespace F = appended;
namespace {
constexpr std::uint64_t safe_integer = 9007199254740991ULL;
constexpr std::size_t field_units = 2048, section_units = 65536, record_limit = 2048;
constexpr std::size_t traversal_limit = 8192, depth_limit = 256;
static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559);
void require(bool ok, const char* message) { if (!ok) throw std::invalid_argument(message); }
void charge(std::size_t& remaining, std::size_t count) {
    require(count <= remaining, "Native-v2 aggregate limit exceeded"); remaining -= count;
}
std::size_t units(std::string_view text) {
    require(text.size() <= field_units * 3 && gui::valid_utf8(text), "Invalid native-v2 scalar UTF8 field");
    std::size_t result = 0;
    for (std::size_t at = 0; at < text.size();) {
        const auto c = static_cast<unsigned char>(text[at]);
        const std::size_t bytes = c < 0x80 ? 1 : c < 0xe0 ? 2 : c < 0xf0 ? 3 : 4;
        result += bytes == 4 ? 2 : 1; at += bytes;
    }
    require(result <= field_units, "Native-v2 UTF16 field limit exceeded"); return result;
}
void identity(DocumentV2Identity value) {
    require(value.application_instance && value.service_generation && value.document_sequence, "Zero native-v2 identity");
    // The current controller uses this exact service generation as its epoch.
    require(value.service_generation <= UINT32_MAX,"Unrepresentable native-v2 epoch");
}
void version(F::FormVersion value, DocumentV2Identity expected) {
    require(value.generation == expected.application_instance && value.epoch == expected.service_generation && value.revision,
        "Native-v2 version identity mismatch");
    require(value.epoch <= UINT32_MAX && value.revision <= safe_integer, "Unrepresentable native-v2 version");
}
void node_id(std::uint64_t value) { require(value && value <= safe_integer, "Unrepresentable native-v2 node identity"); }
void lease(const F::FormLease& value, DocumentV2Identity expected) {
    version(value.captured, expected); node_id(value.node); require(value.id, "Zero native-v2 lease identity");
}
void range(F::FormControlRange value) {
    require(value.start <= value.end && value.end <= field_units && static_cast<unsigned>(value.direction) <= 2,
        "Invalid native-v2 UTF16 range");
}
F::FormAction form_action(const DocumentFormsRequest& request) {
    if (const auto* begin = std::get_if<F::BeginFormControl>(&request.action)) return *begin;
    if (const auto* draft = std::get_if<F::FormDraftRequest>(&request.action)) {
        require(draft->token.generation && draft->token.sequence, "Zero local draft request token"); return draft->action;
    }
    if (const auto* finish = std::get_if<F::FinishFormControl>(&request.action)) return *finish;
    throw std::invalid_argument("Native-v2 body actions are unsupported");
}
void validate_action(const F::FormAction& action, DocumentV2Identity expected) {
    require(!action.valueless_by_exception(),"Valueless native-v2 form action");
    std::visit([&](const auto& value) {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T,F::BeginFormControl> || std::is_same_v<T,F::OpenFormPopup>) {
            version(value.expected, expected); node_id(value.node);
        } else {
            lease(value.expected, expected);
            if constexpr (std::is_same_v<T,F::ReplaceFormText>) { range(value.range); (void)units(value.text); }
            else if constexpr (std::is_same_v<T,F::SetFormOption>) node_id(value.option);
        }
    }, action);
}
std::uint64_t target(const F::FormAction& action) {
    return std::visit([](const auto& value) {
        using T = std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T,F::BeginFormControl> || std::is_same_v<T,F::OpenFormPopup>) return value.node;
        else return value.expected.node;
    }, action);
}
struct Writer {
    std::vector<std::uint8_t> bytes;
    void integer(std::uint64_t value, std::size_t width) {
        require(width <= max_document_v2_action_bytes - bytes.size(), "Native-v2 request byte limit exceeded");
        for (std::size_t i = 0; i < width; ++i) bytes.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
    }
    void string(std::string_view text) {
        integer(text.size(),4);
        require(text.size() <= max_document_v2_action_bytes - bytes.size(), "Native-v2 request byte limit exceeded");
        bytes.insert(bytes.end(),text.begin(),text.end());
    }
    void header(unsigned kind) { integer(0x3256444e,4); integer(2,2); integer(kind,1); integer(0,1); }
    void put(F::FormVersion value) { integer(value.generation,8); integer(value.epoch,8); integer(value.revision,8); }
    void put(const F::FormLease& value) { put(value.captured); integer(value.node,8); integer(value.id,8); }
    void put(F::FormControlRange value) { integer(value.start,4); integer(value.end,4); integer(static_cast<unsigned>(value.direction),1); }
};
struct Reader {
    std::span<const std::uint8_t> bytes;
    std::size_t at{0}, body_units{section_units}, metadata_units{section_units}, forms_units{section_units}, options{record_limit};
    explicit Reader(std::span<const std::uint8_t> input) : bytes(input) {
        require(input.size() <= max_document_v2_reply_bytes, "Native-v2 reply byte limit exceeded");
    }
    std::size_t left() const { return bytes.size() - at; }
    std::uint64_t integer(std::size_t width) {
        require(width <= left(), "Short native-v2 packet"); std::uint64_t value = 0;
        for (std::size_t i = 0; i < width; ++i) value |= std::uint64_t(bytes[at++]) << (8 * i);
        return value;
    }
    bool boolean() { const auto value = integer(1); require(value <= 1, "Noncanonical native-v2 boolean"); return value != 0; }
    unsigned flags(unsigned allowed) {
        const auto value = static_cast<unsigned>(integer(1)); require(!(value & ~allowed), "Unknown native-v2 flags"); return value;
    }
    std::string string(std::size_t& remaining) {
        const auto count = integer(4);
        require(count <= field_units * 3 && count <= left(), "Invalid native-v2 string byte length");
        const std::string_view value(reinterpret_cast<const char*>(bytes.data() + at),static_cast<std::size_t>(count));
        charge(remaining,units(value)); at += static_cast<std::size_t>(count); return std::string(value);
    }
    void header(unsigned expected) {
        require(integer(4) == 0x3256444e && integer(2) == 2 && integer(1) == expected && integer(1) == 0,
            "Unknown native-v2 packet header");
    }
    DocumentV2Identity get_identity() { return {integer(8),integer(8),integer(8)}; }
    F::FormVersion get_version() { return {integer(8),integer(8),integer(8)}; }
    F::FormLease get_lease() { F::FormLease value; value.captured=get_version(); value.node=integer(8); value.id=integer(8); return value; }
    F::FormControlRange get_range() {
        F::FormControlRange value; value.start=static_cast<std::uint32_t>(integer(4)); value.end=static_cast<std::uint32_t>(integer(4));
        const auto direction=integer(1); require(direction<=2,"Unknown native-v2 form direction");
        value.direction=static_cast<F::FormDirection>(direction); return value;
    }
    DocumentNativePoint endpoint() {
        DocumentNativePoint value; value.node=integer(8); const auto kind=integer(1);
        if (kind==1) value.kind=DocumentNativeOffsetKind::text_utf16;
        else if (kind==2) value.kind=DocumentNativeOffsetKind::element_child_index;
        else throw std::invalid_argument("Unknown native-v2 selection endpoint kind");
        value.offset=static_cast<std::uint32_t>(integer(4)); return value;
    }
    F::FormControl control() {
        F::FormControl value; value.node=integer(8); const auto kind=integer(1);
        require(kind<=7,"Unknown native-v2 control kind"); value.kind=static_cast<F::FormKind>(kind);
        const auto f=flags(63); value.disabled=f&1; value.read_only=f&2; value.focusable=f&4;
        value.focused=f&8; value.omitted=f&16; value.complete=f&32;
        value.capabilities=static_cast<std::uint32_t>(integer(4)); const auto state=integer(1);
        require(state<=3,"Unknown native-v2 control state"); const bool has_lease=boolean();
        value.native_type=string(forms_units); value.label=string(forms_units); if (has_lease) value.lease=get_lease();
        if (state==1) {
            F::FormTextState text; text.value=string(forms_units); text.editing_text=string(forms_units);
            if (boolean()) text.selection=get_range();
            value.state=std::move(text);
        } else if (state==2) value.state=F::FormCheckState{boolean(),boolean()};
        else if (state==3) {
            F::FormSelectState select; const auto f2=flags(3); select.multiple=f2&1; select.menu_list=f2&2;
            const auto count=integer(4); require(count<=options && count<=left()/13,"Invalid native-v2 option count");
            charge(options,static_cast<std::size_t>(count)); select.options.reserve(static_cast<std::size_t>(count));
            for (std::uint64_t i=0;i<count;++i) {
                F::FormOption option; option.node=integer(8); const auto f3=flags(7);
                option.selected=f3&1; option.disabled=f3&2; option.omitted=f3&4; option.label=string(forms_units);
                select.options.push_back(std::move(option));
            }
            value.state=std::move(select);
        }
        return value;
    }
    void finish() const { require(!left(),"Trailing native-v2 bytes"); }
};
bool safe_type(std::string_view type) {
    for (const auto known : {"button","checkbox","color","date","datetime-local","email","file","hidden","image","month","number","password","radio","range","reset","search","submit","tel","text","time","url","week","fieldset","object","output","textarea","select-one","select-multiple"})
        if (type==known) return true;
    return false;
}
bool tag_matches(std::string_view type, std::string_view tag) {
    if (type=="textarea" || type=="fieldset" || type=="object" || type=="output") return tag==type;
    if (type=="select-one" || type=="select-multiple") return tag=="select";
    if (type=="button" || type=="reset" || type=="submit") return tag=="input" || tag=="button";
    return tag=="input";
}
DocumentWhiteSpace whitespace(std::string_view value, bool& degraded) {
    if (value=="normal") return DocumentWhiteSpace::normal;
    if (value=="pre") return DocumentWhiteSpace::pre;
    if (value=="pre-wrap") return DocumentWhiteSpace::pre_wrap;
    degraded=true; return value=="break-spaces" ? DocumentWhiteSpace::pre_wrap : DocumentWhiteSpace::normal;
}
void validate_publication(DocumentV2Publication& result, DocumentV2Identity expected, const std::vector<std::uint32_t>& children) {
    auto& joined=result.observation; auto& body=joined.body; auto& snapshot=*body.snapshot; const auto& forms=joined.forms;
    version(joined.publication,expected);
    require(body.editor_state->revision && body.editor_state->revision<=std::uint32_t(INT32_MAX) && body.editor_state->flags<=31,
        "Unrepresentable native-v2 editor state");
    require(!(result.native_degradation & ~127U),"Unknown native-v2 degradation flags");
    if (snapshot.nodes.empty()) require(body.metadata.empty() && forms.controls.empty() && !snapshot.active_node && !result.selection,
        "Empty native-v2 forest retains joins");
    F::validate_document_forms(forms);
    std::map<std::uint64_t,std::size_t> positions, depths, emitted;
    std::vector<std::uint64_t> ancestry;
    std::size_t remaining_children=traversal_limit;
    for (std::size_t i=0;i<snapshot.nodes.size();++i) {
        const auto& n=snapshot.nodes[i]; node_id(n.id);
        require(!positions.contains(n.id),"Duplicate native-v2 body ID");
        if (!n.parent) { require(n.kind==DocumentNodeKind::element,"Native-v2 root is not element"); ancestry.clear(); }
        else {
            const auto found=positions.find(n.parent); require(found!=positions.end(),"Native-v2 parent must precede child");
            const auto& parent=snapshot.nodes[found->second];
            require(parent.kind==DocumentNodeKind::element && !parent.masked && !parent.omitted,"Invalid native-v2 body parent");
            require(++emitted[n.parent]<=children[found->second],"Published children exceed native count");
            while (!ancestry.empty() && ancestry.back()!=n.parent) ancestry.pop_back();
            require(!ancestry.empty(),"Native-v2 body is not preorder");
        }
        const auto depth=n.parent ? depths.at(n.parent)+1 : 1; require(depth<=depth_limit,"Native-v2 depth limit exceeded");
        depths.emplace(n.id,depth);
        if (n.kind==DocumentNodeKind::text) {
            require(n.tag.empty() && n.name.empty() && n.value.empty() && n.href.empty() && !children[i] &&
                !n.masked && !n.omitted && !n.disabled && !n.editable,"Text node retains native element metadata");
        } else {
            require(!n.tag.empty(),"Empty native-v2 element tag"); charge(remaining_children,children[i]); ancestry.push_back(n.id);
        }
        if (n.masked || n.omitted) require(n.text.empty() && n.name.empty() && n.value.empty() && n.href.empty() && !n.editable,
            "Concealed native-v2 body field leak");
        positions.emplace(n.id,i);
    }
    std::set<std::uint64_t> metadata_ids, control_ids;
    std::optional<std::size_t> previous;
    for (auto& m:body.metadata) {
        const auto found=positions.find(m.node);
        require(found!=positions.end() && snapshot.nodes[found->second].kind==DocumentNodeKind::element && metadata_ids.insert(m.node).second,
            "Invalid native-v2 metadata join");
        require(!previous || found->second>*previous,"Native-v2 metadata order mismatch"); previous=found->second;
        auto& n=snapshot.nodes[found->second];
        if (n.masked || n.omitted) require(m.role.empty() && m.display.empty() && m.white_space.empty(),"Concealed native-v2 metadata leak");
        else n.white_space=whitespace(m.white_space,body.degraded.whitespace);
    }
    previous.reset();
    for (const auto& c:forms.controls) {
        node_id(c.node); const auto found=positions.find(c.node);
        require(found!=positions.end() && snapshot.nodes[found->second].kind==DocumentNodeKind::element,"Missing native-v2 control marker");
        require(!previous || found->second>*previous,"Native-v2 controls are not in body order"); previous=found->second;
        control_ids.insert(c.node); const auto& n=snapshot.nodes[found->second];
        require(safe_type(c.native_type) && tag_matches(c.native_type,n.tag),"Native-v2 type/tag mismatch");
        require(n.disabled==c.disabled && n.omitted==c.omitted && n.masked==(c.kind==F::FormKind::secure_readonly),"Native-v2 control redaction/flags mismatch");
        if (c.kind==F::FormKind::text || c.kind==F::FormKind::number || c.kind==F::FormKind::checkbox || c.kind==F::FormKind::secure_readonly)
            require(n.tag=="input","Native-v2 input marker mismatch");
        if (c.kind==F::FormKind::textarea) require(n.tag=="textarea","Native-v2 textarea marker mismatch");
        if (c.kind==F::FormKind::select_one || c.kind==F::FormKind::select_many) require(n.tag=="select","Native-v2 select marker mismatch");
        if (c.omitted) require(c.label.empty() && (c.kind==F::FormKind::secure_readonly || c.kind==F::FormKind::unsupported),"Omitted native-v2 control captured fields");
        if (snapshot.truncated) require(!c.capabilities && !c.lease,"Truncated native-v2 publication grants authority");
        const auto* text=std::get_if<F::FormTextState>(&c.state);
        require(n.text.empty() && n.href.empty() && n.name==c.label && n.value==(text ? text->value : std::string{}),"Native-v2 body/control value mismatch");
        if (c.focused) require(snapshot.active_node==c.node,"Native-v2 focused control mismatch");
        if (c.lease) { lease(*c.lease,expected); }
        if (const auto* select=std::get_if<F::FormSelectState>(&c.state)) {
            std::optional<std::size_t> last_option;
            for (const auto& o:select->options) {
                node_id(o.node);
                if (o.omitted) require(o.label.empty() && !c.complete && !c.capabilities && !c.lease,"Omitted option retains authority/label");
                const auto option=positions.find(o.node); if (option==positions.end()) continue;
                const auto& on=snapshot.nodes[option->second];
                require(on.kind==DocumentNodeKind::element && on.tag=="option" && !on.masked && on.omitted==o.omitted && on.disabled==o.disabled,
                    "Native-v2 option marker mismatch");
                require(!last_option || option->second>*last_option,"Native-v2 option order mismatch"); last_option=option->second;
                auto parent=on.parent;
                while (parent && snapshot.nodes[positions.at(parent)].tag!="select") parent=snapshot.nodes[positions.at(parent)].parent;
                require(parent==c.node,"Native-v2 option select ancestry mismatch");
            }
        }
        const auto metadata=std::find_if(body.metadata.begin(),body.metadata.end(),[&](const auto& m){return m.node==c.node;});
        if (metadata!=body.metadata.end()) {
            metadata->read_only=c.read_only;
            if (const auto* check=std::get_if<F::FormCheckState>(&c.state)) metadata->checked=check->checked;
        }
    }
    for (const auto& n:snapshot.nodes) if (n.masked) require(n.tag=="input" && control_ids.contains(n.id),"Secure marker lacks native descriptor");
    if (snapshot.active_node) {
        const auto active=positions.find(*snapshot.active_node);
        require(active!=positions.end() && snapshot.nodes[active->second].kind==DocumentNodeKind::element,"Invalid native-v2 active node");
    }
    if (result.selection) {
        require(!snapshot.truncated && !(result.native_degradation&8),"Unavailable native-v2 selection present");
        const auto endpoint=[&](DocumentNativePoint point) {
            const auto found=positions.find(point.node); require(found!=positions.end(),"Unpublished native-v2 selection endpoint");
            const auto& n=snapshot.nodes[found->second]; require(!n.masked && !n.omitted,"Concealed native-v2 selection endpoint");
            if (point.kind==DocumentNativeOffsetKind::text_utf16) {
                require(n.kind==DocumentNodeKind::text,"Native-v2 text endpoint names element");
                (void)F::form_byte_selection(n.text,{point.offset,point.offset,F::FormDirection::none});
            } else require(n.kind==DocumentNodeKind::element && point.offset<=children[found->second],"Invalid native-v2 child endpoint");
        };
        const auto& selection=*result.selection; endpoint(selection.endpoints.anchor); endpoint(selection.endpoints.focus);
        if (selection.focus_rect) {
            const auto& r=*selection.focus_rect;
            require(std::isfinite(r.x) && std::isfinite(r.y) && std::isfinite(r.width) && std::isfinite(r.height) && r.width>=0 && r.height>=0,
                "Invalid native-v2 selection geometry");
            body.original_selection=DocumentWireSelection{selection.endpoints,r};
        }
        if (selection.endpoints.anchor.kind==DocumentNativeOffsetKind::text_utf16 && selection.endpoints.focus.kind==DocumentNativeOffsetKind::text_utf16)
            snapshot.selection=DocumentSelection{{selection.endpoints.anchor.node,selection.endpoints.anchor.offset},{selection.endpoints.focus.node,selection.endpoints.focus.offset}};
        else body.degraded.element_selection=true;
    }
    body.degraded.whitespace=body.degraded.whitespace || (result.native_degradation&64);
    AppendedDocument checked; checked.accept(snapshot);
}
DocumentV2Publication publication(Reader& reader, DocumentV2Identity expected, std::uint64_t request_id) {
    DocumentV2Publication result; auto& joined=result.observation; auto& body=joined.body;
    require(reader.get_identity()==expected,"Native-v2 publication document mismatch"); joined.publication=reader.get_version();
    body.request_id=request_id; body.epoch=joined.publication.epoch;
    body.snapshot=DocumentSnapshot{}; auto& snapshot=*body.snapshot;
    snapshot.version={joined.publication.generation,joined.publication.epoch,joined.publication.revision};
    joined.forms.version=joined.publication; snapshot.truncated=reader.boolean();
    const auto revision=reader.integer(8), active=reader.integer(8), flags=reader.integer(4);
    require(revision && revision<=std::uint64_t(INT32_MAX) && flags<=31,"Unrepresentable native-v2 editor state");
    body.editor_state=DocumentEditorState{static_cast<std::uint32_t>(revision),static_cast<std::uint32_t>(flags)};
    if (active) { node_id(active); snapshot.active_node=active; }
    result.native_degradation=static_cast<std::uint32_t>(reader.integer(4));
    const auto nodes=reader.integer(4), metadata=reader.integer(4), controls=reader.integer(4);
    require(nodes<=record_limit && metadata<=record_limit && controls<=record_limit && nodes*42+metadata*20+controls*24+1<=reader.left(),
        "Invalid native-v2 publication counts");
    if (reader.boolean()) {
        DocumentV2NativeSelection selection; selection.endpoints.anchor=reader.endpoint(); selection.endpoints.focus=reader.endpoint();
        if (reader.boolean()) selection.focus_rect=gui::Rect{std::bit_cast<double>(reader.integer(8)),std::bit_cast<double>(reader.integer(8)),
            std::bit_cast<double>(reader.integer(8)),std::bit_cast<double>(reader.integer(8))};
        result.selection=selection;
    }
    snapshot.nodes.reserve(static_cast<std::size_t>(nodes)); body.metadata.reserve(static_cast<std::size_t>(metadata));
    joined.forms.controls.reserve(static_cast<std::size_t>(controls)); std::vector<std::uint32_t> children; children.reserve(static_cast<std::size_t>(nodes));
    for (std::uint64_t i=0;i<nodes;++i) {
        DocumentNode node; node.id=reader.integer(8); node.parent=reader.integer(8); const auto kind=reader.integer(1);
        if (kind==1) node.kind=DocumentNodeKind::element;
        else if (kind==2) node.kind=DocumentNodeKind::text;
        else throw std::invalid_argument("Unknown native-v2 node kind");
        const auto f=reader.flags(15); node.masked=f&1; node.omitted=f&2; node.disabled=f&4; node.editable=f&8;
        children.push_back(static_cast<std::uint32_t>(reader.integer(4)));
        node.tag=reader.string(reader.metadata_units); node.text=reader.string(reader.body_units); node.name=reader.string(reader.body_units);
        node.value=reader.string(reader.body_units); node.href=reader.string(reader.body_units); snapshot.nodes.push_back(std::move(node));
    }
    for (std::uint64_t i=0;i<metadata;++i) {
        DocumentNodeMetadata value; value.node=reader.integer(8); value.role=reader.string(reader.metadata_units);
        value.display=reader.string(reader.metadata_units); value.white_space=reader.string(reader.metadata_units); body.metadata.push_back(std::move(value));
    }
    for (std::uint64_t i=0;i<controls;++i) joined.forms.controls.push_back(reader.control());
    validate_publication(result,expected,children); return result;
}
} // namespace

DocumentV2Request encode_appended_document_v2(DocumentV2Identity expected, const DocumentFormsRequest& source) {
    identity(expected); require(source.token.generation==expected.application_instance && source.token.sequence,"Invalid native-v2 compositor request token");
    DocumentV2Request result; result.identity=expected; Writer writer;
    std::uint64_t nested=0; std::optional<F::FormAction> action;
    if (const auto* document=std::get_if<DocumentEngineRequest>(&source.action)) {
        require(!document->intent,"Native-v2 body actions are unsupported");
        require(document->token.generation==expected.application_instance && document->token.id && document->token.id<=safe_integer,
            "Invalid native-v2 nested document request"); nested=document->token.id; result.kind=DocumentV2RequestKind::snapshot_query; writer.header(1);
    } else {
        // Reject unbounded replacement input before copying its owned action.
        if (const auto* draft=std::get_if<F::FormDraftRequest>(&source.action)) validate_action(draft->action,expected);
        action=form_action(source); validate_action(*action,expected); result.kind=DocumentV2RequestKind::form_command; writer.header(2);
    }
    writer.integer(expected.application_instance,8); writer.integer(expected.service_generation,8); writer.integer(expected.document_sequence,8);
    writer.integer(source.token.sequence,8); writer.integer(nested,8);
    if (action) std::visit([&](const auto& value) {
        using T=std::decay_t<decltype(value)>;
        if constexpr (std::is_same_v<T,F::BeginFormControl>) { writer.integer(0,1); writer.put(value.expected); writer.integer(value.node,8); }
        else if constexpr (std::is_same_v<T,F::OpenFormPopup>) { writer.integer(4,1); writer.put(value.expected); writer.integer(value.node,8); }
        else {
            if constexpr (std::is_same_v<T,F::ReplaceFormText>) writer.integer(1,1);
            else if constexpr (std::is_same_v<T,F::SetFormChecked>) writer.integer(2,1);
            else if constexpr (std::is_same_v<T,F::SetFormOption>) writer.integer(3,1);
            else writer.integer(5,1);
            writer.put(value.expected);
            if constexpr (std::is_same_v<T,F::ReplaceFormText>) { writer.put(value.range); writer.string(value.text); }
            else if constexpr (std::is_same_v<T,F::SetFormChecked>) writer.integer(value.checked,1);
            else if constexpr (std::is_same_v<T,F::SetFormOption>) { writer.integer(value.option,8); writer.integer(value.selected,1); }
        }
    },*action);
    result.source=source; result.bytes=std::move(writer.bytes); return result;
}

DocumentV2Reply decode_appended_document_v2(std::span<const std::uint8_t> bytes, const DocumentV2Request& expected) {
    const auto canonical=encode_appended_document_v2(expected.identity,expected.source);
    require(expected.kind==canonical.kind && expected.bytes==canonical.bytes,"Changed native-v2 expected request");
    Reader reader(bytes); const bool query=expected.kind==DocumentV2RequestKind::snapshot_query; reader.header(query ? 4 : 5);
    require(reader.get_identity()==expected.identity && reader.integer(8)==expected.source.token.sequence,"Foreign native-v2 reply identity");
    const auto nested=query ? std::get<DocumentEngineRequest>(expected.source.action).token.id : 0;
    require(reader.integer(8)==nested,"Foreign native-v2 nested request identity");
    DocumentV2Reply result; result.token=expected.source.token;
    if (query) result.publication=publication(reader,expected.identity,nested);
    else {
        const auto outcome=reader.integer(1), code=reader.integer(1); require(outcome<=2 && code<=8,"Unknown native-v2 completion outcome/code");
        result.control=DocumentFormsControlReply{static_cast<F::FormDraftOutcome>(outcome),{}};
        const auto flags=reader.flags(3); result.action_status=DocumentV2ActionStatus{static_cast<DocumentV2CompletionCode>(code),(flags&1)!=0,(flags&2)!=0};
        require(!(result.action_status->effects_entered && result.control->outcome==F::FormDraftOutcome::rejected),"Post-effect native-v2 rejection");
        require(!result.action_status->popup_opened || result.action_status->effects_entered,"Native-v2 popup without effects");
        if (reader.boolean()) result.publication=publication(reader,expected.identity,0);
        if (result.control->outcome==F::FormDraftOutcome::accepted)
            require(result.publication && result.action_status->code==DocumentV2CompletionCode::ok,"Accepted native-v2 completion lacks readback");
        if (result.publication) {
            const auto node=target(form_action(expected.source)); const auto& joined=result.publication->observation;
            const auto found=std::find_if(joined.forms.controls.begin(),joined.forms.controls.end(),[&](const auto& control){return control.node==node;});
            if (found!=joined.forms.controls.end()) result.control->update=F::FormUpdate{joined.publication,*found};
        }
    }
    reader.finish(); return result;
}

DocumentV2Publication decode_appended_document_v2_publication(
    std::span<const std::uint8_t> bytes, DocumentV2Identity expected) {
    identity(expected);
    require(bytes.size() <= max_document_v2_publication_bytes, "Native-v2 publication byte limit exceeded");
    Reader reader(bytes);
    auto result = publication(reader, expected, 0);
    reader.finish();
    return result;
}

} // namespace foundation::ui
