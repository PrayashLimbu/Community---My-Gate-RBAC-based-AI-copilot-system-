/* eslint-env worker, serviceworker */
/* global firebase */

// public/firebase-messaging-sw.js

// 1. Use the older v8 libraries - this is the fix
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-messaging.js');

// 2. Your config (make sure storageBucket is 'appspot.com')
const firebaseConfig = {
  apiKey: "AIzaSyCU_bzDwyh1r_e8d44srgF-1aWk8xD0pwQ",
  authDomain: "gen-lang-client-0431862828.firebaseapp.com",
  projectId: "gen-lang-client-0431862828",
  storageBucket: "gen-lang-client-0431862828.firebasestorage.app.com",
  messagingSenderId: "184469188139",
  appId: "1:184469188139:web:d00c1269141bb8ffe9046e",
  measurementId: "G-Q7S1HQB379"
};

// 3. Initialize with v8 syntax
firebase.initializeApp(firebaseConfig);

// 4. Get messaging instance with v8 syntax (this is the line that was failing)
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);

  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/favicon.ico'
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});