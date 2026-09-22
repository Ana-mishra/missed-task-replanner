import {
  IconCalendarCheck,
  IconChevron,
  IconEnergy,
  IconHistory,
  IconRecover,
  IconSprout,
  IconStats,
} from "./icons.jsx";

const featureItems = [
  {
    icon: IconRecover,
    tone: "green",
    title: "Missed-task recovery",
    copy: "Life happens. Planora helps you get back on track quickly.",
  },
  {
    icon: IconEnergy,
    tone: "gold",
    title: "Smarter planning",
    copy: "Reorganize your day based on real priorities and your energy.",
  },
  {
    icon: IconSprout,
    tone: "peach",
    title: "A kinder approach",
    copy: "No toxic streaks. Just steady progress at your pace.",
  },
  {
    icon: IconStats,
    tone: "lilac",
    title: "Meaningful insights",
    copy: "Reflect, learn, and build better habits over time.",
  },
];

function MockSidebarItem({ icon: Icon, label, active }) {
  return (
    <div className={`landing-mock__nav-item${active ? " landing-mock__nav-item--active" : ""}`}>
      <Icon />
      <span>{label}</span>
    </div>
  );
}

export function ProductMockup() {
  return (
    <div className="landing-mock" aria-label="Preview of Planora's Today page">
      <div className="landing-mock__browser-bar" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="landing-mock__app">
        <aside className="landing-mock__sidebar">
          <div className="landing-mock__brand">
            <b>P</b>
            <span>Planora</span>
          </div>
          <nav>
            <MockSidebarItem icon={IconCalendarCheck} label="Today" active />
            <MockSidebarItem icon={IconCalendarCheck} label="Plan My Day" />
            <MockSidebarItem icon={IconSprout} label="My Plant" />
            <MockSidebarItem icon={IconHistory} label="History" />
            <MockSidebarItem icon={IconStats} label="Stats" />
            <MockSidebarItem icon={IconSprout} label="Reflection" />
          </nav>
          <div className="landing-mock__profile">
            <b>A</b>
            <span>Ana<small>View profile</small></span>
            <IconChevron />
          </div>
        </aside>

        <section className="landing-mock__content">
          <header className="landing-mock__header">
            <div>
              <p>Today</p>
              <h2>Good evening, Ana! <span aria-hidden="true">🌿</span></h2>
              <small>Here is what your day looks like.</small>
            </div>
            <button type="button">+ Add task</button>
          </header>

          <div className="landing-mock__summary">
            <article><IconCalendarCheck /><span>Scheduled<strong>3</strong></span></article>
            <article><IconEnergy /><span>Needs decision<strong>1</strong></span></article>
            <article><IconHistory /><span>Unscheduled<strong>2</strong></span></article>
          </div>

          <div className="landing-mock__plan-heading">
            <p>Schedule</p>
            <h3>The day&apos;s plan</h3>
            <span>Persisted slots from Plan My Day.</span>
          </div>
          <div className="landing-mock__schedule">
            <div className="landing-mock__now"><span>NOW · 6:30 PM</span></div>
            <p>Earlier</p>
            <div className="landing-mock__task-row">
              <time>5:30 pm</time><IconCalendarCheck /><span><strong>Review lecture notes</strong><small>30 min · Medium energy</small></span><IconChevron />
            </div>
            <div className="landing-mock__task-row">
              <time>6:00 pm</time><IconCalendarCheck /><span><strong>Finish assignment draft</strong><small>45 min · High priority</small></span><IconChevron />
            </div>
            <div className="landing-mock__task-row landing-mock__task-row--next">
              <time>6:45 pm</time><IconCalendarCheck /><span><strong>Plan tomorrow&apos;s study session</strong><small>20 min · Low energy</small></span><IconChevron />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function LandingPage({ onAbout, onSignIn, onGetStarted }) {
  return (
    <main className="landing-page">
      <header className="landing-header">
        <a className="landing-brand" href="#top" aria-label="Planora home">
          <span aria-hidden="true">P</span>
          <strong>Planora</strong>
        </a>
        <nav aria-label="Landing navigation">
          <button type="button" onClick={onAbout}>About</button>
          <button type="button" onClick={onSignIn}>Sign in</button>
          <button type="button" className="landing-button landing-button--compact" onClick={onGetStarted}>
            Get started <span aria-hidden="true">→</span>
          </button>
        </nav>
      </header>

      <section className="landing-hero" id="top">
        <div className="landing-hero__copy">
          <p className="landing-eyebrow">A gentler way forward</p>
          <h1>Plans change.<br />You can still<br /><em>move forward.</em></h1>
          <p className="landing-hero__description">
            Planora helps you recover from missed tasks, reorganize your day,
            and build consistent progress — without guilt.
          </p>
          <div className="landing-hero__actions">
            <button type="button" className="landing-button" onClick={onGetStarted}>
              Get started <span aria-hidden="true">→</span>
            </button>
            <a href="#about" className="landing-see-how"><span aria-hidden="true">▶</span> See how it works</a>
          </div>
          <ul className="landing-reassurance" aria-label="Planora benefits">
            <li>Free to use</li>
            <li>No credit card required</li>
            <li>Built for students</li>
          </ul>
        </div>
        <div className="landing-hero__product">
          <ProductMockup />
        </div>
      </section>

      <section className="landing-features" id="about" aria-label="Planora features">
        {featureItems.map(({ icon: Icon, tone, title, copy }) => (
          <article key={title}>
            <span className={`landing-feature__icon landing-feature__icon--${tone}`}><Icon /></span>
            <div><h2>{title}</h2><p>{copy}</p></div>
          </article>
        ))}
      </section>
    </main>
  );
}

export default LandingPage;
