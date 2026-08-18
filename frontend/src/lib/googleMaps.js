/**
 * Loading the Google Maps JavaScript API, once, and only if we have a key.
 *
 * The key comes from REACT_APP_GOOGLE_MAPS_API_KEY and is never written into
 * the source. It is a browser key, so it is visible in the bundle by
 * necessity — that is what HTTP-referrer restrictions in the Google Cloud
 * console are for, and they are the actual protection. Restrict it there to
 * the deployed origins and to Maps JavaScript API + Places API.
 *
 * **Absent is a supported state, not a failure.** `mapsConfigured()` is false,
 * nothing is injected, and every consumer falls back to a plain text input —
 * so the address field keeps working before the key is configured, and keeps
 * working if a bill goes unpaid. The same shape as the Instagram integration:
 * the feature is off, and nothing else depends on it being on.
 */

const KEY = (process.env.REACT_APP_GOOGLE_MAPS_API_KEY || "").trim();

// India, so the autocomplete offers Indian addresses first. The product is
// Bengaluru-first; the bias is a nudge, not a restriction.
export const INDIA_BOUNDS = { north: 35.7, south: 6.5, west: 68.0, east: 97.5 };
export const INDIA_CENTRE = { lat: 12.9716, lng: 77.5946 }; // Bengaluru

export const mapsConfigured = () => Boolean(KEY);

let loader = null;

/**
 * Resolve once the Maps + Places libraries are on `window.google`.
 *
 * Rejects rather than hanging when there is no key, so a caller can tell
 * "not configured" from "still loading" and render the fallback immediately.
 * The promise is memoised: two fields on one page must not inject two scripts,
 * which Google warns about and which double-bills.
 */
export function loadGoogleMaps() {
    if (!KEY) return Promise.reject(new Error("no-key"));
    if (window.google?.maps?.places) return Promise.resolve(window.google.maps);
    if (loader) return loader;

    loader = new Promise((resolve, reject) => {
        const existing = document.querySelector("script[data-google-maps]");
        const onReady = () =>
            window.google?.maps?.places
                ? resolve(window.google.maps)
                : reject(new Error("places-missing"));

        if (existing) {
            existing.addEventListener("load", onReady);
            existing.addEventListener("error", () => reject(new Error("script-failed")));
            return;
        }

        const script = document.createElement("script");
        script.src =
            `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(KEY)}` +
            "&libraries=places&loading=async&region=IN&language=en";
        script.async = true;
        script.defer = true;
        script.dataset.googleMaps = "true";
        script.addEventListener("load", onReady);
        script.addEventListener("error", () => {
            // Let a later attempt retry rather than caching the failure
            // forever — a flaky first load on mobile data is not permanent.
            loader = null;
            reject(new Error("script-failed"));
        });
        document.head.appendChild(script);
    });

    return loader;
}

/** A link anybody can open, from a pin or from the text address. */
export function googleMapsLink({ lat, lng, placeId, address }) {
    if (typeof lat === "number" && typeof lng === "number") {
        const base = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
        return placeId ? `${base}&query_place_id=${encodeURIComponent(placeId)}` : base;
    }
    if (address) {
        return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
    }
    return null;
}

/** A static map image — no script, no key needed to decide whether to try. */
export function staticMapUrl({ lat, lng, width = 640, height = 240, zoom = 16 }) {
    if (!KEY || typeof lat !== "number" || typeof lng !== "number") return null;
    const params = new URLSearchParams({
        center: `${lat},${lng}`,
        zoom: String(zoom),
        size: `${width}x${height}`,
        scale: "2",
        maptype: "roadmap",
        markers: `color:0xF05D14|${lat},${lng}`,
        key: KEY,
    });
    return `https://maps.googleapis.com/maps/api/staticmap?${params}`;
}

/** Pretty-print a pin for somebody who has to read it out loud. */
export const formatLatLng = (lat, lng) =>
    typeof lat === "number" && typeof lng === "number"
        ? `${lat.toFixed(5)}, ${lng.toFixed(5)}`
        : null;
