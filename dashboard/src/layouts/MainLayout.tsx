import { NavLink, Outlet } from 'react-router-dom';
import './MainLayout.css';

export default function MainLayout() {
  return (
    <div className="layout">
      <header className="header">
        <div className="header-brand">
          <span className="brand-logo">CFD</span>
          <span className="brand-text">AI-CFD Knowledge Harness</span>
        </div>
        <nav className="header-nav">
          <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Dashboard
          </NavLink>
          <NavLink to="/cases" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Cases
          </NavLink>
          <NavLink to="/jobs" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Jobs
          </NavLink>
          <NavLink to="/reports" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Reports
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
            Settings
          </NavLink>
        </nav>
      </header>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
