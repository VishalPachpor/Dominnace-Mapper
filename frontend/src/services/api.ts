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
    withCredentials: true, // Send HttpOnly cookies on every request
});

api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    if ((config.method || "get").toLowerCase() === "get") {
        config.headers["Cache-Control"] = "no-cache";
        config.headers.Pragma = "no-cache";
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const status = error?.response?.status;
        const requestUrl = String(error?.config?.url || "");

        if (typeof window !== "undefined" && status === 401 && !requestUrl.startsWith("/auth/")) {
            // Attempt silent token refresh using HttpOnly cookie (sent automatically)
            if (!error.config._retry) {
                error.config._retry = true;
                try {
                    const res = await api.post("/auth/refresh");
                    const newToken = res.data.access_token;
                    localStorage.setItem("token", newToken);
                    error.config.headers.Authorization = `Bearer ${newToken}`;
                    return api(error.config);
                } catch {
                    // Refresh failed — fall through to logout
                }
            }
            localStorage.removeItem("token");
            if (window.location.pathname !== "/login") {
                window.location.href = "/login";
            }
        }

        return Promise.reject(error);
    }
);

export default api;
