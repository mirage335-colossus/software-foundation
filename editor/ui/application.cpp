#include "application.hpp"
#include "canvas.hpp"
#include "editor/model/project.hpp"
#include "editor/generate/generate.hpp"
#include "editor/generate/publish.hpp"
#include "editor/platform/project_files.hpp"
#include "editor/platform/process_runner.hpp"
#include "editor/self/generated/visual/forms.hpp"
#include "editor/self/generated/visual/events.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace foundation::editor {
namespace {
std::filesystem::path launch_project, launch_root;
std::string number(double n) { std::ostringstream s; s << std::setprecision(8) << n; return s.str(); }
std::string trim(std::string s) {
    const auto a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return {};
    return s.substr(a, s.find_last_not_of(" \t\r\n") - a + 1);
}
std::pair<double,double> pair_of(const std::string& text) {
    auto s = text; std::replace(s.begin(), s.end(), ',', ' ');
    std::istringstream in(s); double a, b; std::string extra;
    if (!(in >> a >> b) || (in >> extra) || !std::isfinite(a) || !std::isfinite(b))
        throw std::invalid_argument("Enter two finite numbers, separated by a comma.");
    return {a,b};
}
std::vector<std::string> lines(const std::string& text) {
    std::vector<std::string> result; std::istringstream stream(text); std::string line;
    while (std::getline(stream,line)) if (!(line=trim(line)).empty()) result.push_back(std::move(line));
    return result;
}
std::string diagnostics(const std::vector<Diagnostic>& ds) {
    std::string out;
    for (const auto& d:ds) { out += d.severity==Severity::error?"Error: ":"Note: "; out += d.path+": "+d.message+"\n"; }
    return out;
}
std::string display_log(std::string_view raw) {
    // Compiler output can contain arbitrary bytes or end mid-character while
    // a pipe is being drained. Only its GUI presentation is normalized.
    std::string out;
    for(std::size_t i=0;i<raw.size()&&out.size()<2*1024*1024;) {
        const auto c=static_cast<unsigned char>(raw[i]);
        const std::size_t n=c<0x80?1:c>=0xc2&&c<=0xdf?2:c>=0xe0&&c<=0xef?3:c>=0xf0&&c<=0xf4?4:0;
        if(c&&n&&n<=raw.size()-i&&ProjectFiles::valid_utf8(raw.substr(i,n))) {
            if(n>2*1024*1024-out.size())break;
            out.append(raw.substr(i,n));i+=n;
        } else {out+='?';++i;}
    }
    return out;
}
}
void configure_launch(std::filesystem::path project,std::filesystem::path root) {
    launch_project=std::move(project); launch_root=std::move(root);
}

struct Application::Impl {
    Application& owner;
    gui::Adapter& adapter;
    gui::Snapshot view;
    Project project=empty_project("Untitled");
    History history;
    Canvas canvas;
    CanvasOptions canvas_options;
    std::unique_ptr<ProjectFiles> files;
    std::optional<FileSnapshot> design_original;
    std::filesystem::path design_path;
    std::unique_ptr<CodeBuffer> code;
    ProcessRunner process;
    ProcessStatus process_status;
    gui::ServiceQueue services;
    std::uint64_t service_id=0, epoch=1, generation=1;
    std::map<std::string,std::string> fields;
    std::vector<std::string> file_names;
    std::string mode="forms", document, selected, palette="button", event="activate";
    std::string modal, status="Open a project, or create a new one.", log, prompt_action;
    std::string saved_design, pending_action, previous_modal;
    bool error=false, pending=false, stopped=false, preview=false, run_after_build=false;
    bool reveal_code=false;
    struct WidgetLife { gui::WidgetSpec spec; bool active=false; std::uint64_t scene=0; };
    std::map<std::string,WidgetLife> widget_lives;
    std::uint64_t widget_generation=0;
    std::optional<Hit> connection;
    struct Drag { std::string id; gui::Point initial, position; bool resize; Rect original; };
    std::optional<Drag> drag;
    double zoom=1;
    gui::Point pan;

