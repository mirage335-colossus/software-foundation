// SPDX-License-Identifier: CC0-1.0
#include "native_editor_codec.hpp"

#include <array>
#include <bit>
#include <cmath>
#include <limits>
#include <string_view>
#include <utility>

namespace foundation::ui::native_editor::codec {
namespace {
using View = std::span<const std::uint8_t>;
constexpr std::size_t text_limit = BIB_ENGINE_EDITOR_MAX_TEXT_BYTES;
constexpr std::size_t dependencies_limit = BIB_ENGINE_EDITOR_MAX_DEPENDENCIES;
constexpr std::size_t groups_limit = BIB_ENGINE_EDITOR_MAX_GROUPS;
constexpr std::array<std::uint8_t, 8> magic{'B','I','B','E','D','V','1',0};
static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559
    && std::numeric_limits<double>::digits == 53 && sizeof(std::size_t) >= 4);

bool utf8(std::string_view value, std::size_t bound, bool nonempty = false, bool ascii = false) noexcept {
    if (value.size() > bound || (nonempty && value.empty())) return false;
    for (std::size_t i = 0; i < value.size();) {
        const auto first = static_cast<unsigned char>(value[i++]);
        if (ascii && (first < 0x21 || first > 0x7e)) return false;
        if (first >= 1 && first <= 0x7f) continue;
        unsigned remaining{}; std::uint32_t scalar{}, minimum{};
        if (first >= 0xc2 && first <= 0xdf) { remaining=1; scalar=first&31u; minimum=0x80; }
        else if (first >= 0xe0 && first <= 0xef) { remaining=2; scalar=first&15u; minimum=0x800; }
        else if (first >= 0xf0 && first <= 0xf4) { remaining=3; scalar=first&7u; minimum=0x10000; }
        else return false;
        if (remaining > value.size()-i) return false;
        while (remaining--) {
            const auto next = static_cast<unsigned char>(value[i++]);
            if ((next & 0xc0u) != 0x80u) return false;
            scalar=(scalar<<6u)|(next&63u);
        }
        if (scalar < minimum || scalar > 0x10ffff || (scalar >= 0xd800 && scalar <= 0xdfff)) return false;
    }
    return true;
}
bool boundary(std::string_view value, std::size_t position) noexcept {
    return position <= value.size() && (position == value.size()
        || (static_cast<unsigned char>(value[position]) & 0xc0u) != 0x80u);
}
bool range(std::string_view value, ByteRange positions) noexcept {
    return positions.begin <= positions.end && boundary(value,positions.begin) && boundary(value,positions.end);
}
bool observation_join(std::string_view value, const TextObservation& observed) noexcept {
    if (observed.byte_length != value.size() || observed.selection_start > observed.selection_end
        || !range(value,observed.selection)) return false;
    std::size_t bytes=0, units=0;
    bool begin=false, end=false;
    while (true) {
        if (units == observed.selection_start) begin=bytes == observed.selection.begin;
        if (units == observed.selection_end) end=bytes == observed.selection.end;
        if (bytes == value.size()) break;
        const auto lead=static_cast<unsigned char>(value[bytes]);
        const std::size_t count=lead < 0x80 ? 1 : lead < 0xe0 ? 2 : lead < 0xf0 ? 3 : 4;
        bytes += count; units += count == 4 ? 2 : 1;
    }
    return begin && end;
}
bool rectangle(const gui_surface::Rect& value) noexcept {
    auto finite=[](double n) { return std::isfinite(n) && std::abs(n) <= 1000000; };
    return finite(value.x) && finite(value.y) && finite(value.width) && finite(value.height)
        && value.width >= 0 && value.height >= 0;
}

// Explicit closed enum mappings. No C++ enum representation enters the wire.
bool bits(Direction v, std::uint32_t& n) noexcept {
    switch(v) { case Direction::forward:n=0;return true; case Direction::backward:n=1;return true; case Direction::none:n=2;return true; } return false;
}
bool from_bits(std::uint32_t n, Direction& v) noexcept {
    switch(n) { case 0:v=Direction::forward;return true; case 1:v=Direction::backward;return true; case 2:v=Direction::none;return true; default:return false; }
}
bool bits(Kind v, std::uint32_t& n) noexcept {
    switch(v) { case Kind::key:n=0;return true; case Kind::text:n=1;return true; case Kind::selection:n=2;return true; case Kind::composition:n=3;return true; } return false;
}
bool from_bits(std::uint32_t n, Kind& v) noexcept {
    switch(n) { case 0:v=Kind::key;return true; case 1:v=Kind::text;return true; case 2:v=Kind::selection;return true; case 3:v=Kind::composition;return true; default:return false; }
}
bool bits(Authority v, std::uint32_t& n) noexcept {
    switch(v) { case Authority::native:n=0;return true; case Authority::range:n=1;return true; case Authority::default_action:n=2;return true; case Authority::composition:n=3;return true; } return false;
}
bool from_bits(std::uint32_t n, Authority& v) noexcept {
    switch(n) { case 0:v=Authority::native;return true; case 1:v=Authority::range;return true; case 2:v=Authority::default_action;return true; case 3:v=Authority::composition;return true; default:return false; }
}
bool bits(gui_surface::KeyPhase v, std::uint32_t& n) noexcept {
    switch(v) { case gui_surface::KeyPhase::down:n=0;return true; case gui_surface::KeyPhase::up:n=1;return true; } return false;
}
bool from_bits(std::uint32_t n, gui_surface::KeyPhase& v) noexcept {
    switch(n) { case 0:v=gui_surface::KeyPhase::down;return true; case 1:v=gui_surface::KeyPhase::up;return true; default:return false; }
}
bool bits(gui_surface::CompositionOperation v, std::uint32_t& n) noexcept {
    switch(v) { case gui_surface::CompositionOperation::begin:n=0;return true; case gui_surface::CompositionOperation::update:n=1;return true; case gui_surface::CompositionOperation::commit:n=2;return true; case gui_surface::CompositionOperation::cancel:n=3;return true; } return false;
}
bool from_bits(std::uint32_t n, gui_surface::CompositionOperation& v) noexcept {
    switch(n) { case 0:v=gui_surface::CompositionOperation::begin;return true; case 1:v=gui_surface::CompositionOperation::update;return true; case 2:v=gui_surface::CompositionOperation::commit;return true; case 3:v=gui_surface::CompositionOperation::cancel;return true; default:return false; }
}
bool bits(Outcome v, std::uint32_t& n) noexcept {
    switch(v) { case Outcome::applied:n=0;return true; case Outcome::cancelled:n=1;return true; case Outcome::rejected:n=2;return true; case Outcome::unknown:n=3;return true; } return false;
}
bool from_bits(std::uint32_t n, Outcome& v) noexcept {
    switch(n) { case 0:v=Outcome::applied;return true; case 1:v=Outcome::cancelled;return true; case 2:v=Outcome::rejected;return true; case 3:v=Outcome::unknown;return true; default:return false; }
}
bool bits(Continuity v, std::uint32_t& n) noexcept {
    switch(v) { case Continuity::same:n=0;return true; case Continuity::key_retarget:n=1;return true; case Continuity::replaced:n=2;return true; } return false;
}
bool from_bits(std::uint32_t n, Continuity& v) noexcept {
    switch(n) { case 0:v=Continuity::same;return true; case 1:v=Continuity::key_retarget;return true; case 2:v=Continuity::replaced;return true; default:return false; }
}
bool bits(CompositionState v, std::uint32_t& n) noexcept {
    switch(v) { case CompositionState::pending:n=0;return true; case CompositionState::live:n=1;return true; case CompositionState::ended:n=2;return true; } return false;
}
bool from_bits(std::uint32_t n, CompositionState& v) noexcept {
    switch(n) { case 0:v=CompositionState::pending;return true; case 1:v=CompositionState::live;return true; case 2:v=CompositionState::ended;return true; default:return false; }
}
bool bits(ProjectionReply::State v, std::uint32_t& n) noexcept {
    switch(v) { case ProjectionReply::State::available:n=0;return true; case ProjectionReply::State::noneditable:n=1;return true; case ProjectionReply::State::unavailable:n=2;return true; } return false;
}
bool from_bits(std::uint32_t n, ProjectionReply::State& v) noexcept {
    switch(n) { case 0:v=ProjectionReply::State::available;return true; case 1:v=ProjectionReply::State::noneditable;return true; case 2:v=ProjectionReply::State::unavailable;return true; default:return false; }
}
bool bits(NativeAvailability v, std::uint32_t& n) noexcept {
    switch(v) { case NativeAvailability::available:n=0;return true; case NativeAvailability::noneditable:n=1;return true; case NativeAvailability::unavailable:n=2;return true; } return false;
}
bool from_bits(std::uint32_t n, NativeAvailability& v) noexcept {
    switch(n) { case 0:v=NativeAvailability::available;return true; case 1:v=NativeAvailability::noneditable;return true; case 2:v=NativeAvailability::unavailable;return true; default:return false; }
}

class Writer {
public:
    explicit Writer(Bytes* output=nullptr) : output_(output) {}
    bool raw(View bytes) {
        if (bytes.size() > maximum_wire_bytes-position_) return false;
        if (output_) output_->insert(output_->end(),bytes.begin(),bytes.end());
        position_ += bytes.size(); return true;
    }
    bool integer(std::uint64_t number, unsigned count) {
        std::array<std::uint8_t,8> storage{};
        for (unsigned i=0;i<count;++i) storage[i]=static_cast<std::uint8_t>(number>>(i*8));
        return raw(View(storage.data(),count));
    }
    bool u32(std::uint32_t n) { return integer(n,4); }
    bool u64(std::uint64_t n) { return integer(n,8); }
    bool size32(std::size_t n) { return n <= std::numeric_limits<std::uint32_t>::max() && u32(static_cast<std::uint32_t>(n)); }
    bool boolean(bool n) { return integer(n ? 1 : 0,1); }
    template<class E> bool enumeration(E value) { std::uint32_t n{};return bits(value,n) && u32(n); }
    bool string(std::string_view value, std::size_t bound=text_limit, bool nonempty=false, bool ascii=false) {
        return utf8(value,bound,nonempty,ascii) && size32(value.size())
            && raw(View(reinterpret_cast<const std::uint8_t*>(value.data()),value.size()));
    }
    bool positions(ByteRange value) { return value.begin <= value.end && size32(value.begin) && size32(value.end); }
    bool rect(const gui_surface::Rect& value) {
        return rectangle(value) && u64(std::bit_cast<std::uint64_t>(value.x)) && u64(std::bit_cast<std::uint64_t>(value.y))
            && u64(std::bit_cast<std::uint64_t>(value.width)) && u64(std::bit_cast<std::uint64_t>(value.height));
    }
    std::size_t position() const noexcept { return position_; }
private:
    Bytes* output_{};
    std::size_t position_{};
};

class Reader {
public:
    Reader(View bytes,bool store) noexcept : bytes_(bytes),store_(store) {}
    bool integer(std::uint64_t& value,unsigned count) noexcept {
        if (count > bytes_.size()-position_) return false;
        std::uint64_t n{};
        for(unsigned i=0;i<count;++i) n |= std::uint64_t(bytes_[position_+i])<<(i*8);
        position_+=count;value=n;return true;
    }
    bool u32(std::uint32_t& value) noexcept { std::uint64_t n{};if(!integer(n,4))return false;value=static_cast<std::uint32_t>(n);return true; }
    bool u64(std::uint64_t& value) noexcept { return integer(value,8); }
    bool size32(std::size_t& value) noexcept { std::uint32_t n{};if(!u32(n))return false;value=n;return true; }
    bool boolean(bool& value) noexcept { std::uint64_t n{};if(!integer(n,1)||n>1)return false;value=n==1;return true; }
    template<class E> bool enumeration(E& value) noexcept { std::uint32_t n{};return u32(n)&&from_bits(n,value); }
    bool string(std::string& value,std::string_view& view,std::size_t bound=text_limit,bool nonempty=false,bool ascii=false) {
        std::uint32_t length{};
        if(!u32(length)||length>bound||length>bytes_.size()-position_)return false;
        view=std::string_view(reinterpret_cast<const char*>(bytes_.data()+position_),length);
        if(!utf8(view,bound,nonempty,ascii))return false;
        position_+=length;
        if(store_)value.assign(view);
        return true;
    }
    bool positions(ByteRange& value) noexcept { return size32(value.begin)&&size32(value.end)&&value.begin<=value.end; }
    bool rect(gui_surface::Rect& value) noexcept {
        std::uint64_t x{},y{},w{},h{};
        if(!u64(x)||!u64(y)||!u64(w)||!u64(h))return false;
        value={std::bit_cast<double>(x),std::bit_cast<double>(y),std::bit_cast<double>(w),std::bit_cast<double>(h)};
        return rectangle(value);
    }
    bool store() const noexcept { return store_; }
    bool done() const noexcept { return position_==bytes_.size(); }
private:
    View bytes_;
    std::size_t position_{};
    bool store_{};
};

template<class T,class Function> bool write_optional(Writer& writer,const std::optional<T>& item,Function function) {
    return writer.boolean(item.has_value())&&(!item||function(writer,*item));
}
template<class T,class Function> bool read_optional(Reader& reader,std::optional<T>& item,Function function) {
    bool present{};
    if(!reader.boolean(present))return false;
    if(!present){if(reader.store())item.reset();return true;}
    T temporary;
    if(!function(reader,temporary))return false;
    if(reader.store())item=std::move(temporary);
    return true;
}
bool write_optional_id(Writer& w,const std::optional<std::uint64_t>& value) {
    return write_optional(w,value,[](Writer& out,std::uint64_t n){return n&&out.u64(n);});
}
bool read_optional_id(Reader& r,std::optional<std::uint64_t>& value) {
    return read_optional(r,value,[](Reader& in,std::uint64_t& n){return in.u64(n)&&n;});
}
bool write(Writer& w,const Identity& value) {
    return w.string(value.owner.id,BIB_ENGINE_EDITOR_MAX_OWNER_BYTES,true)
        && value.owner.generation&&w.u64(value.owner.generation)
        && value.presentation_revision&&w.u64(value.presentation_revision)
        && value.generation&&w.u64(value.generation)&&value.epoch&&w.u64(value.epoch)
        && value.context&&w.u64(value.context);
}
bool read(Reader& r,Identity& value) {
    std::string_view owner;
    return r.string(value.owner.id,owner,BIB_ENGINE_EDITOR_MAX_OWNER_BYTES,true)
        &&r.u64(value.owner.generation)&&value.owner.generation
        &&r.u64(value.presentation_revision)&&value.presentation_revision
        &&r.u64(value.generation)&&value.generation&&r.u64(value.epoch)&&value.epoch
        &&r.u64(value.context)&&value.context;
}
bool write(Writer& w,const Basis& value) {
    return value.token&&w.u64(value.token)&&write(w,value.identity)
        &&value.editor_revision&&w.u64(value.editor_revision)&&w.string(value.surrounding)
        &&range(value.surrounding,value.selection)&&w.positions(value.selection)
        &&w.boolean(value.backward)&&w.u64(value.composition);
}
bool read(Reader& r,Basis& value) {
    std::string_view text;
    return r.u64(value.token)&&value.token&&read(r,value.identity)
        &&r.u64(value.editor_revision)&&value.editor_revision&&r.string(value.surrounding,text)
        &&r.positions(value.selection)&&range(text,value.selection)
        &&r.boolean(value.backward)&&r.u64(value.composition);
}
bool write(Writer& w,const NativeRetireMaterial& value) {
    return value.token&&w.u64(value.token)&&value.mapping_id&&w.u64(value.mapping_id)
        &&value.input_context&&w.u64(value.input_context)&&w.u64(value.composition);
}
bool read(Reader& r,NativeRetireMaterial& value) {
    return r.u64(value.token)&&value.token&&r.u64(value.mapping_id)&&value.mapping_id
        &&r.u64(value.input_context)&&value.input_context&&r.u64(value.composition);
}
bool retirement_matches(const NativeRetireMaterial& material,const NativeProjection& value) noexcept {
    return material.mapping_id==value.mapping_id&&material.input_context==value.identity.context
        &&material.composition==value.composition;
}
bool write_projection(Writer& w,const NativeProjection& value,bool usable) {
    return write(w,value.identity)&&value.editor_revision&&w.u64(value.editor_revision)
        &&w.string(value.surrounding)&&range(value.surrounding,value.selection)&&w.positions(value.selection)
        &&w.boolean(value.backward)&&w.u64(value.composition)
        &&value.mapping_id&&w.u64(value.mapping_id)&&value.frame_id&&w.u64(value.frame_id)
        &&(!usable||value.readback_attested)&&w.boolean(value.readback_attested)&&w.rect(value.caret)
        &&(!usable||value.editable)&&w.boolean(value.editable)&&w.string(value.input_purpose,128)
        &&(!usable||value.retire.has_value())
        &&write_optional(w,value.retire,[&](Writer& out,const NativeRetireMaterial& material) {
            return retirement_matches(material,value)&&write(out,material);
        });
}
bool read_projection(Reader& r,NativeProjection& value,bool usable) {
    std::string_view text,purpose;
    if(!(read(r,value.identity)&&r.u64(value.editor_revision)&&value.editor_revision
        &&r.string(value.surrounding,text)&&r.positions(value.selection)&&range(text,value.selection)
        &&r.boolean(value.backward)&&r.u64(value.composition)
        &&r.u64(value.mapping_id)&&value.mapping_id&&r.u64(value.frame_id)&&value.frame_id
        &&r.boolean(value.readback_attested)&&(!usable||value.readback_attested)&&r.rect(value.caret)
        &&r.boolean(value.editable)&&(!usable||value.editable)&&r.string(value.input_purpose,purpose,128)))return false;
    bool present{};
    if(!r.boolean(present)||(!present&&usable))return false;
    if(present) {
        NativeRetireMaterial material;
        if(!read(r,material)||!retirement_matches(material,value))return false;
        // Scalar-only optional assignment is allocation-free in preflight.
        value.retire=material;
    }
    return true;
}
bool write(Writer& w,const NativeProjection& value) { return write_projection(w,value,true); }
bool read(Reader& r,NativeProjection& value) { return read_projection(r,value,true); }
bool write(Writer& w,const TextObservation& value) {
    return w.string(value.value)&&observation_join(value.value,value)
        &&w.size32(value.selection_start)&&w.size32(value.selection_end)
        &&w.enumeration(value.selection_direction)&&w.positions(value.selection)&&w.size32(value.byte_length);
}
bool read(Reader& r,TextObservation& value,std::string_view* text_output=nullptr) {
    std::string_view text;
    if(!r.string(value.value,text)||!r.size32(value.selection_start)||!r.size32(value.selection_end)
        ||!r.enumeration(value.selection_direction)||!r.positions(value.selection)
        ||!r.size32(value.byte_length)||!observation_join(text,value))return false;
    if(text_output)*text_output=text;
    return true;
}
bool write(Writer& w,const KeyData& value) {
    const auto& k=value.transition;
    return w.enumeration(k.phase)&&w.string(k.key,BIB_ENGINE_EDITOR_MAX_KEY_BYTES,true)
        &&w.string(k.code,BIB_ENGINE_EDITOR_MAX_KEY_BYTES,false,true)
        &&k.location<=3&&w.u32(k.location)&&k.modifiers<=31&&w.u32(k.modifiers)
        &&!(k.phase==gui_surface::KeyPhase::up&&k.repeat)&&w.boolean(k.repeat)&&w.boolean(value.is_composing);
}
bool read(Reader& r,KeyData& value) {
    auto& k=value.transition;
    std::string_view key,code;
    std::uint32_t location{};
    if(!r.enumeration(k.phase)||!r.string(k.key,key,BIB_ENGINE_EDITOR_MAX_KEY_BYTES,true)
        ||!r.string(k.code,code,BIB_ENGINE_EDITOR_MAX_KEY_BYTES,false,true)
        ||!r.u32(location)||location>3||!r.u32(k.modifiers)||k.modifiers>31
        ||!r.boolean(k.repeat)||(k.phase==gui_surface::KeyPhase::up&&k.repeat)||!r.boolean(value.is_composing))return false;
    k.location=location;return true;
}
bool write_groups(Writer& w,const std::vector<std::uint64_t>& values) {
    if(values.size()>dependencies_limit||!w.size32(values.size()))return false;
    for(std::size_t i=0;i<values.size();++i) {
        if(!values[i]||!w.u64(values[i]))return false;
        for(std::size_t j=0;j<i;++j)if(values[i]==values[j])return false;
    }
    return true;
}
bool read_groups(Reader& r,std::vector<std::uint64_t>& values) {
    std::uint32_t count{};
    if(!r.u32(count)||count>dependencies_limit)return false;
    std::array<std::uint64_t,dependencies_limit> seen{};
    for(std::uint32_t i=0;i<count;++i) {
        if(!r.u64(seen[i])||!seen[i])return false;
        for(std::uint32_t j=0;j<i;++j)if(seen[i]==seen[j])return false;
        if(r.store())values.push_back(seen[i]);
    }
    return true;
}
bool write_data(Writer& w,const Observation& value) {
    if(const auto* data=std::get_if<KeyData>(&value.data))
        return value.kind==Kind::key&&write(w,*data);
    if(const auto* data=std::get_if<TextData>(&value.data))
        return value.kind==Kind::text&&w.string(data->input_type,64,true)&&w.string(data->text)
            &&range(value.before.value,data->replacement)&&w.positions(data->replacement)&&write_groups(w,data->source_groups);
    if(const auto* data=std::get_if<SelectionData>(&value.data))
        return value.kind==Kind::selection&&range(value.before.value,data->selection)
            &&w.positions(data->selection)&&w.boolean(data->backward);
    const auto* data=std::get_if<CompositionData>(&value.data);
    return data&&value.kind==Kind::composition&&w.enumeration(data->operation)&&w.string(data->text)
        &&range(data->text,data->selection)&&w.positions(data->selection)
        &&write_optional(w,data->replacement,[&](Writer& out,ByteRange p){return range(value.before.value,p)&&out.positions(p);})
        &&write_groups(w,data->source_groups);
}
bool read_data(Reader& r,Observation& value,std::string_view before) {
    switch(value.kind) {
    case Kind::key: {
        KeyData data;
        if(!read(r,data))return false;
        if(r.store())value.data=std::move(data);
        return true;
    }
    case Kind::text: {
        TextData data;std::string_view type,text;
        if(!r.string(data.input_type,type,64,true)||!r.string(data.text,text)
            ||!r.positions(data.replacement)||!range(before,data.replacement)||!read_groups(r,data.source_groups))return false;
        if(r.store())value.data=std::move(data);
        return true;
    }
    case Kind::selection: {
        SelectionData data;
        if(!r.positions(data.selection)||!range(before,data.selection)||!r.boolean(data.backward))return false;
        if(r.store())value.data=data;
        return true;
    }
    case Kind::composition: {
        CompositionData data;std::string_view text;
        if(!r.enumeration(data.operation)||!r.string(data.text,text)||!r.positions(data.selection)||!range(text,data.selection)
            ||!read_optional(r,data.replacement,[&](Reader& in,ByteRange& p){return in.positions(p)&&range(before,p);})
            ||!read_groups(r,data.source_groups))return false;
        if(r.store())value.data=std::move(data);
        return true;
    }
    }
    return false;
}
bool write(Writer& w,const Observation& value) {
    return value.id&&w.u64(value.id)&&write_optional_id(w,value.predecessor)
        &&w.enumeration(value.kind)&&w.enumeration(value.authority)&&write_optional_id(w,value.group)
        &&w.boolean(value.group_end)&&w.u64(value.transaction)&&write(w,value.before)
        &&write_optional(w,value.after,[](Writer& out,const TextObservation& t){return write(out,t);})
        &&write_data(w,value);
}
bool read(Reader& r,Observation& value) {
    std::string_view before;
    return r.u64(value.id)&&value.id&&read_optional_id(r,value.predecessor)
        &&r.enumeration(value.kind)&&r.enumeration(value.authority)&&read_optional_id(r,value.group)
        &&r.boolean(value.group_end)&&r.u64(value.transaction)&&read(r,value.before,&before)
        &&read_optional(r,value.after,[](Reader& in,TextObservation& t){return read(in,t);})
        &&read_data(r,value,before);
}
bool write(Writer& w,const Packet& value) {
    if(!value.session||!w.u64(value.session)||!write(w,value.basis)||!write_optional_id(w,value.default_token)
        ||value.default_dependencies.size()>dependencies_limit||!w.size32(value.default_dependencies.size()))return false;
    for(std::size_t i=0;i<value.default_dependencies.size();++i) {
        const auto& d=value.default_dependencies[i];
        if(!d.group||!d.token||!w.u64(d.group)||!w.u64(d.token))return false;
        for(std::size_t j=0;j<i;++j)if(d.group==value.default_dependencies[j].group)return false;
    }
    return write(w,value.observation);
}
bool read(Reader& r,Packet& value) {
    std::uint32_t count{};
    if(!r.u64(value.session)||!value.session||!read(r,value.basis)||!read_optional_id(r,value.default_token)
        ||!r.u32(count)||count>dependencies_limit)return false;
    std::array<std::uint64_t,dependencies_limit> groups{};
    for(std::uint32_t i=0;i<count;++i) {
        DefaultDependency d;
        if(!r.u64(d.group)||!d.group||!r.u64(d.token)||!d.token)return false;
        for(std::uint32_t j=0;j<i;++j)if(d.group==groups[j])return false;
        groups[i]=d.group;
        if(r.store())value.default_dependencies.push_back(d);
    }
    return read(r,value.observation);
}
bool write(Writer& w,const NativeRequest& value) { return write(w,value.resolved)&&write(w,value.packet); }
bool read(Reader& r,NativeRequest& value) { return read(r,value.resolved)&&read(r,value.packet); }
bool write(Writer& w,const WireTarget& v) {
    return v.worker_epoch&&w.u64(v.worker_epoch)&&v.application_instance&&w.u64(v.application_instance)
        &&v.document_sequence&&w.u64(v.document_sequence)&&v.service_generation&&w.u64(v.service_generation)
        &&v.request_sequence&&w.u64(v.request_sequence);
}
bool read(Reader& r,WireTarget& v) {
    return r.u64(v.worker_epoch)&&v.worker_epoch&&r.u64(v.application_instance)&&v.application_instance
        &&r.u64(v.document_sequence)&&v.document_sequence&&r.u64(v.service_generation)&&v.service_generation
        &&r.u64(v.request_sequence)&&v.request_sequence;
}
bool write(Writer& w,const ProjectionQuery& v) { return write(w,v.target)&&write(w,v.identity)&&w.u64(v.mapping_id); }
bool read(Reader& r,ProjectionQuery& v) { return read(r,v.target)&&read(r,v.identity)&&r.u64(v.mapping_id); }
bool write(Writer& w,const ProjectionReply& v) {
    return v.observation_revision&&w.u64(v.observation_revision)&&write(w,v.target)&&w.enumeration(v.state)
        &&write(w,v.identity)&&v.readback_attested&&w.boolean(v.readback_attested)
        &&((v.state==ProjectionReply::State::available)==v.projection.has_value())
        &&write_optional(w,v.projection,[&](Writer& out,const NativeProjection& p) {
            return p.identity==v.identity&&write(out,p);
        });
}
bool read(Reader& r,ProjectionReply& v) {
    if(!r.u64(v.observation_revision)||!v.observation_revision||!read(r,v.target)||!r.enumeration(v.state)
        ||!read(r,v.identity)||!r.boolean(v.readback_attested)||!v.readback_attested)return false;
    bool present{};
    if(!r.boolean(present)||(v.state==ProjectionReply::State::available)!=present)return false;
    if(present) {
        NativeProjection p;
        if(!read(r,p))return false;
        // Owning identities are compared by final shape after materialization;
        // preflight still validates every byte/length before any allocation.
        if(r.store())v.projection=std::move(p);
    }
    return true;
}
bool write(Writer& w,const NativeRequestEnvelope& v) { return write(w,v.target)&&write(w,v.request); }
bool read(Reader& r,NativeRequestEnvelope& v) { return read(r,v.target)&&read(r,v.request); }
bool empty_identity(const Identity& i) noexcept {
    return i.owner.id.empty()&&!i.owner.generation&&!i.presentation_revision&&!i.generation&&!i.epoch&&!i.context;
}
bool write_result_identity(Writer& w,const Identity& i,bool unknown) {
    if(!empty_identity(i))return write(w,i);
    return unknown&&w.string({},0)&&w.u64(0)&&w.u64(0)&&w.u64(0)&&w.u64(0)&&w.u64(0);
}
bool read_result_identity(Reader& r,Identity& i,bool unknown) {
    std::string_view owner;
    if(!r.string(i.owner.id,owner,BIB_ENGINE_EDITOR_MAX_OWNER_BYTES)||!r.u64(i.owner.generation)
        ||!r.u64(i.presentation_revision)||!r.u64(i.generation)||!r.u64(i.epoch)||!r.u64(i.context))return false;
    if(owner.empty())return unknown&&!i.owner.generation&&!i.presentation_revision&&!i.generation&&!i.epoch&&!i.context;
    return i.owner.generation&&i.presentation_revision&&i.generation&&i.epoch&&i.context;
}
bool write(Writer& w,const CompositionFact& v) { return v.transaction&&w.u64(v.transaction)&&w.enumeration(v.state); }
bool read(Reader& r,CompositionFact& v) { return r.u64(v.transaction)&&v.transaction&&r.enumeration(v.state); }
bool result_relations(const NativeResult& v) noexcept {
    if(v.outcome==Outcome::unknown) {
        if(v.allow_default||v.key_retarget_attested||v.composition_readback_attested||v.composition)return false;
        if(empty_identity(v.readback_identity))return !v.readback_attested&&!v.observation_revision;
        return !v.readback_attested||v.observation_revision;
    }
    if(!v.readback_attested||!v.observation_revision||empty_identity(v.readback_identity))return false;
    if(v.availability==NativeAvailability::available) {
        if(!v.projection||v.projection->identity!=v.readback_identity)return false;
        if(v.retire&&(!retirement_matches(*v.retire,*v.projection)
            ||v.retire!=v.projection->retire))return false;
    } else if(v.projection||v.allow_default||v.key_retarget_attested
        ||(v.composition&&v.composition->state!=CompositionState::ended))return false;
    // retired proves cleanup of the OLD provider lease. Its context may differ
    // from the actual replacement readback; the outer request checks that lease.
    return !v.retire||v.retire->input_context==v.readback_identity.context;
}
bool write(Writer& w,const NativeResult& v) {
    const bool unknown=v.outcome==Outcome::unknown;
    return result_relations(v)&&w.enumeration(v.outcome)&&w.enumeration(v.continuity)
        &&write_optional(w,v.projection,[&](Writer& out,const NativeProjection& p){return write_projection(out,p,!unknown);})
        &&w.boolean(v.key_dispatch_attested)&&w.boolean(v.default_prevented)&&w.boolean(v.default_handled)
        &&w.boolean(v.changed_focused_frame)&&w.boolean(v.allow_default)&&w.boolean(v.key_retarget_attested)
        &&w.boolean(v.composition_readback_attested)
        &&write_optional(w,v.composition,[](Writer& out,const CompositionFact& c){return write(out,c);})
        &&w.enumeration(v.availability)&&w.u64(v.observation_revision)
        &&write_result_identity(w,v.readback_identity,unknown)&&w.boolean(v.readback_attested)
        &&write_optional(w,v.retire,[](Writer& out,const NativeRetireMaterial& m){return write(out,m);})
        &&write_optional(w,v.retired,[](Writer& out,const NativeRetireMaterial& m){return write(out,m);});
}
bool read(Reader& r,NativeResult& v) {
    if(!r.enumeration(v.outcome)||!r.enumeration(v.continuity))return false;
    const bool unknown=v.outcome==Outcome::unknown;
    return read_optional(r,v.projection,[&](Reader& in,NativeProjection& p){return read_projection(in,p,!unknown);})
        &&r.boolean(v.key_dispatch_attested)&&r.boolean(v.default_prevented)&&r.boolean(v.default_handled)
        &&r.boolean(v.changed_focused_frame)&&r.boolean(v.allow_default)&&r.boolean(v.key_retarget_attested)
        &&r.boolean(v.composition_readback_attested)
        &&read_optional(r,v.composition,[](Reader& in,CompositionFact& c){return read(in,c);})
        &&r.enumeration(v.availability)&&r.u64(v.observation_revision)
        &&read_result_identity(r,v.readback_identity,unknown)&&r.boolean(v.readback_attested)
        &&read_optional(r,v.retire,[](Reader& in,NativeRetireMaterial& m){return read(in,m);})
        &&read_optional(r,v.retired,[](Reader& in,NativeRetireMaterial& m){return read(in,m);});
}
bool write(Writer& w,const NativeResultEnvelope& v) { return write(w,v.target)&&write(w,v.result); }
bool read(Reader& r,NativeResultEnvelope& v) { return read(r,v.target)&&read(r,v.result); }
bool write(Writer& w,const Revocation& v) {
    if(!write(w,v.basis)||!v.incarnation||!w.u64(v.incarnation)||!w.u64(v.composition)
        ||v.held_keys.size()>groups_limit||!w.size32(v.held_keys.size()))return false;
    for(const auto& key:v.held_keys)
        if(key.transition.phase!=gui_surface::KeyPhase::down||!write(w,key))return false;
    return w.string(v.reason,BIB_ENGINE_EDITOR_MAX_REASON_BYTES);
}
bool read(Reader& r,Revocation& v) {
    std::uint32_t count{};
    if(!read(r,v.basis)||!r.u64(v.incarnation)||!v.incarnation||!r.u64(v.composition)
        ||!r.u32(count)||count>groups_limit)return false;
    for(std::uint32_t i=0;i<count;++i) {
        KeyData key;
        if(!read(r,key)||key.transition.phase!=gui_surface::KeyPhase::down)return false;
        if(r.store())v.held_keys.push_back(std::move(key));
    }
    std::string_view reason;
    return r.string(v.reason,reason,BIB_ENGINE_EDITOR_MAX_REASON_BYTES);
}
bool write(Writer& w,const NativeRevocationRequest& v) {
    return write(w,v.material)&&write(w,v.identity)&&v.material.input_context==v.identity.context
        &&write_optional(w,v.observed,[&](Writer& out,const Revocation& observed) {
            return observed.basis.identity==v.identity&&observed.composition==v.material.composition&&write(out,observed);
        });
}
bool read(Reader& r,NativeRevocationRequest& v) {
    return read(r,v.material)&&read(r,v.identity)&&v.material.input_context==v.identity.context
        &&read_optional(r,v.observed,[](Reader& in,Revocation& observed){return read(in,observed);});
}
bool write(Writer& w,const RevocationEnvelope& v) { return write(w,v.target)&&write(w,v.request); }
bool read(Reader& r,RevocationEnvelope& v) { return read(r,v.target)&&read(r,v.request); }

template<class T> bool shape(const T& value) noexcept {
    try { Writer counter;return counter.raw(View(magic))&&counter.integer(0,8)&&write(counter,value); }
    catch(...){return false;}
}
template<class T> bool encode(const T& value,std::uint32_t kind,Bytes& output) noexcept {
    try {
        if(!shape(value))return false;
        Bytes temporary;Writer w(&temporary);
        if(!w.raw(View(magic))||!w.integer(kind,2)||!w.integer(0,2)||!w.u32(0)||!write(w,value))return false;
        const auto size=static_cast<std::uint32_t>(temporary.size());
        for(unsigned i=0;i<4;++i)temporary[12+i]=static_cast<std::uint8_t>(size>>(i*8));
        output=std::move(temporary);return true;
    }catch(...){return false;}
}
template<class T> bool decode(View bytes,std::uint32_t kind,T& output) noexcept {
    try {
        if(bytes.size()<header_bytes||bytes.size()>maximum_wire_bytes)return false;
        for(std::size_t i=0;i<magic.size();++i)if(bytes[i]!=magic[i])return false;
        Reader header(bytes.subspan(8),false);std::uint64_t actual_kind{},flags{};std::uint32_t total{};
        if(!header.integer(actual_kind,2)||actual_kind!=kind||!header.integer(flags,2)||flags||!header.u32(total)||total!=bytes.size())return false;
        T preflight;Reader inspect(bytes.subspan(header_bytes),false);
        if(!read(inspect,preflight)||!inspect.done())return false;
        T temporary;Reader materialize(bytes.subspan(header_bytes),true);
        if(!read(materialize,temporary)||!materialize.done()||!shape(temporary))return false;
        output=std::move(temporary);return true;
    }catch(...){return false;}
}
} // namespace

