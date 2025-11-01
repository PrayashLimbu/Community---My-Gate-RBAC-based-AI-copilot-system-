// src/pages/ResidentDashboard.jsx
import React, { useState, useEffect, useRef } from 'react';
import apiClient from '../services/apiClient';
// We no longer need the FCM service import here
// import { requestNotificationPermission } from '../services/fcmService';
import './ResidentDashboard.css';

// Custom hook to track previous state
function usePrevious(value) {
  const ref = useRef();
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref.current;
}

function ResidentDashboard() {
  const [messages, setMessages] = useState([
    { id: 1, sender: 'bot', text: 'Hello! How can I help you manage visitors today? (e.g., "approve Ramesh", "list my visitors")' }
  ]);
  const [newMessage, setNewMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messageListRef = useRef(null);
  const inputRef = useRef(null); // <-- Ref for the input box

  // State for polling visitors (for notification simulation)
  const [visitors, setVisitors] = useState([]);
  const prevVisitors = usePrevious(visitors);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [messages]);

  // --- FIX 3: Auto-focus input ---
  useEffect(() => {
    // This runs when 'isLoading' changes.
    // When a bot response arrives, isLoading becomes false, and this will focus the input.
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]); // Dependency: run this effect when isLoading changes

  // Polling function to fetch visitors
  const fetchVisitors = async () => {
    try {
      const response = await apiClient.get('/visitors/');
      setVisitors(response.data || []);
    } catch (err) {
      console.error("Failed to poll visitors:", err);
    }
  };

  // Polling Effect
  useEffect(() => {
    fetchVisitors(); // Fetch on load
    const intervalId = setInterval(fetchVisitors, 3000); // Poll every 3 seconds
    return () => clearInterval(intervalId); // Cleanup
  }, []);

  // Notification Simulation Logic
  useEffect(() => {
    if (!prevVisitors || !visitors.length) return;

    visitors.forEach(currentVisitor => {
      const prev = prevVisitors.find(v => v.id === currentVisitor.id);
      if (!prev) return;

      // Simulate check-in notification
      if (currentVisitor.status === 'CHECKED_IN' && prev.status !== 'CHECKED_IN') {
        console.log(`SIMULATING NOTIFICATION: ${currentVisitor.name} checked in!`);
        alert(`[New Notification]\nTitle: Visitor Arrived\nBody: '${currentVisitor.name}' has checked in.`);
      }
      
      // Simulate approval notification for guards (if we were on a guard client)
      if (currentVisitor.status === 'APPROVED' && prev.status !== 'APPROVED') {
        console.log(`SIMULATING NOTIFICATION: ${currentVisitor.name} approved!`);
        // We could show an alert here too if needed
      }
    });

  }, [visitors, prevVisitors]);


  // --- Send Chat Message Handler ---
  const handleSendMessage = async (event) => {
    event.preventDefault();
    const textToSend = newMessage.trim();
    if (!textToSend || isLoading) return;

    const userMessage = { id: Date.now(), sender: 'user', text: textToSend };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setNewMessage('');
    setIsLoading(true); // <-- This triggers the auto-focus effect when set back to false

    const historyForApi = newMessages.slice(-5).map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'model',
        text: msg.text
    }));

    let botResponseText = "Sorry, something went wrong.";
    try {
      const response = await apiClient.post('/chat/', { history: historyForApi });
      botResponseText = response.data.reply;
    } catch (error) {
      console.error("Error sending chat message:", error);
      botResponseText = "Sorry, an error occurred with the AI model.";
    }
    
    const botResponse = { id: Date.now() + 1, sender: 'bot', text: botResponseText };
    setMessages(prevMessages => [...prevMessages, botResponse]);
    setIsLoading(false); // <-- This triggers the auto-focus effect
  };

  // --- JSX ---
  return (
    <div className="chat-container card">
      <h2>AI Copilot Chat</h2>
      
      {/* --- FIX 1: Yellow button is REMOVED --- */}

      <div className="message-list" ref={messageListRef}>
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            <p>
              {msg.text.split('\n').map((line, index, arr) => (
                <React.Fragment key={index}>
                  {line}
                  {index < arr.length - 1 && <br/>}
                </React.Fragment>
              ))}
             </p>
          </div>
        ))}
        {isLoading && (<div className="message bot"><p><i>Thinking...</i></p></div>)}
      </div>
      <form className="message-input-form" onSubmit={handleSendMessage}>
        <input
          ref={inputRef} // <-- Attaching the ref for auto-focus
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          placeholder="Type your message..."
          disabled={isLoading}
          aria-label="Chat message input"
        />
        <button type="submit" disabled={isLoading} aria-label="Send message"></button>
      </form>
    </div>
  );
}

export default ResidentDashboard;