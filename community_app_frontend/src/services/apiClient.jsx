// src/services/apiClient.js
import axios from 'axios';

const apiClient = axios.create({
  // **IMPORTANT**: Use http://localhost:8000 if your backend runs locally via Docker
  // Use your deployed backend URL if it's hosted (e.g., on Azure)
  baseURL: 'http://localhost:8000/api',
  timeout: 10000, // Optional: time in milliseconds before request times out
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add the JWT token to requests automatically
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken'); // Get token from local storage
    if (token) {
      // If token exists, add it to the Authorization header
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config; // Continue with the modified request config
  },
  (error) => {
    // Handle request errors
    return Promise.reject(error);
  }
);

export default apiClient;