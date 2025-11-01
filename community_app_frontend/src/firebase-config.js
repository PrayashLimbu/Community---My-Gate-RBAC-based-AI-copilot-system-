// src/firebase-config.js
import { initializeApp } from "firebase/app";
import { getMessaging } from "firebase/messaging";

// --- PASTE YOUR SAME CONFIG OBJECT FROM FIREBASE CONSOLE HERE ---
const firebaseConfig = {
  apiKey: "AIzaSyCU_bzDwyh1r_e8d44srgF-1aWk8xD0pwQ",
  authDomain: "gen-lang-client-0431862828.firebaseapp.com",
  projectId: "gen-lang-client-0431862828",
  storageBucket: "gen-lang-client-0431862828.firebasestorage.app.com",
  messagingSenderId: "184469188139",
  appId: "1:184469188139:web:d00c1269141bb8ffe9046e",
  measurementId: "G-Q7S1HQB379"
};
// -----------------------------------------------------------

// Initialize Firebase
const app = initializeApp(firebaseConfig);
// Initialize Firebase Cloud Messaging and export it
export const messaging = getMessaging(app);

export default app;