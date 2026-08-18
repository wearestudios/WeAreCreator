// One picture, picked and replaced.
//
// The campaign cover and the brand logo are the same interaction — choose a
// file, check it here before a byte moves, POST it, show what is there now,
// remove it — so they are one component. Two copies is how one of them ends up
// with a size check and the other doesn't.
//
// Two modes, because a cover has to be pickable on a brief that does not exist
// yet:
//   - **immediate**  `endpoint` given: uploads on pick, deletes on remove.
//   - **deferred**   no `endpoint`: holds the File and previews it locally,
//                    handing it up through `onFile` for the caller to send once
//                    it has an id to send it to.
// The deferred preview is an object URL, revoked on replace and unmount — a
// blob left dangling is a copy of the file held in memory for the rest of the
// session.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ImageIcon, Loader2, Upload } from "lucide-react";

import { api, formatApiError, mediaUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

/** The ceiling and the formats, until the server has told us its own. */
export const FALLBACK_MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const FALLBACK_IMAGE_MIMES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
];

const megabytes = (bytes) => `${Math.round((bytes / (1024 * 1024)) * 10) / 10}MB`;

export default function ImageUploadField({
    label,
    hint,
    value,
    onChange,
    onFile,
    endpoint,
    responseKey,
    shape = "cover",
    maxBytes = FALLBACK_MAX_IMAGE_BYTES,
    acceptedMimes = FALLBACK_IMAGE_MIMES,
    disabled = false,
    disabledReason = "",
    testids = {},
}) {
    const inputRef = useRef(null);
    const objectUrlRef = useRef(null);
    const [localPreview, setLocalPreview] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    const releasePreview = useCallback(() => {
        if (objectUrlRef.current) {
            URL.revokeObjectURL(objectUrlRef.current);
            objectUrlRef.current = null;
        }
    }, []);

    useEffect(() => releasePreview, [releasePreview]);

    const accept = acceptedMimes.join(",");
    const shown = localPreview || (value ? mediaUrl(value) : null);

    const pick = async (e) => {
        const file = e.target.files?.[0];
        // Let the same file be chosen again after a refusal, which is what
        // somebody does after resizing it.
        e.target.value = "";
        if (!file) return;
        setError("");

        // Checked here so an oversized file fails instantly rather than after a
        // minute on mobile data — and against the server's own numbers, so the
        // two cannot disagree.
        if (acceptedMimes.length && !acceptedMimes.includes(file.type)) {
            setError("That format isn't accepted. Use a JPG, PNG, WebP or GIF.");
            return;
        }
        if (file.size > maxBytes) {
            setError(`That file is ${megabytes(file.size)}. The limit is ${megabytes(maxBytes)}.`);
            return;
        }

        if (!endpoint) {
            releasePreview();
            objectUrlRef.current = URL.createObjectURL(file);
            setLocalPreview(objectUrlRef.current);
            onFile?.(file);
            return;
        }

        const body = new FormData();
        body.append("file", file);
        setBusy(true);
        try {
            const { data } = await api.post(endpoint, body, {
                // Let the browser set the multipart boundary; the client's JSON
                // default would make this unparseable.
                headers: { "Content-Type": undefined },
            });
            releasePreview();
            setLocalPreview(null);
            onChange?.(responseKey ? data[responseKey] : data);
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setBusy(false);
        }
    };

    const remove = async () => {
        setError("");
        if (!endpoint) {
            releasePreview();
            setLocalPreview(null);
            onFile?.(null);
            return;
        }
        setBusy(true);
        try {
            await api.delete(endpoint);
            releasePreview();
            setLocalPreview(null);
            onChange?.(null);
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setBusy(false);
        }
    };

    const frame =
        shape === "square"
            ? "media-frame grid aspect-square h-20 w-20 flex-none place-items-center overflow-hidden rounded-md border border-white/10"
            : "media-frame relative w-full overflow-hidden rounded-lg border border-white/10 aspect-[16/9] sm:max-w-sm";

    return (
        <div className={shape === "square" ? "flex flex-wrap items-center gap-5" : ""}>
            <div className={frame} data-testid={testids.preview}>
                {shown ? (
                    <img
                        src={shown}
                        alt=""
                        className={
                            shape === "square"
                                ? "h-full w-full object-contain"
                                : "absolute inset-0 h-full w-full object-cover"
                        }
                    />
                ) : (
                    <ImageIcon
                        className={
                            "text-muted-foreground " +
                            (shape === "square"
                                ? "h-6 w-6"
                                : "absolute left-1/2 top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2")
                        }
                        aria-hidden="true"
                    />
                )}
            </div>

            <div className={shape === "square" ? "min-w-0" : "mt-3"}>
                {label && (
                    <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                        {label}
                    </Label>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                    <input
                        ref={inputRef}
                        type="file"
                        accept={accept}
                        onChange={pick}
                        disabled={disabled || busy}
                        data-testid={testids.input}
                        className="hidden"
                    />
                    <Button
                        type="button"
                        variant="outline"
                        disabled={disabled || busy}
                        data-testid={testids.choose}
                        onClick={() => inputRef.current?.click()}
                        className="h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                    >
                        {busy ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Uploading…
                            </>
                        ) : (
                            <>
                                <Upload className="mr-2 h-4 w-4" />
                                {shown ? "Replace" : "Upload"}
                            </>
                        )}
                    </Button>
                    {shown && (
                        <button
                            type="button"
                            disabled={disabled || busy}
                            onClick={remove}
                            data-testid={testids.remove}
                            className="min-h-[2.75rem] px-2 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-red-300 disabled:opacity-40"
                        >
                            Remove
                        </button>
                    )}
                </div>
                {/* A disabled control with no explanation is a support ticket. */}
                {disabled && disabledReason && (
                    <p className="mt-2 text-xs text-muted-foreground">{disabledReason}</p>
                )}
                {hint && !error && (
                    <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
                )}
                {error && (
                    <p data-testid={testids.error} className="mt-2 text-xs text-red-300">
                        {error}
                    </p>
                )}
            </div>
        </div>
    );
}
