// One application, as one process.
//
// **Eight friendly stages over twelve internal states.** The states are the
// machine — they are what transitions are checked against and what a 409 is
// about — and they are unreadable: "commercial agreed", "draft approved",
// "in payment" are twelve boxes describing our bookkeeping, and nobody reading
// them can tell which of the twelve means "nearly done".
//
// **The same eight everywhere**, on the creator's view, the brand's applicant
// view and the admin's collaboration page, because they are three people
// talking about one thing. Before this each side had its own bar — the creator
// saw six stages, the console saw the raw ladder — so "where is this" had two
// answers depending on who you asked.
//
// The stages come from the server (`process.stages`). Rebuilding the mapping
// here would be a second copy of it, and the whole reason this component
// exists is that two surfaces disagreed about what one state meant. The server
// also picks the *voice* of the next-action line: the party who has to act
// reads an instruction, everybody else reads the wait. So this component never
// asks who is looking, which is the rule the shared application screen holds.
import React, { useState } from "react";
import { AlertTriangle, Check, ChevronDown, CircleSlash } from "lucide-react";

import { APPLICATION } from "@/constants/testIds";
import useWide from "@/lib/useWide";

// Who is being waited on. The creator gets the accent because those are the
// steps where nobody at WeAre can do anything except chase.
const OWNER = {
    admin: { label: "WeAre", tone: "text-sky-300 border-sky-500/30 bg-sky-500/10" },
    brand: { label: "The brand", tone: "text-violet-300 border-violet-500/30 bg-violet-500/10" },
    creator: { label: "The creator", tone: "text-ember-500 border-ember-500/40 bg-ember-500/15" },
};

const BANNER_TONE = {
    // An exit. Deliberately quiet: a brand picking somebody else is not a
    // verdict on the creator, and a red band implying otherwise is how you
    // lose one.
    ended: {
        icon: CircleSlash,
        className: "border-white/10 bg-card text-muted-foreground",
        iconClass: "text-muted-foreground",
    },
    // Something came back. This one *is* a call to action.
    attention: {
        icon: AlertTriangle,
        className: "border-amber-500/30 bg-amber-500/10 text-amber-200",
        iconClass: "text-amber-300",
    },
};

/** One box on the line. */
const Stage = ({ stage, index }) => (
    <li
        data-testid={APPLICATION.processStage(stage.key)}
        data-state={stage.current ? "current" : stage.done ? "done" : "todo"}
        aria-current={stage.current ? "step" : undefined}
        className={
            "flex flex-1 flex-none items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.14em] transition-colors duration-150 " +
            (stage.current
                ? "border-ember-500/40 bg-ember-500/15 text-ember-500"
                : stage.done
                  ? "border-white/10 bg-white/5 text-muted-foreground"
                  : "border-white/10 bg-transparent text-muted-foreground/50")
        }
    >
        {stage.done ? (
            <Check className="h-3 w-3 flex-none" aria-hidden="true" />
        ) : (
            <span aria-hidden="true" className="tabular-nums opacity-60">
                {index + 1}
            </span>
        )}
        <span className="truncate">{stage.label}</span>
    </li>
);

export default function ProcessFlow({ process, className = "" }) {
    // **Read synchronously**, so a phone never mounts the eight-across form
    // even for a frame — the other way round, a row of eight boxes appears and
    // vanishes on the device least able to lay it out.
    const wide = useWide();
    const [open, setOpen] = useState(false);

    if (!process) return null;

    const { stages = [], next_action: next, banner, stage_number: number, stage_count: count } =
        process;
    const owner = next?.owner ? OWNER[next.owner] : null;
    const current = stages.find((s) => s.current);
    const tone = banner ? BANNER_TONE[banner.tone] || BANNER_TONE.attention : null;
    const BannerIcon = tone?.icon;

    return (
        <div data-testid={APPLICATION.process} className={"min-w-0 " + className}>
            {/* Above `md` the whole line, so the shape of the process is
                visible at a glance — which is the only thing eight boxes are
                for. Below it, the current stage and a count, because eight
                boxes on a 390px screen are eight illegible boxes. */}
            {wide ? (
                <ol
                    className="flex items-stretch gap-1"
                    aria-label="Application process"
                >
                    {stages.map((stage, i) => (
                        <Stage key={stage.key} stage={stage} index={i} />
                    ))}
                </ol>
            ) : (
                <div>
                    <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => setOpen((v) => !v)}
                        data-testid={APPLICATION.processToggle}
                        className="flex min-h-[2.75rem] w-full items-center gap-3 rounded-md border border-ember-500/40 bg-ember-500/15 px-4 py-2 text-left transition-colors duration-150"
                    >
                        <span className="min-w-0 flex-1">
                            <span className="block text-[10px] uppercase tracking-[0.2em] text-ember-500/80">
                                {number ? `Stage ${number} of ${count}` : "Not on the line"}
                            </span>
                            <span className="mt-0.5 block truncate text-sm text-ember-500">
                                {current?.label || "—"}
                            </span>
                        </span>
                        <ChevronDown
                            aria-hidden="true"
                            className={
                                "h-4 w-4 flex-none text-ember-500 transition-transform duration-150 " +
                                (open ? "rotate-180" : "")
                            }
                        />
                    </button>
                    {open && (
                        <ol
                            className="mt-2 flex flex-col gap-1"
                            aria-label="Application process"
                        >
                            {stages.map((stage, i) => (
                                <Stage key={stage.key} stage={stage} index={i} />
                            ))}
                        </ol>
                    )}
                </div>
            )}

            {/* A banner takes the place of the next action, not of the line:
                the work still has a position on it, and an exit that erased
                the stepper would lose the record of how far it got. */}
            {banner ? (
                <div
                    data-testid={APPLICATION.processBanner}
                    className={
                        "mt-3 flex items-start gap-3 rounded-md border px-4 py-3 " +
                        tone.className
                    }
                >
                    <BannerIcon
                        aria-hidden="true"
                        className={"mt-0.5 h-4 w-4 flex-none " + tone.iconClass}
                    />
                    <span className="min-w-0 text-sm">
                        <span className="font-medium">{banner.title}</span>
                        {banner.detail ? (
                            <span className="mt-0.5 block text-xs opacity-80">
                                {banner.detail}
                            </span>
                        ) : null}
                    </span>
                </div>
            ) : next ? (
                <div
                    data-testid={APPLICATION.processNext}
                    className="mt-3 flex flex-col gap-2 rounded-md border border-white/10 bg-card px-4 py-3 grain-surface sm:flex-row sm:items-center sm:gap-3"
                >
                    <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Next
                    </span>
                    {owner && (
                        <span
                            data-testid={APPLICATION.processOwner}
                            className={
                                "inline-flex w-fit flex-none items-center rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] " +
                                owner.tone
                            }
                        >
                            {owner.label}
                        </span>
                    )}
                    <span className="min-w-0 text-sm">{next.label}</span>
                </div>
            ) : null}
        </div>
    );
}
