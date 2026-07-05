import axios from "axios";

// Priority order for API URL:
// 1. localStorage override (can be set in browser console: localStorage.setItem('docuextract_api_url', 'https://...')
// 2. Vite build-time env var VITE_API_BASE_URL
// 3. Fallback to localhost
const buildTimeUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const apiClient = axios.create({
  baseURL: buildTimeUrl,
  headers: {
    "Content-Type": "application/json",
    "Bypass-Tunnel-Reminder": "true",
  },
});

// Intercept every request and apply runtime localStorage override if present
apiClient.interceptors.request.use((config) => {
  const runtimeUrl = typeof localStorage !== "undefined"
    ? localStorage.getItem("docuextract_api_url")
    : null;
  if (runtimeUrl) {
    config.baseURL = runtimeUrl;
  }
  return config;
});

export default apiClient;
