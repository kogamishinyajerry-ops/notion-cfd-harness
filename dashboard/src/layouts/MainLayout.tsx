import { NavLink, Outlet } from 'react-router-dom';
import { useState, useEffect } from 'react';
import './MainLayout.css';

export default function MainLayout() {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

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
        <button className="theme-toggle" onClick={toggleTheme} type="button">
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </header>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
