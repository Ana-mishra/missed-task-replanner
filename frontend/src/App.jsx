import { useEffect, useMemo, useRef, useState } from "react";
import AppShell from "./components/AppShell.jsx";
import DaySheet from "./components/DaySheet.jsx";
import PlanPage from "./components/PlanPage.jsx";
import TaskForm from "./components/TaskForm.jsx";
import HistoryPage from "./components/HistoryPage.jsx";
import StatsPage from "./components/StatsPage.jsx";
import ReflectionPage from "./components/ReflectionPage.jsx";
import AuthPage from "./components/AuthPage.jsx";
import LandingPage from "./components/LandingPage.jsx";
import AboutPage from "./components/AboutPage.jsx";
import MyPlantPage from "./components/MyPlantPage.jsx";
import OAuthCallback from "./components/OAuthCallback.jsx";

import {
  createTask,
  deleteTask,
  getCurrentUser,
  getTasks,
  updateCurrentUser,
   getTaskHistory,
  planDay,
  replanTask,
  getProgress,
  recommendTask,
  updateTask,
  getWeeklyReflection,
  clearAccessToken,
  getAccessToken,
  getPlant,
} from "./services/api.js";
import {
  DEFAULT_AVAILABLE_MINUTES,
} from "./utils/workload.mjs";
import { mergeScheduleReasons } from "./utils/planReasons.mjs";
import { buildPlanPayload } from "./utils/planRequest.mjs";
import { createRecoveryLock, runRecoverySequence } from "./utils/recovery.mjs";

const LAST_PLANNED_AVAILABLE_MINUTES_KEY = "planora.lastPlannedAvailableMinutes";
const PLANORA_PAGES = new Set(["today", "plan", "plant", "history", "stats", "reflection"]);

function pageFromLocation() {
  const page = new URLSearchParams(window.location.search).get("page");
  return PLANORA_PAGES.has(page) ? page : "today";
}

