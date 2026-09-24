import {
  IconCalendar,
  IconCheck,
  IconChevron,
  IconClock,
  IconClose,
  IconEnergy,
  IconFlag,
  IconLeaf,
  IconList,
  IconRecover,
} from "./icons.jsx";
import { isCurrentlyRecovered } from "../utils/taskRecovery.mjs";

const EVENT_LABELS = {
  created: "Created",
  scheduled: "Scheduled",
  completed: "Completed",
  missed: "Missed",
  overdue: "Overdue",
  rescheduled: "Rescheduled",
  recovered: "Recovered",
};

function fmtDateTime(value) {
  if (!value) return null;
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function stateLine(task) {
  if (task.completed || task.status === "completed") return "Completed";
  if (task.status === "missed") return "Missed — open loop";
  if (new Date(task.deadline) < new Date()) return "Overdue — deadline passed";
  return "Pending";
}

function stateKey(task) {
  if (task.completed || task.status === "completed") return "completed";
  if (task.status === "missed") return "missed";
  if (new Date(task.deadline) < new Date()) return "overdue";
  return "pending";
}

// One compact information row. Rows flagged editable reuse the existing
// onEdit handler (keyboard accessible); otherwise the row is inert display.
function FactRow({ icon, iconTone, label, onEdit, children }) {
  const editable = typeof onEdit === "function";
  return (
    <div
      className={`inspector__fact${editable ? " inspector__fact--editable" : ""}`}
      {...(editable
        ? {
            role: "button",
            tabIndex: 0,
            title: `Edit ${label.toLowerCase()}`,
            "aria-label": `Edit ${label.toLowerCase()}`,
            onClick: onEdit,
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onEdit();
              }
            },
          }
        : {})}
    >
      <dt>
        <span className={`inspector__fact-icon inspector__fact-icon--${iconTone}`} aria-hidden="true">
          {icon}
        </span>
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

// Side detail panel: everything shown is task fields or recorded history.
// No invented explanations.
export default function TaskInspector({
  task,
  history,
  onClose,
  onEdit,
  onComplete,
  onDelete,
  onRecover,
  recovering,
  inline = false,
  happeningNow = false,
}) {
  if (!task) return null;
  const missed = task.status === "missed" && !task.completed;
  const done = task.completed || task.status === "completed";

  const panel = (
        <aside
          className={inline ? "inspector inspector--inline" : "inspector"}
        role="dialog"
        aria-modal="false"
        aria-label={`Details for ${task.title}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="inspector__head">
          <p className="sheet-eyebrow">Task detail</p>
          <button className="button button--quiet" type="button" onClick={onClose} aria-label="Close details">
            <IconClose />
            Close
          </button>
        </div>
        <h2 className="inspector__title">{task.title}</h2>
        {happeningNow && !done && (
          <p><span className="inspector__now">Happening now</span></p>
        )}
        {task.description && <p className="inspector__desc">{task.description}</p>}
        <p className="inspector__state-row">
          <span className={`inspector__status inspector__status--${stateKey(task)}`}>
            {stateLine(task)}
          </span>
        </p>
        {isCurrentlyRecovered(task) && (
          <p className="inspector__recovered">
            <IconRecover aria-hidden="true" />
            <span>Recovered — previously missed, brought back into the plan.</span>
          </p>
        )}

        <dl className="inspector__facts">
          <FactRow icon={<IconCalendar />} iconTone="scheduled" label="Scheduled" onEdit={!done ? onEdit : undefined}>
            {task.scheduled_start && task.scheduled_end
              ? `${fmtDateTime(task.scheduled_start)} – ${fmtDateTime(task.scheduled_end)}`
              : "Unscheduled"}
          </FactRow>
          <FactRow icon={<IconCalendar />} iconTone="deadline" label="Deadline">
            {fmtDateTime(task.deadline)}
          </FactRow>
          <FactRow icon={<IconClock />} iconTone="duration" label="Duration" onEdit={!done ? onEdit : undefined}>
            {task.duration_minutes} min
          </FactRow>
          <FactRow icon={<IconFlag />} iconTone="priority" label="Priority" onEdit={!done ? onEdit : undefined}>
            <span className={`priority priority--${task.priority}`}>{task.priority}</span>
          </FactRow>
          <FactRow icon={<IconEnergy />} iconTone="energy" label="Energy" onEdit={!done ? onEdit : undefined}>
            <span className="inspector__chip">{task.energy_level}</span>
          </FactRow>
        </dl>

        {history.length > 0 && (
          <section className="inspector__journey" aria-label="Recorded journey">
            <div className="inspector__journey-head">
              <h3>
                <IconList aria-hidden="true" />
                Recorded journey
              </h3>
              <span className="inspector__count" aria-label={`${history.length} recorded events`}>
                {history.length}
              </span>
            </div>
            <ol>
              {history.map((event) => (
                <li key={event.id} className={`inspector__event inspector__event--${event.event_type}`}>
                  <strong>{EVENT_LABELS[event.event_type] ?? event.event_type}</strong>
                  <span> · {fmtDateTime(event.timestamp)}</span>
                  {event.reason && <span> · {event.reason}</span>}
                </li>
              ))}
            </ol>
          </section>
        )}

        <div className="inspector__actions">
          {!done && !missed && (
            <button className="button button--primary" type="button" onClick={onComplete}>
              <IconCheck />
              Complete
            </button>
          )}
          {!done && (
            <button className="button button--quiet" type="button" onClick={onEdit}>
              Edit
            </button>
          )}
          <button className="button button--quiet button--danger" type="button" onClick={onDelete}>
            Delete
          </button>
        </div>
        <p className="inspector__back">
          <button type="button" onClick={onClose}>
            <IconChevron /> Back to today
          </button>
        </p>
        <p className="inspector__flourish" aria-hidden="true">
          <IconLeaf />
        </p>
      </aside>
    );

  if (inline) {
    return panel;
  }

  return (
    <div className="inspector-backdrop" onClick={onClose}>
      {panel}
    </div>
  );
}
