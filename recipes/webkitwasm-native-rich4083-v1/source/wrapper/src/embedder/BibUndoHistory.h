// SPDX-License-Identifier: CC0-1.0
// Native adapters supply owned steps. Pending ownership is separate from history.
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <optional>
#include <utility>

namespace BIB {
template<typename OwnedStep> class UndoHistory {
public:
    using Token = std::uint64_t;
    explicit UndoHistory(std::size_t limit = 128, Token tokenLimit = std::numeric_limits<Token>::max())
        : m_limit(limit), m_tokenLimit(tokenLimit) { }

    Token beginPending(const void* owner = nullptr)
    {
        if (m_state != State::None || m_busy || m_replay != Replay::None || m_nextToken == m_tokenLimit)
            return 0;
        m_token = ++m_nextToken;
        m_owner = owner;
        m_scopeGeneration = m_generation;
        m_state = State::Pending;
        m_pendingRemovalStarted = m_rollbackRemovalStarted = false;
        return m_token;
    }
    bool matchesOwner(Token token, const void* owner) const
    {
        return token && token == m_token && m_scopeGeneration == m_generation &&
            m_state != State::None && m_state != State::Quarantined && m_owner == owner;
    }
    bool matchesPending(Token token, const void* exact) const
    {
        return eligible(token) && (m_pending ? identity(*m_pending) : nullptr) == exact;
    }
    bool commitPending(Token token, const void* exact)
    {
        if (!matchesPending(token, exact) || m_busy)
            return false;
        if (!m_pending) { resetScope(); return true; }
        Busy busy(*this);
        m_state = State::Committing;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
        try {
#endif
            const bool published = registerNormal(*m_pending, true);
            if (m_state != State::Committing || !published) return false;
            m_pending.reset(); resetScope();
            return true;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
        } catch (...) {
            // A callback-cleared scope must never be resurrected. Otherwise
            // retain uncertain material outside both replayable stacks.
            if (m_state != State::None) {
                std::erase_if(m_undo, [&](const auto& value) { return identity(value) == exact; });
                m_state = State::Quarantined;
            }
            throw;
        }
#endif
    }
    bool detachForRollback(Token token, const void* exact)
    {
        if (!matchesPending(token, exact) || m_busy)
            return false;
        m_rollback = std::exchange(m_pending, { });
        m_state = State::Detached;
        return true;
    }
    bool rollbackMatches(Token token, const void* exact) const
    {
        return token && token == m_token && m_scopeGeneration == m_generation &&
            (m_state == State::Detached || m_state == State::Consumed) &&
            (m_rollback ? identity(*m_rollback) : nullptr) == exact;
    }
    bool consumeRollback(Token token, const void* exact)
    {
        if (m_state != State::Detached || !rollbackMatches(token, exact) || m_busy)
            return false;
        m_state = State::Consumed; // Before the first potentially uncertain native effect.
        return true;
    }
    bool finishRollback(Token token, const void* exact)
    {
        if (m_state != State::Consumed || !rollbackMatches(token, exact) || m_busy)
            return false;
        if (!m_rollback) { resetScope(); return true; }
        Busy busy(*this);
        auto active = *m_rollback;
        m_state = State::Finishing;
        const auto generation = m_generation;
        m_rollbackRemovalStarted = true;
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS) || defined(_CPPUNWIND)
        try { active->didRemoveFromUndoManager(); }
        catch (...) { if (m_state == State::Finishing) m_state = State::Quarantined; throw; }
#else
        active->didRemoveFromUndoManager();
#endif
        if (m_state != State::Finishing || generation != m_generation)
            return false;
        m_rollback.reset(); resetScope();
        return true;
    }
    void quarantine(Token token)
    {
        if (token && token == m_token && m_state != State::None)
            { m_state = State::Quarantined; m_owner = nullptr; }
    }
    void registerUndo(OwnedStep step)
    {
        if (m_replay == Replay::Redo)
            return; // The retained step was transferred before reapply().
        if (m_busy) ++m_generation;
        if (m_state == State::Pending) {
            if (!m_pending) { m_pending = std::move(step); return; }
            if (identity(*m_pending) == identity(step)) return;
            promotePending(); // Chronologically precedes the distinct foreign edit.
        } else if (m_state != State::None) {
            ++m_generation; m_state = State::Quarantined; m_owner = nullptr;
        }
        registerNormal(std::move(step));
    }
    bool canUndo() const { return m_replay == Replay::None && !m_busy && !blocked() && (!m_undo.empty() || (m_state == State::Pending && m_pending)); }
    bool canRedo() const { return m_replay == Replay::None && !m_busy && !blocked() && !m_redo.empty(); }
    bool undo() { return replay(m_undo, m_redo, Replay::Undo); }
    bool redo() { return replay(m_redo, m_undo, Replay::Redo); }
    void clear()
    {
        ++m_generation;
        auto undo = std::exchange(m_undo, { });
        auto redo = std::exchange(m_redo, { });
        auto pending = std::exchange(m_pending, { });
        auto rollback = std::exchange(m_rollback, { });
        const bool removalStarted = m_rollbackRemovalStarted;
        const bool pendingRemovalStarted = m_pendingRemovalStarted;
        const bool pendingInHistory = pending &&
            (std::any_of(undo.begin(), undo.end(), [&](const auto& value) { return identity(value) == identity(*pending); }) ||
             std::any_of(redo.begin(), redo.end(), [&](const auto& value) { return identity(value) == identity(*pending); }));
        resetScope(); // All material detached before any script-capable callback.
        notifyRemoved(undo); notifyRemoved(redo);
        if (pending && !pendingRemovalStarted && !pendingInHistory) (*pending)->didRemoveFromUndoManager();
        if (rollback && !removalStarted) (*rollback)->didRemoveFromUndoManager();
    }

private:
    enum class Replay { None, Undo, Redo };
    enum class State { None, Pending, Committing, Detached, Consumed, Finishing, Quarantined };
    using Stack = std::deque<OwnedStep>;
    struct Busy {
        UndoHistory& owner;
        explicit Busy(UndoHistory& value) : owner(value) { owner.m_busy = true; }
        ~Busy() { owner.m_busy = false; }
    };
    static const void* identity(const OwnedStep& step) { return step.operator->(); }
    bool eligible(Token token) const { return token && token == m_token && m_state == State::Pending && m_scopeGeneration == m_generation; }
    bool blocked() const { return m_state != State::None && m_state != State::Pending; }
    void resetScope() { m_state = State::None; m_token = 0; m_owner = nullptr; }
    void notifyStep(const OwnedStep& step)
    {
        if (m_pending && identity(*m_pending) == identity(step)) m_pendingRemovalStarted = true;
        step->didRemoveFromUndoManager();
    }
    void notifyRemoved(Stack& steps) { for (auto& step : steps) notifyStep(step); }
    void trim(Stack& steps)
    {
        while (steps.size() > m_limit) {
            auto removed = std::move(steps.front()); steps.pop_front();
            notifyStep(removed);
        }
    }
    bool registerNormal(OwnedStep step, bool provisional = false)
    {
        const auto generation = m_generation;
        auto discarded = std::exchange(m_redo, { });
        notifyRemoved(discarded);
        if (generation != m_generation) { if (!provisional) notifyStep(step); return false; }
        m_undo.push_back(std::move(step)); trim(m_undo);
        return generation == m_generation;
    }
    void promotePending()
    {
        auto pending = std::exchange(m_pending, { });
        resetScope(); ++m_generation;
        if (pending) registerNormal(std::move(*pending));
    }
    bool replay(Stack& source, Stack& inverse, Replay operation)
    {
        if (m_replay != Replay::None || m_busy || blocked()) return false;
        if (m_state == State::Pending) promotePending();
        if (source.empty()) return false;
        auto active = std::move(source.back()); source.pop_back();
        inverse.push_back(active); // Before script: clear/edit cannot resurrect it.
        m_replay = operation;
        struct Reset { Replay& value; ~Reset() { value = Replay::None; } } reset { m_replay };
        if (operation == Replay::Undo) active->unapply(); else active->reapply();
        return true;
    }
    const void* m_owner { nullptr }; // Borrowed identity only; native owner retains its Document.
    Stack m_undo, m_redo;
    std::optional<OwnedStep> m_pending, m_rollback;
    std::size_t m_limit;
    std::uint64_t m_generation { 0 }, m_scopeGeneration { 0 };
    Token m_tokenLimit, m_nextToken { 0 }, m_token { 0 };
    Replay m_replay { Replay::None };
    State m_state { State::None };
    bool m_busy { false }, m_pendingRemovalStarted { false }, m_rollbackRemovalStarted { false };
};
} // namespace BIB
