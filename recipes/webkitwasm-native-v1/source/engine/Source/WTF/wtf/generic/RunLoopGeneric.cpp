/*
 * Copyright (C) 2016 Konstantin Tokavev <annulen@yandex.ru>
 * Copyright (C) 2016 Yusuke Suzuki <utatane.tea@gmail.com>
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY APPLE INC. ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL APPLE INC. OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "config.h"
#include <wtf/RunLoop.h>

#include <wtf/DataLog.h>
#include <wtf/NeverDestroyed.h>
#include <wtf/ProcessID.h>
#include <wtf/TZoneMallocInlines.h>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

// Private optional provider scheduler. The wrapper-private declaration is in
// BibEngineProviderTimerHooks.h; no public WTF header or class changes.
#include <atomic>
#include <stdint.h>
#include <wtf/MainThread.h>
namespace {
using BibProviderTimerCallback = void (*)(void*, double, uint32_t);
std::atomic<BibProviderTimerCallback> bibProviderTimerCallback { nullptr };
void* bibProviderTimerContext { nullptr };
}
extern "C" int bib_engine_provider_set_timer_scheduler_v1(void* context, BibProviderTimerCallback callback)
{
    // Installation precedes Page creation and is permanently bound to this
    // engine's initialized main owner. Worker RunLoops retain supplier behavior.
    if (!WTF::isMainThread() || !callback || bibProviderTimerCallback.load(std::memory_order_acquire))
        return -1;
    bibProviderTimerContext = context;
    bibProviderTimerCallback.store(callback, std::memory_order_release);
    return 0;
}

namespace WTF {

static constexpr bool report = false;

class RunLoop::TimerBase::ScheduledTask final : public ThreadSafeRefCounted<ScheduledTask>, public RedBlackTree<ScheduledTask, MonotonicTime>::ThreadSafeNode {
    WTF_MAKE_TZONE_ALLOCATED(ScheduledTask);
    WTF_MAKE_NONCOPYABLE(ScheduledTask);
    WTF_OVERRIDE_DELETE_FOR_CHECKED_PTR(ScheduledTask);
public:
    static Ref<ScheduledTask> create(RunLoop::TimerBase& timer)
    {
        return adoptRef(*new ScheduledTask(timer));
    }

    void fired()
    {
        if (!isActive())
            return;

        if (!m_isRepeating)
            deactivate();

        if (isActive())
            updateReadyTime();

        m_timer.fired();
    }

    MonotonicTime scheduledTimePoint() const
    {
        return m_scheduledTimePoint;
    }

    void updateReadyTime()
    {
        ASSERT(!isScheduled());
        m_scheduledTimePoint = MonotonicTime::now();
        if (!m_fireInterval)
            return;
        m_scheduledTimePoint += m_fireInterval;
    }

    MonotonicTime key() const
    {
        return scheduledTimePoint();
    }

    bool isScheduled() const
    {
        return m_isScheduled;
    }

    void setScheduled(bool flag)
    {
        m_isScheduled = flag;
    }

    bool isActive() const
    {
        return m_isActive.load();
    }

    void activate(Seconds interval, bool repeating)
    {
        m_fireInterval = interval;
        m_isRepeating = repeating;
        updateReadyTime();
        m_isActive.store(true);
    }

    void deactivate()
    {
        m_isActive.store(false);
    }

private:
    ScheduledTask(RunLoop::TimerBase& timer)
        : m_timer(timer)
    {
    }

    RunLoop::TimerBase& m_timer;
    MonotonicTime m_scheduledTimePoint;
    Seconds m_fireInterval;
    std::atomic<bool> m_isActive { };
    bool m_isRepeating { };
    bool m_isScheduled { };
};

WTF_MAKE_TZONE_ALLOCATED_IMPL(RunLoop::TimerBase::ScheduledTask);

RunLoop::RunLoop()
{
}

RunLoop::~RunLoop()
{
    Locker locker { m_loopLock };
    m_shutdown = true;
    m_readyToRun.notifyOne();

    // Here is running main loops. Wait until all the main loops are destroyed.
    if (!m_mainLoops.isEmpty())
        m_stopCondition.wait(m_loopLock);
}

inline bool RunLoop::populateTasks(RunMode runMode, Status& statusOfThisLoop, Deque<Ref<TimerBase::ScheduledTask>>& firedTimers)
{
    Locker locker { m_loopLock };

    if (runMode == RunMode::Drain) {
        MonotonicTime sleepUntil = MonotonicTime::infinity();
        if (!m_schedules.isEmpty())
            sleepUntil = m_schedules.first()->scheduledTimePoint();

        m_readyToRun.waitUntil(m_loopLock, sleepUntil, [&] {
            return m_shutdown || m_pendingTasks || statusOfThisLoop == Status::Stopping;
        });
    }

    if (statusOfThisLoop == Status::Stopping || m_shutdown) {
        m_mainLoops.removeLast();
        if (m_mainLoops.isEmpty())
            m_stopCondition.notifyOne();
        return false;
    }
    m_pendingTasks = false;
    if (runMode == RunMode::Iterate)
        statusOfThisLoop = Status::Stopping;

    // Check expired timers.
    MonotonicTime now = MonotonicTime::now();
    while (!m_schedules.isEmpty()) {
        auto task = m_schedules.first();
        if (task->scheduledTimePoint() > now)
            break;
        unscheduleWithLock(*task);
        firedTimers.append(Ref(*task));
    }

    return true;
}

void RunLoop::runImpl(RunMode runMode)
{
    ASSERT(this == &RunLoop::currentSingleton());

    if constexpr (report) {
        static LazyNeverDestroyed<Timer> reporter;
        static std::once_flag onceKey;
        std::call_once(onceKey, [&] {
            reporter.construct(*this, "RunLoop::runImpl::Reporter"_s, [this] {
                unsigned count = 0;
                unsigned active = 0;
                for (auto task = m_schedules.first(); task; task = task->successor()) {
                    count++;
                    if (task->isActive())
                        active++;
                }

                dataLogF("[RunLoop][pid %d main %s] m_schedules size %u active %u\n",
                    getCurrentProcessID(),
                    (isMain() ? "true" : "false"),
                    count,
                    active);
            });
            reporter->startRepeating(30_s);
            dataLogF("[RunLoop][pid %d main %s] Reporter installed\n",
                getCurrentProcessID(),
                (isMain() ? "true" : "false"));
        });
    }

    Status statusOfThisLoop = Status::Clear;
    {
        Locker locker { m_loopLock };
        m_mainLoops.append(&statusOfThisLoop);
    }

    Deque<Ref<TimerBase::ScheduledTask>> firedTimers;
    while (true) {
        if (!populateTasks(runMode, statusOfThisLoop, firedTimers)) {
            if (runMode == RunMode::Iterate) {
                Locker locker { m_loopLock };
                auto callback = bibProviderTimerCallback.load(std::memory_order_acquire);
                if (callback && isMainThread()) {
                    const bool armed = !m_schedules.isEmpty();
                    double delayMs = armed ? (m_schedules.first()->scheduledTimePoint() - MonotonicTime::now()).milliseconds() : 0;
                    if (!(delayMs >= 0)) delayMs = 0;
                    if (delayMs > 2147483647.0) delayMs = 2147483647.0;
                    // Called while locked: the retained host must only replace
                    // its queued deadline, including explicit empty disarm.
                    callback(bibProviderTimerContext, delayMs, armed ? 1u : 0u);
                } else {
#if defined(__EMSCRIPTEN__)
                    // Original optional supplier route, unchanged when no
                    // private provider scheduler has been installed.
                    if (!m_schedules.isEmpty()) {
                        double delayMs = (m_schedules.first()->scheduledTimePoint() - MonotonicTime::now()).milliseconds();
                        EM_ASM({ if (Module.bibArmTimer) Module.bibArmTimer($0); }, delayMs < 0 ? 0 : delayMs);
                    }
#endif
                }
            }
            return;
        }

        // Dispatch scheduled timers.
        while (!firedTimers.isEmpty()) {
            auto task = firedTimers.takeFirst();
            task->fired();

            Locker locker { m_loopLock };
            // It is possible the task is already scheduled while executing fired().
            if (task->isActive() && !task->isScheduled()) {
                // Reschedule because the timer requires repeating.
                // Since we will query the timers' time points before sleeping,
                // we do not call wakeUp() here.
                scheduleWithLock(task.get());
            }
        }
        performWork();
    }
}

void RunLoop::run()
{
    RunLoop::currentSingleton().runImpl(RunMode::Drain);
}

void RunLoop::setWakeUpCallback(WTF::Function<void()>&& function)
{
    RunLoop::currentSingleton().m_wakeUpCallback = WTF::move(function);
}

// RunLoop operations are thread-safe. These operations can be called from outside of the RunLoop's thread.
// For example, WorkQueue::{dispatch, dispatchAfter} call the operations of the WorkQueue thread's RunLoop
// from the caller's thread.

void RunLoop::stop()
{
    Locker locker { m_loopLock };
    if (m_mainLoops.isEmpty())
        return;

    Status* status = m_mainLoops.last();
    if (*status != Status::Stopping) {
        *status = Status::Stopping;
        m_readyToRun.notifyOne();
    }
}

void RunLoop::wakeUpWithLock()
{
    m_pendingTasks = true;
    m_readyToRun.notifyOne();

    if (m_wakeUpCallback)
        m_wakeUpCallback();
}

void RunLoop::wakeUp()
{
    Locker locker { m_loopLock };
    wakeUpWithLock();
}

RunLoop::CycleResult RunLoop::cycle(RunLoopMode)
{
    RunLoop::currentSingleton().runImpl(RunMode::Iterate);
    return CycleResult::Continue;
}

void RunLoop::scheduleWithLock(TimerBase::ScheduledTask& task)
{
    if (!task.isScheduled()) {
        m_schedules.insert(&task);
        task.setScheduled(true);
    }
}

void RunLoop::unscheduleWithLock(TimerBase::ScheduledTask& task)
{
    if (task.isScheduled()) {
        m_schedules.remove(&task);
        task.setScheduled(false);
    }
}

// Since RunLoop does not own the registered TimerBase,
// TimerBase and its owner should manage these lifetime.
RunLoop::TimerBase::TimerBase(Ref<RunLoop>&& runLoop, ASCIILiteral description)
    : m_runLoop(WTF::move(runLoop))
    , m_description(description)
    , m_scheduledTask(ScheduledTask::create(*this))
{
}

RunLoop::TimerBase::~TimerBase()
{
    Locker locker { m_runLoop->m_loopLock };
    stopWithLock();
}

void RunLoop::TimerBase::start(Seconds interval, bool repeating)
{
    Locker locker { m_runLoop->m_loopLock };
    stopWithLock();
    m_scheduledTask->activate(interval, repeating);
    m_runLoop->scheduleWithLock(m_scheduledTask.get());
    m_runLoop->wakeUpWithLock();
}

void RunLoop::TimerBase::stopWithLock()
{
    m_runLoop->unscheduleWithLock(m_scheduledTask.get());
    m_scheduledTask->deactivate();
}

void RunLoop::TimerBase::stop()
{
    Locker locker { m_runLoop->m_loopLock };
    stopWithLock();
}

bool RunLoop::TimerBase::isActive() const
{
    Locker locker { m_runLoop->m_loopLock };
    return isActiveWithLock();
}

bool RunLoop::TimerBase::isActiveWithLock() const
{
    return m_scheduledTask->isActive();
}

Seconds RunLoop::TimerBase::secondsUntilFire() const
{
    Locker locker { m_runLoop->m_loopLock };
    if (isActiveWithLock())
        return std::max<Seconds>(m_scheduledTask->scheduledTimePoint() - MonotonicTime::now(), 0_s);
    return 0_s;
}

} // namespace WTF