bool valid_projection_query_shape(const ProjectionQuery& v) noexcept { return shape(v); }
bool valid_native_projection_shape(const NativeProjection& v) noexcept { return shape(v); }
bool valid_projection_reply_shape(const ProjectionReply& v) noexcept { return shape(v); }
bool valid_native_request_shape(const NativeRequestEnvelope& v) noexcept { return shape(v); }
bool valid_native_result_shape(const NativeResultEnvelope& v) noexcept { return shape(v); }
bool valid_revocation_shape(const RevocationEnvelope& v) noexcept { return shape(v); }
bool encode_projection_query(const ProjectionQuery& v,Bytes& out) noexcept { return encode(v,BIB_ENGINE_EDITOR_WIRE_PROJECTION_QUERY,out); }
bool decode_projection_query(View bytes,ProjectionQuery& out) noexcept { return decode(bytes,BIB_ENGINE_EDITOR_WIRE_PROJECTION_QUERY,out); }
bool encode_projection_reply(const ProjectionReply& v,Bytes& out) noexcept { return encode(v,BIB_ENGINE_EDITOR_WIRE_PROJECTION_REPLY,out); }
bool decode_projection_reply(View bytes,ProjectionReply& out) noexcept { return decode(bytes,BIB_ENGINE_EDITOR_WIRE_PROJECTION_REPLY,out); }
bool encode_native_request(const NativeRequestEnvelope& v,Bytes& out) noexcept { return encode(v,BIB_ENGINE_EDITOR_WIRE_NATIVE_REQUEST,out); }
bool decode_native_request(View bytes,NativeRequestEnvelope& out) noexcept { return decode(bytes,BIB_ENGINE_EDITOR_WIRE_NATIVE_REQUEST,out); }
bool encode_native_result(const NativeResultEnvelope& v,Bytes& out) noexcept { return encode(v,BIB_ENGINE_EDITOR_WIRE_NATIVE_RESULT,out); }
bool decode_native_result(View bytes,NativeResultEnvelope& out) noexcept { return decode(bytes,BIB_ENGINE_EDITOR_WIRE_NATIVE_RESULT,out); }
bool encode_revocation(const RevocationEnvelope& v,Bytes& out) noexcept { return encode(v,BIB_ENGINE_EDITOR_WIRE_REVOCATION,out); }
bool decode_revocation(View bytes,RevocationEnvelope& out) noexcept { return decode(bytes,BIB_ENGINE_EDITOR_WIRE_REVOCATION,out); }
} // namespace foundation::ui::native_editor::codec
