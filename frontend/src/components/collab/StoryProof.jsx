// A screenshot of a story that has since expired.
//
// **An Instagram story is gone in twenty-four hours.** A creator posts one,
// submits the link, and by the time anybody reviews it the URL answers with
// nothing — so a story deliverable was the one thing on this platform that
// could be asked for, delivered, and then not verified. The brand's options
// were to take somebody's word for it or to refuse work that had actually
// happened.
//
// Two halves of one file, because they are two views of the same list: the
// creator attaches and removes, whoever reviews the delivery looks. Everything
// either half decides — whether proof is required, whether a link is still
// needed, how many are attached — arrives in the server's `proof` block, so
// neither view works anything out for itself.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Image as ImageIcon, Loader2, Trash2, X } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError } from "@/lib/feedback";
import { PROOF as IDS } from "@/constants/testIds";
import { formatDate } from "@/lib/time";

/** Bytes, said the way somebody reads them. */
const size = (n) =>
    !n ? "" : n > 1_000_000 ? `${(n / 1_048_576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`;

/**
 * One screenshot, fetched as an authenticated blob.
 *
 * Never an `<img>` pointed straight at the backend — the same reasoning the
 * brand-document panel states: the session cookie is `SameSite=None`, so a
 * bare URL rides along in production and silently does not on a plain-http
 * laptop, and these bytes are a picture of somebody's phone rather than
 * something to leave at an address anybody can paste into a chat.
 */
function ProofThumb({ path, proof, onRemove, removing }) {
    const [blobUrl, setBlobUrl] = useState(null);
    const [failed, setFailed] = useState(false);
    // Held in a ref as well as state so the cleanup revokes the *current* one
    // rather than whatever the closure captured when the effect first ran.
    const urlRef = useRef(null);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(path, { responseType: "blob" });
            const url = URL.createObjectURL(data);
            urlRef.current = url;
            setBlobUrl(url);
        } catch {
            setFailed(true);
        }
    }, [path]);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(
        () => () => {
            if (urlRef.current) URL.revokeObjectURL(urlRef.current);
            urlRef.current = null;
        },
        []
    );

    return (
        <li
            data-testid={IDS.item(proof.id)}
            className="relative overflow-hidden rounded-md border border-white/10 bg-background/60"
        >
            {/* The ratio is on the container, never on the image, so a
                screenshot that never arrives still occupies the space it
                claimed — the same rule `CampaignCover` holds. A story is 9:16. */}
            <div className="media-frame aspect-[9/16] w-full">
                {blobUrl ? (
                    <img
                        src={blobUrl}
                        alt={proof.original_name || "Story screenshot"}
                        data-testid={IDS.view(proof.id)}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                        {failed ? (
                            <X aria-hidden="true" className="h-4 w-4" />
                        ) : (
                            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                        )}
                    </div>
                )}
            </div>
            <p className="truncate px-2 py-1.5 text-xs text-muted-foreground">
                {proof.note || formatDate(proof.uploaded_at)}
                {proof.size ? ` · ${size(proof.size)}` : ""}
            </p>
            {onRemove && (
                <button
                    type="button"
                    aria-label="Remove this screenshot"
                    data-testid={IDS.remove(proof.id)}
                    onClick={() => onRemove(proof.id)}
                    disabled={removing}
                    className="absolute right-1.5 top-1.5 rounded-full bg-background/80 p-2 text-muted-foreground transition-colors duration-150 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 disabled:opacity-40"
                >
                    <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                </button>
            )}
        </li>
    );
}

/**
 * The creator's half: attach, review, take back off.
 *
 * `proof` is the server's block. `onChanged` receives the new block after
 * every upload and removal, so the submit button beside this can enable and
 * disable off the same numbers the route will check.
 */
