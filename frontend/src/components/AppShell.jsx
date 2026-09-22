import { useEffect, useRef, useState } from 'react'
import { getSettings, updateSettings } from '../services/api.js'
import {
  IconBellRing,
  IconCalendarCheck,
  IconChecklist,
  IconHistory,
  IconJournal,
  IconPaintbrush,
  IconPlanCalendar,
  IconSprout,
  IconStats,
  IconSun,
  IconUser,
} from './icons.jsx';
import {
  ensurePushSubscription,
  getBrowserPermission,
  hasPushSubscription,
  isPushSupported,
  removePushSubscription,
} from '../utils/browserNotifications.js'

const THEME_CACHE_KEY = 'planora.theme'

function applyTheme(theme) {
  const normalizedTheme = theme === 'dark' || theme === 'system' ? theme : 'light'
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const resolvedTheme = normalizedTheme === 'system'
    ? (systemPrefersDark ? 'dark' : 'light')
    : normalizedTheme
  document.documentElement.dataset.theme = resolvedTheme
  try {
    localStorage.setItem(THEME_CACHE_KEY, normalizedTheme)
  } catch {
    // Private-mode storage failures must not break theme application.
  }
}

const DEFAULT_SETTINGS = {
  theme: 'light',
  planning_reminders: true,
  missed_task_reminders: true,
  reflection_reminders: true,
}

const NOTIFICATION_FIELDS = ['planning_reminders', 'missed_task_reminders', 'reflection_reminders']

