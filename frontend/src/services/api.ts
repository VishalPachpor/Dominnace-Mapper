import axios from "axios";

const FALLBACK_LOCAL_API_URL = "http://127.0.0.1:8000";
const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

function resolveApiBaseUrl() {
    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        const isLocalDevHost = host === "localhost" || host === "127.0.0.1";

        // When we are developing locally, prefer the local FastAPI server even if
        // an old Fly URL is still sitting in the frontend env file.
        if (isLocalDevHost) {
            return FALLBACK_LOCAL_API_URL;
        }
    }

    return rawApiUrl || FALLBACK_LOCAL_API_URL;
}

const api = axios.create({
    baseURL: resolveApiBaseUrl(),
});

api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error?.response?.status;
        const requestUrl = String(error?.config?.url || "");

        if (typeof window !== "undefined" && status === 401 && !requestUrl.startsWith("/auth/")) {
            localStorage.removeItem("token");
            if (window.location.pathname !== "/login") {
                window.location.href = "/login";
            }
        }

        return Promise.reject(error);
    }
);

export default api;
