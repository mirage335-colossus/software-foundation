// SPDX-License-Identifier: CC0-1.0
// Prototype-only ownership policy. The WebCore adapter supplies Ref<UndoStep>.
#pragma once

#include <cstddef>
#include <deque>
#include <utility>

namespace BIB {
template<typename OwnedStep> class UndoHistory {
public:
    explicit UndoHistory(std::size_t limit = 128) : m_limit(limit) { }

    void registerUndo(OwnedStep step)
    {
        if (m_replay == Replay::Redo)
            return; // The retained step was transferred before reapply().
        auto generation = m_generation;
        auto discarded = std::exchange(m_redo, { });
        notifyRemoved(discarded);
        if (generation != m_generation) {
            step->didRemoveFromUndoManager();
            return; // A removal callback invalidated this registration.
        }
        m_undo.push_back(std::move(step));
        trim(m_undo);
    }

    bool canUndo() const { return m_replay == Replay::None && !m_undo.empty(); }
    bool canRedo() const { return m_replay == Replay::None && !m_redo.empty(); }

    bool undo() { return replay(m_undo, m_redo, Replay::Undo); }
    bool redo() { return replay(m_redo, m_undo, Replay::Redo); }

    void clear()
    {
        ++m_generation;
        auto undo = std::exchange(m_undo, { });
        auto redo = std::exchange(m_redo, { });
        // Both stacks are detached before script-capable removal callbacks.
        notifyRemoved(undo);
        notifyRemoved(redo);
    }

private:
    enum class Replay { None, Undo, Redo };
    using Stack = std::deque<OwnedStep>;

    static void notifyRemoved(Stack& steps)
    {
        for (auto& step : steps)
            step->didRemoveFromUndoManager();
    }

    void trim(Stack& steps)
    {
        while (steps.size() > m_limit) {
            auto removed = std::move(steps.front());
            steps.pop_front();
            removed->didRemoveFromUndoManager();
        }
    }

    bool replay(Stack& source, Stack& inverse, Replay operation)
    {
        if (m_replay != Replay::None || source.empty())
            return false;
        auto active = std::move(source.back());
        source.pop_back();
        inverse.push_back(active); // Before script: clear/edit cannot resurrect it.
        m_replay = operation;
        struct Reset {
            Replay& value;
            ~Reset() { value = Replay::None; }
        } reset { m_replay };
        if (operation == Replay::Undo)
            active->unapply();
        else
            active->reapply();
        return true;
    }

    Stack m_undo;
    Stack m_redo;
    std::size_t m_limit;
    std::size_t m_generation { 0 };
    Replay m_replay { Replay::None };
};
} // namespace BIB
