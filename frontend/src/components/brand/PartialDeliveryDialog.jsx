// Accepting what actually arrived.
//
// Two of three stories delivered was neither complete nor failed. The
// collaboration could be approved — paying in full for work that did not all
// happen — or sent back forever, paying nothing for work that mostly did.
// Both were wrong, and both were happening over WhatsApp with a figure
// somebody agreed verbally and nobody wrote down.
//
// **The counts are the runner's to type, because they can see what is up.**
// The fee is theirs too: two of three stories is not two-thirds of the value
// when the reel was the point, so the pro-rata figure is shown as a suggestion
// beside the box and never filled in for them. The same rule the withholding
// field holds — this records what somebody decided, it does not decide.
import React, { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { SHORTFALL as IDS } from "@/constants/testIds";
import { DELIVERABLE_TYPES } from "@/lib/deliverables";
import { isBarter } from "@/lib/compensation";

export default function PartialDeliveryDialog({
    open,
    onOpenChange,
    campaign,
    applicant,
    busy,
    onConfirm,
}) {
    // Memoised because the `|| []` makes a fresh array every render, which
    // would defeat the useMemo below and recompute the totals on every
    // keystroke in the note field.
    const asked = useMemo(() => campaign?.deliverable_items || [], [campaign]);
    const [counts, setCounts] = useState({});
    const [amount, setAmount] = useState("");
    const [note, setNote] = useState("");

    // Reset when the dialog opens on a different applicant, or a second
    // partial acceptance inherits the first one's numbers.
    const key = `${open}-${applicant?.id || ""}`;
    const [seen, setSeen] = useState(key);
    if (seen !== key) {
        setSeen(key);
        setCounts({});
        setAmount("");
        setNote("");
    }

    const totals = useMemo(() => {
        const askedTotal = asked.reduce((n, i) => n + i.quantity, 0);
        const gotTotal = asked.reduce(
            (n, i) => n + Math.min(i.quantity, Number(counts[i.type] || 0)),
            0
        );
        return { askedTotal, gotTotal };
    }, [asked, counts]);

    const barter = isBarter(campaign);
    const fullFee = campaign?.budget_per_creator;
    // Shown, never applied. A number in a disabled box is a number people
    // assume was agreed; a number beside an empty box is a starting point.
    const suggestion =
        !barter && typeof fullFee === "number" && totals.askedTotal
            ? Math.round((fullFee * totals.gotTotal) / totals.askedTotal)
            : null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent data-testid={IDS.dialog} className="sm:max-w-lg">
                <DialogHeader className="text-left">
                    <DialogTitle>What arrived?</DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                        Count what is actually up. The creator is told what was accepted and
                        what it was agreed at, and the shortfall goes on the record.
                    </DialogDescription>
                </DialogHeader>

                <ul className="space-y-2">
                    {asked.map((item) => (
                        <li key={item.type} className="flex items-center gap-3">
                            <span className="min-w-0 flex-1 text-sm">
                                {DELIVERABLE_TYPES[item.type] || item.type}
                                <span className="ml-2 text-xs text-muted-foreground">
                                    asked for {item.quantity}
                                </span>
                            </span>
                            <Input
                                type="number"
                                inputMode="numeric"
                                min={0}
                                max={item.quantity}
                                value={counts[item.type] ?? ""}
                                onChange={(e) =>
                                    setCounts((c) => ({ ...c, [item.type]: e.target.value }))
                                }
                                data-testid={IDS.count(item.type)}
                                className="h-10 w-20 border-white/10 bg-background/60 text-right tabular-nums"
                            />
                        </li>
                    ))}
                </ul>

                {!barter && (
                    <label className="block">
                        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                            Agreed for this
                        </span>
                        <Input
                            type="number"
                            inputMode="numeric"
                            min={0}
                            value={amount}
                            onChange={(e) => setAmount(e.target.value)}
                            placeholder={suggestion != null ? String(suggestion) : ""}
                            data-testid={IDS.amount}
                            className="mt-2 h-11 border-white/10 bg-background/60 text-base tabular-nums"
                        />
                        {suggestion != null && (
                            <span
                                data-testid={IDS.suggestion}
                                className="mt-1.5 block text-xs text-muted-foreground"
                            >
                                Pro-rata would be ₹{suggestion.toLocaleString("en-IN")} —
                                a suggestion, not a rule. Two of three stories is not
                                two-thirds of the value if the reel was the point.
                            </span>
                        )}
                    </label>
                )}

                <label className="block">
                    <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Why
                    </span>
                    {/* Required. "Accepted partial" with no reason is a
                        decision somebody has to reconstruct from a payment
                        figure a year later. */}
                    <Textarea
                        rows={2}
                        maxLength={1000}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="e.g. Two stories went up, the third clashed with their own launch."
                        data-testid={IDS.note}
                        className="mt-2 rounded-md border-white/10 bg-background/60 text-base focus-visible:ring-ember-500"
                    />
                </label>

                <DialogFooter className="gap-2">
                    <Button variant="ghost" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={() =>
                            onConfirm({
                                delivered: Object.fromEntries(
                                    Object.entries(counts)
                                        .map(([k, v]) => [k, Number(v)])
                                        .filter(([, v]) => Number.isFinite(v) && v > 0)
                                ),
                                agreed_amount: barter || !amount ? null : Number(amount),
                                note: note.trim(),
                            })
                        }
                        disabled={busy || !note.trim()}
                        data-testid={IDS.submit}
                        className="bg-ember-500 text-white hover:bg-ember-600"
                    >
                        {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Accept {totals.gotTotal} of {totals.askedTotal}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
