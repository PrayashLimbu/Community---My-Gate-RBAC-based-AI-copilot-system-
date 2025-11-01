// src/firebase-config.js
import { initializeApp } from "firebase/app";
import { getMessaging } from "firebase/messaging";

// --- PASTE YOUR SAME CONFIG OBJECT FROM FIREBASE CONSOLE HERE ---
x--------------------------------------------------------

// Initialize Firebase
const app = initializeApp(firebaseConfig);
// Initialize Firebase Cloud Messaging and export it
export const messaging = getMessaging(app);

export default app;