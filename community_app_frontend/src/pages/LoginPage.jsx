// src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
// Corrected import path: Go up one level from 'pages' then into 'services'
import apiClient from '../services/apiClient'; // <-- CORRECTED PATH

function LoginPage() {
  // --- State Variables ---
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  // --- Login Handler Function ---
  const handleLogin = async (event) => {
    event.preventDefault();
    setError('');
    setIsLoading(true);
    console.log('Attempting login with:', username);

    try {
      const response = await apiClient.post('/token/', {
        username: username,
        password: password,
      });
      const { access, refresh } = response.data;
      localStorage.setItem('accessToken', access);
      localStorage.setItem('refreshToken', refresh);
      console.log('Login successful!');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      console.error('Login failed:', err);
      if (err.response && err.response.status === 401) {
        setError('Invalid username or password.');
      } else {
        setError(`Login failed: ${err.message || 'Please try again later.'}`);
      }
    } finally {
      setIsLoading(false);
    }
  }; // <-- End of handleLogin

  // --- JSX Return Statement ---
  return (
    <div>
      <h2>Login</h2>
      <form onSubmit={handleLogin}>
        <div>
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={isLoading}
            autoComplete="username"
          />
        </div>
        <div>
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isLoading}
            autoComplete="current-password"
          />
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  ); // <-- End of return
} // <-- End of LoginPage

export default LoginPage;