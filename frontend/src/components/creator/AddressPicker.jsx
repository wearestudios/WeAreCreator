// The full address, as text and as a pin.
//
// Two things that look like one. The text is what gets printed on a delivery
// label and read by a human; the pin is what a courier or one of our team
// actually navigates to. Autocomplete routinely lands on the street rather
// than the building, so the pin has to be draggable — otherwise we would be
// storing a precise-looking coordinate that is precisely wrong, which is worse
// than none at all.
//
// **Degrades to a plain textarea when there is no API key.** That is a
// supported state, not a failure: the field has to work before the key is
// configured and keep working if it is ever removed. Everything below the
// textarea is additive.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MapPin, X } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import {
    INDIA_BOUNDS,
    formatLatLng,
    googleMapsLink,
    loadGoogleMaps,
    mapsConfigured,
    staticMapUrl,
} from "@/lib/googleMaps";
import { ADDRESS } from "@/constants/testIds";

export default function AddressPicker({
    address,
    lat,
    lng,
    placeId,
    onChange,
    testid,
    disabled,
}) {
    const inputRef = useRef(null);
    const mapNodeRef = useRef(null);
    const mapRef = useRef(null);
    const markerRef = useRef(null);
    // onChange changes identity every render in the parent form; keeping it in
    // a ref means the map effect does not tear down and rebuild the map on
    // every keystroke.
    const changeRef = useRef(onChange);
    changeRef.current = onChange;

    const [status, setStatus] = useState(mapsConfigured() ? "loading" : "off");

    const hasPin = typeof lat === "number" && typeof lng === "number";

    const setPin = useCallback((next) => {
        changeRef.current(next);
    }, []);

    // --- load the API --------------------------------------------------
    useEffect(() => {
        if (!mapsConfigured()) return;
        let cancelled = false;
        loadGoogleMaps()
            .then(() => !cancelled && setStatus("ready"))
            .catch(() => !cancelled && setStatus("failed"));
        return () => {
            cancelled = true;
        };
    }, []);

    // --- autocomplete on the text field --------------------------------
    useEffect(() => {
        if (status !== "ready" || !inputRef.current) return;
        const maps = window.google.maps;
        const autocomplete = new maps.places.Autocomplete(inputRef.current, {
            // Biased to India rather than restricted to it, so somebody with a
            // genuinely foreign address is not simply stuck.
            bounds: new maps.LatLngBounds(
                { lat: INDIA_BOUNDS.south, lng: INDIA_BOUNDS.west },
                { lat: INDIA_BOUNDS.north, lng: INDIA_BOUNDS.east },
            ),
            componentRestrictions: { country: "in" },
            fields: ["formatted_address", "geometry", "place_id", "name"],
        });

        const listener = autocomplete.addListener("place_changed", () => {
            const place = autocomplete.getPlace();
            if (!place?.geometry?.location) return; // they typed and pressed enter
            setPin({
                address: place.formatted_address || place.name || "",
                lat: place.geometry.location.lat(),
                lng: place.geometry.location.lng(),
                placeId: place.place_id || null,
            });
        });

        return () => listener.remove();
    }, [status, setPin]);

    // --- the draggable pin ----------------------------------------------
    useEffect(() => {
        if (status !== "ready" || !hasPin || !mapNodeRef.current) return;
        const maps = window.google.maps;
        const position = { lat, lng };

        if (!mapRef.current) {
            mapRef.current = new maps.Map(mapNodeRef.current, {
                center: position,
                zoom: 17,
                disableDefaultUI: true,
                zoomControl: true,
                gestureHandling: "cooperative",
            });
            markerRef.current = new maps.Marker({
                map: mapRef.current,
                position,
                draggable: true,
            });
            markerRef.current.addListener("dragend", (e) => {
                // Only the coordinates move. The text address is deliberately
                // left alone: they wrote "2nd floor, above the pharmacy" and
                // reverse-geocoding would throw that away for a street name.
                setPin({ lat: e.latLng.lat(), lng: e.latLng.lng() });
            });
        } else {
            mapRef.current.setCenter(position);
            markerRef.current.setPosition(position);
        }
    }, [status, hasPin, lat, lng, setPin]);

    // A map instance outlives the element it drew into if the component
    // unmounts mid-edit; drop the refs so a remount builds a fresh one.
    useEffect(
        () => () => {
            mapRef.current = null;
            markerRef.current = null;
        },
        [],
    );

    const showMap = status === "ready" && hasPin;

    return (
        <div data-testid={testid || ADDRESS.field}>
            {/* One textarea in every state. When the API is up it is also the
                autocomplete input; when it is not, it is just a textarea, and
                nothing about typing an address changes. */}
            <Textarea
                ref={inputRef}
                id="full-address"
                data-testid={ADDRESS.input}
                value={address || ""}
                disabled={disabled}
                onChange={(e) => setPin({ address: e.target.value })}
                rows={2}
                maxLength={500}
                autoComplete="street-address"
                className="mt-2 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                placeholder={
                    status === "ready"
                        ? "Start typing and pick your address"
                        : "Flat, street, area, city, PIN"
                }
            />

            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                We use this for sending physical invites and delivery campaigns —
                product samples, event passes, gifting. Only the WeAre team sees it.
            </p>

            {status === "loading" && (
                <p
                    data-testid={ADDRESS.loading}
                    className="mt-2 flex items-center gap-2 text-xs text-muted-foreground"
                >
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading address suggestions…
                </p>
            )}

            {status === "failed" && (
                <p data-testid={ADDRESS.failed} className="mt-2 text-xs text-amber-300">
                    Address suggestions couldn't load. Type it out in full instead — that
                    works just as well.
                </p>
            )}

            {showMap && (
                <div className="mt-3">
                    <div
                        ref={mapNodeRef}
                        data-testid={ADDRESS.map}
                        aria-label="Drag the pin to the exact spot"
                        className="h-48 w-full overflow-hidden rounded-md border border-white/10 media-frame"
                    />
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs text-muted-foreground">
                            Drag the pin to your door — autocomplete usually stops at the
                            street.{" "}
                            <span data-testid={ADDRESS.coords} className="text-foreground/70">
                                {formatLatLng(lat, lng)}
                            </span>
                        </p>
                        <button
                            type="button"
                            data-testid={ADDRESS.clearPin}
                            onClick={() => setPin({ lat: null, lng: null, placeId: null })}
                            className="inline-flex min-h-[2.75rem] items-center gap-1 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-red-300 md:min-h-0"
                        >
                            <X className="h-3 w-3" />
                            Remove pin
                        </button>
                    </div>
                </div>
            )}

            {/* A saved pin, when the interactive map can't be drawn — no key,
                or the script failed. A static image needs neither, and a pin
                the creator can't see is one they can't tell is wrong. */}
            {status !== "ready" && hasPin && (
                <div className="mt-3" data-testid={ADDRESS.miniMap}>
                    {staticMapUrl({ lat, lng, height: 160 }) ? (
                        <img
                            src={staticMapUrl({ lat, lng, height: 160 })}
                            alt="Your saved location"
                            width={640}
                            height={160}
                            className="w-full rounded-md border border-white/10 media-frame"
                        />
                    ) : null}
                    <p className="mt-2 text-xs text-muted-foreground">
                        Pin saved at{" "}
                        <span className="text-foreground/70">{formatLatLng(lat, lng)}</span>.{" "}
                        <a
                            href={googleMapsLink({ lat, lng, placeId })}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={ADDRESS.openInMaps}
                            className="text-ember-500 transition-colors duration-200 hover:text-ember-400"
                        >
                            Check it on Google Maps
                        </a>
                    </p>
                </div>
            )}

            {status === "ready" && !hasPin && (address || "").trim() && (
                <p
                    data-testid={ADDRESS.noPin}
                    className="mt-2 flex items-start gap-2 text-xs text-muted-foreground"
                >
                    <MapPin className="mt-0.5 h-3 w-3 flex-none" />
                    No pin yet. Pick your address from the suggestions to drop one — a
                    courier can find a pin when they can't find a door number.
                </p>
            )}
        </div>
    );
}
