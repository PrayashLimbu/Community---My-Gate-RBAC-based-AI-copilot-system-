// src/App.jsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import ResidentDashboard from './pages/ResidentDashboard';
import GuardDashboard from './pages/GuardDashboard';
import AdminDashboard from './pages/AdminDashboard';
import { jwtDecode } from 'jwt-decode';
import FirebaseNotificationHandler from './services/FirebaseNotificationHandler';
// eslint-disable-next-line no-unused-vars
import { requestNotificationPermission } from './services/fcmService';

// --- Authentication Hook ---
// (Checks token validity and decodes role)
function useAuth() {
  const token = localStorage.getItem('accessToken');
  if (!token) return { isAuthenticated: false, role: null };
  try {
    const decodedToken = jwtDecode(token);
    const currentTime = Date.now() / 1000;
    if (decodedToken.exp < currentTime) {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      return { isAuthenticated: false, role: null };
    }
    return { isAuthenticated: true, role: decodedToken.role || 'UNKNOWN' };
  } catch (error) {
    console.error("Failed to decode token:", error);
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    return { isAuthenticated: false, role: null };
  }
}

// --- Main Layout Component (Contains Header) ---
// This component wraps all pages 
function Layout() {
    // eslint-disable-next-line no-unused-vars
    const location = useLocation();
    const { isAuthenticated } = useAuth(); // This hook now re-runs on navigation
    const [theme, setTheme] = useState('light');

    useEffect(() => {
        document.body.className = theme;
    }, [theme]);

    const handleLogout = () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login'; // Force reload/redirect
    };

    return (
        <div className={`app-container ${theme}`}>
            <header className="app-header">
                <h1>Community App</h1>
                
                <button
                    onClick={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
                    className="theme-toggle-button"
                    aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                >
                    {theme === 'light' ? '🌙' : '☀️'}
                </button>
                
                {/* This 'isAuthenticated' is now reactive to navigation */}
                
                {isAuthenticated && (
                    <button onClick={handleLogout} className="logout-button">Logout</button>
                )}
            </header>
            {/* Only load the listener if the user is logged in */}
            {isAuthenticated && <FirebaseNotificationHandler />}
            <main className="app-main-content">
                {/* Renders the current route's page (Login, Dashboard, etc.) */}
                <Outlet /> 
            </main>
        </div>
    );
}

// --- Protected Route (For Logged-in Users) ---
function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <Outlet />;
}

// --- Login Page Wrapper (Redirects if already logged in) ---
function LoginPageWrapper() {
    const { isAuthenticated } = useAuth();
    if (isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }
    return <LoginPage />;
}

// --- Root Path Handler (Decides where to go first) ---
function NavigateBasedOnAuth() {
    const { isAuthenticated } = useAuth();
    return <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />;
}

// --- Dashboard Component (Role-Based Rendering) ---
function Dashboard() {
    const { role } = useAuth();
    switch (role) {
        case 'RESIDENT': return <ResidentDashboard />;
        case 'GUARD': return <GuardDashboard />;
        case 'ADMIN': return <AdminDashboard />;
        case 'UNKNOWN': return <h2>Error: Unknown Role</h2>;
        default: return <p>Loading user...</p>;
    }
}

// --- Main App Component (Defines Routes) ---
function App() {
  return (
    <Router>
      <Routes>
        {/* The Layout component now wraps ALL routes */}
        <Route element={<Layout />}>
          <Route path="/login" element={<LoginPageWrapper />} />
          <Route element={<ProtectedRoute />}>
             <Route path="/dashboard" element={<Dashboard />} />
          </Route>
          <Route path="/" element={<NavigateBasedOnAuth />} />
          <Route path="*" element={<p>404 - Page Not Found</p>} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;