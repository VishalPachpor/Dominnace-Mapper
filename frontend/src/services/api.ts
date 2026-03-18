import axios from "axios";

const FALLBACK_LOCAL_API_URL = "http://127.0.0.1:8000";
const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

function resolveApiBaseUrl() {
    // If an explicit API URL is configured, always use it (even on localhost).
    if (rawApiUrl) return rawApiUrl;

    if (typeof window !== "undefined") {
        const { hostname, port, origin } = window.location;
        const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";
        if (isLocalhost || port === "3000" || port === "5173") {
            return FALLBACK_LOCAL_API_URL;
        }
        // In production, prefer same-origin API to avoid network errors.
        return origin;
    }

    // No env var set and no window — fall back to local dev server.
    return FALLBACK_LOCAL_API_URL;
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
