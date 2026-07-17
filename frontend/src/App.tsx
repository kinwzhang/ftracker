import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import TasksPage from './pages/TasksPage';
import DashboardPage from './pages/DashboardPage';
import TemplatesPage from './pages/TemplatesPage';
import HolidaysPage from './pages/HolidaysPage';
import LoginPage from './components/LoginPage';
import LoadingSpinner from './components/common/LoadingSpinner';
import { fetchMe, logoutUser } from './api/auth';
import { setOnUnauthorized } from './api/client';

const App: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [auth, setAuth] = useState<{ username: string; isStaff: boolean } | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const data = await fetchMe();
      if (data.authenticated) {
        setAuth({ username: data.username, isStaff: data.is_staff });
      } else {
        setAuth(null);
      }
    } catch {
      setAuth(null);
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => setAuth(null));
    checkAuth();
    return () => setOnUnauthorized(null);
  }, [checkAuth]);

  const handleLogin = (username: string, isStaff: boolean) => {
    setAuth({ username, isStaff });
  };

  const handleLogout = async () => {
    await logoutUser();
    setAuth(null);
  };

  if (authLoading) {
    return <LoadingSpinner message="Checking authentication..." />;
  }

  if (!auth) {
    return <LoginPage onLogin={handleLogin} />;
  }

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
              <li className="nav-item">
                <button className="nav-link btn btn-link" onClick={handleLogout}>
                  Logout ({auth.username})
                </button>
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
