// The code on the manager's screen that creators scan.
//
// A manager checking twenty people in one at a time is twenty taps on the
// worst network in the product. The creator has a phone in their hand already.
//
// **It refreshes on a timer, and that is the security property.** The code
// lives ninety seconds; this asks for a new one every sixty. A photograph of
// the screen taken across the room is stale before it can be passed around,
// and a screenshot posted anywhere is worthless. Nothing here is a secret
// worth protecting for longer — the code names a slot, never a creator, and
// the server still checks that whoever scanned it has a booking on that slot.
//
// The manual button beside this stays exactly as it was. It is what works when
// the camera doesn't, and it is not a lesser path.
import React, { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Loader2, RefreshCw } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CHECKIN as IDS } from "@/constants/testIds";

// Comfortably inside the server's 90-second life, so a creator who starts
// scanning as it turns over still lands on a live one.
const REFRESH_MS = 60_000;

export default function CheckInQr({ slotId }) {
    const [code, setCode] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        if (!slotId) return;
        setBusy(true);
        try {
            const { data } = await api.get(`/manager/slots/${slotId}/check-in-code`);
            setCode(data);
            setError("");
        } catch (e) {
            setError(formatApiError(e));
        } finally {
            setBusy(false);
        }
    }, [slotId]);

    useEffect(() => {
        load();
        const timer = setInterval(load, REFRESH_MS);
        return () => clearInterval(timer);
    }, [load]);

    if (!slotId) return null;

    return (
        <div
            data-testid={IDS.panel}
            className="rounded-md border border-white/10 bg-card p-6 text-center grain-surface"
        >
            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                Scan to check in
            </p>

            {error ? (
                <p className="mt-4 text-sm text-destructive">{error}</p>
            ) : !code ? (
                <div className="mt-5 flex h-[220px] items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <>
                    {/* White ground and dark modules: a QR inverted on a dark
                        card is one many phone cameras will not read at all,
                        and this is being held up in a badly lit venue. */}
                    <div
                        data-testid={IDS.qr}
                        className="mx-auto mt-5 w-fit rounded-md bg-white p-3"
                    >
                        <QRCodeSVG value={code.url} size={196} level="M" />
                    </div>
                    <p
                        data-testid={IDS.expiry}
                        className="mt-4 text-xs leading-relaxed text-muted-foreground"
                    >
                        Refreshes every minute. Creators can also open{" "}
                        <span data-testid={IDS.link} className="text-foreground/80">
                            {code.url.replace(/^https?:\/\//, "").split("?")[0]}
                        </span>{" "}
                        from the link on their booking.
                    </p>
                </>
            )}

            <Button
                type="button"
                variant="outline"
                data-testid={IDS.refresh}
                onClick={load}
                disabled={busy}
                className="mt-5 h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
            >
                {busy ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                )}
                New code
            </Button>
        </div>
    );
}
