// Proof that the business exists, and the person asking represents it.
//
// Uploads here are the slowest thing a brand does in the product: a phone photo
// of a GST certificate is a few megabytes going up an Indian mobile connection.
// A button that greys out and says nothing for forty seconds gets pressed
// again, and the second press is a second document in the reviewer's queue —
// so every file gets its own visible progress, and the input is closed while
// anything is in flight.
//
// Two rules the shape of this follows:
//
//   - **A file that cannot succeed never leaves the browser.** Type and size
//     are checked against the server's own limits (which arrive in the
//     verification payload — see `max_document_bytes`) before the upload
//     starts, so a 9MB scan fails in a tenth of a second instead of after the
//     whole upload is refused. The server still checks; this is courtesy, not
//     security, and the sniffing on the other end is the real gate.
//   - **A failure is attached to the file that caused it.** One error line at
//     the bottom of a form cannot say which of three files was the wrong
//     format, which is the only thing the person needs to know.
import React, { useCallback, useMemo, useRef, useState } from "react";
import {
    AlertCircle,
    CheckCircle2,
    FileText,
    Loader2,
    Paperclip,
    RotateCw,
    Trash2,
    Upload,
    X,
} from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/data/DenseView";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { BRAND_VERIFICATION as IDS } from "@/constants/testIds";

const MB = 1024 * 1024;

/** Bytes as something a person reads: "1.4 MB", "812 KB". */
export function formatBytes(bytes) {
    if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "—";
    if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`;
    if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${bytes} B`;
}

/**
 * Why this file can't be sent, in the words of the thing that's wrong with it.
 *
 * Returns null when it can. Deliberately names the actual limit and the actual
 * type: "That file is 8.2 MB — the limit is 5 MB" tells somebody to find a
 * smaller scan, where "invalid file" tells them to give up.
 */
export function checkFile(file, { maxBytes, acceptedMimes }) {
    if (!file) return "No file chosen.";
    if (file.size === 0) return "That file is empty.";
    if (maxBytes && file.size > maxBytes) {
        return `That file is ${formatBytes(file.size)} — the limit is ${formatBytes(
            maxBytes,
        )}. A photo of the document usually comes in well under it.`;
    }
    // An empty browser-reported type is not a refusal: some Android pickers
    // send "" for a perfectly good PDF, and the server sniffs the bytes anyway.
    if (file.type && acceptedMimes?.length && !acceptedMimes.includes(file.type)) {
        return `We can't read ${file.type || "that format"}. Send a PDF, JPEG, PNG, WebP or GIF.`;
    }
    return null;
}

let _key = 0;
const nextKey = () => `f${++_key}`;

function ProgressBar({ value, testid }) {
    return (
        <div
            data-testid={testid}
            role="progressbar"
            aria-valuenow={value}
            aria-valuemin={0}
            aria-valuemax={100}
            className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/10"
        >
            <div
                className="h-full rounded-full bg-ember-500 transition-[width] duration-200 ease-out"
                style={{ width: `${value}%` }}
            />
        </div>
    );
}