    Impl(Application& o,gui::Adapter& a):owner(o),adapter(a) {
        view.client_size={1120,800}; view.title="Foundation Editor";
        history.reset(project); saved_design=write_project(project); choose_document();
        if(!launch_project.empty()) {
            try { open(launch_project,launch_root); }
            catch(const std::exception& e) { failure(e.what()); }
        }
        publish();
    }
    bool dirty() const { return write_project(project)!=saved_design; }
    void failure(std::string text) { status=std::move(text); error=true; }
    void success(std::string text) { status=std::move(text); error=false; }
    Form* form() {
        for(auto& f:project.forms) if(f.id==document) return &f;
        return nullptr;
    }
    Control* control() {
        for(auto& f:project.forms) for(auto& c:f.controls) if(c.id==selected) return &c;
        return nullptr;
    }
    Block* block() { for(auto& b:project.blocks) if(b.id==selected) return &b; return nullptr; }
    Binding* binding(std::string_view id) { for(auto& b:project.bindings) if(b.id==id) return &b; return nullptr; }
    std::string binding_for(const Control& c) {
        if(const auto it=c.event_bindings.find(event);it!=c.event_bindings.end())return it->second;
        for(const auto& [name,id]:c.event_bindings)
            if(canonical_event_name(name)==canonical_event_name(event))return id;
        if(const auto* b=binding(c.binding);b&&canonical_event_name(b->event)==canonical_event_name(event))return b->id;
        return {};
    }
    std::string unique(std::string prefix) const {
        auto used=[&](std::string_view id) {
            for(const auto& f:project.forms) { if(f.id==id)return true; for(const auto& c:f.controls)if(c.id==id)return true; }
            for(const auto& f:project.flows)if(f.id==id)return true;
            for(const auto& b:project.blocks)if(b.id==id)return true;
            for(const auto& b:project.bindings)if(b.id==id)return true;
            for(const auto& e:project.edges)if(e.id==id)return true;
            return false;
        };
        for(std::size_t i=1;i<100000;++i) { auto id=prefix+std::to_string(i); if(!used(id))return id; }
        throw std::length_error("Object identity limit reached.");
    }
    void choose_document() {
        if(mode=="flows") {
            if(std::none_of(project.flows.begin(),project.flows.end(),[&](const auto& f){return f.id==document;}))
                document=project.flows.empty()?"":project.flows.front().id;
        } else if(mode=="forms") {
            if(std::none_of(project.forms.begin(),project.forms.end(),[&](const auto& f){return f.id==document;}))
                document=project.forms.empty()?"":project.forms.front().id;
        }
        selected.clear(); connection.reset(); pan={}; sync_fields();
    }
    void sync_fields() {
        fields["property.label"]=""; fields["property.position"]="0, 0"; fields["property.size"]="120, 32";
        if(auto* c=control()) {
            fields["property.label"]=c->label;
            fields["property.position"]=number(c->layout.x)+", "+number(c->layout.y);
            fields["property.size"]=number(c->layout.width)+", "+number(c->layout.height);
        } else if(auto* b=block()) {
            fields["property.label"]=b->label;
            fields["property.position"]=number(b->x)+", "+number(b->y);
        }
    }
    void changed() { history.commit(project); ++epoch; success("Design modified."); }
    void refresh_files() {
        file_names.clear(); if(!files)return;
        std::size_t visits=0;
        for(std::filesystem::recursive_directory_iterator it(files->root(),std::filesystem::directory_options::skip_permission_denied),end;
            it!=end && visits++<10000 && file_names.size()<1500;++it) {
            const auto name=it->path().filename().string();
            if(it->is_symlink()) { if(it->is_directory())it.disable_recursion_pending(); continue; }
            if(it->is_directory()) {
                if(name=="build"||name=="third_party"||name=="target"||name=="node_modules"||name.starts_with('.'))it.disable_recursion_pending();
                continue;
            }
            if(!it->is_regular_file())continue;
            const auto ext=it->path().extension().string();
            if(ext==".cpp"||ext==".hpp"||ext==".h"||ext==".c"||ext==".rs"||ext==".json"||ext==".toml"||ext==".cmake"||ext==".md"||name=="CMakeLists.txt")
                file_names.push_back(it->path().lexically_relative(files->root()).generic_string());
        }
        std::sort(file_names.begin(),file_names.end());
    }
    void open(std::filesystem::path path,std::filesystem::path root={}) {
        path=std::filesystem::absolute(path).lexically_normal();
        if(std::filesystem::is_directory(path))path/="design/project.json";
        if(root.empty())root=path.parent_path().filename()=="design"?path.parent_path().parent_path():path.parent_path();
        auto next=std::make_unique<ProjectFiles>(std::filesystem::absolute(root));
        auto relative=path.lexically_relative(next->root());
        auto snapshot=next->read(relative);
        auto parsed=parse_project(snapshot.text);
        if(!parsed)throw std::runtime_error(diagnostics(parsed.diagnostics));
        if(next->recovery_pending())throw std::runtime_error("An interrupted save needs recovery. Run foundation-editor-tool recover for this project.");
        project=std::move(*parsed.project); files=std::move(next); design_original=std::move(snapshot); design_path=relative;
        saved_design=write_project(project); history.reset(project); code.reset(); modal.clear(); ++generation;
        fields["project.path"]=path.string(); choose_document(); refresh_files();
        log=diagnostics(parsed.diagnostics); success("Opened "+project.name);
    }
    void create(std::filesystem::path root,bool keep_design=false) {
        root=std::filesystem::absolute(root).lexically_normal();
        std::filesystem::create_directories(root);
        auto next=std::make_unique<ProjectFiles>(root);
        next->ensure_directory("design");
        auto original=next->inspect("design/project.json");
        if(original.identity.exists)throw std::runtime_error("That project already exists. Use Open.");
        if(!keep_design)project=empty_project(root.filename().string());
        if(project.forms.empty())project.forms.push_back(Form{"form1","Main"});
        if(project.flows.empty())project.flows.push_back(Flow{"flow1","Main flow"});
        files=std::move(next); design_path="design/project.json"; design_original=std::move(original);
        saved_design.clear(); history.reset(project); ++generation; modal.clear(); code.reset();
        fields["project.path"]=(root/design_path).string(); choose_document(); save(); refresh_files();
    }
    void save() {
        if(!files||!design_original)throw std::runtime_error("Create or open a project before saving.");
        if(code&&code->dirty())code->save(*files);
        const auto text=write_project(project);
        auto output=generate(project);
        log=diagnostics(output.diagnostics);
        if(!output) {
            design_original=files->save(*design_original,text); saved_design=text;
            failure("Draft saved. Fix the diagnostics before generating or building."); return;
        }
        const auto batch=capture_generated_batch(*files,output,*design_original,text,!design_original->identity.exists);
        if(batch.changed)(void)files->save_batch(batch.writes,batch.revision_marker);
        design_original=files->read(design_path); saved_design=text;
        success("Saved design and generated C++."); refresh_files();
    }
    void prompt(std::string action,std::string title,std::string value={}) {
        prompt_action=std::move(action);
        gui::ServiceRequest req; req.id=++service_id; req.kind=gui::ServiceKind::prompt;
        req.title=std::move(title); req.value=std::move(value); req.byte_limit=4096;
        if(!services.enqueue(std::move(req)))throw std::runtime_error("Another prompt is active.");
    }
    void require_clean(std::string action) {
        if(dirty()||(code&&code->dirty())) {
            pending_action=std::move(action);
            if(modal!="unsaved")previous_modal=modal;
            modal="unsaved"; return;
        }
        if(action=="open")prompt("open","Open project JSON or directory",fields["project.path"]);
        else if(action=="new")prompt("new","New project directory");
        else { owner.shutdown(); adapter.close(); }
    }
    void select(std::string id) {
        const bool different=selected!=id;
        selected=std::move(id);
        if(auto* c=control();c&&different) {
            if(c->kind=="text")event="text_changed";
            else if(c->kind=="choice"||c->kind=="menu")event="choose";
            else if(c->kind=="toggle")event="checked";
            else if(c->kind=="list")event="activate_record";
            else if(c->kind=="bitmap"||c->kind=="label"||c->kind=="group")event="pointer";
            else event="activate";
        }
        sync_fields();
    }
    void add_item() {
        if(preview)preview=false;
        if(mode=="forms") {
            if(!form())throw std::runtime_error("Add a form first.");
            Control c; c.id=unique(palette); c.kind=palette; c.label=palette; c.layout={24,24+48.0*form()->controls.size(),160,36};
            if(palette=="label"||palette=="text")c.text=palette=="label"?"Label":"";
            if(palette=="text"){c.multiline=true;c.layout.height=90;}
            if(palette=="choice"||palette=="menu")c.options={{"first","First","first",true},{"second","Second","second",true}};
            if(palette=="group") { c.layout.width=260;c.layout.height=180; }
            if(palette=="list"||palette=="bitmap")c.layout.height=120;
            selected=c.id;form()->controls.push_back(std::move(c));
        } else if(mode=="flows") {
            Block b; b.id=unique("block"); b.label="Block";b.flow=document;b.x=40+32.0*project.blocks.size();b.y=40;
            b.inputs={{"in","float",true}};b.outputs={{"out","float",true}};selected=b.id;project.blocks.push_back(std::move(b));
        } else throw std::runtime_error("Use Forms or Flows to add an element.");
        changed();select(selected);
    }
    void remove() {
        if(selected.empty())return;
        if(auto* f=form())std::erase_if(f->controls,[&](const auto& c){return c.id==selected;});
        for(auto& f:project.forms)for(auto& c:f.controls)if(c.parent==selected)c.parent.clear();
        std::erase_if(project.blocks,[&](const auto& b){return b.id==selected;});
        std::erase_if(project.edges,[&](const auto& e){return e.id==selected||e.from_block==selected||e.to_block==selected;});
        selected.clear();connection.reset();changed();sync_fields();
    }
    void duplicate() {
        if(auto* c=control()) { auto next=*c;next.id=unique(c->kind);next.layout.x+=20;next.layout.y+=20; selected=next.id;form()->controls.push_back(std::move(next)); }
        else if(auto* b=block()) { auto next=*b;next.id=unique("block");next.x+=30;next.y+=30;selected=next.id;project.blocks.push_back(std::move(next)); }
        else return;
        changed();sync_fields();
    }
    void apply_properties() {
        const auto [x,y]=pair_of(fields["property.position"]);
        if(auto* c=control()) {
            auto [w,h]=pair_of(fields["property.size"]);if(w<8||h<8)throw std::invalid_argument("Size must be at least 8 by 8.");
            c->layout={x,y,w,h};c->label=fields["property.label"];
            if(c->kind=="label")c->text=c->label;
        } else if(auto* b=block()) { b->x=x;b->y=y;b->label=fields["property.label"]; }
        else return;
        changed();
    }
    void begin_details() {
        if(auto* c=control()) {
            fields["detail.text"]=c->text; fields["detail.parent"]=c->parent; fields["detail.options"].clear();
            for(const auto& option:c->options)fields["detail.options"]+=option.id+" | "+option.label+" | "+option.value+"\n";
            const auto id=binding_for(*c);
            auto* b=binding(id); fields["detail.file"]=b?b->file:"";fields["detail.symbol"]=b?b->symbol:"";fields["detail.header"]=b?b->header:"";
            fields["detail.enabled"]=c->enabled?"true":"false";
            fields["detail.multiline"]=c->multiline?"true":"false";
            fields["detail.read_only"]=c->read_only?"true":"false";
        } else if(auto* b=block()) {
            fields["detail.file"]=b->file; fields["detail.symbol"]=b->factory; fields["detail.header"]=b->header;
            fields["detail.inputs"].clear(); fields["detail.outputs"].clear();fields["detail.params"].clear();
            for(const auto& p:b->inputs)fields["detail.inputs"]+=p.id+" : "+p.type+"\n";
            for(const auto& p:b->outputs)fields["detail.outputs"]+=p.id+" : "+p.type+"\n";
            for(const auto& [k,v]:b->params)fields["detail.params"]+=k+" = "+v+"\n";
        } else throw std::runtime_error("Select a widget or block first.");
        modal="details";
    }
    std::vector<Port> ports(const std::string& text,const std::vector<Port>& previous) {
        std::vector<Port> out;
        for(const auto& line:lines(text)) {
            const auto pos=line.find(':'); if(pos==std::string::npos)throw std::invalid_argument("Ports use name : C++ type, one per line.");
            auto id=trim(line.substr(0,pos)), type=trim(line.substr(pos+1));
            if(!safe_id(id)||!valid_cpp_type(type))throw std::invalid_argument("Invalid port name or C++ type.");
            const auto old=std::find_if(previous.begin(),previous.end(),[&](const auto& p){return p.id==id&&p.type==type;});
            out.push_back({id,type,old==previous.end()?true:old->required});
        }
        return out;
    }
    void apply_details() {
        auto before=project;
        try {
            if(auto* c=control()) {
                const auto previous_options=c->options;
                c->text=fields["detail.text"];c->parent=fields["detail.parent"];c->enabled=fields["detail.enabled"]!="false";c->options.clear();
                c->multiline=fields["detail.multiline"]=="true";c->read_only=fields["detail.read_only"]=="true";
                for(const auto& line:lines(fields["detail.options"])) {
                    const auto p=line.find('|'),q=p==std::string::npos?p:line.find('|',p+1);
                    Option o;o.id=trim(line.substr(0,p));o.label=p==std::string::npos?o.id:trim(line.substr(p+1,q==std::string::npos?q:q-p-1));o.value=q==std::string::npos?o.id:trim(line.substr(q+1));
                    const auto old=std::find_if(previous_options.begin(),previous_options.end(),[&](const auto& v){return v.id==o.id;});
                    if(old!=previous_options.end())o.enabled=old->enabled;
                    c->options.push_back(std::move(o));
                }
                if(!fields["detail.file"].empty()) {
                    const auto id=binding_for(*c);
                    auto* b=binding(id);
                    if(!b) { Binding next;next.id=unique("handler");next.event=event;project.bindings.push_back(next);b=&project.bindings.back();c->event_bindings[event]=b->id; }
                    b->file=fields["detail.file"];b->symbol=fields["detail.symbol"];b->header=fields["detail.header"];b->event=event;
                }
            } else if(auto* b=block()) {
                b->file=fields["detail.file"];b->header=fields["detail.header"];b->factory=fields["detail.symbol"];b->symbol=b->factory;
                b->inputs=ports(fields["detail.inputs"],b->inputs);b->outputs=ports(fields["detail.outputs"],b->outputs);b->params.clear();
                for(const auto& line:lines(fields["detail.params"])) {const auto p=line.find('=');if(p==std::string::npos)throw std::invalid_argument("Parameters use name = value.");b->params.emplace(trim(line.substr(0,p)),trim(line.substr(p+1)));}
            }
            (void)write_project(project); // Safe drafts may still need wiring.
            log=diagnostics(validate(project));
            modal.clear();changed();sync_fields();
        } catch(...) { project=std::move(before);throw; }
    }
    void open_file(const std::filesystem::path& path,std::string anchor={}) {
        if(!files)throw std::runtime_error("Open or create a project first.");
        if(code&&code->dirty()) {
            modal="code";
            throw std::runtime_error("Save or discard the current source edits before opening another file.");
        }
        auto snapshot=files->read(path);
        if(snapshot.text.find('\0')!=std::string::npos)
            throw std::runtime_error("The source contains zero bytes; use an external binary editor. No bytes were changed.");
        code=std::make_unique<CodeBuffer>(std::move(snapshot)); modal="code";
        fields["code.find"]=std::move(anchor);fields["code.text"]=code->text();
        reveal_code=true;
        success("Editing "+path.generic_string());
    }
    void edit_code() {
        if(mode=="files") {open_file(selected);return;}
        if(!files)throw std::runtime_error("Save the project in a directory before creating source files.");
        std::string file,anchor,stub;
        if(auto* c=control()) {
            const auto id=binding_for(*c);
            auto* b=binding(id);
            if(!b) {
                Binding next;next.id=unique("handler");next.event=event;next.file="src/ui/"+generated_identifier(c->id)+"_"+event+".hpp";
                next.header=next.file;next.symbol="on_"+generated_identifier(c->id)+"_"+event;next.anchor=next.symbol;
                project.bindings.push_back(next);b=&project.bindings.back();c->event_bindings[event]=b->id;changed();
            }
            file=b->file;anchor=b->anchor.empty()?b->symbol:b->anchor;stub=handler_stub(*b);
        } else if(auto* b=block()) {
            if(b->file.empty()) {b->file="src/blocks/"+generated_identifier(b->id)+".hpp";b->header=b->file;b->factory="make_"+generated_identifier(b->id);b->symbol=b->factory;changed();}
            file=b->file;anchor=b->symbol.empty()?b->factory:b->symbol;stub=block_stub(*b);
        } else throw std::runtime_error("Select a widget, block or source file.");
        if(const auto parent=std::filesystem::path(file).parent_path();!parent.empty())files->ensure_directory(parent);
        auto original=files->inspect(file);
        if(!original.identity.exists) { (void)files->save(original,stub);refresh_files(); }
        open_file(file,anchor);
    }
    void source_find() {
        if(!code)return;
        const gui::Widget* widget=nullptr;for(const auto& w:view.widgets)if(w.spec.key.id=="code.text"){widget=&w;break;}if(!widget)return;
        auto selection=adapter.text_selection(widget->spec.key);
        auto at=code->find(fields["code.find"],selection.caret);
        if(at==std::string::npos)at=code->find(fields["code.find"]);
        if(at==std::string::npos){failure("Text not found.");return;}
        adapter.focus(widget->spec.key);adapter.text_selection(widget->spec.key,{at,at+fields["code.find"].size()});
    }
    const Recipe* recipe(std::string_view id) const { for(const auto& r:project.recipes)if(r.id==id)return &r;return nullptr; }
    void start_recipe(std::string_view id) {
        if(!files)throw std::runtime_error("Open a project first.");
        const auto* r=recipe(id);if(!r)throw std::runtime_error("No "+std::string(id)+" recipe. Add an argv recipe to the project JSON; normal command-line builds also work.");
        process.start(r->argv,files->directory(r->working_directory));
        // tick must observe even an immediately completed or failed start.
        process_status={};process_status.state=ProcessState::running;
        log.clear();success(std::string(id)+" running...");
    }
    void build(bool then_run) {
        if(process.running())throw std::runtime_error("Stop the current process first.");
        save();if(error)return;
        run_after_build=then_run;start_recipe("build");
    }
    void external() {
        if(!files||!code)return;
        if(process.running())throw std::runtime_error("Stop the current process first.");
        code->save(*files);
        std::vector<std::string> args;
        auto cwd=files->root();
        if(const auto* r=recipe("edit")){args=r->argv;cwd=files->directory(r->working_directory);}
        else if(const auto* editor=std::getenv("EDITOR"))args.push_back(editor);
        else throw std::runtime_error("Set EDITOR to an executable path, or define an edit argv recipe. No shell is used.");
        bool replaced=false;for(auto& a:args)if(a=="{file}"){a=files->absolute(code->path()).string();replaced=true;}
        if(!replaced)args.push_back(files->absolute(code->path()).string());
        run_after_build=false;process.start(args,cwd);
        process_status={};process_status.state=ProcessState::running;
        log.clear();success("External editor running; use Reload afterward.");
    }
    void connect(Hit hit) {
        if(!hit.direction)return;
        if(!connection) {connection=std::move(hit);success("Select the matching destination port.");return;}
        auto a=*connection,b=std::move(hit);connection.reset();
        if(a.direction==b.direction)throw std::invalid_argument("Connect an output to an input.");
        if(a.direction==PortDirection::input)std::swap(a,b);
        Edge edge;edge.id=unique("edge");edge.from_block=a.object;edge.from_port=a.port;edge.to_block=b.object;edge.to_port=b.port;
        const auto prior=validate(project);
        project.edges.push_back(std::move(edge));auto ds=validate(project);
        std::vector<Diagnostic> introduced;
        for(const auto& d:ds)if(d.severity==Severity::error&&std::none_of(prior.begin(),prior.end(),[&](const auto& old){return old.severity==d.severity&&old.path==d.path&&old.message==d.message;}))introduced.push_back(d);
        if(!introduced.empty()){project.edges.pop_back();throw std::invalid_argument(diagnostics(introduced));}
        log=diagnostics(ds);
        changed();success("Connected ports.");
    }
    void pointer(const gui::PointerInput& input) {
        if(preview)return;
        if(input.kind==gui::PointerKind::wheel) {
            if(input.control)zoom=std::clamp(zoom*(input.wheel_y>0?1.1:1/1.1),.25,3.0);
            else {pan.x=std::max(0.0,pan.x-input.wheel_x*28/zoom);pan.y=std::max(0.0,pan.y-input.wheel_y*28/zoom);}
            return;
        }
        if(input.kind==gui::PointerKind::cancel){
            if(drag){selected=drag->id;if(auto* c=control())c->layout=drag->original;else if(auto* b=block()){b->x=drag->original.x;b->y=drag->original.y;}sync_fields();}
            drag.reset();return;
        }
        if(input.kind==gui::PointerKind::move&&drag) {
            const auto p=canvas.view_to_model(input.position);const auto dx=p.x-drag->initial.x,dy=p.y-drag->initial.y;
            selected=drag->id;
            if(auto* c=control()) {
                if(drag->resize){c->layout.width=std::max(8.0,drag->original.width+dx);c->layout.height=std::max(8.0,drag->original.height+dy);}
                else {c->layout.x=std::max(0.0,drag->original.x+dx);c->layout.y=std::max(0.0,drag->original.y+dy);}
            } else if(auto* b=block()){b->x=std::max(0.0,drag->original.x+dx);b->y=std::max(0.0,drag->original.y+dy);}
            sync_fields();return;
        }
        if(input.kind==gui::PointerKind::release&&drag) {drag.reset();changed();if(input.clicks>=2)edit_code();return;}
        if(input.kind!=gui::PointerKind::press&&input.kind!=gui::PointerKind::click&&input.kind!=gui::PointerKind::double_click&&input.kind!=gui::PointerKind::release)return;
        auto hit=canvas.hit_test(input.position);
        if(!hit){selected.clear();connection.reset();sync_fields();return;}
        select(hit->object);
        if(hit->direction) {if(input.kind!=gui::PointerKind::press)connect(*hit);return;}
        if(input.kind==gui::PointerKind::double_click||(input.kind==gui::PointerKind::release&&input.clicks>=2)) {if(!hit->edge)edit_code();return;}
        if(input.kind==gui::PointerKind::press&&!hit->edge) {
            Rect r;if(auto* c=control())r=c->layout;else if(auto* b=block())r={b->x,b->y,0,0};
            drag=Drag{selected,canvas.view_to_model(input.position),input.position,hit->resize,r};
        }
    }
    void action(std::string_view id) {
        if(id=="editor.open")require_clean("open");
        else if(id=="editor.new")require_clean("new");
        else if(id=="editor.save"){if(files)save();else prompt("save_as","Save project in directory");}
        else if(id=="editor.undo") {if(auto p=history.undo()){project=std::move(*p);sync_fields();success("Undone.");}}
        else if(id=="editor.redo") {if(auto p=history.redo()){project=std::move(*p);sync_fields();success("Redone.");}}
        else if(id=="editor.preview"){preview=!preview;success(preview?"Layout preview; application code is not executed.":"Design mode.");}
        else if(id=="editor.build")build(false);
        else if(id=="editor.run")build(true);
        else if(id=="editor.stop"){process_status=process.cancel();run_after_build=false;success("Process stopped.");}
        else if(id=="editor.add")add_item();
        else if(id=="editor.remove")remove();
        else if(id=="editor.duplicate")duplicate();
        else if(id=="editor.document.new") {if(mode=="flows"){Flow f{unique("flow"),"New flow"};document=f.id;project.flows.push_back(std::move(f));}else{Form f;f.id=unique("form");f.label="New form";document=f.id;project.forms.push_back(std::move(f));}selected.clear();changed();sync_fields();}
        else if(id=="editor.apply")apply_properties();
        else if(id=="editor.details")begin_details();
        else if(id=="editor.code")edit_code();
        else if(id=="editor.zoom.in")zoom=std::min(3.0,zoom*1.2);
        else if(id=="editor.zoom.out")zoom=std::max(.25,zoom/1.2);
        else if(id=="editor.zoom.reset"){zoom=1;pan={};}
        else if(id=="detail.apply")apply_details();
        else if(id=="detail.cancel")modal.clear();
        else if(id=="code.save"){code->save(*files);success("Source saved.");}
        else if(id=="code.undo"){(void)code->undo();fields["code.text"]=code->text();}
        else if(id=="code.redo"){(void)code->redo();fields["code.text"]=code->text();}
        else if(id=="code.reload"){if(code->dirty())throw std::runtime_error("Save or discard local edits before reloading.");code->reload(files->read(code->path()));fields["code.text"]=code->text();success("Reloaded source.");}
        else if(id=="code.external")external();
        else if(id=="code.find.next")source_find();
        else if(id=="code.close"){if(code->dirty()){failure("Save edits or choose Discard to close this buffer.");}else{modal.clear();code.reset();}}
        else if(id=="code.discard"){modal.clear();code.reset();success("Unsaved buffer discarded.");}
        else if(id=="unsaved.save"){if(!files){prompt("save_as","Save project in directory");}else{save();if(!error){modal.clear();auto next=std::exchange(pending_action,{});require_clean(next);}}}
        else if(id=="unsaved.discard"){modal.clear();if(code)code.reset();saved_design=write_project(project);auto next=std::exchange(pending_action,{});require_clean(next);}
        else if(id=="unsaved.cancel"){modal=std::exchange(previous_modal,{});pending_action.clear();}
        else if(id=="editor.file.open")open_file(fields["file.path"]);
        ++epoch;
    }
    gui::Widget& add(gui::Kind kind,std::string id,std::string label,gui::Rect bounds,std::string parent="editor.root") {
        gui::Widget w;w.spec.key={std::move(id),generation};w.spec.kind=kind;w.spec.parent=std::move(parent);
        w.state.bounds=bounds;w.state.label=label;w.state.accessible_name=label;
        if(kind==gui::Kind::label)w.state.text=label;
        w.state.font.size=14;view.widgets.push_back(std::move(w));return view.widgets.back();
    }
    gui::Widget& button(std::string id,std::string label,double x,double y,double w=86,std::string parent="editor.root") {
        return add(gui::Kind::button,std::move(id),std::move(label),{x,y,w,30},std::move(parent));
    }
    gui::Widget& input(std::string id,std::string label,gui::Rect area,bool multi=false,std::string parent="editor.root") {
        auto& w=add(gui::Kind::text,id,std::move(label),area,std::move(parent));w.state.text=fields[id];
        w.spec.text_policy={multi,false,multi?8U*1024U*1024U:4096U,gui::SubmitKey::none};return w;
    }
    void label(std::string text,double x,double y,double width,std::string parent="editor.root") {
        add(gui::Kind::label,"label."+std::to_string(view.widgets.size()),std::move(text),{x,y,width,22},std::move(parent));
    }
    void choice(std::string id,std::string title,gui::Rect area,const std::vector<std::pair<std::string,std::string>>& values,const std::string& value,std::string parent="editor.root") {
        auto& w=add(gui::Kind::choice,std::move(id),std::move(title),area,std::move(parent));
        for(const auto& [key,text]:values)w.state.options.push_back({key,text,key,true});
        if(std::any_of(values.begin(),values.end(),[&](const auto& v){return v.first==value;}))w.state.selected=value;
    }
    void draw_modal(double width,double height) {
        const auto x=std::max(8.0,width*.07),y=std::max(55.0,height*.06),w=std::max(380.0,width-2*x),h=std::max(300.0,height-y-45);
        const std::string parent="modal.root";
        auto& group=add(gui::Kind::group,parent,"",{x,y,w,h});group.state.content_size={w,h};
        view.modal_root=group.spec.key;
        if(modal=="code"&&code) {
            label(code->path().generic_string()+(code->dirty()?"  (modified)":""),x+12,y+8,w-24,parent);
            double bx=x+12;
            for(const auto& [id,text]:std::array<std::pair<const char*,const char*>,7>{{{"code.save","Save"},{"code.undo","Undo"},{"code.redo","Redo"},{"code.reload","Reload"},{"code.external","External"},{"code.close","Close"},{"code.discard","Discard"}}}) {
                button(id,text,bx,y+36,77,parent);bx+=81;
            }
            input("code.find","Find",{x+12,y+74,std::max(120.0,w-130),28},false,parent);
            button("code.find.next","Find next",x+w-108,y+74,96,parent);
            auto& text=input("code.text","Source code",{x+12,y+112,w-24,h-156},true,parent);
            text.state.font.size=14; text.state.wrap=gui::TextWrap::none;
            label("Ordinary source file. Generated application code is separate.",x+12,y+h-34,w-24,parent);
            view.key_bindings.push_back({gui::ShortcutKey::escape,{"code.close",generation}});
        } else if(modal=="details") {
            label("Details: "+selected,x+12,y+8,w-24,parent);
            const double column=(w-36)/2;
            auto field=[&](const char* id,const char* title,double px,double py,double fh=28) {
                label(title,px,py,column,parent);input(id,title,{px,py+23,column,fh},fh>28,parent);
            };
            field("detail.file","Source file (relative to project)",x+12,y+40);
            field("detail.header","C++ declaration header",x+24+column,y+40);
            field("detail.symbol",control()?"Handler symbol":"Factory symbol",x+12,y+104);
            if(control()) {
                field("detail.parent","Parent group ID (optional)",x+24+column,y+104);
                field("detail.text","Initial text",x+12,y+170,90);
                field("detail.options","Options: ID | label | value",x+24+column,y+170,90);
                choice("detail.enabled","Enabled",{x+12,y+300,column,30},{{"true","Enabled"},{"false","Disabled"}},fields["detail.enabled"],parent);
                if(control()->kind=="text") {
                    choice("detail.multiline","Text lines",{x+24+column,y+300,column,30},{{"true","Multiple lines"},{"false","Single line"}},fields["detail.multiline"],parent);
                    choice("detail.read_only","Editing",{x+12,y+345,column,30},{{"true","Read only"},{"false","Editable"}},fields["detail.read_only"],parent);
                }
            } else {
                field("detail.inputs","Input ports: name : type",x+12,y+170,110);
                field("detail.outputs","Output ports: name : type",x+24+column,y+170,110);
                field("detail.params","Parameters: name = value",x+12,y+315,70);
            }
            button("detail.apply","Apply",x+12,y+h-46,100,parent);
            button("detail.cancel","Cancel",x+124,y+h-46,100,parent);
            view.key_bindings.push_back({gui::ShortcutKey::escape,{"detail.cancel",generation}});
        } else if(modal=="unsaved") {
            label("There are unsaved changes.",x+16,y+18,w-32,parent);
            label("Save before continuing, discard changes, or cancel.",x+16,y+54,w-32,parent);
            button("unsaved.save","Save",x+16,y+100,100,parent);
            button("unsaved.discard","Discard",x+132,y+100,100,parent);
            button("unsaved.cancel","Cancel",x+248,y+100,100,parent);
        }
    }
    void publish() {
        if(stopped||adapter.closed())return;
        pending=true;
        view.widgets.clear();view.pages.clear();view.active_page.reset();view.key_bindings.clear();view.modal_root.reset();
        const auto width=std::max(640.0,view.client_size.width),height=std::max(480.0,view.client_size.height);
        view.title="Foundation Editor — "+project.name+(dirty()?" *":"");
        auto& root=add(gui::Kind::group,"editor.root","",{0,0,width,height},"");root.state.content_size={width,height};
        auto chrome=self_generated::snapshot("editor.chrome",generation);
        for(auto& widget:chrome.widgets) {
            widget.spec.page.clear();
            if(widget.spec.parent.empty())widget.spec.parent="editor.root";
            view.widgets.push_back(std::move(widget));
        }
        const bool running=process.running();
        for(auto& widget:view.widgets) {
            if(widget.spec.key.id=="editor.stop")widget.state.enabled=running;
            if(widget.spec.key.id=="editor.build"||widget.spec.key.id=="editor.run")widget.state.enabled=!running&&files!=nullptr;
            if(widget.spec.key.id=="editor.undo")widget.state.enabled=history.can_undo();
            if(widget.spec.key.id=="editor.redo")widget.state.enabled=history.can_redo();
        }
        label(files?files->root().string():"No project directory",12,46,width-24);
        choice("editor.mode","Workspace",{12,74,172,30},{{"forms","Forms"},{"flows","Flows"},{"files","Files"}},mode);
        std::vector<std::pair<std::string,std::string>> docs;
        if(mode=="flows")for(const auto& f:project.flows)docs.emplace_back(f.id,f.label);
        else for(const auto& f:project.forms)docs.emplace_back(f.id,f.label);
        choice("editor.document","Document",{198,74,260,30},docs,document);
        button("editor.document.new",mode=="flows"?"New flow":"New form",468,74,100);
        button("editor.zoom.out","-",width-120,74,30);button("editor.zoom.reset",number(zoom*100)+"%",width-85,74,66);
        button("editor.zoom.in","+",width-155,74,30);
        const double body_y=120,body_h=std::max(230.0,height-270),right=width-235;
        auto& list=add(gui::Kind::list,"editor.objects",mode=="files"?"Source files":"Elements",{12,body_y,174,body_h});
        list.spec.row_height=29;list.state.content_size={174,body_h};
        auto row=[&](const std::string& id,const std::string& text){gui::Record r;r.id=id;r.accessible_text=text;r.activatable=true;r.cells={{text,{4,0,162,29},{}}};list.state.records.push_back(std::move(r));};
        if(mode=="forms"&&form())for(const auto& c:form()->controls)row(c.id,c.label.empty()?c.id:c.label);
        else if(mode=="flows") {for(const auto& b:project.blocks)if(b.flow==document)row(b.id,b.label.empty()?b.id:b.label);for(const auto& e:project.edges){auto i=std::find_if(project.blocks.begin(),project.blocks.end(),[&](const auto& b){return b.id==e.from_block&&b.flow==document;});if(i!=project.blocks.end())row(e.id,e.from_port+" -> "+e.to_port);}}
        else if(mode=="files")for(const auto& file:file_names)row(file,file);
        if(std::any_of(list.state.records.begin(),list.state.records.end(),[&](const auto& r){return r.id==selected;}))list.state.selected=selected;
        list.state.content_size.height=list.state.records.size()*29;
        if(mode!="files") {
            canvas_options={mode=="flows"?CanvasMode::flows:CanvasMode::forms,document,selected,{198,body_y,std::max(120.0,right-212),body_h},zoom,pan,preview,connection,
                [this](const gui::TextMeasureRequest& request){return adapter.measure_text(request);}};
            auto widgets=canvas.render(project,canvas_options);
            for(auto& w:widgets){w.spec.key.generation=generation;if(w.spec.parent.empty())w.spec.parent="editor.root";view.widgets.push_back(std::move(w));}
        } else {
            label("Double-click a source file to edit it.",210,145,std::max(160.0,right-225));
            input("file.path","Relative path",{210,180,std::max(120.0,right-225),32});button("editor.file.open","Open file",210,222,110);
            label("C++, Rust and build files remain ordinary text files.",210,270,std::max(160.0,right-225));
        }
        label("Properties",right,body_y,210);
        label(selected.empty()?"Select an element":selected,right,body_y+25,210);
        label("Label",right,body_y+56,210);input("property.label","Label",{right,body_y+80,216,30});
        label("Position: x, y",right,body_y+118,210);input("property.position","Position",{right,body_y+142,216,30});
        label("Size: width, height",right,body_y+180,210);input("property.size","Size",{right,body_y+204,216,30});
        button("editor.apply","Apply",right,body_y+248,100);button("editor.code","Edit code",right+110,body_y+248,106);
        choice("editor.event","Event",{right,body_y+292,216,30},{{"activate","Activate / click"},{"text_changed","Text changed"},{"submit","Submit text"},{"choose","Choice changed"},{"checked","Toggle changed"},{"select_record","Row selected"},{"activate_record","Row activated"},{"pointer","Pointer"},{"action","Named action"}},event);
        button("editor.duplicate","Duplicate",right,body_y+338,100);button("editor.remove","Delete",right+110,body_y+338,106);
        if(mode=="forms")choice("editor.palette","Widget",{12,height-136,174,30},{{"button","Button"},{"label","Label"},{"text","Text"},{"choice","Dropdown"},{"toggle","Toggle"},{"list","List"},{"bitmap","Bitmap"},{"menu","Menu"},{"group","Group"}},palette);
        button("editor.add",mode=="flows"?"Add block":"Add widget",198,height-136,112);
        label(connection?"Choose the other port to connect.":preview?"Preview: code is inactive.":"Double-click to edit code. Drag to move; Ctrl+wheel to zoom.",322,height-132,width-340);
        auto& output=add(gui::Kind::text,"editor.diagnostics","Diagnostics",{12,height-95,width-24,48});output.spec.text_policy={true,true,2*1024*1024,gui::SubmitKey::none};output.state.text=display_log(log);
        auto& state=add(gui::Kind::label,"editor.status",status,{12,height-36,width-24,26});state.state.font.tone=error?gui::Tone::error:gui::Tone::muted;
        if(!modal.empty())draw_modal(width,height);
        else {
            view.key_bindings.push_back({gui::ShortcutKey::f2,{"editor.code",generation}});
            view.key_bindings.push_back({gui::ShortcutKey::f5,{"editor.run",generation}});
            view.key_bindings.push_back({gui::ShortcutKey::f3,{"editor.save",generation}});
        }
        // Retired identities and changed specifications cannot reuse a native
        // widget generation. Unchanged live controls keep focus/caret/capture.
        std::map<std::string,bool> active;
        for(auto& widget:view.widgets) {
            auto& previous=widget_lives[widget.spec.key.id];
            auto compare=widget.spec;compare.key.generation=previous.spec.key.generation;
            if(previous.active&&previous.scene==generation&&compare==previous.spec)
                widget.spec.key.generation=previous.spec.key.generation;
            else widget.spec.key.generation=++widget_generation;
            previous={widget.spec,true,generation};active[widget.spec.key.id]=true;
        }
        for(auto& [id,life]:widget_lives)if(!active.contains(id))life.active=false;
        if(view.modal_root)view.modal_root=widget_lives.at(view.modal_root->id).spec.key;
        for(auto& key:view.key_bindings)key.target=widget_lives.at(key.target.id).spec.key;
        ++view.revision;
        adapter.present(view);pending=false;
        if(reveal_code&&modal=="code") {
            reveal_code=false;
            if(!fields["code.find"].empty())source_find();
            else if(const auto it=widget_lives.find("code.text");it!=widget_lives.end())adapter.focus(it->second.spec.key);
        }
    }
};
Application::Application(gui::Adapter& adapter):impl_(std::make_unique<Impl>(*this,adapter)) {}
Application::~Application(){shutdown();}
const gui::Snapshot& Application::view() const noexcept{return impl_->view;}
bool Application::presentation_pending()const noexcept{return impl_->pending;}
std::uint64_t Application::input_epoch()const noexcept{return impl_->epoch;}
void Application::retry_presentation(){if(impl_->pending)impl_->publish();}
void Application::shutdown()noexcept{
    if(!impl_||impl_->stopped)return;
    impl_->stopped=true;impl_->services.shutdown();
    try{if(impl_->process.running())(void)impl_->process.cancel();}catch(...){}
}
void Application::invoke(std::string_view action){impl_->action(action);}
std::optional<gui::ServiceRequest> Application::next_service(){return impl_->services.begin_next();}
bool Application::complete_service(gui::ServiceResult result){
    auto& p=*impl_;if(!p.services.complete(result))return false;
    if(result.status==gui::ServiceStatus::success){try{if(p.prompt_action=="open")p.open(result.value);else if(p.prompt_action=="new")p.create(result.value);else if(p.prompt_action=="save_as"){p.create(result.value,true);if(!p.pending_action.empty()){auto next=std::exchange(p.pending_action,{});p.require_clean(next);}}}catch(const std::exception& e){p.failure(e.what());}}
    else if(result.status==gui::ServiceStatus::error)p.failure(result.error);
    p.prompt_action.clear();p.publish();return true;
}
void Application::handle(gui::Event event){
    auto& p=*impl_;if(p.stopped||p.adapter.closed())return;
    if(std::holds_alternative<gui::CloseEvent>(event)) {
        try{p.require_clean("close");if(!p.stopped)p.publish();}catch(const std::exception& e){p.failure(e.what());p.publish();}return;
    }
    if(!gui::normalize_event(p.view,event,[&](const auto& key){return p.adapter.scroll_offset(key);}))return;
    try{
        if(const auto* resize=std::get_if<gui::ResizeEvent>(&event)){p.view.client_size=resize->client_size;p.view.display_scale=resize->display_scale;}
        else if(const auto* w=std::get_if<gui::WidgetEvent>(&event)) {
            const auto& id=w->target.id;
            std::visit([&](const auto& input){
                using T=std::decay_t<decltype(input)>;
                if constexpr(std::is_same_v<T,gui::EditText>){
                    if(id=="code.text"&&p.code)p.code->set_text(input.value);
                    p.fields[id]=input.value;
                } else if constexpr(std::is_same_v<T,gui::ChooseOption>){
                    if(id=="editor.mode"){p.mode=input.id;p.choose_document();}
                    else if(id=="editor.document"){p.document=input.id;p.choose_document();}
                    else if(id=="editor.palette")p.palette=input.id;
                    else if(id=="editor.event")p.event=input.id;
                    else p.fields[id]=input.id;
                } else if constexpr(std::is_same_v<T,gui::SelectRecord>){p.select(input.id);}
                else if constexpr(std::is_same_v<T,gui::ActivateRecord>){p.select(input.id);p.edit_code();}
                else if constexpr(std::is_same_v<T,gui::Activate>){
                    if(!self_generated::dispatch_handler(*this,*this,*w))p.action(id);
                } else if constexpr(std::is_same_v<T,gui::PointerInput>){if(id.starts_with("canvas."))p.pointer(input);}
                else if constexpr(std::is_same_v<T,gui::InvokeAction>){if(input.id=="edit"||input.id=="edit_code")p.edit_code();}
            },w->input);
        }
        ++p.epoch;p.publish();
    }catch(const std::exception& e){p.failure(e.what());try{p.publish();}catch(...){p.pending=true;}}
}
void Application::tick(){
    auto& p=*impl_;if(p.stopped)return;
    if(p.adapter.closed()){shutdown();return;}
    if(p.process.running()||p.process_status.state==ProcessState::running) {
        auto next=p.process.poll();
        const bool update=next.output!=p.process_status.output||next.state!=p.process_status.state;
        p.process_status=std::move(next);
        if(update){
            p.log=p.process_status.output;
            if(p.process_status.finished()){
                if(p.process_status.state==ProcessState::succeeded){
                    p.success("Process completed successfully.");
                    if(p.run_after_build){p.run_after_build=false;try{p.start_recipe("run");}catch(const std::exception& e){p.failure(e.what());}}
                }else{p.run_after_build=false;p.failure(p.process_status.error.empty()?"Process failed (exit "+std::to_string(p.process_status.exit_code)+").":p.process_status.error);}
            }
            p.publish();
        }
    }
    retry_presentation();
}
void Application::qualify(const std::function<void()>& present){
    auto& p=*impl_;
    const auto require=[](bool condition,const char* what){if(!condition)throw std::runtime_error(what);};
    const auto activate=[&](const char* id){const auto found=std::find_if(p.view.widgets.begin(),p.view.widgets.end(),[&](const auto& w){return w.spec.key.id==id;});require(found!=p.view.widgets.end(),"Missing editor action");handle(gui::WidgetEvent{found->spec.key,gui::Activate{}});present();};
    present();require(!p.pending&&!p.view.widgets.empty(),"Editor did not present.");
    if(p.project.forms.empty()){Form f;f.id="smoke.form";f.label="Smoke form";p.project.forms.push_back(f);}
    p.history.reset(p.project);
    p.mode="forms";p.choose_document();p.publish();
    const auto count=p.form()->controls.size();activate("editor.add");
    require(p.form()->controls.size()==count+1,"Editor add-widget failed.");
    activate("editor.undo");require(p.form()->controls.size()==count,"Editor undo failed.");
    activate("editor.redo");require(p.form()->controls.size()==count+1,"Editor redo failed.");
    activate("editor.preview");require(p.preview,"Editor preview failed.");activate("editor.preview");
    p.saved_design=write_project(p.project); // Smoke uses memory only, never writes a project.
    p.code.reset();p.modal.clear();present();
}
} // namespace foundation::editor
