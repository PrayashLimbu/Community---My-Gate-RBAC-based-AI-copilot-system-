// src/services/FirebaseNotificationHandler.jsx
import { useEffect } from 'react';
import { onMessage } from "firebase/messaging";
import { messaging } from '../firebase-config'; // Import our initialized messaging

function FirebaseNotificationHandler() {
  useEffect(() => {
    console.log("Setting up foreground message listener...");

    const unsubscribe = onMessage(messaging, (payload) => {
      console.log('Foreground message received: ', payload);

      // Show a simple alert to prove it's working
      const notificationTitle = payload.notification?.title || "New Notification";
      const notificationBody = payload.notification?.body || "You have a new update.";

      alert(`[New Notification]\nTitle: ${notificationTitle}\nBody: ${notificationBody}`);

      // Here, you could use a library like 'react-toastify'
      // to show a much nicer-looking popup instead of an alert.
    });

    // Cleanup: Remove the listener when the component unmounts
    return () => {
      console.log("Cleaning up foreground message listener.");
      unsubscribe();
    };
  }, []);

  return null; // This component renders nothing
}

export default FirebaseNotificationHandler;