/** A file on its way up, or one that didn't make it. */
function QueuedFile({ item, onRetry, onDismiss }) {
    const failed = item.status === "error";
    return (
        <li
            data-testid={IDS.queueItem(item.key)}
            className={
                "flex items-start gap-3 rounded-md border p-4 " +
                (failed
                    ? "border-destructive/40 bg-destructive/5"
                    : "border-white/10 bg-background/60")
            }
        >
            <div className="mt-0.5 flex-none">
                {failed ? (
                    <AlertCircle className="h-4 w-4 text-destructive" />
                ) : (
                    <Loader2 className="h-4 w-4 animate-spin text-ember-500" />
                )}
            </div>
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground" title={item.name}>
                    {item.name}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    {item.docLabel} · {formatBytes(item.size)}
                </p>
                {failed ? (
                    <p
                        data-testid={IDS.queueError(item.key)}
                        className="mt-2 text-xs leading-relaxed text-destructive"
                    >
                        {item.error}
                    </p>
                ) : (
                    <>
                        <ProgressBar
                            value={item.progress}
                            testid={IDS.queueProgress(item.key)}
                        />
                        <p
                            data-testid={IDS.queuePercent(item.key)}
                            className="mt-1.5 text-xs text-muted-foreground"
                        >
                            {item.progress < 100
                                ? `Uploading — ${item.progress}%`
                                : "Finishing up…"}
                        </p>
                    </>
                )}
            </div>
            {failed && (
                <div className="flex flex-none gap-1">
                    {item.retryable && (
                        <button
                            type="button"
                            onClick={() => onRetry(item)}
                            data-testid={IDS.queueRetry(item.key)}
                            aria-label={`Try ${item.name} again`}
                            className="rounded-full p-2 text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                        >
                            <RotateCw className="h-3.5 w-3.5" />
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={() => onDismiss(item.key)}
                        data-testid={IDS.queueDismiss(item.key)}
                        aria-label={`Dismiss ${item.name}`}
                        className="rounded-full p-2 text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                        <X className="h-3.5 w-3.5" />
                    </button>
                </div>
            )}
        </li>
    );
}

/** One document already on file, with a two-step remove. */
function StoredDocument({ doc, onRemoved, disabled }) {
    const [confirming, setConfirming] = useState(false);
    const [removing, setRemoving] = useState(false);
    const [error, setError] = useState("");

    const remove = async () => {
        setRemoving(true);
        setError("");
        try {
            await api.delete(`/brand/verification/documents/${doc.id}`);
            notifySuccess("Document removed");
            onRemoved(doc.id);
        } catch (e) {
            setError(formatApiError(e));
            setRemoving(false);
            setConfirming(false);
        }
    };

    return (
        <li
            data-testid={IDS.document(doc.id)}
            className="flex items-start gap-3 rounded-md border border-white/10 bg-background/60 p-4"
        >
            <FileText className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground" title={doc.original_name}>
                    {doc.original_name}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    <span data-testid={IDS.documentType(doc.id)}>{doc.doc_label}</span>
                    {" · "}
                    {formatBytes(doc.size)}
                </p>
                {doc.review_note && (
                    <p className="mt-2 text-xs leading-relaxed text-amber-300">
                        {doc.review_note}
                    </p>
                )}
                {error && (
                    <p
                        data-testid={IDS.documentError(doc.id)}
                        className="mt-2 text-xs text-destructive"
                    >
                        {error}
                    </p>
                )}
            </div>

            {/* Deleting is cheap to undo — re-upload — but it is still the
              * only copy we hold, so it asks. Inline rather than a dialog:
              * a modal for one row of a list is heavier than the action. */}
            {!disabled &&
                (confirming ? (
                    <div className="flex flex-none items-center gap-2">
                        <button
                            type="button"
                            onClick={remove}
                            disabled={removing}
                            data-testid={IDS.documentConfirmRemove(doc.id)}
                            className="rounded-full px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-destructive transition-colors duration-200 hover:bg-destructive/10 disabled:opacity-60"
                        >
                            {removing ? "Removing…" : "Remove"}
                        </button>
                        <button
                            type="button"
                            onClick={() => setConfirming(false)}
                            disabled={removing}
                            data-testid={IDS.documentCancelRemove(doc.id)}
                            className="rounded-full px-3 py-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-foreground"
                        >
                            Keep
                        </button>
                    </div>
                ) : (
                    <button
                        type="button"
                        onClick={() => setConfirming(true)}
                        data-testid={IDS.documentRemove(doc.id)}
                        aria-label={`Remove ${doc.original_name}`}
                        className="flex-none rounded-full p-2 text-muted-foreground transition-colors duration-200 hover:text-destructive"
                    >
                        <Trash2 className="h-4 w-4" />
                    </button>
                ))}
        </li>
    );
}

export function VerificationDocumentsSkeleton() {
    return (
        <div aria-hidden="true" className="space-y-4">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-11 w-full rounded-md" />
            <div className="space-y-3">
                {Array.from({ length: 2 }).map((_, i) => (
                    <div
                        key={i}
                        className="flex items-start gap-3 rounded-md border border-white/10 bg-background/60 p-4"
                    >
                        <Skeleton className="mt-0.5 h-4 w-4 flex-none rounded" />
                        <div className="min-w-0 flex-1">
                            <Skeleton className="h-4 w-1/2" />
                            <Skeleton className="mt-2 h-3 w-1/3" />
                        </div>
                        <Skeleton className="h-8 w-8 flex-none rounded-full" />
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function VerificationDocuments({
    verification,
    onChanged,
    readOnly = false,
}) {
    // Memoised because the `|| []` default is a fresh array each render, which
    // would otherwise re-run every hook downstream of it on every keystroke.
    const accepted = useMemo(
        () => verification?.accepted_document_types || [],
        [verification],
    );
    const documents = verification?.documents || [];
    const maxBytes = verification?.max_document_bytes || 5 * MB;
    const acceptedMimes = verification?.accepted_mime_types || [];
    const maxDocuments = verification?.max_documents || 12;

    const [docType, setDocType] = useState(accepted[0]?.value || "");
    const [queue, setQueue] = useState([]);
    const inputRef = useRef(null);
    // A ref as well as state: the upload loop reads it between awaits, where a
    // captured state value would be the one from before the first file.
    const uploadingRef = useRef(false);
    const [uploading, setUploading] = useState(false);

    const docLabel = useMemo(
        () => accepted.find((a) => a.value === docType)?.label || "Document",
        [accepted, docType],
    );

    const full = documents.length >= maxDocuments;
    const remaining = Math.max(0, maxDocuments - documents.length);

    const setItem = useCallback((key, patch) => {
        setQueue((q) => q.map((i) => (i.key === key ? { ...i, ...patch } : i)));
    }, []);

    const uploadOne = useCallback(
        async (item) => {
            setItem(item.key, { status: "uploading", progress: 0, error: "" });
            const body = new FormData();
            body.append("doc_type", item.docType);
            body.append("file", item.file, item.name);
            try {
                await api.post("/brand/verification/documents", body, {
                    headers: { "Content-Type": "multipart/form-data" },
                    onUploadProgress: (e) => {
                        // `total` is absent on some proxies. Showing an
                        // indeterminate bar is honest; showing 0% forever is not.
                        if (!e.total) return;
                        setItem(item.key, {
                            progress: Math.min(
                                99,
                                Math.round((e.loaded / e.total) * 100),
                            ),
                        });
                    },
                });
                setItem(item.key, { progress: 100 });
                // Off the queue only once the list that replaces it is fresh,
                // so the row never blinks out of existence and back in.
                await onChanged();
                setQueue((q) => q.filter((i) => i.key !== item.key));
            } catch (e) {
                setItem(item.key, {
                    status: "error",
                    // A 413/422 is about this file and retrying changes
                    // nothing; anything else might be the network.
                    retryable: ![413, 422].includes(e?.response?.status),
                    error: formatApiError(e),
                });
            }
        },
        [onChanged, setItem],
    );

    /** Drain the queue one file at a time. Parallel uploads on a phone
     *  connection make every bar crawl and none of them finish. */
    const drain = useCallback(
        async (items) => {
            if (uploadingRef.current) return;
            uploadingRef.current = true;
            setUploading(true);
            try {
                for (const item of items) await uploadOne(item);
            } finally {
                uploadingRef.current = false;
                setUploading(false);
            }
        },
        [uploadOne],
    );

    const onPick = (e) => {
        const files = Array.from(e.target.files || []);
        // Let the same file be chosen twice in a row — without this, picking a
        // file, having it fail, and picking it again fires no change event.
        e.target.value = "";
        if (!files.length) return;

        const room = remaining - queue.filter((i) => i.status !== "error").length;
        const accepted_ = files.slice(0, Math.max(0, room));
        const rejected = files.slice(Math.max(0, room));

        const items = accepted_.map((file) => {
            const problem = checkFile(file, { maxBytes, acceptedMimes });
            return {
                key: nextKey(),
                file,
                name: file.name,
                size: file.size,
                docType,
                docLabel,
                progress: 0,
                // A file that fails the local check is queued as already-failed
                // rather than dropped: it has to be *visible* that it was not
                // sent, or somebody submits believing four documents went up.
                status: problem ? "error" : "queued",
                retryable: false,
                error: problem || "",
            };
        });

        const overflow = rejected.map((file) => ({
            key: nextKey(),
            file,
            name: file.name,
            size: file.size,
            docType,
            docLabel,
            progress: 0,
            status: "error",
            retryable: false,
            error: `That's more than ${maxDocuments} documents. Remove one before adding another.`,
        }));

        setQueue((q) => [...q, ...items, ...overflow]);
        drain(items.filter((i) => i.status === "queued"));
    };

    const retry = (item) => {
        const problem = checkFile(item.file, { maxBytes, acceptedMimes });
        if (problem) {
            setItem(item.key, { error: problem, retryable: false });
            return;
        }
        drain([item]);
    };

    const dismiss = (key) => setQueue((q) => q.filter((i) => i.key !== key));

    const inFlight = queue.filter((i) => i.status !== "error");

    return (
        <section data-testid={IDS.documentsSection} className="space-y-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Proof of business
                </p>
                {/* **A count, not a target.** "1 of 12 uploaded" reads as
                  * eleven still to go, on a panel whose own copy says any one
                  * of them is enough — the 12 is the point at which we stop
                  * accepting more, which is only worth saying when somebody is
                  * near it. */}
                <span
                    data-testid={IDS.documentCount}
                    className="text-xs text-muted-foreground"
                >
                    {documents.length === 0
                        ? "None uploaded yet"
                        : documents.length === 1
                        ? "1 document uploaded"
                        : `${documents.length} documents uploaded`}
                    {documents.length >= maxDocuments - 2 && documents.length > 0
                        ? ` · ${maxDocuments} is the limit`
                        : ""}
                </span>
            </div>

            <p className="max-w-xl text-xs leading-relaxed text-muted-foreground">
                Any one of these is enough — a GST certificate, business
                registration, FSSAI licence or shop &amp; establishment licence.
                Only the WeAre review team ever sees them. PDF or a photo, under{" "}
                {formatBytes(maxBytes)}.
            </p>

            {!readOnly && (
                <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                    <div>
                        <Label className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            What is this document?
                        </Label>
                        <Select value={docType} onValueChange={setDocType}>
                            <SelectTrigger
                                data-testid={IDS.docTypeTrigger}
                                disabled={uploading || full}
                                className="mt-2 h-11 border-white/10 bg-card/60"
                            >
                                <SelectValue placeholder="Pick a document type" />
                            </SelectTrigger>
                            <SelectContent>
                                {accepted.map((a) => (
                                    <SelectItem
                                        key={a.value}
                                        value={a.value}
                                        data-testid={IDS.docTypeOption(a.value)}
                                    >
                                        {a.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div>
                        <input
                            ref={inputRef}
                            type="file"
                            multiple
                            className="sr-only"
                            data-testid={IDS.fileInput}
                            accept={
                                acceptedMimes.length
                                    ? acceptedMimes.join(",")
                                    : undefined
                            }
                            onChange={onPick}
                            disabled={uploading || full || !docType}
                        />
                        <Button
                            type="button"
                            variant="outline"
                            data-testid={IDS.chooseBtn}
                            disabled={uploading || full || !docType}
                            onClick={() => inputRef.current?.click()}
                            className="h-11 w-full rounded-full border-white/15 bg-transparent hover:bg-white/5 sm:w-auto"
                        >
                            {uploading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Uploading {inFlight.length}…
                                </>
                            ) : (
                                <>
                                    <Upload className="mr-2 h-4 w-4" />
                                    Choose file
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            )}

            {full && !readOnly && (
                <p
                    data-testid={IDS.documentsFull}
                    className="text-xs text-amber-300"
                >
                    That's the maximum. Remove one before adding another.
                </p>
            )}

            {queue.length > 0 && (
                <ul data-testid={IDS.queue} className="space-y-3">
                    {queue.map((item) => (
                        <QueuedFile
                            key={item.key}
                            item={item}
                            onRetry={retry}
                            onDismiss={dismiss}
                        />
                    ))}
                </ul>
            )}

            {documents.length === 0 ? (
                <EmptyState
                    Icon={Paperclip}
                    title="No documents yet"
                    testid={IDS.documentsEmpty}
                >
                    We need at least one before we can check the business out.
                    Upload the easiest one to hand — a photo of a licence is
                    fine.
                </EmptyState>
            ) : (
                <ul data-testid={IDS.documentList} className="space-y-3">
                    {documents.map((doc) => (
                        <StoredDocument
                            key={doc.id}
                            doc={doc}
                            disabled={readOnly || uploading}
                            onRemoved={onChanged}
                        />
                    ))}
                </ul>
            )}

            {readOnly && documents.length > 0 && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Your documents are on file. Get in touch if one needs
                    changing.
                </p>
            )}
        </section>
    );
}
