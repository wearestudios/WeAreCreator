import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API_BASE,
    withCredentials: true,
    headers: { "Content-Type": "application/json" },
});

/**
 * Resolve a stored media path to a URL the browser can load.
 *
 * Uploads are stored as origin-relative paths ("/uploads/xyz.jpg") so the
 * record survives the backend moving host. Absolute URLs pass through
 * untouched, which keeps this working if storage moves to a CDN later.
 */
export function mediaUrl(path) {
    if (!path) return null;
    if (/^https?:\/\//i.test(path)) return path;
    return `${BACKEND_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

export function formatApiError(err) {
    const detail = err?.response?.data?.detail;
    if (detail == null) return err?.message || "Something went wrong.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
        return detail
            .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
            .join(" ");
    if (detail && typeof detail.msg === "string") return detail.msg;
    return String(detail);
}
