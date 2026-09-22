import { IconEnergy, IconRecover, IconSprout, IconStats } from "./icons.jsx";
import { ProductMockup } from "./LandingPage.jsx";

const features = [
  { icon: IconRecover, tone: "green", title: "Recover easily", copy: "Life happens. Planora helps you get back on track quickly." },
  { icon: IconEnergy, tone: "gold", title: "Plan smarter", copy: "Reorganize your day based on real priorities and your energy." },
  { icon: IconSprout, tone: "peach", title: "A kinder approach", copy: "No toxic streaks. Just steady progress at your pace." },
  { icon: IconStats, tone: "lilac", title: "Meaningful insights", copy: "Reflect, learn, and build better habits over time." },
];

function AboutPage({ onHome, onSignIn, onGetStarted }) {
  return (
    <main className="about-page">
      <header className="about-header">
        <button type="button" className="landing-brand" onClick={onHome} aria-label="Planora home">
          <span aria-hidden="true">P</span><strong>Planora</strong>
        </button>
        <nav aria-label="About navigation">
          <button type="button" className="about-header__active">About</button>
          <button type="button" onClick={onSignIn}>Sign in</button>
          <button type="button" className="landing-button landing-button--compact" onClick={onGetStarted}>
            Get started <span aria-hidden="true">→</span>
          </button>
        </nav>
      </header>

      <section className="about-hero">
        <div>
          <p className="landing-eyebrow">About Planora</p>
          <h1>Built for real life.</h1>
          <p>
            Planora helps you recover from missed tasks, reorganize your day,
            and build consistent progress — without guilt. It&apos;s a planning tool
            that adapts to you, not the other way around.
          </p>
        </div>
        <div className="about-hero__botanical" aria-hidden="true"><i /><i /><i /></div>
      </section>

      <section className="about-features" aria-label="Planora features">
        {features.map(({ icon: Icon, tone, title, copy }) => (
          <article key={title}>
            <span className={`landing-feature__icon landing-feature__icon--${tone}`}><Icon /></span>
            <div><h2>{title}</h2><p>{copy}</p></div>
          </article>
        ))}
      </section>

      <section className="about-story">
        <ProductMockup />
        <article className="about-story__copy">
          <p className="landing-eyebrow">Our story</p>
          <h2>Created by a student,<br />for students like you.</h2>
          <p>Planora started from a simple idea: productivity tools should be flexible, human, and kind.</p>
          <p>As a student, I found that traditional planners punished me for falling behind. Planora takes a different approach — it helps you adapt, recover, and keep moving forward, even when life doesn&apos;t go to plan.</p>
          <p>Today, Planora supports students who want to make progress in a way that feels realistic, sustainable, and genuinely helpful.</p>
          <dl>
            <div><dt>1+</dt><dd>Student-built</dd></div>
            <div><dt>Real life</dt><dd>First approach</dd></div>
            <div><dt>Always evolving</dt><dd>With your feedback</dd></div>
          </dl>
        </article>
      </section>

      <section className="about-cta">
        <span aria-hidden="true">❧</span>
        <p>“Progress isn&apos;t about being perfect.<br />It&apos;s about showing up, again and again.”</p>
        <div>
          <button type="button" className="landing-button" onClick={onGetStarted}>Get started <span aria-hidden="true">→</span></button>
          <small>Join Planora and make progress, your way.</small>
        </div>
      </section>
    </main>
  );
}

export default AboutPage;
