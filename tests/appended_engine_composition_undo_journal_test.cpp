// SPDX-License-Identifier: CC0-1.0
// Pure journal ownership fixtures. These do not execute or emulate WebCore.
#include "../recipes/webkitwasm-document-v2/overlays/editor/wrapper/src/embedder/BibUndoHistory.h"
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(COMPOSITION_JOURNAL_NO_EXCEPTIONS)
struct NoThrowStep {
    int inverse{}, removed{};
    void unapply() { ++inverse; }
    void reapply() { }
    void didRemoveFromUndoManager() { ++removed; }
};
int main() {
    BIB::UndoHistory<std::shared_ptr<NoThrowStep>> history;
    auto owned=std::make_shared<NoThrowStep>(); auto token=history.beginPending();
    history.registerUndo(owned);
    if(!history.detachForRollback(token,owned.get())||!history.consumeRollback(token,owned.get()))return 1;
    owned->unapply();
    if(!history.finishRollback(token,owned.get())||owned->inverse!=1||owned->removed!=1||history.canRedo())return 2;
    token=history.beginPending();history.registerUndo(owned);
    return history.commitPending(token,owned.get())&&history.undo()&&owned->inverse==2?0:3;
}
#else
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct FakeStep {
    int id, undone{}, redone{}, removed{};
    std::function<void()> onUndo, onRemove;
    explicit FakeStep(int value) : id(value) { }
    void unapply() { ++undone; if (onUndo) onUndo(); }
    void reapply() { ++redone; }
    void didRemoveFromUndoManager() { ++removed; if (onRemove) onRemove(); }
};
using Step=std::shared_ptr<FakeStep>;
using History=BIB::UndoHistory<Step>;
Step step(int value) { return std::make_shared<FakeStep>(value); }
void cancel(History& h, History::Token token, const Step& s) {
    check(h.detachForRollback(token,s.get()),"detach refused");
    check(h.consumeRollback(token,s.get()),"consume refused");
    if (s) s->unapply();
    check(h.finishRollback(token,s.get()),"finish refused");
}
void test(const std::string& name) {
    if(name=="normal") {
        History h;auto a=step(1);h.registerUndo(a);
        check(h.undo()&&a->undone==1&&h.canRedo(),"normal undo failed");
        check(h.redo()&&a->redone==1&&h.canUndo(),"normal redo failed");
    } else if(name=="empty") {
        History h;auto a=step(1);h.registerUndo(a);h.undo();auto t=h.beginPending();
        check(t&&!h.beginPending()&&h.matchesPending(t,nullptr),"empty/nested scope");
        cancel(h,t,{});check(h.canRedo()&&!h.canUndo()&&a->removed==0,"empty cancel changed history");
        check(!h.consumeRollback(t,nullptr)&&!h.finishRollback(t,nullptr),"empty scope replayed");
    } else if(name=="cancel") {
        History h;auto a=step(1),b=step(2),p=step(3);h.registerUndo(a);h.registerUndo(b);h.undo();
        auto t=h.beginPending();h.registerUndo(p);std::weak_ptr<FakeStep> retained=p;
        check(b->removed==0&&h.matchesPending(t,p.get()),"pending cleared prior redo");
        cancel(h,t,p);check(p->undone==1&&p->removed==1&&b->removed==0,"pending cancel not exact once");
        p.reset();check(retained.expired(),"finished pending reference leaked");
        check(h.redo()&&b->redone==1&&h.undo()&&b->undone==2&&h.undo()&&a->undone==1,"history order changed");
    } else if(name=="commit") {
        History h;auto a=step(1),p=step(2);h.registerUndo(a);h.undo();auto t=h.beginPending();h.registerUndo(p);
        check(!h.commitPending(t,a.get())&&h.matchesPending(t,p.get()),"foreign pointer committed");
        check(h.commitPending(t,p.get())&&a->removed==1&&!h.commitPending(t,p.get()),"commit not exact once");
        check(!h.canRedo()&&h.undo()&&p->undone==1,"commit not published normally");
    } else if(name=="empty_commit") {
        History h;auto a=step(1);h.registerUndo(a);h.undo();auto t=h.beginPending();
        check(h.commitPending(t,nullptr)&&h.canRedo()&&a->removed==0,"empty commit destroyed redo");
    } else if(name=="foreign") {
        History h;auto a=step(1),p=step(2),f=step(3);h.registerUndo(a);auto t=h.beginPending();h.registerUndo(p);h.registerUndo(f);
        check(!h.matchesPending(t,p.get())&&!h.detachForRollback(t,p.get()),"foreign step left eligible journal");
        check(h.undo()&&f->undone==1&&h.undo()&&p->undone==1&&h.undo()&&a->undone==1,"foreign edit discarded/reordered");
    } else if(name=="public_undo") {
        History h;auto p=step(1);auto t=h.beginPending();h.registerUndo(p);
        check(h.undo()&&p->undone==1&&!h.detachForRollback(t,p.get())&&h.redo()&&p->redone==1,"public replay did not invalidate scope");
    } else if(name=="clear") {
        History h;auto a=step(1),p=step(2),f=step(3);h.registerUndo(a);auto t=h.beginPending();h.registerUndo(p);
        a->onRemove=[&]{h.clear();h.registerUndo(f);};h.clear();
        check(!h.detachForRollback(t,p.get())&&p->removed==1&&a->removed==1&&h.undo()&&f->undone==1,"clear reentry resurrected old material");
    } else if(name=="tokens") {
        History h(128,2);auto t=h.beginPending();cancel(h,t,{});auto u=h.beginPending();
        check(u>t&&!h.commitPending(t,nullptr),"token reused/stale admitted");cancel(h,u,{});
        check(!h.beginPending(),"token exhaustion wrapped");
    } else if(name=="commit_clear") {
        History h;auto a=step(1),p=step(2);h.registerUndo(a);h.undo();auto t=h.beginPending();h.registerUndo(p);
        a->onRemove=[&]{h.clear();};check(!h.commitPending(t,p.get())&&!h.canUndo()&&p->removed==1,"commit resurrected callback-cleared step");
    } else if(name=="commit_exception") {
        History h;auto a=step(1),p=step(2);h.registerUndo(a);h.undo();auto t=h.beginPending();h.registerUndo(p);
        std::weak_ptr<FakeStep> retained=p;a->onRemove=[]{throw std::runtime_error("removal exception");};
        bool threw=false;try{h.commitPending(t,p.get());}catch(const std::runtime_error&){threw=true;}
        p.reset();check(threw&&!retained.expired()&&!h.canUndo()&&!h.canRedo()&&!h.detachForRollback(t,retained.lock().get()),"uncertain commit escaped quarantine");
        h.clear();check(retained.expired(),"terminal clear did not release quarantine");
    } else if(name=="finish_exception") {
        History h;auto p=step(1);auto t=h.beginPending();h.registerUndo(p);h.detachForRollback(t,p.get());h.consumeRollback(t,p.get());
        p->onRemove=[]{throw std::runtime_error("finish exception");};bool threw=false;
        try{h.finishRollback(t,p.get());}catch(const std::runtime_error&){threw=true;}
        check(threw&&p->removed==1&&!h.finishRollback(t,p.get())&&!h.consumeRollback(t,p.get())&&!h.canUndo(),"uncertain finalization replayed");
        h.clear();check(p->removed==1,"uncertain removal callback retried");
    } else if(name=="finish_clear") {
        History h;auto p=step(1);auto t=h.beginPending();h.registerUndo(p);h.detachForRollback(t,p.get());h.consumeRollback(t,p.get());
        p->onRemove=[&]{h.clear();};check(!h.finishRollback(t,p.get())&&p->removed==1&&!h.canRedo(),"finish reentry resurrected or removed twice");
    } else if(name=="foreign_rollback") {
        History h;auto p=step(1),f=step(2);auto t=h.beginPending();h.registerUndo(p);h.detachForRollback(t,p.get());h.registerUndo(f);
        check(!h.consumeRollback(t,p.get())&&!h.canUndo()&&!h.finishRollback(t,p.get()),"foreign callback did not block inverse");
        h.clear();check(p->removed==1&&f->removed==1,"quarantine lost foreign history");
    } else if(name=="limit") {
        History h;std::vector<Step> all;for(int i=0;i<128;++i){all.push_back(step(i));h.registerUndo(all.back());}
        auto p=step(128);auto t=h.beginPending();h.registerUndo(p);check(all[0]->removed==0,"pending applied history limit early");
        check(h.commitPending(t,p.get())&&all[0]->removed==1&&all[1]->removed==0,"128 limit changed");
        for(int i=0;i<128;++i) { check(h.undo(),"history retained wrong count"); }
        check(!h.undo(),"history exceeded limit");
    } else if(name=="inverse_exception") {
        History h;auto p=step(1);auto t=h.beginPending();h.registerUndo(p);h.detachForRollback(t,p.get());h.consumeRollback(t,p.get());
        p->onUndo=[]{throw std::runtime_error("inverse exception");};try{p->unapply();}catch(const std::runtime_error&){h.quarantine(t);}
        check(p->undone==1&&!h.consumeRollback(t,p.get())&&!h.finishRollback(t,p.get())&&!h.undo(),"uncertain inverse replayed");
    } else if(name=="same_step") {
        History h;auto p=step(1);auto t=h.beginPending();h.registerUndo(p);h.registerUndo(p);
        check(h.commitPending(t,p.get())&&h.undo()&&!h.undo()&&p->undone==1,"same native step duplicated");
    } else if(name=="empty_update") {
        History h;auto original=std::make_shared<int>(9),replacement=std::make_shared<int>(10);auto live=original;
        auto p=step(1);p->onUndo=[&]{live=original;};auto t=h.beginPending();h.registerUndo(p);live=replacement;live.reset();
        cancel(h,t,p);check(live==original&&p->undone==1&&!h.canRedo(),"live-empty cancel lost independent root/inverse");
    } else if(name=="owner_identity") {
        History h;int oldDocument=0,replacementDocument=0;auto t=h.beginPending(&oldDocument);
        check(h.matchesOwner(t,&oldDocument)&&!h.matchesOwner(t,&replacementDocument)&&h.matchesPending(t,nullptr),"empty historical owner mismatch");
        check(h.commitPending(t,nullptr)&&!h.matchesOwner(t,&oldDocument),"empty close retained owner");
        auto u=h.beginPending(&oldDocument);check(u!=t&&!h.matchesOwner(t,&oldDocument),"owner address reused old token");
        auto p=step(1);h.registerUndo(p);h.detachForRollback(u,p.get());
        check(h.matchesOwner(u,&oldDocument)&&!h.matchesPending(u,nullptr),"native debt became empty historical scope");
        h.quarantine(u);check(!h.matchesOwner(u,&oldDocument)&&!h.commitPending(u,nullptr),"quarantine accepted metadata close");h.clear();
        auto v=h.beginPending(&replacementDocument);h.registerUndo(p);h.registerUndo(step(2));
        check(!h.matchesOwner(v,&replacementDocument),"foreign invalidation retained owner binding");
        auto w=h.beginPending(&replacementDocument);h.clear();check(!h.matchesOwner(w,&replacementDocument),"clear retained owner binding");
    } else if(name=="commit_reentry") {
        History h;auto a=step(1),p=step(2);h.registerUndo(a);h.undo();auto t=h.beginPending();h.registerUndo(p);
        a->onRemove=[&]{check(!h.beginPending()&&!h.undo(),"commit allowed nested transaction/replay");};
        check(h.commitPending(t,p.get())&&h.undo()&&p->undone==1,"commit reentry damaged publish");
    } else throw std::runtime_error("unknown fixture case");
}
int main(int argc,char** argv) { try{check(argc==2,"one case required");test(argv[1]);std::cout<<"passed "<<argv[1]<<'\n';return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;} }

#endif
