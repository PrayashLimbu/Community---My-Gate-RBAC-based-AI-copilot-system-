// src/services/fcmService.js
import { getToken } from "firebase/messaging";
import { messaging } from '../firebase-config'; // Import the initialized messaging
import apiClient from './apiClient';

//
// --- 1. FIND THIS KEY IN YOUR FIREBASE CONSOLE ---
// Project Settings > Cloud Messaging > Web configuration (Web Push certificates)
//
const VAPID_KEY = "BEV77t-FxO2RJTbBzN0SLKrq3yq6W0Lh0Ww3KEiXYDosoBokAyoEoyemicDeYWrkEFbBZdN6Y76UxyXxTXLTV1M";
//
// ------------------------------------------------
//

export const requestNotificationPermission = async () => {
  if (!VAPID_KEY) {
      console.error("VAPID_KEY is missing in fcmService.js");
      alert("FCM VAPID key is not set. Notifications will not work.");
      return;
  }
    
  try {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      console.log('Notification permission granted.');
      await registerDeviceToken();
    } else {
      console.warn('Notification permission denied.');
    }
  } catch (error) {
    console.error('An error occurred while requesting permission ', error);
  }
};

const registerDeviceToken = async () => {
  try {
    const currentToken = await getToken(messaging, { vapidKey: VAPID_KEY });
    if (currentToken) {
      console.log('FCM Token:', currentToken);
      // Send this token to your backend
      await sendTokenToBackend(currentToken);
    } else {
      console.log('No registration token available. Request permission to generate one.');
    }
  } catch (err) {
    console.error('An error occurred while retrieving token. ', err);
  }
};

const sendTokenToBackend = async (token) => {
  // Only send if we haven't sent this exact token before
  if (localStorage.getItem('fcmTokenSent') === token) {
      console.log("FCM token already sent to backend.");
      return;
  }
    
  try {
    // Call the new backend endpoint we created
    await apiClient.post('/register-fcm/', {
      registration_id: token
    });
    console.log('FCM Token sent to backend successfully.');
    // Store the token we sent so we don't send it on every page load
    localStorage.setItem('fcmTokenSent', token);
  } catch (error) {
    console.error('Error sending FCM token to backend:', error);
  }
};