export function StoryProofUpload({ collabId, proof, onChanged }) {
    const [busy, setBusy] = useState(false);
    const [removing, setRemoving] = useState(false);
    const [err, setErr] = useState("");
    const input = useRef(null);

    // Nothing to say on a brief that counted no stories. Absent rather than a
    // disabled box: an uploader on a reel-only brief is a question nobody
    // needs to answer.
    if (!proof?.required) return null;

    const items = proof.items || [];
    const full = items.length >= (proof.max || 12);

    const pick = async (event) => {
        const file = event.target.files?.[0];
        // Cleared immediately so picking the same file twice in a row still
        // fires a change event.
        if (input.current) input.current.value = "";
        if (!file) return;
        setErr("");
        setBusy(true);
        try {
            const body = new FormData();
            body.append("file", file);
            const { data } = await api.post(
                `/creator/collaborations/${collabId}/content-proof`,
                body,
                { headers: { "Content-Type": "multipart/form-data" } }
            );
            onChanged?.(data);
        } catch (e) {
            setErr(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    const remove = async (proofId) => {
        setRemoving(true);
        try {
            const { data } = await api.delete(
                `/creator/collaborations/${collabId}/content-proof/${proofId}`
            );
            onChanged?.(data);
        } catch (e) {
            notifyError(e, { fallback: "That couldn't be removed." });
        } finally {
            setRemoving(false);
        }
    };

    const short = Math.max(0, (proof.story_quantity || 0) - items.length);

    return (
        <div data-testid={IDS.panel} className="space-y-3">
            <div>
                <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    <Camera aria-hidden="true" className="h-3 w-3" />
                    Story screenshots
                </p>
                <p
                    data-testid={IDS.required}
                    className="mt-1 text-sm leading-relaxed text-muted-foreground"
                >
                    A story link is dead within a day, so a screenshot is what
                    gets reviewed.{" "}
                    {short > 0
                        ? `${short} still to add.`
                        : "That's all of them — thank you."}
                </p>
            </div>

            {items.length > 0 && (
                <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {items.map((p) => (
                        <ProofThumb
                            key={p.id}
                            proof={p}
                            removing={removing}
                            onRemove={remove}
                            path={`/creator/collaborations/${collabId}/content-proof/${p.id}/file`}
                        />
                    ))}
                </ul>
            )}

            <input
                ref={input}
                type="file"
                accept="image/*"
                onChange={pick}
                className="sr-only"
                id={`proof-${collabId}`}
            />
            <label
                htmlFor={`proof-${collabId}`}
                data-testid={IDS.pick}
                aria-disabled={busy || full}
                className={`inline-flex min-h-[2.75rem] cursor-pointer items-center gap-1.5 rounded-full border border-white/10 px-4 text-xs uppercase tracking-[0.15em] transition-colors duration-150 ${
                    busy || full
                        ? "pointer-events-none opacity-40"
                        : "text-muted-foreground hover:border-ember-500/40 hover:text-ember-500"
                }`}
            >
                {busy ? (
                    <Loader2
                        aria-hidden="true"
                        data-testid={IDS.busy}
                        className="h-3.5 w-3.5 animate-spin"
                    />
                ) : (
                    <ImageIcon aria-hidden="true" className="h-3.5 w-3.5" />
                )}
                {full ? "That's the maximum" : "Add a screenshot"}
            </label>

            {err && (
                <p data-testid={IDS.error} className="text-sm text-destructive">
                    {err}
                </p>
            )}
        </div>
    );
}

/**
 * The reviewer's half: read-only, and absent when there is nothing attached.
 *
 * Rendered wherever a delivery is reviewed. It takes the collaboration id and
 * the block; it never asks what role is looking, because the route behind the
 * path answers that with a 404.
 */
export function StoryProofReview({ collabId, proof }) {
    const items = proof?.items || [];
    if (!proof?.required && items.length === 0) return null;
    return (
        <div data-testid={IDS.panel} className="space-y-2">
            <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                <Camera aria-hidden="true" className="h-3 w-3" />
                Story screenshots
            </p>
            {items.length === 0 ? (
                <p data-testid={IDS.empty} className="text-sm text-muted-foreground">
                    None attached yet.
                </p>
            ) : (
                <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {items.map((p) => (
                        <ProofThumb
                            key={p.id}
                            proof={p}
                            path={`/collaborations/${collabId}/content-proof/${p.id}/file`}
                        />
                    ))}
                </ul>
            )}
        </div>
    );
}

export default StoryProofUpload;
