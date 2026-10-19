#include "NativeDocumentV2Codec.hpp"
#include <iostream>
#include <stdexcept>
namespace N=BIB::NativeDocumentV2;namespace F=foundation::appended;
static unsigned checks;static void check(bool v,const char*m){++checks;if(!v)throw std::runtime_error(m);}
static N::OwnedPublication publication(){
 N::OwnedPublication p;p.identity={1,2,3};p.version={1,2,1};p.editor.revision=1;
 N::Node n;n.id=1;n.tag="select";n.name="Visible menu";n.native_child_count=3;p.nodes.push_back(n);
 F::FormControl c;c.node=1;c.kind=F::FormKind::select_one;c.native_type="select-one";c.label=n.name;c.complete=true;c.focusable=true;
 c.capabilities=20;c.state=F::FormSelectState{false,true,{{2,"Alpha",true,false,false},{3,"",false,false,true},{4,"Omega",false,false,false}}};
 p.forms={2,p.version,{c}};return p;
}
template<class Change>static void rejects(Change change,const char*m){auto p=publication();change(p);bool refused=false;
 try{N::validatePublication(p);}catch(const std::invalid_argument&){refused=true;}check(refused,m);}
int main(){try{
 for(unsigned caps:{0u,4u,16u,20u}){auto p=publication();p.forms.controls[0].capabilities=caps;N::validatePublication(p);
  auto decoded=N::decodePublication(N::encodePublication(p));check(decoded.forms.controls[0].complete&&std::get<F::FormSelectState>(decoded.forms.controls[0].state).options[1].omitted,"production Types/codec preserve complete opaque popup");}
 rejects([](auto&p){std::get<F::FormSelectState>(p.forms.controls[0].state).options[1].label="leak";},"opaque label leak accepted");
 rejects([](auto&p){p.forms.controls[0].capabilities=8;},"opaque select gained direct option mutation");
 rejects([](auto&p){auto&c=p.forms.controls[0];c.kind=F::FormKind::select_many;c.native_type="select-multiple";c.capabilities=8;auto&s=std::get<F::FormSelectState>(c.state);s.multiple=true;s.menu_list=false;},"opaque multiselect gained authority");
 rejects([](auto&p){auto&c=p.forms.controls[0];c.kind=F::FormKind::select_many;c.native_type="select-multiple";c.capabilities=0;std::get<F::FormSelectState>(c.state).multiple=true;},"complete opaque multiselect accepted");
 rejects([](auto&p){std::get<F::FormSelectState>(p.forms.controls[0].state).menu_list=false;},"opaque non-menu popup accepted");
 rejects([](auto&p){p.forms.controls[0].complete=false;},"incomplete popup retains authority");
 rejects([](auto&p){p.forms.controls[0].disabled=true;p.nodes[0].disabled=true;},"disabled popup retains authority");
 rejects([](auto&p){p.forms.controls[0].read_only=true;},"readonly popup retains authority");
 rejects([](auto&p){p.truncated=true;},"truncated popup retains authority");
 rejects([](auto&p){p.forms.controls[0].lease=F::FormLease{{1,2,1},1,1};},"unfocused popup retains lease");
 rejects([](auto&p){std::get<F::FormSelectState>(p.forms.controls[0].state).options[2].selected=true;},"single popup has two selections");
 {auto p=publication();p.forms.controls[0].complete=false;p.forms.controls[0].capabilities=0;N::validatePublication(p);check(true,"original incomplete redacted observation remains valid");}
 std::cout<<"passed "<<checks<<" production value checks\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
