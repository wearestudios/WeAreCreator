// The evidence behind a delivery WeAre marked received for a creator.
//
// Mark-received is the one override that costs evidence rather than only a
// reason — a courier link showing delivered, or a photo of the parcel — so the
// page that offers it is also the page that shows what it was taken on. The
// link is a courier's public page and opens as one. The photo is a picture of
// somebody's doorstep: **fetched as an authenticated blob, never linked**, the
// arrangement `BrandDocuments` settled — the session cookie is `SameSite=None`
// and a bare `<img src>` at the API rides along in production and silently
// does not on a plain-http laptop. The object URL is held in a ref as well as
// state so the cleanup revokes the current one.
//
// Renders nothing when the delivery was confirmed by the creator themselves.
import React, { useEffect, useRef, useState } from "react";
import { ExternalLink, ImageIcon, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, formatApiError } from "@/lib/api";
import { ADMIN_ACT_ON_BEHALF as IDS } from "@/constants/testIds";

export default function ReceivedEvidence({ collabId, record, className = "" }) {
    const [src, setSrc] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const urlRef = useRef(null);

    useEffect(
        () => () => {
            if (urlRef.current) URL.revokeObjectURL(urlRef.current);
        },
        [],
    );

    const evidence = record?.evidence;
    if (!evidence) return null;

    const open = async () => {
        setLoading(true);
        setError("");
        try {
            const { data } = await api.get(
                `/admin/collaborations/${collabId}/on-behalf/received-evidence`,
                { responseType: "blob" },
            );
            if (urlRef.current) URL.revokeObjectURL(urlRef.current);
            urlRef.current = URL.createObjectURL(data);
            setSrc(urlRef.current);
        } catch (err) {
            setError(formatApiError(err) || "That photo couldn't be opened.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            data-testid={IDS.evidence}
            className={`rounded-md border border-border bg-muted/40 p-3 text-meta ${className}`}
        >
            <p className="font-medium text-foreground">The evidence it was marked received on</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
                {evidence.tracking_url && (
                    <a
                        href={evidence.tracking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 font-medium text-foreground underline underline-offset-4"
                    >
                        Courier tracking
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                )}
                {evidence.has_image && !src && (
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={open}
                        disabled={loading}
                        className="rounded-full"
                    >
                        {loading ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                            <ImageIcon className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                        )}
                        View the proof photo
                    </Button>
                )}
            </div>
            {error && <p className="mt-2 text-destructive">{error}</p>}
            {src && (
                <div className="mt-3 aspect-[4/3] w-full max-w-sm overflow-hidden rounded-md border border-border bg-muted">
                    <img
                        src={src}
                        alt="The parcel, as attached when the delivery was marked received"
                        data-testid={IDS.evidenceImage}
                        className="h-full w-full object-contain"
                    />
                </div>
            )}
        </div>
    );
}
