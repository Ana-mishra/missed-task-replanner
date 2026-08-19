import { useEffect, useRef, useState } from 'react'

function AppShell({ children, activePage = 'today', onNavigate, onLogout }) {
  const [profileOpen, setProfileOpen] = useState(false)
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
              <span className="sidebar__icon" aria-hidden="true">⌂</span>
              <span className="sidebar__label">Today</span>
            </button>

            <button
              className="sidebar__item"
              type="button"
            >
              <span className="sidebar__icon" aria-hidden="true">▣</span>
              <span className="sidebar__label">Tasks</span>
            </button>

            <button
              className="sidebar__item"
              type="button"
            >
              <span className="sidebar__icon" aria-hidden="true">□</span>
              <span className="sidebar__label">Schedule</span>
            </button>

            <button
              className={`sidebar__item ${activePage === 'history' ? 'sidebar__item--active' : ''}`}
              type="button"
              onClick={() => onNavigate?.('history')}
            >
              <span className="sidebar__icon" aria-hidden="true">↶</span>
              <span className="sidebar__label">History</span>
            </button>


            <button
              className="sidebar__item"
              type="button"
            >
              <span className="sidebar__icon" aria-hidden="true">◇</span>
              <span className="sidebar__label">Stats</span>
            </button>

            <button className="sidebar__item" type="button">
              <span className="sidebar__icon" aria-hidden="true">⚙</span>
              <span className="sidebar__label">Settings</span>
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
              A
            </span>

            <span className="sidebar__profile-copy">
              <strong>Ana</strong>
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
                  A
                </span>

                <div>
                  <strong>Ana</strong>
                  <span>Your account</span>
                </div>
              </div>

              <button type="button" role="menuitem">
                Profile
              </button>

              <button type="button" role="menuitem">
                Personalization
              </button>

              <button type="button" role="menuitem">
                Settings
              </button>

              <button type="button" role="menuitem">
                Help
              </button>

              <button
                className="profile-menu__logout"
                type="button"
                role="menuitem"
                onClick={onLogout}
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

    </div>
  )
}

export default AppShell
