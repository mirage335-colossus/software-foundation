#include "NativeDocumentV2Types.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>

namespace BIB::NativeDocumentV2 {
namespace {
[[noreturn]] void invalid(const char* s) { throw std::invalid_argument(s); }
struct Scalar { std::uint32_t code; std::size_t bytes; };
Scalar next(std::string_view s, std::size_t p) {
    const auto a = static_cast<unsigned char>(s[p]);
    std::uint32_t c; std::size_t n;
    if (a && a < 0x80) return {a,1};
    if (a >= 0xc2 && a <= 0xdf) { c=a&31; n=2; }
    else if (a >= 0xe0 && a <= 0xef) { c=a&15; n=3; }
    else if (a >= 0xf0 && a <= 0xf4) { c=a&7; n=4; }
    else invalid("invalid UTF8 scalar lead/NUL");
    if (n > s.size()-p) invalid("short UTF8 scalar");
    for (std::size_t i=1;i<n;++i) {
        const auto b=static_cast<unsigned char>(s[p+i]);
        if ((b&0xc0)!=0x80) invalid("invalid UTF8 continuation");
        c=(c<<6)|(b&63);
    }
    if ((n==2 && c<0x80)||(n==3 && c<0x800)||(n==4 && c<0x10000)||
        c>0x10ffff||(c>=0xd800&&c<=0xdfff)) invalid("noncanonical UTF8 scalar");
    return {c,n};
}
void charge(std::size_t& remaining, std::size_t n) {
    if (n>remaining) invalid("native-v2 budget exhausted");
    remaining-=n;
}
bool version(F::FormVersion v) { return v.generation&&v.epoch&&v.revision; }
void identity(Identity i) {
    if (!i.application_instance||!i.service_generation||!i.document_sequence) invalid("zero native identity");
}
void matches(F::FormVersion v, Identity i) {
    if (!version(v)||v.generation!=i.application_instance||v.epoch!=i.service_generation)
        invalid("native publication identity mismatch");
}
void range(F::FormControlRange r) {
    if (r.start>r.end||r.end>maxFieldUnits||static_cast<unsigned>(r.direction)>2)
        invalid("invalid action UTF16 range");
}
void lease(const F::FormLease& l, Identity i) {
    matches(l.captured,i);
    if (!l.node||!l.id) invalid("zero native lease identity");
}
void consumerID(std::uint64_t n) { if (n>maxConsumerInteger) invalid("consumer integer overflow"); }
bool safeNativeType(std::string_view type) {
    for (auto candidate:{"button","checkbox","color","date","datetime-local","email","file","hidden","image","month","number","password","radio","range","reset","search","submit","tel","text","time","url","week","fieldset","object","output","textarea","select-one","select-multiple"})
        if (type==candidate) return true;
    return false;
}
bool typeTagMatches(std::string_view type,std::string_view tag) {
    if (type=="textarea"||type=="fieldset"||type=="object"||type=="output") return tag==type;
    if (type=="select-one"||type=="select-multiple") return tag=="select";
    if (type=="button"||type=="reset"||type=="submit") return tag=="input"||tag=="button";
    return tag=="input";
}
} // namespace

std::size_t utf16Units(std::string_view s) {
    if (s.size()>maxFieldUnits*3) invalid("UTF8 string byte bound");
    std::size_t units=0;
    for (std::size_t p=0;p<s.size();) {
        const auto v=next(s,p); p+=v.bytes;
        units+=v.code>0xffff?2:1;
        if (units>maxFieldUnits) invalid("UTF16 field bound");
    }
    return units;
}
bool scalarBoundary(std::string_view s, std::uint32_t target) {
    (void)utf16Units(s);
    std::uint32_t units=0;
    if (!target) return true;
    for (std::size_t p=0;p<s.size();) {
        const auto v=next(s,p); p+=v.bytes; units+=v.code>0xffff?2:1;
        if (units==target) return true;
        if (units>target) return false;
    }
    return false;
}
std::string utf16ToUtf8(std::u16string_view s) {
    if (s.size()>maxFieldUnits) invalid("UTF16 field bound");
    // Validate all code units before allocation or conversion.
    for (std::size_t p=0;p<s.size();++p) {
        const auto c=s[p];
        if (!c) invalid("UTF16 NUL");
        if (c>=0xd800&&c<=0xdbff) {
            if (++p==s.size()||s[p]<0xdc00||s[p]>0xdfff) invalid("unpaired UTF16 surrogate");
        } else if (c>=0xdc00&&c<=0xdfff) invalid("unpaired UTF16 surrogate");
    }
    std::string out; out.reserve(s.size()*3);
    for (std::size_t p=0;p<s.size();++p) {
        std::uint32_t c=s[p];
        if (c>=0xd800&&c<=0xdbff) { c=0x10000+((c-0xd800)<<10)+(s[p+1]-0xdc00); ++p; }
        if (c<0x80) out.push_back(static_cast<char>(c));
        else if (c<0x800) {
            out.push_back(static_cast<char>(0xc0|(c>>6))); out.push_back(static_cast<char>(0x80|(c&63)));
        } else if (c<0x10000) {
            out.push_back(static_cast<char>(0xe0|(c>>12))); out.push_back(static_cast<char>(0x80|((c>>6)&63)));
            out.push_back(static_cast<char>(0x80|(c&63)));
        } else {
            out.push_back(static_cast<char>(0xf0|(c>>18))); out.push_back(static_cast<char>(0x80|((c>>12)&63)));
            out.push_back(static_cast<char>(0x80|((c>>6)&63))); out.push_back(static_cast<char>(0x80|(c&63)));
        }
    }
    return out;
}
std::u16string utf8ToUtf16(std::string_view s) {
    std::u16string out; out.reserve(utf16Units(s));
    for (std::size_t p=0;p<s.size();) {
        auto v=next(s,p); p+=v.bytes;
        if (v.code<=0xffff) out.push_back(static_cast<char16_t>(v.code));
        else { v.code-=0x10000; out.push_back(static_cast<char16_t>(0xd800+(v.code>>10)));
               out.push_back(static_cast<char16_t>(0xdc00+(v.code&1023))); }
    }
    return out;
}
void ReadBudget::chargeString(TextSection section,std::size_t n) {
    const auto index=static_cast<unsigned>(section);
    if (index>3||n>maxFieldUnits) invalid("invalid native string charge");
    charge(text_[index],n);
}
void ReadBudget::chargeNode() { charge(nodes_,1); }
void ReadBudget::chargeControl() { charge(controls_,1); }
void ReadBudget::chargeOption() { charge(options_,1); }
void ReadBudget::chargeTraversal(std::size_t n) { charge(traversal_,n); }
void ReadBudget::chargeEvidence(std::size_t n) { charge(evidence_,n); }
void ReadBudget::checkDepth(std::size_t n) const { if (n>maxDepth) invalid("native depth bound"); }
std::size_t ReadBudget::remaining(TextSection s) const noexcept {
    const auto index=static_cast<unsigned>(s); return index<4?text_[index]:0;
}
std::optional<std::uint64_t> Counter::reserve() noexcept {
    if (retired_||high_==std::numeric_limits<std::uint64_t>::max()) { retired_=true; return {}; }
    return ++high_;
}
void validateQuery(const Query& q) {
    identity(q.identity);
    if (!q.outer_sequence||!q.document_request_id) invalid("zero request sequence");
}
void validateActionPrefix(const Query& q) {
    identity(q.identity);
    if (!q.outer_sequence||q.document_request_id) invalid("invalid action correlation prefix");
}
void validateActionRequest(const ActionRequest& q) {
    validateActionPrefix(q.request);
    std::visit([&](const auto& a) {
        using A=std::decay_t<decltype(a)>;
        if constexpr (std::is_same_v<A,F::BeginFormControl>||std::is_same_v<A,F::OpenFormPopup>) {
            matches(a.expected,q.request.identity); if (!a.node) invalid("zero action node");
        } else {
            lease(a.expected,q.request.identity);
            if constexpr (std::is_same_v<A,F::ReplaceFormText>) { range(a.range); (void)utf16Units(a.text); }
            if constexpr (std::is_same_v<A,F::SetFormOption>) { if (!a.option) invalid("zero option identity"); }
        }
    },q.action);
}
void validatePublication(const OwnedPublication& p) {
    identity(p.identity); matches(p.version,p.identity);
    if (!p.editor.revision||(p.editor.flags&~31U)||(p.degradation&~127U)) invalid("invalid editor/degradation state");
    if (p.nodes.size()>maxNodes||p.metadata.size()>maxNodes)
        invalid("invalid body or metadata count");
    if (p.nodes.empty()&&(!p.metadata.empty()||!p.forms.controls.empty()||p.editor.active_node||p.selection))
        invalid("empty native forest retains nonempty joins");
    if (p.forms.protocol!=2||p.forms.version!=p.version) invalid("unpaired forms publication");
    // Exact public form policy, including scalar-boundary editing ranges,
    // native-type allowlist, aggregate/options, secure state, caps and leases.
    F::validate_document_forms(p.forms);
    ReadBudget budget;
    std::map<std::uint64_t,const Node*> nodes;
    std::map<std::uint64_t,std::size_t> depths;
    std::map<std::uint64_t,std::size_t> indexes;
    std::map<std::uint64_t,std::size_t> emittedChildren;
    std::vector<std::uint64_t> ancestry;
    for (const auto& n:p.nodes) {
        budget.chargeNode();
        if (!n.id||nodes.contains(n.id)) invalid("duplicate body node identity");
        indexes.emplace(n.id,indexes.size());
        if (n.kind!=NodeKind::element&&n.kind!=NodeKind::text) invalid("unknown body node kind");
        if (!n.parent) {
            if (n.kind!=NodeKind::element) invalid("body root is not a native element");
            ancestry.clear();
        } else {
            const auto parent=nodes.find(n.parent);
            if (parent==nodes.end()||parent->second->kind!=NodeKind::element||parent->second->masked||parent->second->omitted)
                invalid("invalid/suppressed body parent");
            if (++emittedChildren[n.parent]>parent->second->native_child_count)
                invalid("published children exceed native child count");
            while (!ancestry.empty()&&ancestry.back()!=n.parent) ancestry.pop_back();
            if (ancestry.empty()) invalid("body is not native preorder");
        }
        const auto depth=n.parent?depths.at(n.parent)+1:1;
        budget.checkDepth(depth); depths.emplace(n.id,depth);
        budget.chargeMetadata(utf16Units(n.tag));
        budget.chargeBody(utf16Units(n.text)); budget.chargeBody(utf16Units(n.name));
        budget.chargeBody(utf16Units(n.value)); budget.chargeBody(utf16Units(n.href));
        if (n.kind==NodeKind::text) {
            if (!n.tag.empty()||!n.name.empty()||!n.value.empty()||!n.href.empty()||n.native_child_count||n.masked||n.omitted||n.disabled||n.editable)
                invalid("text node has element metadata");
        } else {
            if (n.tag.empty()||n.native_child_count>maxTraversal) invalid("invalid native element metadata");
            budget.chargeTraversal(n.native_child_count);
            ancestry.push_back(n.id);
        }
        if ((n.masked||n.omitted)&&(!n.text.empty()||!n.name.empty()||!n.value.empty()||!n.href.empty()))
            invalid("suppressed body field leak");
        if ((n.masked||n.omitted)&&n.editable) invalid("suppressed native node grants editing");
        nodes.emplace(n.id,&n);
    }
    std::set<std::uint64_t> metadata;
    std::optional<std::size_t> lastMetadata;
    for (const auto& m:p.metadata) {
        const auto n=nodes.find(m.node);
        if (n==nodes.end()||n->second->kind!=NodeKind::element||!metadata.insert(m.node).second)
            invalid("invalid metadata element join");
        if (lastMetadata&&indexes.at(m.node)<=*lastMetadata) invalid("metadata is not in native body order");
        lastMetadata=indexes.at(m.node);
        budget.chargeMetadata(utf16Units(m.role)); budget.chargeMetadata(utf16Units(m.display));
        budget.chargeMetadata(utf16Units(m.white_space));
        if ((n->second->masked||n->second->omitted)&&(!m.role.empty()||!m.display.empty()||!m.white_space.empty()))
            invalid("suppressed metadata leak");
    }
    std::set<std::uint64_t> controlIDs;
    std::optional<std::size_t> lastControl;
    for (const auto& c:p.forms.controls) {
        if (!safeNativeType(c.native_type)) invalid("unsafe native form type name");
        const auto n=nodes.find(c.node);
        if (n==nodes.end()||n->second->kind!=NodeKind::element) invalid("control missing native body marker");
        if (lastControl&&indexes.at(c.node)<=*lastControl) invalid("controls are not in native body order");
        lastControl=indexes.at(c.node);
        controlIDs.insert(c.node);
        const auto& b=*n->second;
        if (!typeTagMatches(c.native_type,b.tag)) invalid("native form type/tag mismatch");
        if (b.disabled!=c.disabled) invalid("body/form disabled flag mismatch");
        if ((c.kind==F::FormKind::text||c.kind==F::FormKind::number||c.kind==F::FormKind::checkbox||c.kind==F::FormKind::secure_readonly)&&b.tag!="input")
            invalid("input form native element mismatch");
        if ((c.kind==F::FormKind::textarea&&b.tag!="textarea")||
            ((c.kind==F::FormKind::select_one||c.kind==F::FormKind::select_many)&&b.tag!="select"))
            invalid("form native element mismatch");
        if (b.omitted!=c.omitted||b.masked!=(c.kind==F::FormKind::secure_readonly)) invalid("body/form redaction mismatch");
        if (b.masked&&b.tag!="input") invalid("secure control is not input");
        if (c.omitted&&c.kind!=F::FormKind::secure_readonly&&c.kind!=F::FormKind::unsupported)
            invalid("omitted form captures state");
        if (c.omitted&&!c.label.empty()) invalid("omitted form label leak");
        if (p.truncated&&(c.capabilities||c.lease)) invalid("truncated publication grants actions");
        if (!b.text.empty()||!b.href.empty()||b.name!=c.label) invalid("body/form label mismatch");
        const auto* t=std::get_if<F::FormTextState>(&c.state);
        if (b.value!=(t?t->value:std::string{})) invalid("body/form canonical value mismatch");
        if (c.focused&&p.editor.active_node!=c.node) invalid("focused control/editor mismatch");
        std::optional<std::size_t> lastOption;
        if (const auto* s=std::get_if<F::FormSelectState>(&c.state)) for (const auto& o:s->options) {
            if (o.omitted&&(!o.label.empty()||c.complete||c.capabilities||c.lease))
                invalid("omitted option leaks text or grants incomplete control authority");
            const auto on=nodes.find(o.node);
            if (on!=nodes.end()&&(on->second->kind!=NodeKind::element||on->second->tag!="option")) invalid("option native node kind mismatch");
            if (on!=nodes.end()) {
                if (on->second->masked||on->second->omitted!=o.omitted||on->second->disabled!=o.disabled)
                    invalid("option body/form flags mismatch");
                if (lastOption&&indexes.at(o.node)<=*lastOption) invalid("options are not in native body order");
                lastOption=indexes.at(o.node);
                auto ancestor=on->second->parent;
                while (ancestor&&nodes.at(ancestor)->tag!="select") ancestor=nodes.at(ancestor)->parent;
                if (ancestor!=c.node) invalid("option is not descendant of its native select");
            }
        }
    }
    for (const auto& n:p.nodes) if (n.masked&&!controlIDs.contains(n.id)) invalid("secure marker lacks safe descriptor");
    if (p.editor.active_node) {
        const auto n=nodes.find(p.editor.active_node);
        if (n==nodes.end()||n->second->kind!=NodeKind::element)
            invalid("invalid active native node");
    }
    if (p.selection) {
        if (p.truncated||(p.degradation&8)) invalid("unavailable/truncated selection is present");
        const auto endpoint=[&](const Endpoint& e) {
            const auto n=nodes.find(e.node);
            if (n==nodes.end()||n->second->masked||n->second->omitted) invalid("selection endpoint unpublished or suppressed");
            if (e.kind==EndpointKind::text_utf16) {
                if (n->second->kind!=NodeKind::text||!scalarBoundary(n->second->text,e.offset)) invalid("invalid native text endpoint");
            } else if (e.kind==EndpointKind::element_child) {
                if (n->second->kind!=NodeKind::element||e.offset>n->second->native_child_count) invalid("invalid native child endpoint");
            } else invalid("unknown native endpoint kind");
        };
        endpoint(p.selection->anchor); endpoint(p.selection->focus);
        if (p.selection->rect) {
            const auto r=*p.selection->rect;
            if (!std::isfinite(r.x)||!std::isfinite(r.y)||!std::isfinite(r.width)||!std::isfinite(r.height)||r.width<0||r.height<0)
                invalid("nonfinite/negative native selection geometry");
        }
    }
}
void validateCompletion(const Completion& c) {
    validateActionPrefix(c.request);
    if (static_cast<unsigned>(c.outcome)>2||static_cast<unsigned>(c.code)>8) invalid("unknown completion outcome/code");
    if (c.effects_entered&&c.outcome==F::FormDraftOutcome::rejected) invalid("post-effect result cannot claim rejection");
    if (c.popup_opened&&!c.effects_entered) invalid("popup without effects");
    if (c.outcome==F::FormDraftOutcome::accepted&&(!c.publication||c.code!=CompletionCode::ok)) invalid("accepted completion lacks readback");
    if (c.publication) { validatePublication(*c.publication); if (c.publication->identity!=c.request.identity) invalid("completion document mismatch"); }
}
void validateConsumerRepresentability(const Reply& r) {
    validateQuery(r.request); validatePublication(r.publication);
    if (r.request.identity!=r.publication.identity) invalid("reply document mismatch");
    const auto& p=r.publication;
    consumerID(r.request.document_request_id); consumerID(p.version.revision);
    if (p.version.epoch>std::numeric_limits<std::uint32_t>::max()||p.editor.revision>std::numeric_limits<std::int32_t>::max())
        invalid("consumer epoch/editor overflow");
    for (const auto& n:p.nodes) { consumerID(n.id); consumerID(n.parent); }
    for (const auto& c:p.forms.controls) {
        consumerID(c.node); if(c.lease) consumerID(c.lease->captured.revision);
        if (const auto* s=std::get_if<F::FormSelectState>(&c.state)) for (const auto& o:s->options) consumerID(o.node);
    }
}
} // namespace BIB::NativeDocumentV2
