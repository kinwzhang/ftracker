import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import TasksPage from './pages/TasksPage';
import DashboardPage from './pages/DashboardPage';
import TemplatesPage from './pages/TemplatesPage';
import HolidaysPage from './pages/HolidaysPage';

const App: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <BrowserRouter>
      <nav className="navbar glass navbar-expand-lg">
        <div className="container-fluid">
          <NavLink className="navbar-brand" to="/">
            Monthly Activities Tracker
          </NavLink>
          <button
            className="navbar-toggler"
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-controls="navbarNav"
            aria-expanded={menuOpen}
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div className={`collapse navbar-collapse ${menuOpen ? 'show' : ''}`} id="navbarNav">
            <ul className="navbar-nav ms-auto">
              <li className="nav-item">
                <NavLink
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  to="/"
                  end
                  onClick={() => setMenuOpen(false)}
                >
                  Tasks
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  to="/dashboard"
                  onClick={() => setMenuOpen(false)}
                >
                  Dashboard
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  to="/templates"
                  onClick={() => setMenuOpen(false)}
                >
                  Templates
                </NavLink>
              </li>
              <li className="nav-item">
                <NavLink
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  to="/holidays"
                  onClick={() => setMenuOpen(false)}
                >
                  Holidays
                </NavLink>
              </li>
            </ul>
          </div>
        </div>
      </nav>

      <div className="container-fluid" style={{ paddingTop: '80px' }}>
        <Routes>
          <Route path="/" element={<TasksPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/holidays" element={<HolidaysPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
