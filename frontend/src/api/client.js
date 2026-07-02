import axios from "axios";

// Read from Vite env, fallback to standard localhost port for local backend
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

export default apiClient;
