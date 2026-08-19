import { useEffect, useMemo, useRef, useState } from "react";
import AppShell from "./components/AppShell.jsx";
import TaskCard from "./components/TaskCard.jsx";
import TaskForm from "./components/TaskForm.jsx";
import AvailableTimeCard from "./components/AvailableTimeCard.jsx";
import DashboardRail from "./components/DashboardRail.jsx";
import HistoryPage from "./components/HistoryPage.jsx";
import { formatDuration } from "./utils/duration.mjs";

import {
  createTask,
  deleteTask,
  getTasks,
  planDay,
  getProgress,
  recommendTask,
  replanTask,
  updateTask,
  getWeeklyReflection,
} from "./services/api.js";
import {
  DEFAULT_AVAILABLE_MINUTES,
  getTodayOverloadStatus,
} from "./utils/workload.mjs";

function formatDeadline(deadline) {
  return new Date(deadline).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function App() {
  const [activePage, setActivePage] = useState("today");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState(null);
  const [selected, setSelected] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [taskToDelete, setTaskToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [hasPlanned, setHasPlanned] = useState(false);
  const [plannedTasks, setPlannedTasks] = useState([]);
  const [planIsOverloaded, setPlanIsOverloaded] = useState(false);
  const [recommendation, setRecommendation] = useState(null);
  const [progress, setProgress] = useState(null);
  const [reflection, setReflection] = useState(null);
  const [replanNotice, setReplanNotice] = useState(null);
  const replanNoticeRef = useRef(null);
  const [availableMinutes, setAvailableMinutes] = useState(
    () =>
      Number(localStorage.getItem("todayAvailableMinutes")) ||
      DEFAULT_AVAILABLE_MINUTES,
  );

  useEffect(() => {
    getTasks()
      .then(setTasks)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getProgress().then(setProgress).catch(() => setProgress(null));
    getWeeklyReflection().then(setReflection).catch(() => setReflection(null));
  }, []);

  useEffect(() => {
  if (replanNotice && replanNoticeRef.current) {
    replanNoticeRef.current.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }
}, [replanNotice]);

  const isCompletedTask = (task) =>
    task.completed || task.status === "completed";
  const incompleteTasks = tasks.filter((task) => !isCompletedTask(task));
  const completedTasks = tasks.filter(isCompletedTask);
  const totalMinutes = incompleteTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  );
  const currentPlannedTasks = plannedTasks
    .map((plannedTask) =>
      tasks.find((task) => String(task.id) === String(plannedTask.id)),
    )
    .filter((task) => task && !isCompletedTask(task));

  function openForm(nextMode, task = null) {
    setSelected(task);
    setMode(nextMode);
    setFormError(null);
  }

  async function submitForm(data) {
    setSubmitting(true);

    try {
      let saved;

      if (mode === "create") {
        saved = await createTask(data);
        setTasks((all) => [...all, saved]);
      } else if (mode === "edit") {
        saved = await updateTask(selected.id, { ...selected, ...data });
        setTasks((all) =>
          all.map((task) => (task.id === saved.id ? saved : task)),
        );
      } else {
        saved = await updateTask(selected.id, {
          ...selected,
          completed: true,
          status: "completed",
          actual_duration_minutes: data.actual_duration_minutes,
        });
        setTasks((all) =>
          all.map((task) => (task.id === saved.id ? saved : task)),
        );
      }

      setMode(null);
      setSelected(null);
    } catch (requestError) {
      setFormError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmDelete() {
    setDeleting(true);

    try {
      await deleteTask(taskToDelete.id);
      setTasks((all) => all.filter((task) => task.id !== taskToDelete.id));
      setTaskToDelete(null);
    } catch (requestError) {
      setDeleteError(requestError.message);
    } finally {
      setDeleting(false);
    }
  }
  async function handleMiss(task) {
    setError(null);

    try {
      const now = new Date();
      const availableStart = now;
      const availableEnd = new Date(
        now.getTime() + availableMinutes * 60 * 1000,
      );

      const result = await replanTask(task.id, {
  available_start: availableStart.toISOString(),
  available_end: availableEnd.toISOString(),
});

console.log("REPLAN RESULT:", result);

if (result.missed_task_scheduled) {
  setReplanNotice({
    title: "We reshaped your day",
    message: `${task.title} was missed earlier, but we've found a place for it in today's plan.`,
  });
} else {
  setReplanNotice({
    title: "We'll find a place for it",
    message: `${task.title} couldn't fit into the remaining time today, so it will be considered again when the next day's plan is built.`,
  });
}

const updatedTasks = await getTasks();
      setTasks(updatedTasks);

      setPlannedTasks([]);
      setPlanIsOverloaded(false);
      setHasPlanned(false);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handlePlanDay() {
    if (hasPlanned) {
      setHasPlanned(false);
      return;
    }

    setPlanning(true);

    try {
      const now = new Date();
      const availableStart = now;
      const availableEnd = new Date(
        now.getTime() + availableMinutes * 60 * 1000,
      );

      const result = await planDay({
        available_start: availableStart.toISOString(),
        available_end: availableEnd.toISOString(),
      });

      setPlannedTasks(
        result.schedule.map((item) => ({
          id: item.task_id,
        })),
      );
      setPlanIsOverloaded(result.is_overloaded);
      setHasPlanned(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setPlanning(false);
    }
  }
  async function handleRecommend() {
    setError(null);

    try {
      const result = await recommendTask();
      setRecommendation(result);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function planReason(task) {
    const deadline = new Date(task.deadline);
    if (deadline < new Date()) {
      return "Overdue";
    }
    if (task.priority === "high") {
      return "High priority";
    }
    return "Closest upcoming deadline";
  }

  const plannedMinutes = currentPlannedTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  );
  const overloadStatus = getTodayOverloadStatus(tasks, availableMinutes);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      {activePage === "history" ? <HistoryPage /> : <>
      <section className="welcome">
  <div>
    <p className="eyebrow">Your gentle reset</p>
    <h1>Good evening, Ana! 🌿</h1>
    <p className="welcome__copy">
      Let’s plan a balanced and meaningful day.
    </p>
  </div>
</section>

      <section className="summary">
        <div className="summary__item">
          <span className="summary__label">Tasks Today</span>
          <span className="summary__value">{tasks.length}</span>
          <span className="summary__detail">
            {completedTasks.length} completed
          </span>
        </div>

        <div className="summary__item summary__item--time">
          <span className="summary__label">Available Time</span>
          <span className="summary__value">
            {formatDuration(availableMinutes)}
          </span>
          <span className="summary__detail">available today</span>
        </div>

        <div className="summary__item summary__item--planned">
          <span className="summary__label">Planned Work</span>
          <span className="summary__value">
            {formatDuration(plannedMinutes)}
          </span>
          <span className="summary__detail">
            {currentPlannedTasks.length} planned
          </span>
        </div>

        <div
          className={`summary__item ${
            overloadStatus.isOverloaded
              ? "summary__item--overloaded"
              : "summary__item--on-track"
          }`}
        >
          <span className="summary__label">Overload Status</span>

          <span className="summary__value">
            {overloadStatus.isOverloaded ? "Overloaded" : "On Track"}
          </span>

          <span className="summary__detail">
            {overloadStatus.isOverloaded
              ? `${formatDuration(overloadStatus.overloadedByMinutes)} over`
              : "You’re doing great!"}
          </span>
        </div>
      </section>

      <section className="tasks-section">
        {replanNotice && (
          <section
            ref={replanNoticeRef}
            className="replan-notice"
            aria-live="polite"
          >
            <div className="replan-notice__copy">
              <p className="replan-notice__eyebrow">🌱 GENTLE RESET</p>
              <h3>{replanNotice.title}</h3>
              <p>{replanNotice.message}</p>
            </div>

            <button
              className="button button--quiet replan-notice__dismiss"
              type="button"
              onClick={() => setReplanNotice(null)}
            >
              Dismiss
            </button>
          </section>
        )}
        <div className="section-heading">
          <h2>Today’s tasks</h2>
        </div>

        <AvailableTimeCard
          availableMinutes={availableMinutes}
          onSave={setAvailableMinutes}
        />

        <div className="task-list-actions">
          <button
            className={`button button--quiet ${hasPlanned ? "button--plan-open" : ""}`}
            onClick={handlePlanDay}
            disabled={planning}
            aria-expanded={hasPlanned}
            aria-controls="today-plan"
          >
            {planning
              ? "Planning…"
              : hasPlanned
                ? "Hide plan ×"
                : "Plan my day"}
          </button>
          <button
            className="button button--primary"
            onClick={() => openForm("create")}
          >
            Add task
          </button>
        </div>

        {overloadStatus.isOverloaded && (
          <section
            className="overload-notice"
            aria-labelledby="overload-heading"
          >
            <div className="overload-notice__copy">
              <p className="overload-notice__eyebrow">Your day looks full</p>
              <h3 id="overload-heading">
                More needs attention than fits today.
              </h3>
              <p className="overload-notice__support">
                Plan My Day will prioritize what matters most and leave the rest
                for later.
              </p>
            </div>
            <div
              className="overload-notice__limits"
              aria-label="Daily workload limits"
            >
              <span className="overload-limit">
                {formatDuration(overloadStatus.availableMinutes)}{" "}
                available
              </span>
              <span className="overload-limit">
                {formatDuration(overloadStatus.totalTodayMinutes)} of
                tasks
              </span>
              <span className="overload-limit overload-limit--exceeded">
                {formatDuration(overloadStatus.overloadedByMinutes)} over
                capacity
              </span>
            </div>
          </section>
        )}

        <div className="dashboard-grid">
          <main className="dashboard-main">
            {hasPlanned && (
              <section
                className="plan-panel"
                id="today-plan"
                aria-live="polite"
              >
                <div className="plan-panel__header">
                  <div>
                    <p className="plan-panel__eyebrow">Daily roadmap</p>
                    <h3>Your plan for today</h3>
                    <p className="plan-panel__subtitle">
                      Your clearest path through today’s priorities.
                    </p>
                  </div>
                </div>

                {currentPlannedTasks.length === 0 ? (
                  <p className="plan-panel__clear">
                    {incompleteTasks.length === 0
                      ? "You’re all clear for today."
                      : "No pending task fits into the remaining time today."}
                  </p>
                ) : (
                  <>
                    <ol className="plan-panel__list">
                      {currentPlannedTasks.map((task, index) => (
                        <li className="plan-panel__item" key={task.id}>
                          <span className="plan-panel__number">
                            {index + 1}
                          </span>
                          <div>
                            <strong>{task.title}</strong>
                            <span className="plan-panel__meta">
                              {formatDuration(task.duration_minutes)} ·{" "}
                              {task.priority} priority · Due{" "}
                              {formatDeadline(task.deadline)}
                            </span>
                            <span className="plan-panel__reason">
                              <span className="plan-panel__reason-label">
                                Why now
                              </span>
                              {planReason(task)}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ol>

                    <p className="plan-panel__summary">
                      {currentPlannedTasks.length}{" "}
                      {currentPlannedTasks.length === 1 ? "task" : "tasks"} ·{" "}
                      {formatDuration(plannedMinutes)} planned
                      {plannedMinutes < availableMinutes &&
                        ` · ${formatDuration(availableMinutes - plannedMinutes)} remaining`}
                    </p>
                  </>
                )}
              </section>
            )}

            {loading && <p className="state-message">Loading your tasks…</p>}

            {error && (
              <p className="state-message state-message--error">{error}</p>
            )}

            {incompleteTasks.length > 0 && (
              <div className="task-list">
                {incompleteTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onEdit={() => openForm("edit", task)}
                    onComplete={() => openForm("complete", task)}
                    onMiss={() => handleMiss(task)}
                    onDelete={() => setTaskToDelete(task)}
                  />
                ))}
              </div>
            )}

            {completedTasks.length > 0 && (
              <section className="completed-section">
                <h2>Completed</h2>

                <div className="task-list">
                  {completedTasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      onEdit={() => openForm("edit", task)}
                      onComplete={() => openForm("complete", task)}
                      onDelete={() => setTaskToDelete(task)}
                    />
                  ))}
                </div>
              </section>
            )}
          </main>

          <DashboardRail
            recommendation={recommendation}
            onRecommend={handleRecommend}
            plannedMinutes={plannedMinutes}
            availableMinutes={availableMinutes}
            plannedCount={currentPlannedTasks.length}
            progress={progress}
            reflection={reflection}
          />
        </div>
      </section>

      {mode && (
        <TaskForm
          key={`${mode}-${selected?.id ?? "new"}`}
          mode={mode}
          task={selected}
          onSubmit={submitForm}
          onClose={() => !submitting && setMode(null)}
          submitting={submitting}
          error={formError}
        />
      )}

      {taskToDelete && (
        <div className="modal-backdrop">
          <section className="task-form">
            <h2>Delete this task?</h2>
            <p className="completion-copy">
              This task will be permanently removed.
            </p>
            {deleteError && <p className="form-error">{deleteError}</p>}
            <div className="task-form__actions">
              <button
                className="button button--quiet"
                onClick={() => setTaskToDelete(null)}
              >
                Cancel
              </button>
              <button
                className="button button--quiet button--danger"
                onClick={confirmDelete}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Delete task"}
              </button>
            </div>
          </section>
        </div>
      )}
      </>}
    </AppShell>
  );
}

export default App;
