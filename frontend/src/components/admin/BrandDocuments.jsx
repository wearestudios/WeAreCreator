// The papers, on the screen where the decision is made.
//
// The endpoints for this existed for months with no caller: an admin verifying
// a brand could see that a GST certificate had been uploaded and could not
// read it without leaving the page, and the per-document review route — "this
// FSSAI licence is illegible, the rest are fine" — had no button anywhere at
// all. So verification was a judgement made from a filename.
//
// **Fetched as an authenticated blob, not linked.** The obvious thing is an
// `<iframe src={API_BASE + …}>`, and it half works: the cookie is `SameSite=
// None`, so it rides along in production and silently does not on a plain-http
// laptop, which is the worst kind of difference. Going through `api` means the
// same auth every other call uses, it honours `Cache-Control: no-store`
// because the object URL dies with the panel, and the bytes never sit at an
// address anybody can paste into a chat.
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
    Check,
    ChevronDown,
    Download,
    FileText,
    Loader2,
    X,
} from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BRAND_DOCS as IDS } from "@/constants/testIds";
import { formatDate } from "@/lib/time";
import { TEXT } from "./console/tokens";

const STATUS_TONE = {
    accepted: "text-emerald-300",
    rejected: "text-destructive",
    submitted: "text-muted-foreground",
};

/** Bytes, said the way somebody reads them. */
const size = (n) =>
    !n ? "" : n > 1_000_000 ? `${(n / 1_048_576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`;

/**
 * One document, expandable in place.
 *
 * Inline rather than in a dialog: a reviewer compares the registered address
 * on the certificate with the one on the profile two sections up, and a modal
 * covers the thing they are comparing it to.
 */
