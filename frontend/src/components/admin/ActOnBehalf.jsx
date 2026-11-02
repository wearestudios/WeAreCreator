// "Act on behalf of" — the console's one door for doing somebody else's step.
//
// Every act here is an override: a step the ordinary Advance refuses because
// it belongs to the creator or to the brand, taken by an admin who has been
// asked to, on the record. The server decides which acts are offered on this
// row right now (`on_behalf_actions`) — admin only, never under a dispute, the
// creator's by the campaign's own ladder, the brand's only on a brand-run
// brief — so the menu never lists one the route would refuse, and it never
// asks what role is looking.
//
// Split into **Creator** and **Brand**, because "whose step is this" is the
// first thing an admin has to be sure of before taking one: the reason is read
// by that party, and getting the side wrong means explaining yourself to the
// wrong person.
import React, { useEffect, useState } from "react";
import { ChevronDown, Loader2, UserCog } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ADMIN_ACT_ON_BEHALF as IDS } from "@/constants/testIds";

const MIN_REASON = 3;
const SIDES = [
    { key: "creator", label: "Creator" },
    { key: "brand", label: "Brand" },
];

/** The menu. Renders nothing when there is nothing to offer. */
export function ActOnBehalfMenu({ actions, onPick, testidFor = {} }) {
    const list = actions || [];
    if (list.length === 0) return null;
    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="outline"
                    data-testid={IDS.trigger}
                    className="rounded-full border-border bg-transparent hover:bg-muted"
                >
                    <UserCog className="mr-1.5 h-4 w-4" aria-hidden="true" />
                    Act on behalf of
                    <ChevronDown className="ml-1 h-4 w-4" aria-hidden="true" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" data-testid={IDS.menu} className="min-w-[15rem]">
                {SIDES.map((side, i) => {
                    const mine = list.filter((a) => a.side === side.key);
                    if (mine.length === 0) return null;
                    const earlier = SIDES.slice(0, i).some((s) => list.some((a) => a.side === s.key));
                    return (
                        <React.Fragment key={side.key}>
                            {earlier && <DropdownMenuSeparator />}
                            <DropdownMenuLabel
                                data-testid={IDS.group(side.key)}
                                className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground"
                            >
                                {side.label}
                            </DropdownMenuLabel>
                            {mine.map((a) => (
                                <DropdownMenuItem
                                    key={a.key}
                                    data-testid={testidFor[a.key] || IDS.item(a.key)}
                                    onSelect={() => onPick(a)}
                                >
                                    {a.label}
                                </DropdownMenuItem>
                            ))}
                        </React.Fragment>
                    );
                })}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}

// What each act says about itself in the dialog. The reason label names who
// reads it, because that is what decides how it should be written.
const COPY = {
    mark_received: {
        title: (name) => `Mark ${name}'s delivery received`,
        description:
            "Moves it to received and starts their content clock. Only with evidence: a courier tracking link showing it was delivered, or a photo of the parcel. The creator reads your reason and is told to say now if it never reached them.",
        reader: "the creator",
        placeholder: "e.g. The courier shows it delivered on the 12th and you confirmed on the phone",
        confirm: "Mark it received",
    },
    accept: {
        title: (name) => `Accept ${name} for the brand`,
        description:
            "Takes the brand's own step: the fee, the budget cap, the capacity check and the terms are exactly what the brand's Accept would record. The brand is told who did it and why.",
        reader: "the brand",
        placeholder: "e.g. The brand approved them on our call this morning",
        confirm: "Accept for the brand",
    },
    approve_draft: {
        title: () => "Approve the draft for the brand",
        description:
            "The brand's approval, on the brand's terms — including confirming the disclosure label is on it. The brand is told who did it and why.",
        reader: "the brand",
        placeholder: "e.g. The brand signed this off on WhatsApp",
        confirm: "Approve for the brand",
    },
    request_draft_changes: {
        title: () => "Ask for changes to the draft, for the brand",
        description:
            "Sends the draft back with a note the creator reads, and counts the round trip. The brand reads your reason.",
        reader: "the brand",
        placeholder: "e.g. The brand sent their notes to us by email",
        confirm: "Send it back for the brand",
    },
    approve_content: {
        title: () => "Approve the content for the brand",
        description:
            "The brand's sign-off on the live post — including confirming the disclosure label is on it. The brand is told who did it and why.",
        reader: "the brand",
        placeholder: "e.g. The brand approved the live reel on our call",
        confirm: "Approve for the brand",
    },
};

/**
 * One dialog for the five newer acts. What it collects follows the action the
 * server sent: a disclosure box where the act is an approval, a note for the
 * creator where it is a send-back, and evidence where it is an arrival.
 */
