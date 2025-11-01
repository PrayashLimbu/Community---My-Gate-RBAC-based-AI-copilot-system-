// src/pages/AdminDashboard.jsx
import React, { useState, useEffect } from 'react';
import apiClient from '../services/apiClient';
import GuardDashboard from './GuardDashboard'; // <-- 1. Import the Guard Dashboard
import './AdminDashboard.css';

// --- Reusable Audit Log Component ---
// We've moved the original AdminDashboard logic into its own component
function AuditLogView() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchEvents = async () => {
    setError('');
    try {
      const response = await apiClient.get('/events/');
      setEvents(response.data || []);
    } catch (err) {
      console.error('Failed to fetch events:', err);
      setError(`Failed to load audit log: ${err.message}`);
    } finally {
      if (loading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    const intervalId = setInterval(fetchEvents, 3000); // Poll for updates
    return () => clearInterval(intervalId);
  }, []);

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString('en-US', {
      dateStyle: 'medium', timeStyle: 'short',
    });
  };

  return (
    <div className="audit-log-container"> {/* Removed .card, as tab content handles it */}
      <h3>Audit Log</h3>
      <div className="table-wrapper">
        {loading && <p>Loading audit log...</p>}
        {error && <p className="error-message">{error}</p>}
        {!loading && !error && (
          <table>
            <thead>
              <tr>
                <th>Event Type</th>
                <th>Timestamp</th>
                <th>Actor (User)</th>
                <th>Subject (Visitor ID)</th>
                <th>Details (Payload)</th>
              </tr>
            </thead>
            <tbody>
              {events.length > 0 ? (
                events.map(event => (
                  <tr key={event.id}>
                    <td>
                      <span className={`event-badge event-${event.type.toLowerCase()}`}>
                        {event.type.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{formatTimestamp(event.timestamp)}</td>
                    <td>{event.actor || 'System'}</td>
                    <td>{event.subject_visitor || 'N/A'}</td>
                    <td>
                      {event.payload && Object.keys(event.payload).length > 0 ? (
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      ) : ( 'None' )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>
                    No audit events found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// --- NEW User Management Component ---
function UserManagementView() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    setError('');
    try {
      const response = await apiClient.get('/users/');
      setUsers(response.data || []);
    } catch (err) {
      console.error('Failed to fetch users:', err);
      setError(`Failed to load users: ${err.message}`);
    } finally {
      if (loading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    // No polling needed for user list unless you expect frequent changes
  }, []);

  const handleEditRole = (userId) => {
    // TODO: Implement edit logic (e.g., show a modal)
    alert(`Edit role for user ${userId} (not implemented)`);
    // Example API call:
    // await apiClient.patch(`/users/${userId}/`, { role: 'NEW_ROLE' });
    // fetchUsers(); // Refetch
  };

  return (
    <div className="user-management-container">
      <h3>User Management</h3>
      <div className="table-wrapper">
        {loading && <p>Loading users...</p>}
        {error && <p className="error-message">{error}</p>}
        {!loading && !error && (
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Household (Flat)</th>
                <th>Email / Phone</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length > 0 ? (
                users.map(user => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>
                      <span className={`user-role-badge role-${user.role.toLowerCase()}`}>
                        {user.role}
                      </span>
                    </td>
                    <td>{user.household_flat_number || 'N/A'}</td>
                    <td>{user.email || user.phone || 'N/A'}</td>
                    <td>
                      <button className="action-button edit-btn" onClick={() => handleEditRole(user.id)}>Edit Role</button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


// --- Main Admin Dashboard (Tabbed Layout) ---
function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('operations'); // 'operations', 'users', 'audit'

  return (
    <div className="admin-dashboard container">
      <h2>Admin Dashboard</h2>

      {/* Admin Tabs */}
      <div className="tabs admin-tabs">
        <button
          className={`tab-button ${activeTab === 'operations' ? 'active' : ''}`}
          onClick={() => setActiveTab('operations')}
        >
          Daily Operations
        </button>
        <button
          className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          User Management
        </button>
         <button
          className={`tab-button ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          Audit Log
        </button>
      </div>

      {/* Tab Content */}
      <div className="admin-tab-content card">
        {activeTab === 'operations' && (
          // 2. Render the GuardDashboard component directly
          <GuardDashboard />
        )}
        {activeTab === 'users' && (
          <UserManagementView />
        )}
        {activeTab === 'audit' && (
          <AuditLogView />
        )}
      </div>
    </div>
  );
}

export default AdminDashboard;