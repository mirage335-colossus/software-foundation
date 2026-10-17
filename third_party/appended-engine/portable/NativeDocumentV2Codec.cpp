#include "NativeDocumentV2Codec.hpp"
#include <algorithm>
#include <bit>
#include <limits>
#include <stdexcept>
#include <type_traits>

namespace BIB::NativeDocumentV2 {
namespace {
[[noreturn]] void invalid(const char* s) { throw std::invalid_argument(s); }
static_assert(maxEncodedCompletionBytes <= maxReplyBytes);
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559);
struct Writer {
    Bytes b;
    Writer() { b.reserve(serviceReplyBytes); }
    void integer(std::uint64_t v,std::size_t n) {
        if (n>maxReplyBytes-b.size()) invalid("encoded reply limit");
        for (std::size_t i=0;i<n;++i) b.push_back(static_cast<std::uint8_t>(v>>(i*8)));
    }
    void byte(unsigned v) { integer(v,1); }
    void str(std::string_view s) {
        integer(s.size(),4);
        if (s.size()>maxReplyBytes-b.size()) invalid("encoded reply limit");
        b.insert(b.end(),s.begin(),s.end());
    }
    void header(PacketKind k) { for (auto c:std::string_view("NDV2")) byte(static_cast<unsigned char>(c)); integer(2,2); byte(static_cast<unsigned>(k)); byte(0); }
};
struct Reader {
    std::span<const std::uint8_t> b;
    std::size_t p{0};
    ReadBudget budget;
    explicit Reader(std::span<const std::uint8_t> input): b(input) { if(b.size()>maxReplyBytes) invalid("packet byte limit"); }
    std::size_t left() const { return b.size()-p; }
    std::uint64_t integer(std::size_t n) {
        if(n>left()) invalid("short native-v2 packet");
        std::uint64_t v=0; for(std::size_t i=0;i<n;++i) v|=static_cast<std::uint64_t>(b[p++])<<(8*i); return v;
    }
    std::uint8_t byte() { return static_cast<std::uint8_t>(integer(1)); }
    bool boolean() { const auto v=byte(); if(v>1) invalid("noncanonical boolean"); return v!=0; }
    std::uint8_t flags(std::uint8_t mask) { const auto v=byte(); if(v&~mask) invalid("unknown flags"); return v; }
    std::string str(TextSection section) {
        const auto n=integer(4);
        if(n>maxFieldUnits*3||n>left()) invalid("invalid bounded string length");
        const std::string_view s(reinterpret_cast<const char*>(b.data()+p),static_cast<std::size_t>(n));
        budget.chargeString(section,utf16Units(s));
        p+=static_cast<std::size_t>(n); return std::string(s);
    }
    std::size_t count(std::size_t maximum,std::size_t minBytes) {
        const auto n=integer(4);
        if(n>maximum||n>left()/minBytes) invalid("invalid bounded record count");
        return static_cast<std::size_t>(n);
    }
    void header(PacketKind expected) {
        if(integer(4)!=0x3256444e||integer(2)!=2||byte()!=static_cast<unsigned>(expected)||byte()!=0)
            invalid("unknown native-v2 header");
    }
    void finish() { if(left()) invalid("trailing native-v2 bytes"); }
};
void putIdentity(Writer& w,Identity v) { w.integer(v.application_instance,8); w.integer(v.service_generation,8); w.integer(v.document_sequence,8); }
Identity getIdentity(Reader& r) { return {r.integer(8),r.integer(8),r.integer(8)}; }
void putVersion(Writer& w,F::FormVersion v) { w.integer(v.generation,8); w.integer(v.epoch,8); w.integer(v.revision,8); }
F::FormVersion getVersion(Reader& r) { return {r.integer(8),r.integer(8),r.integer(8)}; }
void putQuery(Writer& w,const Query& q) { putIdentity(w,q.identity); w.integer(q.outer_sequence,8); w.integer(q.document_request_id,8); }
Query getQuery(Reader& r,bool action=false) { Query q; q.identity=getIdentity(r); q.outer_sequence=r.integer(8); q.document_request_id=r.integer(8); if(action) validateActionPrefix(q); else validateQuery(q); return q; }
void putLease(Writer& w,const F::FormLease& l) { putVersion(w,l.captured); w.integer(l.node,8); w.integer(l.id,8); }
F::FormLease getLease(Reader& r) { F::FormLease l; l.captured=getVersion(r); l.node=r.integer(8); l.id=r.integer(8); return l; }
void putRange(Writer& w,F::FormControlRange v) { w.integer(v.start,4); w.integer(v.end,4); w.byte(static_cast<unsigned>(v.direction)); }
F::FormControlRange getRange(Reader& r) { F::FormControlRange v; v.start=static_cast<std::uint32_t>(r.integer(4)); v.end=static_cast<std::uint32_t>(r.integer(4)); const auto d=r.byte(); if(d>2) invalid("unknown form range direction"); v.direction=static_cast<F::FormDirection>(d); return v; }
void putControl(Writer& w,const F::FormControl& c) {
    w.integer(c.node,8); w.byte(static_cast<unsigned>(c.kind));
    w.byte((c.disabled?1:0)|(c.read_only?2:0)|(c.focusable?4:0)|(c.focused?8:0)|(c.omitted?16:0)|(c.complete?32:0));
    w.integer(c.capabilities,4); w.byte(static_cast<unsigned>(c.state.index())); w.byte(c.lease.has_value());
    w.str(c.native_type); w.str(c.label); if(c.lease) putLease(w,*c.lease);
    if(const auto* t=std::get_if<F::FormTextState>(&c.state)) {
        w.str(t->value); w.str(t->editing_text); w.byte(t->selection.has_value()); if(t->selection) putRange(w,*t->selection);
    } else if(const auto* check=std::get_if<F::FormCheckState>(&c.state)) {
        w.byte(check->checked); w.byte(check->indeterminate);
    } else if(const auto* s=std::get_if<F::FormSelectState>(&c.state)) {
        w.byte((s->multiple?1:0)|(s->menu_list?2:0)); w.integer(s->options.size(),4);
        for(const auto& o:s->options) { w.integer(o.node,8); w.byte((o.selected?1:0)|(o.disabled?2:0)|(o.omitted?4:0)); w.str(o.label); }
    }
}
F::FormControl getControl(Reader& r) {
    r.budget.control(); F::FormControl c; c.node=r.integer(8);
    const auto kind=r.byte(); if(kind>7) invalid("unknown control kind"); c.kind=static_cast<F::FormKind>(kind);
    const auto f=r.flags(63); c.disabled=f&1; c.read_only=f&2; c.focusable=f&4; c.focused=f&8; c.omitted=f&16; c.complete=f&32;
    c.capabilities=static_cast<std::uint32_t>(r.integer(4)); const auto tag=r.byte(); if(tag>3) invalid("unknown form state tag");
    const auto hasLease=r.boolean(); c.native_type=r.str(TextSection::forms); c.label=r.str(TextSection::forms);
    if(hasLease) c.lease=getLease(r);
    if(tag==1) {
        F::FormTextState t; t.value=r.str(TextSection::forms); t.editing_text=r.str(TextSection::forms);
        if(r.boolean()) t.selection=getRange(r);
        c.state=std::move(t);
    } else if(tag==2) { F::FormCheckState v; v.checked=r.boolean(); v.indeterminate=r.boolean(); c.state=v; }
    else if(tag==3) {
        F::FormSelectState s; const auto f2=r.flags(3); s.multiple=f2&1; s.menu_list=f2&2;
        const auto n=r.count(maxOptions,13); s.options.reserve(n);
        for(std::size_t i=0;i<n;++i) {
            r.budget.option(); F::FormOption o; o.node=r.integer(8); const auto f3=r.flags(7);
            o.selected=f3&1; o.disabled=f3&2; o.omitted=f3&4; o.label=r.str(TextSection::forms); s.options.push_back(std::move(o));
        }
        c.state=std::move(s);
    }
    return c;
}
void putEndpoint(Writer& w,const Endpoint& e) { w.integer(e.node,8); w.byte(static_cast<unsigned>(e.kind)); w.integer(e.offset,4); }
Endpoint getEndpoint(Reader& r) { Endpoint e; e.node=r.integer(8); const auto k=r.byte(); if(k<1||k>2) invalid("unknown endpoint kind"); e.kind=static_cast<EndpointKind>(k); e.offset=static_cast<std::uint32_t>(r.integer(4)); return e; }
void putPublication(Writer& w,const OwnedPublication& p) {
    putIdentity(w,p.identity); putVersion(w,p.version); w.byte(p.truncated);
    w.integer(p.editor.revision,8); w.integer(p.editor.active_node,8); w.integer(p.editor.flags,4); w.integer(p.degradation,4);
    w.integer(p.nodes.size(),4); w.integer(p.metadata.size(),4); w.integer(p.forms.controls.size(),4);
    w.byte(p.selection.has_value());
    if(p.selection) {
        putEndpoint(w,p.selection->anchor); putEndpoint(w,p.selection->focus); w.byte(p.selection->rect.has_value());
        if(p.selection->rect) { const auto v=*p.selection->rect; for(double d:{v.x,v.y,v.width,v.height}) w.integer(std::bit_cast<std::uint64_t>(d),8); }
    }
    for(const auto& n:p.nodes) {
        w.integer(n.id,8); w.integer(n.parent,8); w.byte(static_cast<unsigned>(n.kind)); w.byte((n.masked?1:0)|(n.omitted?2:0)|(n.disabled?4:0)|(n.editable?8:0));
        w.integer(n.native_child_count,4); w.str(n.tag); w.str(n.text); w.str(n.name); w.str(n.value); w.str(n.href);
    }
    for(const auto& m:p.metadata) { w.integer(m.node,8); w.str(m.role); w.str(m.display); w.str(m.white_space); }
    for(const auto& c:p.forms.controls) putControl(w,c);
}
OwnedPublication getPublication(Reader& r) {
    OwnedPublication p; p.identity=getIdentity(r); p.version=getVersion(r); p.forms.version=p.version;
    p.truncated=r.boolean(); p.editor.revision=r.integer(8); p.editor.active_node=r.integer(8);
    p.editor.flags=static_cast<std::uint32_t>(r.integer(4)); p.degradation=static_cast<std::uint32_t>(r.integer(4));
    // Three counts occur consecutively; check global physical minimum before
    // allocating any vectors, then check per-record lengths before each copy.
    const auto nn=r.integer(4),nm=r.integer(4),nc=r.integer(4);
    if(nn>maxNodes||nm>maxNodes||nc>maxControls||nn*42+nm*20+nc*24+1>r.left()) invalid("invalid publication record counts");
    if(r.boolean()) {
        NativeSelection s; s.anchor=getEndpoint(r); s.focus=getEndpoint(r);
        if(r.boolean()) { Rect v; v.x=std::bit_cast<double>(r.integer(8)); v.y=std::bit_cast<double>(r.integer(8)); v.width=std::bit_cast<double>(r.integer(8)); v.height=std::bit_cast<double>(r.integer(8)); s.rect=v; }
        p.selection=s;
    }
    p.nodes.reserve(static_cast<std::size_t>(nn)); p.metadata.reserve(static_cast<std::size_t>(nm)); p.forms.controls.reserve(static_cast<std::size_t>(nc));
    for(std::uint64_t i=0;i<nn;++i) {
        r.budget.chargeNode(); Node n; n.id=r.integer(8); n.parent=r.integer(8); const auto k=r.byte();
        if(k<1||k>2) invalid("unknown node kind");
        n.kind=static_cast<NodeKind>(k);
        const auto f=r.flags(15); n.masked=f&1; n.omitted=f&2; n.disabled=f&4; n.editable=f&8; n.native_child_count=static_cast<std::uint32_t>(r.integer(4));
        n.tag=r.str(TextSection::metadata); n.text=r.str(TextSection::body); n.name=r.str(TextSection::body); n.value=r.str(TextSection::body); n.href=r.str(TextSection::body); p.nodes.push_back(std::move(n));
    }
    for(std::uint64_t i=0;i<nm;++i) { Metadata m; m.node=r.integer(8); m.role=r.str(TextSection::metadata); m.display=r.str(TextSection::metadata); m.white_space=r.str(TextSection::metadata); p.metadata.push_back(std::move(m)); }
    for(std::uint64_t i=0;i<nc;++i) p.forms.controls.push_back(getControl(r));
    validatePublication(p); return p;
}
void validateReply(const Reply& r) { validateQuery(r.request); validatePublication(r.publication); if(r.request.identity!=r.publication.identity) invalid("unpaired reply identity"); }
} // namespace