function DocumentRow({ brandId, doc, onReviewed }) {
    const [open, setOpen] = useState(false);
    const [blobUrl, setBlobUrl] = useState(null);
    const [loading, setLoading] = useState(false);
    const [failed, setFailed] = useState(null);
    const [rejecting, setRejecting] = useState(false);
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);
    // Held in a ref as well as state so the cleanup revokes the *current* one
    // rather than whatever the closure captured when the effect first ran.
    const urlRef = useRef(null);

    const load = useCallback(async () => {
        setLoading(true);
        setFailed(null);
        try {
            const { data } = await api.get(
                `/admin/brands/${brandId}/documents/${doc.id}`,
                { responseType: "blob" }
            );
            const url = URL.createObjectURL(data);
            urlRef.current = url;
            setBlobUrl(url);
        } catch (err) {
            // 410 is the honest one: the row is a tombstone and the file has
            // been purged under the retention policy. Saying "couldn't load"
            // would send somebody looking for a bug.
            setFailed(
                err?.response?.status === 410
                    ? "This file has been deleted under the retention policy. The record of it stays."
                    : "That couldn't be opened."
            );
        } finally {
            setLoading(false);
        }
    }, [brandId, doc.id]);

    useEffect(() => {
        if (open && !urlRef.current) load();
    }, [open, load]);

    // The object URL is the only copy of these bytes in the page, so it goes
    // when the row does.
    useEffect(
        () => () => {
            if (urlRef.current) URL.revokeObjectURL(urlRef.current);
            urlRef.current = null;
        },
        []
    );

    const review = async (status) => {
        setBusy(true);
        try {
            await api.post(`/admin/brands/${brandId}/documents/${doc.id}/review`, {
                status,
                // **The note belongs to the rejection.** Both actions shared
                // one box, so accepting a document while a half-typed "the
                // entity name doesn't match" was still in it recorded that
                // sentence against an acceptance — caught in a browser, and it
                // would have read as a reviewer contradicting themselves.
                reason: status === "rejected" ? note.trim() || null : null,
            });
            notifySuccess(status === "accepted" ? "Document accepted" : "Document rejected");
            setRejecting(false);
            setNote("");
            onReviewed?.();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be recorded." });
        } finally {
            setBusy(false);
        }
    };

    const isImage = (doc.mime || "").startsWith("image/");
    const isPdf = (doc.mime || "") === "application/pdf";

    return (
        <li data-testid={IDS.row(doc.id)} className="px-5 py-4">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:gap-6">
                <button
                    type="button"
                    onClick={() => setOpen((v) => !v)}
                    aria-expanded={open}
                    data-testid={IDS.toggle(doc.id)}
                    className="inline-flex min-w-0 flex-1 items-center gap-2.5 text-left text-sm transition-colors duration-150 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                >
                    <FileText className="h-4 w-4 flex-none text-ember-500" />
                    <span className="min-w-0">
                        {doc.doc_label}
                        <span className="block truncate text-sm text-muted-foreground">
                            {doc.original_name}
                            {doc.size ? ` · ${size(doc.size)}` : ""}
                        </span>
                    </span>
                    <ChevronDown
                        aria-hidden="true"
                        className={`h-4 w-4 flex-none text-muted-foreground transition-transform duration-150 ${
                            open ? "rotate-180" : ""
                        }`}
                    />
                </button>

                <span
                    data-testid={IDS.status(doc.id)}
                    className={`flex-none ${TEXT.meta} uppercase tracking-[0.18em] ${
                        STATUS_TONE[doc.status] || "text-muted-foreground"
                    }`}
                >
                    {doc.status}
                </span>
                <span className="w-32 flex-none text-sm text-muted-foreground">
                    {formatDate(doc.uploaded_at)}
                </span>
            </div>

            {/* The reviewer's own note from last time, so a second look starts
                from what the first one said. */}
            {doc.review_note && (
                <p className={`mt-2 ${TEXT.meta} text-muted-foreground`}>
                    “{doc.review_note}”
                </p>
            )}

            {open && (
                <div className="mt-3 space-y-3">
                    <div
                        data-testid={IDS.viewer(doc.id)}
                        className="overflow-hidden rounded-md border border-white/10 bg-background/60"
                    >
                        {loading && (
                            <p className="flex items-center gap-2 px-4 py-8 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Opening…
                            </p>
                        )}
                        {failed && (
                            <p className="px-4 py-8 text-sm text-muted-foreground">{failed}</p>
                        )}
                        {blobUrl && isImage && (
                            // The ratio is on the container, not the image: an
                            // A4 scan and a phone photo of a licence are very
                            // different shapes and neither should move the page.
                            <div className="max-h-[70vh] overflow-auto">
                                <img
                                    src={blobUrl}
                                    alt={doc.doc_label}
                                    className="w-full"
                                />
                            </div>
                        )}
                        {blobUrl && isPdf && (
                            <iframe
                                src={blobUrl}
                                title={doc.doc_label}
                                className="h-[70vh] w-full"
                            />
                        )}
                        {blobUrl && !isImage && !isPdf && (
                            <p className="px-4 py-8 text-sm text-muted-foreground">
                                This one can't be shown here. Download it to read it.
                            </p>
                        )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {blobUrl && (
                            <a
                                href={blobUrl}
                                download={doc.original_name || "document"}
                                data-testid={IDS.download(doc.id)}
                                className={`inline-flex items-center gap-1.5 rounded border border-white/15 px-3 py-2 ${TEXT.meta} uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-150 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500`}
                            >
                                <Download className="h-3.5 w-3.5" />
                                Download
                            </a>
                        )}
                        {/* **Per document, not per brand.** "Your FSSAI licence
                            is illegible" should not have to be written as a
                            whole-brand rejection that sends four good documents
                            back with it. */}
                        <Button
                            size="sm"
                            onClick={() => review("accepted")}
                            disabled={busy || doc.status === "accepted"}
                            data-testid={IDS.accept(doc.id)}
                            className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                        >
                            {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                            <Check className="mr-1.5 h-3.5 w-3.5" />
                            Accept
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setRejecting((v) => !v)}
                            data-testid={IDS.rejectOpen(doc.id)}
                            className="min-h-[2.75rem] border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10 sm:min-h-0"
                        >
                            <X className="mr-1.5 h-3.5 w-3.5" />
                            Reject
                        </Button>
                    </div>

                    {rejecting && (
                        <div className="space-y-2">
                            <Textarea
                                rows={2}
                                maxLength={500}
                                value={note}
                                onChange={(e) => setNote(e.target.value)}
                                placeholder="What's wrong with it. The brand is told this, so it can re-upload the right one."
                                data-testid={IDS.rejectNote(doc.id)}
                                className="rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                            />
                            <Button
                                size="sm"
                                onClick={() => review("rejected")}
                                // The route refuses a rejection with no reason;
                                // the button agrees with it rather than
                                // producing a 422.
                                disabled={busy || !note.trim()}
                                data-testid={IDS.rejectSubmit(doc.id)}
                                className="min-h-[2.75rem] bg-destructive text-white hover:bg-destructive/90 sm:min-h-0"
                            >
                                {busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                                Reject this document
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </li>
    );
}

export default function BrandDocuments({ brandId, documents, onChanged }) {
    if (!documents?.length) {
        return (
            <p
                data-testid={IDS.empty}
                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground"
            >
                Nothing uploaded. A brand needs at least one — GST certificate, business
                registration, FSSAI licence or shop &amp; establishment licence — before
                we'll look.
            </p>
        );
    }
    return (
        <ul
            data-testid={IDS.list}
            className="divide-y divide-white/10 rounded-md border border-white/10 bg-card"
        >
            {documents.map((d) => (
                <DocumentRow key={d.id} brandId={brandId} doc={d} onReviewed={onChanged} />
            ))}
        </ul>
    );
}
