import ProgressPreview from './ProgressPreview.jsx'

function AppShell({ children }) {
  return <div className="app-shell"><header className="app-header"><a className="brand" href="#today-heading" aria-label="Missed Task Replanner home"><span className="brand__mark" aria-hidden="true">M</span><span>Missed Task<br /><em>Replanner</em></span></a><nav className="navigation" aria-label="Primary navigation"><button className="navigation__item navigation__item--active" type="button">Today</button><button className="navigation__item" type="button">Progress</button><button className="navigation__item" type="button">Reflection</button></nav><ProgressPreview /></header><main className="app-content">{children}</main></div>
}

export default AppShell