function pageUrl(page) {
  const url = new URL(window.location.href);
  if (page === "today") {
    url.searchParams.delete("page");
  } else {
    url.searchParams.set("page", page);
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

function getTodayCompletedTaskIds(history) {
  const today = new Date().toDateString();
  return history
    .filter(
      (event) =>
        event.event_type === "completed" &&
        new Date(event.timestamp).toDateString() === today,
    )
    .map((event) => String(event.task_id));
}

function App() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(getAccessToken()));
  const [publicView, setPublicView] = useState("landing");
  const [currentUser, setCurrentUser] = useState(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [nameInput, setNameInput] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameError, setNameError] = useState(null)
  const [activePage, setActivePage] = useState(pageFromLocation);
  const [tasks, setTasks] = useState([]);
  const [todayCompletedTaskIds, setTodayCompletedTaskIds] = useState([]);
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
  const [todayPlanTaskIds, setTodayPlanTaskIds] = useState([]);
  const [planIsOverloaded, setPlanIsOverloaded] = useState(false);
  const [unscheduledMinutes, setUnscheduledMinutes] = useState(0);
  const [badDayProtectedCount, setBadDayProtectedCount] = useState(0);
  const [badDayCapacityMinutes, setBadDayCapacityMinutes] = useState(0);
  const [scheduleRefreshReason, setScheduleRefreshReason] = useState("");
  const [recommendation, setRecommendation] = useState(null);
  const [recoveringId, setRecoveringId] = useState(null);
  const [completingId, setCompletingId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [plantData, setPlantData] = useState(null);
  const [plantLoading, setPlantLoading] = useState(true);
  const [plantError, setPlantError] = useState(null);
  const [reflection, setReflection] = useState(null);
  const [replanNotice, setReplanNotice] = useState(null);
  const replanNoticeRef = useRef(null);
  // Synchronous backstop under the `recoveringId` UI guard: ref updates are
  // visible immediately, so two same-tick invocations cannot both proceed.
  const recoveryLockRef = useRef(null);
  if (recoveryLockRef.current === null) {
    recoveryLockRef.current = createRecoveryLock();
  }
  const planIsStaleRef = useRef(false);
  const lastPlannedAvailableMinutesRef = useRef(
    Number(localStorage.getItem(LAST_PLANNED_AVAILABLE_MINUTES_KEY)) || null,
  );
  const [availableMinutes, setAvailableMinutes] = useState(
    () =>
      Number(localStorage.getItem("todayAvailableMinutes")) ||
      DEFAULT_AVAILABLE_MINUTES,
  );
  const [badDayMode, setBadDayMode] = useState(false);
  const lastPlannedBadDayModeRef = useRef(false);
  // Synchronous in-flight guard: set/ref-cleared around the planning request
  // so rapid clicks (toggle or Re-plan) cannot fire duplicate requests while
  // React state is still settling.
  const planningRef = useRef(false);

  useEffect(() => {
  if (!authenticated) {
    setCurrentUser(null);
    setLoadingUser(false);
    return;
  }

  setLoadingUser(true);

  getCurrentUser()
    .then(setCurrentUser)
    .catch((requestError) => {
      if (
        requestError.message ===
        "Invalid or expired authentication credentials"
      ) {
        clearAccessToken();
        setAuthenticated(false);
      } else {
        setError(requestError.message);
      }
    })
    .finally(() => setLoadingUser(false));
}, [authenticated]);

  useEffect(() => {
    if (!authenticated) {
      setLoading(false);
      return;
    }

    setLoading(true);
    getTasks()
      .then(setTasks)
      .catch((requestError) => {
        if (requestError.message === "Invalid or expired authentication credentials") {
          clearAccessToken();
          setAuthenticated(false);
        } else {
          setError(requestError.message);
        }
      })
      .finally(() => setLoading(false));
  }, [authenticated]);

  useEffect(() => {
  if (!authenticated) return;

  getProgress()
    .then(setProgress)
    .catch(() => setProgress(null));

  getPlant()
    .then((data) => {
      setPlantData(data);
      setPlantError(null);
    })
    .catch((err) => {
      setPlantData(null);
      setPlantError(err.message || 'Could not load your plant data.');
    })
    .finally(() => setPlantLoading(false));

  getWeeklyReflection()
    .then(setReflection)
    .catch(() => setReflection(null));

  getTaskHistory()
    .then((history) => {
      setTodayCompletedTaskIds((ids) => [
        ...new Set([...ids, ...getTodayCompletedTaskIds(history)]),
      ]);
    })
    .catch(() => setTodayCompletedTaskIds([]));
}, [authenticated]);

  useEffect(() => {
  if (replanNotice && replanNoticeRef.current) {
    replanNoticeRef.current.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }
}, [replanNotice]);

  useEffect(() => {
    // Seed the initial entry without adding a duplicate browser-history item.
    window.history.replaceState({ planoraPage: activePage, publicView: publicView }, "", pageUrl(activePage));

    function handlePopState(event) {
      const state = event.state || {};
      setActivePage(PLANORA_PAGES.has(state.planoraPage) ? state.planoraPage : pageFromLocation());
      setPublicView(state.publicView || "landing");
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // SPA navigation keeps the browser's scroll offset by default. A new
  // page must always paint from the top: otherwise switching to/from a
  // tall page (History/Stats grow when data arrives) lands the user
  // mid-page or on a blank viewport, which reads as a navigation pause.
  // Covers both sidebar navigation and browser back/forward.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [activePage]);

  function navigateToPage(page) {
    if (!PLANORA_PAGES.has(page) || page === activePage) return;
    window.history.pushState({ planoraPage: page, publicView: publicView }, "", pageUrl(page));
    setActivePage(page);
  }

  function navigatePublicView(view) {
    window.history.pushState({ planoraPage: activePage, publicView: view }, "", pageUrl(activePage));
    setPublicView(view);
  }

  const isCompletedTask = (task) =>
    task.completed || task.status === "completed";
  const incompleteTasks = tasks.filter((task) => !isCompletedTask(task));
  const completedTasks = tasks.filter(isCompletedTask);
  const totalMinutes = incompleteTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  );
const completedTodayTasks = tasks.filter((task) =>
  isCompletedTask(task) && todayCompletedTaskIds.includes(String(task.id)),
);
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
        setTodayCompletedTaskIds((ids) => [
          ...new Set([...ids, String(saved.id)]),
        ]);
        getTaskHistory()
          .then((history) => setTodayCompletedTaskIds(getTodayCompletedTaskIds(history)))
          .catch(() => {
            // The successful update above remains the immediate UI source.
          });
        // Refresh plant data after form-based completion too.
        getPlant()
          .then((d) => { setPlantData(d); setPlantError(null); })
          .catch(() => {});
      }

      planIsStaleRef.current = true;

      setMode(null);
      setSelected(null);
    } catch (requestError) {
      setFormError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function completeTaskDirectly(task) {
    // Immediate completion without the actual-duration prompt. Reuses the
    // same backend update flow as the form; the backend records the
    // `completed` history event and the same refresh follows on success.
    if (!task || completingId) return;
    setCompletingId(task.id);
    setError(null);

    // Snapshot whether the plant has already grown today BEFORE the completion
    // so the plant page can detect the first-of-day event after the refresh.
    const wasGrownToday = plantData?.grew_today ?? false;

    try {
      const saved = await updateTask(task.id, {
        ...task,
        completed: true,
        status: "completed",
      });
      setTasks((all) =>
        all.map((t) => (t.id === saved.id ? saved : t)),
      );
      setTodayCompletedTaskIds((ids) => [
        ...new Set([...ids, String(saved.id)]),
      ]);
      getTaskHistory()
        .then((history) => setTodayCompletedTaskIds(getTodayCompletedTaskIds(history)))
        .catch(() => {
          // The successful update above remains the immediate UI source.
        });
      // Refresh plant data after every completion so the page reflects the
      // new state instantly. The plant service only counts the first
      // completion of each IST calendar day, so subsequent completions are
      // safe to refresh without double-counting.
      getPlant()
        .then((data) => { setPlantData(data); setPlantError(null); })
        .catch(() => {});
      planIsStaleRef.current = true;
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCompletingId(null);
    }
  }

  async function confirmDelete() {
    setDeleting(true);

    try {
      await deleteTask(taskToDelete.id);
      setTasks((all) => all.filter((task) => task.id !== taskToDelete.id));
      planIsStaleRef.current = true;
      setTaskToDelete(null);
    } catch (requestError) {
      setDeleteError(requestError.message);
    } finally {
      setDeleting(false);
    }
  }

  function handleHidePlan() {
    setHasPlanned(false);
    setPlannedTasks([]);
    setPlanIsOverloaded(false);
    setUnscheduledMinutes(0);
  }

  async function handlePlanDay(badDayOverride) {
    // One planning request at a time: a second invocation while a request
    // is in flight is ignored so stale responses cannot overwrite newer ones.
    if (planningRef.current) return;
    planningRef.current = true;
    setPlanning(true);
    // The Bad Day toggle passes its new value explicitly so the request
    // never reads a stale badDayMode closure. Manual Plan clicks omit it
    // and use current state exactly as before.
    const effectiveBadDayMode = badDayOverride ?? badDayMode;

    try {
      const now = new Date();
      const availableStart = now;
      const availableEnd = new Date(
        now.getTime() + availableMinutes * 60 * 1000,
      );

      const result = await planDay({
        ...buildPlanPayload({ availableStart, availableEnd, badDayMode: effectiveBadDayMode }),
        // The backend's normal idempotency guard preserves a saved plan as
        // wall-clock time moves. Recalculate only after a meaningful task
        // mutation or an available-capacity change.
        force_replan:
          planIsStaleRef.current ||
          effectiveBadDayMode !== lastPlannedBadDayModeRef.current ||
          (lastPlannedAvailableMinutesRef.current !== null &&
            lastPlannedAvailableMinutesRef.current !== availableMinutes),
      });

      const updatedTasks = await getTasks();
      // Task objects carry no planning reason themselves; join the reasons
      // from this planning result onto them by task_id for rendering.
      setTasks(mergeScheduleReasons(updatedTasks, result.schedule));

   const planTaskIds = result.schedule.map((item) => String(item.task_id));

setPlannedTasks(
  planTaskIds.map((id) => ({
    id,
  })),
);

      setTodayPlanTaskIds(planTaskIds);
      setPlanIsOverloaded(result.is_overloaded);
      setUnscheduledMinutes(result.unscheduled_minutes ?? 0);
      setBadDayProtectedCount(result.bad_day_protected_count ?? 0);
      setBadDayCapacityMinutes(result.bad_day_capacity_minutes ?? 0);
      setScheduleRefreshReason(result.schedule_refresh_reason || "");
      lastPlannedAvailableMinutesRef.current = availableMinutes;
localStorage.setItem(LAST_PLANNED_AVAILABLE_MINUTES_KEY, String(availableMinutes));
planIsStaleRef.current = false;
lastPlannedBadDayModeRef.current = effectiveBadDayMode;
setHasPlanned(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      planningRef.current = false;
      setPlanning(false);
    }
  }

  async function handleBadDayModeChange(nextMode) {
    // Toggling Bad Day Mode reuses the existing Plan My Day flow with the
    // new mode passed explicitly (state timing safe). One toggle click
    // produces at most one planning request.
    setBadDayMode(nextMode);
    if (planningRef.current) return;
    await handlePlanDay(nextMode);
  }
  async function handleRecover(task) {
    // Genuine recovery flow: open/refresh the missed cycle via /replan,
    // then persist it into today's plan via /plan. The backend records
    // the `recovered` history event; the task itself returns to pending.
    if (!task || recoveringId) return;
    setRecoveringId(task.id);
    setError(null);

    try {
      const now = new Date();
      const window = {
        available_start: now.toISOString(),
        available_end: new Date(
          now.getTime() + availableMinutes * 60 * 1000,
        ).toISOString(),
      };
      const result = await runRecoverySequence({
        lock: recoveryLockRef.current,
        taskId: task.id,
        window,
        isBusy: () => recoveringId,
        replanTask,
        planDay: () => handlePlanDay(),
        getTasks,
      });
      if (!result.started) return;
      const updated = result.tasks;
      const recovered = updated.find((item) => item.id === task.id);
      if (recovered && (recovered.completed || recovered.status === "completed")) {
        setReplanNotice({
          title: "Recovered",
          message: `${task.title} was recovered and is now marked completed.`,
        });
      } else if (recovered && recovered.scheduled_start) {
        setReplanNotice({
          title: "Recovered",
          message: `${task.title} is back in today's plan.`,
        });
      } else {
        setReplanNotice({
          title: "Not recovered yet",
          message: `${task.title} is still missed. Try planning with more available time.`,
        });
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRecoveringId(null);
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

  async function handleNameSubmit(event) {
  event.preventDefault();

  const trimmedName = nameInput.trim();

  if (!trimmedName) {
    setNameError("Please enter your name.");
    return;
  }

  setSavingName(true);
  setNameError(null);

  try {
    const updatedUser = await updateCurrentUser(trimmedName);
    setCurrentUser(updatedUser);
  } catch (requestError) {
    setNameError(requestError.message);
  } finally {
    setSavingName(false);
  }
}

  async function handleProfileUpdate(name) {
    const updatedUser = await updateCurrentUser(name);
    setCurrentUser(updatedUser);
    return updatedUser;
  }

  function handleLogout() {
    clearAccessToken();
    setAuthenticated(false);
    setCurrentUser(null);
    setNameInput("");
    setNameError(null);
    setTasks([]);
    setPlannedTasks([]);
    setTodayPlanTaskIds([]);
    setRecommendation(null);
    setError(null);
    setActivePage("today");
    navigatePublicView("landing");
  }

  function handleAuthenticated() {
    setCurrentUser(null);
    setLoadingUser(true);
    setError(null);
    setAuthenticated(true);
  }

  if (window.location.pathname === "/oauth/callback") {
    return (
      <OAuthCallback onAuthenticated={handleAuthenticated} />
    );
  }

  if (!authenticated) {
    if (publicView === "landing") {
      return (
        <LandingPage
          onAbout={() => navigatePublicView("about")}
          onSignIn={() => navigatePublicView("login")}
          onGetStarted={() => navigatePublicView("register")}
        />
      );
    }

    if (publicView === "about") {
      return (
        <AboutPage
          onHome={() => navigatePublicView("landing")}
          onSignIn={() => navigatePublicView("login")}
          onGetStarted={() => navigatePublicView("register")}
        />
      );
    }

    return (
      <AuthPage
        key={publicView}
        initialMode={publicView}
        onAuthenticated={handleAuthenticated}
        onBack={() => navigatePublicView("landing")}
      />
    );
}

if (loadingUser) {
  return <p className="state-message">Loading your account…</p>;
}

if (!currentUser) {
  return (
    <p className="state-message state-message--error">
      {error || "Could not load your account."}
    </p>
  );
}

if (currentUser && !currentUser.name_confirmed) {
  return (
    <div className="name-setup-page">
      <form className="name-setup-card" onSubmit={handleNameSubmit}>
        <p className="name-setup-eyebrow">Welcome to Planora</p>

        <h1>What should we call you?</h1>

        <p>
          Tell Planora your name so your days can feel a little more personal.
        </p>

        <input
          type="text"
          value={nameInput}
          onChange={(event) => setNameInput(event.target.value)}
          placeholder="Your name"
          maxLength={100}
          autoFocus
        />

        {nameError && (
          <p className="name-setup-error">{nameError}</p>
        )}

        <button type="submit" disabled={savingName}>
          {savingName ? "Saving…" : "Continue"}
        </button>
      </form>
    </div>
  );
}

return (
    <AppShell
      activePage={activePage}
      onNavigate={navigateToPage}
  onLogout={handleLogout}
  onUpdateCurrentUser={handleProfileUpdate}
  progress={progress}
  currentUser={currentUser}
>
      {activePage === "history" ? <HistoryPage /> : activePage === "stats" ? <StatsPage /> : activePage === "reflection" ? <ReflectionPage availableMinutes={availableMinutes}       /> : activePage === "plant" ? <MyPlantPage plantData={plantData} plantLoading={plantLoading} plantError={plantError} /> : activePage === "plan" ? <PlanPage
        tasks={tasks}
        availableMinutes={availableMinutes}
        badDayMode={badDayMode}
        onBadDayModeChange={handleBadDayModeChange}
        onSaveAvailableMinutes={setAvailableMinutes}
        planning={planning}
        hasPlanned={hasPlanned}
        planIsOverloaded={planIsOverloaded}
        unscheduledMinutes={unscheduledMinutes}
        badDayProtectedCount={badDayProtectedCount}
        badDayCapacityMinutes={badDayCapacityMinutes}
        scheduleRefreshReason={scheduleRefreshReason}
        onPlanDay={handlePlanDay}
        onHidePlan={handleHidePlan}
        onGoToToday={() => navigateToPage("today")}
        onEditTask={(task) => openForm("edit", task)}
        onCompleteTask={(task) => completeTaskDirectly(task)}
        onDeleteTask={(task) => setTaskToDelete(task)}
      /> : <>
      {replanNotice && (
        <section
          ref={replanNoticeRef}
          className="replan-notice"
          aria-live="polite"
        >
          <div className="replan-notice__copy">
            <p className="replan-notice__eyebrow">Recovery</p>
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
      <DaySheet
        tasks={tasks}
        incompleteTasks={incompleteTasks}
        completedTodayTasks={completedTodayTasks}
        currentUser={currentUser}
        loading={loading}
        error={error}
        onCreate={() => openForm("create")}
        onEdit={(task) => openForm("edit", task)}
        onComplete={(task) => completeTaskDirectly(task)}
        onDelete={(task) => setTaskToDelete(task)}
        onRecover={handleRecover}
        recoveringId={recoveringId}
      />
      </>}
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
    </AppShell>
  );
}

export default App;
