import {
  IconCalendarCheck,
  IconHistory,
  IconJournal,
  IconList,
  IconLogout,
  IconSliders,
  IconSprout,
  IconStats,
  IconSun,
} from './icons.jsx';

// Mobile-only app shell pieces for the M1 phase. Rendered by AppShell; all
// styling hides these on desktop (>768px). Routing reuses App.jsx's existing
// page state — no new routes are introduced here.

const PRIMARY_TABS = [
  { page: 'today', label: 'Today', Icon: IconSun },
  { page: 'plan', label: 'Plan', Icon: IconCalendarCheck },
  { page: 'plant', label: 'Plant', Icon: IconSprout },
];

const SECONDARY_PAGES = new Set(['history', 'stats', 'reflection']);

const MORE_ITEMS = [
  { page: 'history', label: 'History', Icon: IconHistory },
  { page: 'stats', label: 'Stats', Icon: IconStats },
  { page: 'reflection', label: 'Reflection', Icon: IconJournal },
];

export function MobileHeader() {
  return (
    <header className="mobile-header">
      <span className="mobile-header__brand" aria-label="Planora home">
        <span className="mobile-header__brand-mark" aria-hidden="true">
          P
        </span>
        <strong className="mobile-header__brand-name">Planora</strong>
      </span>
    </header>
  );
}

export function MobileBottomNav({ activePage, onNavigate, onOpenMore }) {
  const moreActive = SECONDARY_PAGES.has(activePage);
  return (
    <nav className="mobile-bottom-nav" aria-label="Primary navigation">
      <div className="mobile-bottom-nav__bar">
        {PRIMARY_TABS.map(({ page, label, Icon }) => {
          const active = activePage === page;
          return (
            <button
              key={page}
              className={`mobile-bottom-nav__item${active ? ' mobile-bottom-nav__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.(page)}
              aria-current={active ? 'page' : undefined}
            >
              <span className="mobile-bottom-nav__icon" aria-hidden="true">
                <Icon width={22} height={22} />
              </span>
              <span className="mobile-bottom-nav__label">{label}</span>
            </button>
          );
        })}
        <button
          className={`mobile-bottom-nav__item${moreActive ? ' mobile-bottom-nav__item--active' : ''}`}
          type="button"
          onClick={onOpenMore}
          aria-current={moreActive ? 'page' : undefined}
          aria-label="More navigation options"
        >
          <span className="mobile-bottom-nav__icon" aria-hidden="true">
            <IconList width={22} height={22} />
          </span>
          <span className="mobile-bottom-nav__label">More</span>
        </button>
      </div>
    </nav>
  );
}

export function MobileMoreSheet({
  open,
  activePage,
  onNavigate,
  onOpenSettings,
  onRequestLogout,
  onClose,
}) {
  if (!open) return null;
  const go = (page) => {
    onClose?.();
    onNavigate?.(page);
  };
  const openSettings = () => {
    onClose?.();
    onOpenSettings?.();
  };
  const requestLogout = () => {
    onClose?.();
    onRequestLogout?.();
  };
  return (
    <div className="mobile-more" role="presentation">
      <div
        className="mobile-more__scrim"
        aria-hidden="true"
        onClick={onClose}
      />
      <section
        className="mobile-more__panel"
        role="dialog"
        aria-modal="true"
        aria-label="More navigation options"
      >
        <div className="mobile-more__grabber" aria-hidden="true" />
        <p className="mobile-more__eyebrow">More</p>
        <ul className="mobile-more__list">
          {MORE_ITEMS.map(({ page, label, Icon }) => {
            const active = activePage === page;
            return (
              <li key={page}>
                <button
                  className={`mobile-more__item${active ? ' mobile-more__item--active' : ''}`}
                  type="button"
                  onClick={() => go(page)}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="mobile-more__item-icon" aria-hidden="true">
                    <Icon width={20} height={20} />
                  </span>
                  <span className="mobile-more__item-label">{label}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <div className="mobile-more__divider" aria-hidden="true" />
        <ul className="mobile-more__list">
          <li>
            <button
              className="mobile-more__item"
              type="button"
              onClick={openSettings}
            >
              <span className="mobile-more__item-icon" aria-hidden="true">
                <IconSliders width={20} height={20} />
              </span>
              <span className="mobile-more__item-label">Settings</span>
            </button>
          </li>
          <li>
            <button
              className="mobile-more__item mobile-more__item--danger"
              type="button"
              onClick={requestLogout}
            >
              <span className="mobile-more__item-icon" aria-hidden="true">
                <IconLogout width={20} height={20} />
              </span>
              <span className="mobile-more__item-label">Log out</span>
            </button>
          </li>
        </ul>
        <button
          className="mobile-more__close"
          type="button"
          onClick={onClose}
        >
          Close
        </button>
      </section>
    </div>
  );
}
