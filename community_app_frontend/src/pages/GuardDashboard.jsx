// src/pages/GuardDashboard.jsx
import React, { useState, useEffect } from 'react';
import apiClient from '../services/apiClient';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import './GuardDashboard.css';

// --- Helper Functions ---
function formatDate(date) {
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatTime(dateString) {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit'});
}

function GuardDashboard() {
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedDate, setSelectedDate] = useState(formatDate(new Date()));
  const [activeTab, setActiveTab] = useState('expected'); // 'expected', 'pending', 'inside', 'dailyLog'
  const [calendarDate, setCalendarDate] = useState(new Date());

  // --- Single, shared function to fetch visitors ---
  const fetchVisitors = async () => {
    setError('');
    try {
      const response = await apiClient.get('/visitors/');
      setVisitors(response.data || []);
    } catch (err) {
      console.error('Failed to fetch visitors:', err);
      setError(`Failed to load visitors: ${err.message}`);
    } finally {
      if (loading) setLoading(false);
    }
  };

  // --- Action Handlers (CheckIn/CheckOut) ---
  const handleCheckIn = async (visitorId) => {
    try {
      await apiClient.post(`/visitors/${visitorId}/checkin/`);
      await fetchVisitors();
    } catch (err) {
      setError(`Check In failed: ${err.message || 'Server error'}`);
      await fetchVisitors();
    }
  };

  const handleCheckOut = async (visitorId) => {
    try {
      await apiClient.post(`/visitors/${visitorId}/checkout/`);
      await fetchVisitors();
    } catch (err) {
      setError(`Check Out failed: ${err.message || 'Server error'}`);
      await fetchVisitors();
    }
  };

  // --- Polling Effect ---
  useEffect(() => {
    fetchVisitors();
    const intervalId = setInterval(fetchVisitors, 3000);
    return () => clearInterval(intervalId);
  }, [selectedDate]);

  // --- Calendar Date Change Handler ---
  const handleDateChange = (date) => {
    setCalendarDate(date);
    setSelectedDate(formatDate(date));
  };

  // --- Filtering & Counting Logic (Client-side) ---
  
  // Get visitors filtered *only by the selected date* first
  const visitorsForSelectedDate = visitors.filter(v => {
      const visitDateStr = v.scheduled_time ? v.scheduled_time.split('T')[0] : v.created_at.split('T')[0];
      return visitDateStr === selectedDate;
  });

  // Now, get counts from that pre-filtered list
  const getCounts = () => {
    return {
      expectedCount: visitorsForSelectedDate.filter(v => v.status === 'APPROVED').length,
      pendingCount: visitorsForSelectedDate.filter(v => v.status === 'PENDING').length,
      insideCount: visitorsForSelectedDate.filter(v => v.status === 'CHECKED_IN').length,
      logCount: visitorsForSelectedDate.filter(v => 
          ['APPROVED', 'DENIED', 'CHECKED_IN', 'CHECKED_OUT'].includes(v.status)
      ).length
    };
  };

  // Get the final displayed list based on the active tab
  const getDisplayedVisitors = () => {
    switch (activeTab) {
      case 'expected':
        return visitorsForSelectedDate.filter(v => v.status === 'APPROVED');
      case 'pending':
        return visitorsForSelectedDate.filter(v => v.status === 'PENDING');
      case 'inside':
        return visitorsForSelectedDate.filter(v => v.status === 'CHECKED_IN');
      case 'dailyLog':
        // Show all non-pending for the log
        return visitorsForSelectedDate.filter(v => 
          ['APPROVED', 'DENIED', 'CHECKED_IN', 'CHECKED_OUT'].includes(v.status)
        );
      default:
        return [];
    }
  };

  const counts = getCounts();
  const displayedVisitors = getDisplayedVisitors();

  // --- **NEW** Function to get the correct time for the default table ---
  const getDisplayTime = (visitor) => {
    if (visitor.status === 'CHECKED_IN' && visitor.checked_in_at) {
      return formatTime(visitor.checked_in_at);
    }
    return formatTime(visitor.scheduled_time); // Fallback to scheduled time
  };

  // --- JSX Return ---
  return (
    <div className="guard-dashboard">

      <div className="calendar-container card">
        <Calendar
          onChange={handleDateChange}
          value={calendarDate}
        />
      </div>

      {/* Tabs - Added Daily Log */}
      <div className="tabs guard-tabs">
        <button
          className={`tab-button expected ${activeTab === 'expected' ? 'active' : ''}`}
          onClick={() => setActiveTab('expected')}
        >
          Expected ({counts.expectedCount})
        </button>
        <button
          className={`tab-button pending ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          Pending ({counts.pendingCount})
        </button>
         <button
          className={`tab-button inside ${activeTab === 'inside' ? 'active' : ''}`}
          onClick={() => setActiveTab('inside')}
        >
          Inside ({counts.insideCount})
        </button>
        <button
          className={`tab-button log ${activeTab === 'dailyLog' ? 'active' : ''}`}
          onClick={() => setActiveTab('dailyLog')}
        >
          Daily Log ({counts.logCount})
        </button>
      </div>

      {/* Visitor List Card */}
      <div className="visitor-list-container card">
        <h3>Visitors for {new Date(selectedDate).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'long', day: 'numeric' })}</h3>
        
        {loading && <p style={{ textAlign: 'center', padding: '20px' }}><i>Loading visitors...</i></p>}
        {error && <p className="error-message" style={{ textAlign: 'center' }}>{error}</p>}

        {!loading && !error && (
          <div className="table-wrapper">
            {/* --- **NEW** Conditional Table Rendering --- */}

            {/* Table for default tabs (Expected, Pending, Inside) */}
            {activeTab !== 'dailyLog' && (
              <table>
                <thead>
                  <tr>
                    <th>Visitor</th>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedVisitors.length > 0 ? (
                    displayedVisitors.map(visitor => (
                      <tr key={visitor.id}>
                        <td>
                          <div className="visitor-name">{visitor.name}</div>
                          <div className="visitor-flat">{visitor.host_household?.flat_number || 'N/A'}</div>
                        </td>
                        <td>{getDisplayTime(visitor)}</td>
                        <td>
                          <span className={`status-text status-${visitor.status.toLowerCase()}`}>
                              {visitor.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          {visitor.status === 'APPROVED' && (
                            <button className="action-button checkin-btn" onClick={() => handleCheckIn(visitor.id)}>Check In</button>
                          )}
                          {visitor.status === 'CHECKED_IN' && (
                            <button className="action-button checkout-btn" onClick={() => handleCheckOut(visitor.id)}>Check Out</button>
                          )}
                          {['PENDING', 'DENIED'].includes(visitor.status) && (
                            <span className="action-text">{visitor.status}</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="4" style={{ textAlign: 'center', padding: '20px' }}>
                        No visitors match this filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}

            {/* Table for "Daily Log" tab */}
            {activeTab === 'dailyLog' && (
              <table>
                <thead>
                  <tr>
                    <th>Visitor</th>
                    <th>Status</th>
                    <th>Approved At</th>
                    <th>Check-In At</th>
                    <th>Check-Out At</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedVisitors.length > 0 ? (
                    displayedVisitors.map(visitor => (
                      <tr key={visitor.id}>
                        <td>
                          <div className="visitor-name">{visitor.name}</div>
                          <div className="visitor-flat">{visitor.host_household?.flat_number || 'N/A'}</div>
                        </td>
                        <td>
                          <span className={`status-text status-${visitor.status.toLowerCase()}`}>
                              {visitor.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td>{formatTime(visitor.approved_at)}</td>
                        <td>{formatTime(visitor.checked_in_at)}</td>
                        <td>{formatTime(visitor.checked_out_at)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>
                        No log entries for this date.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
            
          </div>
        )}
      </div>
    </div>
  );
}

export default GuardDashboard;