function AppShell({
  children,
  activePage = 'today',
  onNavigate,
  onLogout,
  onUpdateCurrentUser,
  progress,
  currentUser,
}) {
  const [profileOpen, setProfileOpen] = useState(false)
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSection, setSettingsSection] = useState('account')
  const [nameDraft, setNameDraft] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [settingsError, setSettingsError] = useState(null)
  const [settings, setSettings] = useState(null)
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [savingSetting, setSavingSetting] = useState(null)
  const [browserPermission, setBrowserPermission] = useState(() => getBrowserPermission())
  const [pushSubscriptionExists, setPushSubscriptionExists] = useState(false)
  const [browserNotice, setBrowserNotice] = useState(null)
 const sidebarRef = useRef(null)
   useEffect(() => {
    function handleOutsideClick(event) {
      if (
        profileOpen &&
        sidebarRef.current &&
        !sidebarRef.current.contains(event.target)
      ) {
        setProfileOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
    }
  }, [profileOpen])

  useEffect(() => {
    if (!logoutConfirmOpen && !settingsOpen) return undefined

    function handleEscape(event) {
      if (event.key === 'Escape') {
        setLogoutConfirmOpen(false)
        setSettingsOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [logoutConfirmOpen, settingsOpen])

  useEffect(() => {
    if (settingsOpen) {
      setNameDraft(currentUser?.name ?? '')
      setSettingsError(null)
    }
  }, [settingsOpen, currentUser])

  useEffect(() => {
    let active = true
    getSettings()
      .then((result) => {
        if (!active) return
        setSettings(result)
        applyTheme(result.theme)
        hasPushSubscription()
          .then(setPushSubscriptionExists)
          .catch(() => setPushSubscriptionExists(false))
      })
      .catch(() => active && setSettingsError("Couldn't load your settings right now."))
      .finally(() => active && setSettingsLoading(false))

    return () => {
      active = false
    }
  }, [currentUser?.id])

  useEffect(() => {
    if (!settings || settings.theme !== 'system') return undefined
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => applyTheme('system')
    mediaQuery.addEventListener?.('change', handleChange)
    return () => mediaQuery.removeEventListener?.('change', handleChange)
  }, [settings?.theme])

  function openLogoutConfirmation() {
    setProfileOpen(false)
    setLogoutConfirmOpen(true)
  }

  function confirmLogout() {
    setLogoutConfirmOpen(false)
    onLogout?.()
  }

  function openSettings() {
    setProfileOpen(false)
    setSettingsSection('account')
    setSettingsOpen(true)
  }

  async function saveSettingsName(event) {
    event.preventDefault()
    const trimmedName = nameDraft.trim()
    if (!trimmedName || !onUpdateCurrentUser) return

    setSavingName(true)
    setSettingsError(null)
    try {
      await onUpdateCurrentUser(trimmedName)
    } catch (error) {
      setSettingsError(error.message)
    } finally {
      setSavingName(false)
    }
  }

  async function saveSetting(field, value) {
    if (!settings) return
    const previous = settings
    setSettings({ ...settings, [field]: value })
    setSavingSetting(field)
    setSettingsError(null)
    if (field === 'theme') applyTheme(value)
    try {
      const saved = await updateSettings({ [field]: value })
      setSettings(saved)
      if (field === 'theme') applyTheme(saved.theme)
      if (NOTIFICATION_FIELDS.includes(field)) {
        try {
          await handleNotificationToggle(saved, field, value)
        } catch (pushError) {
          // The preference itself is already persisted above: a push-setup
          // failure must not roll it back locally or masquerade as a save
          // failure. Surface it in the notification notice area only, so
          // the visible error names the operation that actually failed.
          setBrowserNotice(
            pushError?.message ||
              'Could not enable browser notifications. Please try again.',
          )
        }
      }
    } catch {
      setSettings(previous)
      if (field === 'theme') applyTheme(previous.theme)
      setSettingsError("Couldn't save that setting. Please try again.")
    } finally {
      setSavingSetting(null)
    }
  }

  // Browser permission flow: only runs after the user explicitly enables a
  // notification preference. Never prompts merely for opening Settings.
  async function handleNotificationToggle(savedSettings, field, value) {
    if (!NOTIFICATION_FIELDS.includes(field)) return
    if (!isPushSupported()) {
      setBrowserPermission('unsupported')
      setBrowserNotice('Browser notifications are not supported in this browser.')
      throw new Error('Browser notifications are not supported in this browser.')
    }
    setBrowserPermission(getBrowserPermission())
    if (value === true) {
      const permission = getBrowserPermission()
      if (permission === 'denied') {
        // Do not re-prompt; explain calmly and keep the modal usable.
        setBrowserNotice(
          'Browser notifications are blocked. Enable them in your browser site settings to receive reminders.',
        )
        throw new Error('Browser notifications are blocked. Enable them in your browser site settings to receive reminders.')
      }
      if (permission === 'default') {
        let next
        try {
          next = await Notification.requestPermission()
        } catch {
          setBrowserNotice('Browser notifications need your permission to work.')
          throw new Error('Browser notifications need your permission to work.')
        }
        setBrowserPermission(next)
        if (next !== 'granted') {
          setBrowserNotice(
            next === 'denied'
              ? 'Browser notifications are blocked. Enable them in your browser site settings to receive reminders.'
              : 'Browser notifications need your permission to work.',
          )
          throw new Error('Browser notifications need your permission to work.')
        }
      }
      try {
        await ensurePushSubscription()
        setPushSubscriptionExists(true)
        setBrowserPermission(getBrowserPermission())
        setBrowserNotice('Browser notifications are enabled.')
      } catch (pushError) {
        // The preference itself is already persisted above: a push-setup
        // failure must not roll it back locally or masquerade as a save
        // failure. Surface the calm push message in the notification
        // notice area only.
        setBrowserNotice(
          pushError?.message ||
            'Could not enable browser notifications. Please try again.',
        )
      }
      return
    }
    // Preference turned off: if no reminder type remains on, drop the push
    // subscription so nothing is delivered.
    const anyEnabled = NOTIFICATION_FIELDS.some((name) => savedSettings[name])
    if (!anyEnabled) {
      await removePushSubscription()
      setPushSubscriptionExists(false)
      setBrowserNotice(null)
    }
  }

  async function enableBrowserNotifications() {
    setBrowserNotice(null)
    if (!isPushSupported()) {
      setBrowserPermission('unsupported')
      setBrowserNotice('Browser notifications are not supported in this browser.')
      return
    }
    const permission = getBrowserPermission()
    if (permission === 'denied') {
      setBrowserPermission(permission)
      setBrowserNotice(
        'Browser notifications are blocked. Enable them in your browser site settings to receive reminders.',
      )
      return
    }
    if (permission === 'default') {
      const next = await Notification.requestPermission()
      setBrowserPermission(next)
      if (next !== 'granted') return
    }
    try {
      await ensurePushSubscription()
      setPushSubscriptionExists(true)
      setBrowserPermission(getBrowserPermission())
      setBrowserNotice('Browser notifications are enabled.')
    } catch {
      setBrowserNotice('Could not enable browser notifications. Please try again.')
    }
  }

  const displayedSettings = settings ?? DEFAULT_SETTINGS

  return (
    <div className="app-shell">

      <aside
  ref={sidebarRef}
  className="sidebar"
  onMouseLeave={() => setProfileOpen(false)}
>


        <div className="sidebar__top">

          <button
            className="sidebar__brand"
            type="button"
            onClick={() => onNavigate?.('today')}
            aria-label="Planora home"
          >
            <span className="sidebar__brand-mark" aria-hidden="true">
              P
            </span>

            <span className="sidebar__brand-name">
              Planora
            </span>
          </button>

          <nav className="sidebar__navigation" aria-label="Primary navigation">

            <button
              className={`sidebar__item ${activePage === 'today' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('today')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconSun width={22} height={22} /></span>
              <span className="sidebar__label">Today</span>
            </button>

            <button
              className={`sidebar__item ${activePage === 'plan' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('plan')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconCalendarCheck width={22} height={22} /></span>
              <span className="sidebar__label">Plan My Day</span>
            </button>

            <button
              className={`sidebar__item ${activePage === 'plant' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('plant')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconSprout width={22} height={22} /></span>
              <span className="sidebar__label">My Plant</span>
            </button>

            <button
              className={`sidebar__item ${activePage === 'history' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('history')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconHistory width={22} height={22} /></span>
              <span className="sidebar__label">History</span>
            </button>


            <button
              className={`sidebar__item ${activePage === 'stats' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('stats')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconStats width={22} height={22} /></span>
              <span className="sidebar__label">Stats</span>
            </button>

            <button
              className={`sidebar__item ${activePage === 'reflection' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('reflection')}
            >
              <span className="sidebar__icon" aria-hidden="true"><IconJournal width={22} height={22} /></span>
              <span className="sidebar__label">Reflection</span>
            </button>

          </nav>

        </div>

        <div className="sidebar__bottom">
          <button
            className="sidebar__profile"
            type="button"
            onClick={() => setProfileOpen((current) => !current)}
            aria-expanded={profileOpen}
            aria-haspopup="menu"
          >
            <span className="sidebar__avatar" aria-hidden="true">
  {currentUser?.name?.charAt(0).toUpperCase()}
</span>

<span className="sidebar__profile-copy">
  <strong>{currentUser?.name}</strong>
  <span>View profile</span>
</span>

            <span className="sidebar__profile-arrow" aria-hidden="true">
              ›
            </span>
          </button>

          {profileOpen && (
            <div className="profile-menu" role="menu">

              <div className="profile-menu__header">
              <span className="profile-menu__avatar">
  {currentUser?.name?.charAt(0).toUpperCase()}
</span>

<div>
  <strong>{currentUser?.name}</strong>
  <span>Your account</span>
</div>
              </div>

              <button type="button" role="menuitem" onClick={openSettings}>
                Settings
              </button>

              <button
                className="profile-menu__logout"
                type="button"
                role="menuitem"
                onClick={openLogoutConfirmation}
              >
                Log out
              </button>

            </div>
          )}

        </div>

      </aside>

      <main className="app-content">
        {children}
      </main>

      {logoutConfirmOpen && (
        <div
          className="modal-backdrop logout-confirmation-backdrop"
          role="presentation"
          onClick={() => setLogoutConfirmOpen(false)}
        >
          <section
            className="logout-confirmation"
            role="dialog"
            aria-modal="true"
            aria-labelledby="logout-confirmation-title"
            aria-describedby="logout-confirmation-description"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="icon-button logout-confirmation__close"
              type="button"
              onClick={() => setLogoutConfirmOpen(false)}
              aria-label="Close logout confirmation"
            >
              ×
            </button>
            <div className="logout-confirmation__content">
              <span className="logout-confirmation__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 17l5-5-5-5" />
                  <path d="M15 12H3" />
                  <path d="M21 4v16" />
                </svg>
              </span>
              <div>
                <h2 id="logout-confirmation-title">Log out?</h2>
                <p id="logout-confirmation-description">
                  Are you sure you want to log out of your Planora account?
                </p>
              </div>
            </div>
            <div className="logout-confirmation__actions">
              <button
                className="button button--quiet"
                type="button"
                onClick={() => setLogoutConfirmOpen(false)}
              >
                Cancel
              </button>
              <button className="button button--primary" type="button" onClick={confirmLogout}>
                Log out
              </button>
            </div>
          </section>
        </div>
      )}

      {settingsOpen && (
        <div
          className="modal-backdrop settings-modal-backdrop"
          role="presentation"
          onClick={() => setSettingsOpen(false)}
        >
          <section
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="settings-modal__close"
              type="button"
              onClick={() => setSettingsOpen(false)}
              aria-label="Close settings"
            >
              ×
            </button>
            <nav className="settings-modal__navigation" aria-label="Settings sections">
              {[
                ['account', IconUser, 'Account'],
                ['notifications', IconBellRing, 'Notifications'],
                ['appearance', IconPaintbrush, 'Appearance'],
              ].map(([value, Icon, label]) => (
                <button
                  key={value}
                  className={settingsSection === value ? 'settings-modal__nav-item settings-modal__nav-item--active' : 'settings-modal__nav-item'}
                  type="button"
                  onClick={() => setSettingsSection(value)}
                >
                  <span aria-hidden="true">
                    <Icon width={18} height={18} style={{ display: 'block', margin: '0 auto' }} />
                  </span>
                  {label}
                </button>
              ))}
            </nav>
            <div className="settings-modal__content">
              {settingsLoading && !settings ? (
                <p className="settings-modal__loading">Loading your settings…</p>
              ) : settingsSection === 'account' ? (
                <>
                  <header className="settings-modal__header">
                    <h2 id="settings-modal-title">Account</h2>
                    <p>View and manage your account information.</p>
                  </header>
                  <div className="settings-modal__identity">
                    <span className="settings-modal__avatar" aria-hidden="true">
                      {currentUser?.name?.charAt(0).toUpperCase()}
                    </span>
                    <div>
                      <strong>{currentUser?.name}</strong>
                      <span>Your Planora account</span>
                    </div>
                  </div>
                  <form className="settings-modal__form" onSubmit={saveSettingsName}>
                    <label>
                      Name
                      <input value={nameDraft} onChange={(event) => setNameDraft(event.target.value)} />
                    </label>
                    <label>
                      Email
                      <input value={currentUser?.email ?? ''} disabled />
                      <small>Your email cannot be changed right now.</small>
                    </label>
                    {settingsError && <p className="settings-modal__error" role="alert">{settingsError}</p>}
                    <button className="button button--primary" type="submit" disabled={savingName || !nameDraft.trim()}>
                      {savingName ? 'Saving…' : 'Save changes'}
                    </button>
                  </form>
                </>
              ) : settingsSection === 'notifications' ? (
                <>
                  <header className="settings-modal__header">
                    <h2 id="settings-modal-title">Notifications</h2>
                    <p>Stay on track with gentle reminders.</p>
                  </header>
                  <div className="settings-modal__rows">
                    {[
                      ['planning_reminders', IconPlanCalendar, 'Planning reminders', 'Get reminded to plan your day.'],
                      ['missed_task_reminders', IconChecklist, 'Missed-task reminders', 'Get gentle nudges for incomplete tasks.'],
                      ['reflection_reminders', IconSprout, 'Reflection reminders', 'Get reminded to do your weekly reflection.'],
                    ].map(([field, Icon, title, description]) => (
                      <div className="settings-modal__row" key={field}>
                        <span className="settings-modal__row-icon" aria-hidden="true">
                          <Icon width={19} height={19} style={{ display: 'block' }} />
                        </span>
                        <div>
                          <strong>{title}</strong>
                          <span>{description}</span>
                        </div>
                        <button
                          className={`settings-toggle ${displayedSettings[field] ? 'settings-toggle--on' : ''}`}
                          type="button"
                          role="switch"
                          aria-checked={displayedSettings[field]}
                          aria-label={title}
                          disabled={!settings || savingSetting === field}
                          onClick={() => saveSetting(field, !displayedSettings[field])}
                        >
                          <span />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="settings-modal__notice" role="status">
                    {!NOTIFICATION_FIELDS.some((field) => displayedSettings[field]) ? (
                      browserNotice ? (
                        <span>{browserNotice}</span>
                      ) : (
                        <span>Browser notifications are off.</span>
                      )
                    ) : NOTIFICATION_FIELDS.some((field) => displayedSettings[field]) && pushSubscriptionExists ? (
                      <span>Browser notifications are enabled.</span>
                    ) : browserPermission === 'denied' ? (
                      <span>Browser notifications are blocked. Enable them in your browser site settings to receive reminders.</span>
                    ) : browserNotice ? (
                      <span>{browserNotice}</span>
                    ) : (
                      <button
                        className="button button--quiet"
                        type="button"
                        onClick={enableBrowserNotifications}
                      >
                        Enable browser notifications
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <header className="settings-modal__header">
                    <h2 id="settings-modal-title">Appearance</h2>
                    <p>Choose how Planora looks for you.</p>
                  </header>
                  <div className="settings-theme-section">
                    <div>
                      <strong>Theme</strong>
                      <span>Select your preferred theme.</span>
                    </div>
                    <div className="settings-theme-options">
                      {[
                        ['light', '☼', 'Light'],
                        ['dark', '☾', 'Dark'],
                        ['system', '▣', 'System'],
                      ].map(([value, icon, label]) => (
                        <button
                          className={displayedSettings.theme === value ? 'settings-theme-option settings-theme-option--selected' : 'settings-theme-option'}
                          key={value}
                          type="button"
                          onClick={() => saveSetting('theme', value)}
                          disabled={!settings || savingSetting === 'theme'}
                        >
                          <span className="settings-theme-option__icon" aria-hidden="true">{icon}</span>
                          <span>{label}</span>
                          <i aria-hidden="true" />
                        </button>
                      ))}
                    </div>
                    <small>You can always change this later.</small>
                  </div>
                </>
              )}
              {settingsError && <p className="settings-modal__notice" role="alert">{settingsError}</p>}
            </div>
          </section>
        </div>
      )}

    </div>
  )
}

export default AppShell