Bytes encodeQuery(const Query& q) { validateQuery(q); Writer w; w.header(PacketKind::query); putQuery(w,q); return std::move(w.b); }
Query decodeQuery(std::span<const std::uint8_t> b) { Reader r(b); r.header(PacketKind::query); auto q=getQuery(r); r.finish(); return q; }
Bytes encodeAction(const ActionRequest& q) {
    validateActionRequest(q); Writer w; w.header(PacketKind::action); putQuery(w,q.request); w.byte(static_cast<unsigned>(q.action.index()));
    std::visit([&](const auto& a) {
        using A=std::decay_t<decltype(a)>;
        if constexpr(std::is_same_v<A,F::BeginFormControl>||std::is_same_v<A,F::OpenFormPopup>) { putVersion(w,a.expected); w.integer(a.node,8); }
        else {
            putLease(w,a.expected);
            if constexpr(std::is_same_v<A,F::ReplaceFormText>) { putRange(w,a.range); w.str(a.text); }
            else if constexpr(std::is_same_v<A,F::SetFormChecked>) w.byte(a.checked);
            else if constexpr(std::is_same_v<A,F::SetFormOption>) { w.integer(a.option,8); w.byte(a.selected); }
        }
    },q.action);
    return std::move(w.b);
}
ActionRequest decodeAction(std::span<const std::uint8_t> b) {
    Reader r(b); r.header(PacketKind::action); ActionRequest q; q.request=getQuery(r,true); const auto tag=r.byte();
    switch(tag) {
    case 0: { const auto v=getVersion(r); const auto node=r.integer(8); q.action=F::BeginFormControl{v,node}; break; }
    case 1: { auto l=getLease(r); auto range=getRange(r); auto text=r.str(TextSection::forms); q.action=F::ReplaceFormText{l,range,std::move(text)}; break; }
    case 2: { auto l=getLease(r); const auto v=r.boolean(); q.action=F::SetFormChecked{l,v}; break; }
    case 3: { auto l=getLease(r); const auto node=r.integer(8); const auto v=r.boolean(); q.action=F::SetFormOption{l,node,v}; break; }
    case 4: { const auto v=getVersion(r); const auto node=r.integer(8); q.action=F::OpenFormPopup{v,node}; break; }
    case 5: q.action=F::FinishFormControl{getLease(r)}; break;
    default: invalid("unknown form action tag");
    }
    r.finish(); validateActionRequest(q); return q;
}
Bytes encodePublication(const OwnedPublication& p) { validatePublication(p); Writer w; w.header(PacketKind::publication); putPublication(w,p); return std::move(w.b); }
OwnedPublication decodePublication(std::span<const std::uint8_t> b) { Reader r(b); r.header(PacketKind::publication); auto p=getPublication(r); r.finish(); return p; }
Bytes encodePublicationRecord(const OwnedPublication& p) {
    validatePublication(p); Writer w; putPublication(w,p);
    if(w.b.size()>maxPublicationRecordBytes) invalid("publication record byte limit");
    return std::move(w.b);
}
OwnedPublication decodePublicationRecord(std::span<const std::uint8_t> b) {
    if(b.size()>maxPublicationRecordBytes) invalid("publication record byte limit");
    Reader r(b); auto p=getPublication(r); r.finish(); return p;
}
Bytes encodeReply(const Reply& q) { validateReply(q); Writer w; w.header(PacketKind::reply); putQuery(w,q.request); putPublication(w,q.publication); return std::move(w.b); }
Reply decodeReply(std::span<const std::uint8_t> b) { Reader r(b); r.header(PacketKind::reply); Reply q; q.request=getQuery(r); q.publication=getPublication(r); r.finish(); validateReply(q); return q; }
Bytes encodeCompletion(const Completion& c) {
    validateCompletion(c); Writer w; w.header(PacketKind::completion); putQuery(w,c.request); w.byte(static_cast<unsigned>(c.outcome)); w.byte(static_cast<unsigned>(c.code));
    w.byte((c.effects_entered?1:0)|(c.popup_opened?2:0)); w.byte(c.publication.has_value()); if(c.publication) putPublication(w,*c.publication); return std::move(w.b);
}
Completion decodeCompletion(std::span<const std::uint8_t> b) {
    Reader r(b); r.header(PacketKind::completion); Completion c; c.request=getQuery(r,true);
    const auto outcome=r.byte(),code=r.byte(); if(outcome>2||code>8) invalid("unknown completion status");
    c.outcome=static_cast<F::FormDraftOutcome>(outcome); c.code=static_cast<CompletionCode>(code); const auto f=r.flags(3); c.effects_entered=f&1; c.popup_opened=f&2;
    if(r.boolean()) c.publication=getPublication(r);
    r.finish(); validateCompletion(c); return c;
}
Query admitRequestPrefix(std::span<const std::uint8_t> b,PacketKind kind,Identity expected) {
    if(kind!=PacketKind::query&&kind!=PacketKind::action) invalid("invalid request packet kind");
    Reader r(b); r.header(kind); auto q=getQuery(r,kind==PacketKind::action); if(q.identity!=expected) invalid("request prefix identity mismatch");
    if(kind==PacketKind::query) r.finish();
    return q;
}
ReplyReservation::ReplyReservation(std::size_t capacity) {
    if(capacity<maxReplyBytes) invalid("native reply capacity must precede effects");
    storage_.resize(maxReplyBytes);
}
void ReplyReservation::retain(std::span<const std::uint8_t> b) {
    if(b.size()>storage_.size()) invalid("completion exceeds reserved storage");
    if(retained_) {
        if(b.size()!=used_||!std::equal(b.begin(),b.end(),storage_.begin())) invalid("immutable completion replacement");
        return;
    }
    std::copy(b.begin(),b.end(),storage_.begin()); used_=b.size(); retained_=true;
}
std::span<const std::uint8_t> ReplyReservation::bytes() const noexcept { return {storage_.data(),used_}; }
PreparedPublication preparePublication(OwnedPublication p) {
    auto encoded=std::make_shared<const Bytes>(encodePublication(p));
    auto publication=std::make_shared<const OwnedPublication>(std::move(p));
    return {std::move(publication),std::move(encoded)};
}
void PublicationSlot::commit(PreparedPublication&& p) noexcept {
    if (!p.publication_||!p.encoded_) return;
    current_.publication_=std::move(p.publication_);
    current_.encoded_=std::move(p.encoded_);
}
} // namespace BIB::NativeDocumentV2
