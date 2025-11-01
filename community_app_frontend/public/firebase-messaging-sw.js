/* eslint-env worker, serviceworker */
/* global firebase */

// public/firebase-messaging-sw.js

// 1. Use the older v8 libraries - this is the fix
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-messaging.js');

// 2. Your config (make sure storageBucket is 'appspot.com')
const firebaseConfig = {
x
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