export function OnBehalfActDialog({ open, onOpenChange, action, creatorName, submitting, onSubmit }) {
    const [reason, setReason] = useState("");
    const [note, setNote] = useState("");
    const [disclosure, setDisclosure] = useState(false);
    const [trackingUrl, setTrackingUrl] = useState("");
    const [file, setFile] = useState(null);
    const [err, setErr] = useState("");

    useEffect(() => {
        if (open) {
            setReason("");
            setNote("");
            setDisclosure(false);
            setTrackingUrl("");
            setFile(null);
            setErr("");
        }
    }, [open]);

    if (!action) return null;
    const copy = COPY[action.key];
    if (!copy) return null;

    const submit = (e) => {
        e.preventDefault();
        if (reason.trim().length < MIN_REASON) {
            setErr(`Say why — ${copy.reader} reads it.`);
            return;
        }
        if (action.needs_note && !note.trim()) {
            setErr("Tell the creator what needs to change.");
            return;
        }
        if (action.needs_disclosure && !disclosure) {
            setErr("Confirm the disclosure label is on it — the brand's approval asks the same.");
            return;
        }
        const url = trackingUrl.trim();
        if (action.needs_evidence) {
            if (!url && !file) {
                setErr("Attach the evidence: a tracking link showing delivered, or a photo of the parcel.");
                return;
            }
            if (url && !/^https?:\/\//i.test(url)) {
                setErr("The tracking link has to be a web address (https://…).");
                return;
            }
        }
        setErr("");
        onSubmit({
            reason: reason.trim(),
            note: note.trim() || null,
            disclosure_confirmed: disclosure,
            tracking_url: url || null,
            file,
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                data-testid={IDS.dialog}
                className="max-w-md rounded-md border border-border bg-card ![background-image:none]"
            >
                <DialogHeader className="text-left">
                    <p className="text-eyebrow uppercase tracking-eyebrow text-primary-ink">
                        On the {action.side}'s behalf
                    </p>
                    <DialogTitle className="mt-3 font-serif text-h3 leading-tight">
                        {copy.title(creatorName || "the creator")}
                    </DialogTitle>
                    <DialogDescription className="mt-2 text-body leading-relaxed text-muted-foreground">
                        {copy.description}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} noValidate className="mt-4 space-y-5">
                    {action.needs_evidence && (
                        <div className="space-y-4 rounded-md border border-border p-4">
                            <div>
                                <Label
                                    htmlFor="on-behalf-tracking"
                                    className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground"
                                >
                                    Tracking link showing delivered
                                </Label>
                                <Input
                                    id="on-behalf-tracking"
                                    data-testid={IDS.tracking}
                                    type="url"
                                    inputMode="url"
                                    value={trackingUrl}
                                    onChange={(e) => setTrackingUrl(e.target.value)}
                                    placeholder="https://"
                                    maxLength={500}
                                    className="mt-2 h-11 rounded-md border-border bg-background/60"
                                />
                            </div>
                            <div>
                                <Label
                                    htmlFor="on-behalf-photo"
                                    className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground"
                                >
                                    Or a photo of the parcel
                                </Label>
                                <Input
                                    id="on-behalf-photo"
                                    data-testid={IDS.photo}
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp,image/gif"
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="mt-2 rounded-md border-border bg-background/60"
                                />
                                <p className="mt-1.5 text-meta text-muted-foreground">
                                    Kept privately with the record — only the WeAre team can open it.
                                </p>
                            </div>
                        </div>
                    )}

                    {action.needs_note && (
                        <div>
                            <Label
                                htmlFor="on-behalf-note"
                                className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground"
                            >
                                What needs to change — the creator reads this
                            </Label>
                            <Textarea
                                id="on-behalf-note"
                                data-testid={IDS.note}
                                value={note}
                                onChange={(e) => setNote(e.target.value)}
                                maxLength={1000}
                                rows={3}
                                className="mt-2 rounded-md border-border bg-background/60"
                            />
                        </div>
                    )}

                    <div>
                        <Label
                            htmlFor="on-behalf-reason"
                            className="text-eyebrow uppercase tracking-eyebrow text-muted-foreground"
                        >
                            Why — {copy.reader} reads this
                        </Label>
                        <Textarea
                            id="on-behalf-reason"
                            data-testid={IDS.reason}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            maxLength={500}
                            rows={3}
                            placeholder={copy.placeholder}
                            className="mt-2 rounded-md border-border bg-background/60"
                        />
                    </div>

                    {action.needs_disclosure && (
                        <label className="flex items-start gap-3 text-body leading-relaxed">
                            <Checkbox
                                data-testid={IDS.disclosure}
                                checked={disclosure}
                                onCheckedChange={(v) => setDisclosure(v === true)}
                                className="mt-1"
                            />
                            <span>The disclosure label is on it, where the brief says it has to be.</span>
                        </label>
                    )}

                    {err && (
                        <p role="alert" data-testid={IDS.error} className="text-meta text-destructive">
                            {err}
                        </p>
                    )}

                    <div className="flex justify-end gap-2">
                        <Button
                            type="button"
                            variant="ghost"
                            onClick={() => onOpenChange(false)}
                            className="rounded-full"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            data-testid={IDS.submit}
                            disabled={submitting}
                            className="rounded-full bg-primary text-primary-foreground hover:bg-primary-hover"
                        >
                            {submitting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />}
                            {copy.confirm}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    );
}
