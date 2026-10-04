#pragma once
#include <gui/interaction.hpp>
#include <string>
#include <vector>

namespace foundation::host {
// A three/five physical-key projection of declared, eligible actions. No
// application IDs, menus or domain commands are known by the driver.
class Bezel {
    struct Action {
        gui::WidgetKey target;
        std::string id, label;
        gui::Input input;
    };
    unsigned buttons_;
    std::size_t selected_=0;
    std::vector<Action> actions_;
    template<class Adapter> void refresh(Adapter& adapter) {
        std::optional<std::pair<gui::WidgetKey,std::string>> old;
        if(selected_<actions_.size())old={{actions_[selected_].target,actions_[selected_].id}};
        actions_.clear();
        if(adapter.closed() || adapter.prompt() || adapter.popup())return;
        for(const auto& widget:adapter.snapshot().widgets) {
            const auto& key=widget.spec.key;const auto available=adapter.resolved_availability(key);
            if(!available.visible||!available.enabled||!gui::in_modal_scope(adapter.snapshot(),key))continue;
            if(widget.spec.kind==gui::Kind::button)
                actions_.push_back({key,"",widget.state.label,gui::Activate{}});
            else if(widget.spec.kind==gui::Kind::toggle)
                actions_.push_back({key,"",widget.state.label,gui::SetChecked{!widget.state.checked}});
            else if(widget.spec.kind==gui::Kind::choice||widget.spec.kind==gui::Kind::menu) {
                for(const auto& option:widget.state.options)if(option.enabled)
                    actions_.push_back({key,option.id,option.label,gui::ChooseOption{option.id}});
            } else if(widget.spec.kind==gui::Kind::bitmap) {
                for(const auto& action:widget.state.actions)if(action.enabled)
                    actions_.push_back({key,action.id,action.label,gui::InvokeAction{action.id}});
            }
        }
        selected_=0;
        if(old)for(std::size_t i=0;i<actions_.size();++i)
            if(actions_[i].target==old->first&&actions_[i].id==old->second){selected_=i;break;}
    }
public:
    explicit Bezel(unsigned buttons=3):buttons_(buttons) {
        if(buttons!=3&&buttons!=5)throw std::invalid_argument("Bezel requires three or five buttons");
    }
    template<class Adapter> std::vector<std::string> labels(Adapter& adapter) {
        refresh(adapter);
        if(adapter.closed())return std::vector<std::string>(buttons_);
        std::vector<std::string> result;
        if(adapter.prompt())result={"Cancel","Accept",""};
        else if(adapter.popup())result={"Previous","Next","Choose"};
        else result={actions_.empty()?"":"Previous",actions_.empty()?"":"Next",actions_.empty()?"":actions_[selected_].label};
        if(buttons_==5){result.push_back(adapter.prompt()?"":"Back");result.push_back(adapter.prompt()||adapter.popup()?"":"Next page");}
        return result;
    }
    // Call once per debounced hardware press. Touch drivers retain their own
    // press/release cancellation contract; do not feed raw repeated contacts.
    template<class Adapter> bool activate(Adapter& adapter,unsigned button) {
        refresh(adapter);
        if(adapter.closed()||button<1||button>buttons_)return false;
        if(adapter.prompt()) {
            if(button>2)return false;
            adapter.key(button==1?gui::Key::escape:gui::Key::enter);return true;
        }
        if(adapter.popup()) {
            if(button==5)return false;
            adapter.key(button==1?gui::Key::up:button==2?gui::Key::down:button==3?gui::Key::enter:gui::Key::escape);return true;
        }
        if(button==4){adapter.key(gui::Key::escape);return true;}
        if(button==5){adapter.key(gui::Key::next_page);return true;}
        if(actions_.empty())return false;
        if(button==1)selected_=(selected_+actions_.size()-1)%actions_.size();
        else if(button==2)selected_=(selected_+1)%actions_.size();
        else {
            // Copy before delivery: callbacks may replace the complete snapshot.
            auto action=actions_[selected_];
            adapter.policy().send(gui::WidgetEvent{action.target,std::move(action.input)});
        }
        return true;
    }
};
}
