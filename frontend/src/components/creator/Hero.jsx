// The creator's hero.
//
// Who they are on the left, what they've made on the right. The money is the
// headline because it is the reason anybody keeps a profile here — everything
// else on this page is in service of that number going up.
import React from "react";
import { Link } from "react-router-dom";
import {
    ArrowRight,
    CheckCircle2,
    Clock,
    Instagram,
    XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { mediaUrl } from "@/lib/api";
import { CREATOR_HERO as IDS } from "@/constants/testIds";
import { CountUp, Money, formatCompact, formatRupees } from "./shared";

const VERIFICATION_META = {
    pending: {
        Icon: Clock,
        label: "Under review",
        tone: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    },
    verified: {
        Icon: CheckCircle2,
        label: "Verified",
        tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    },
    rejected: {
        Icon: XCircle,
        label: "Needs changes",
        tone: "bg-red-500/15 text-red-300 border-red-500/40",
    },
};

const initialsOf = (name) =>
    (name || "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join("") || "·";

const SmallStat = ({ label, children, testid }) => (
    <div className="rounded-md border border-white/10 bg-card p-5">
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {label}
        </p>
        <div data-testid={testid} className="mt-3 font-serif text-2xl leading-none">
            {children}
        </div>
    </div>
);

export default function Hero({ user, profile, earnings }) {
    const status = profile?.verification_status || "pending";
    const meta = VERIFICATION_META[status] || VERIFICATION_META.pending;
    const handle = profile?.instagram_handle;
    const lifetime = earnings?.lifetime_earned ?? 0;

    return (
        <header
            data-testid={IDS.section}
            className="grid gap-8 md:grid-cols-12 md:items-start"
        >
            <div className="md:col-span-7">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Creator · India
                </p>

                <div className="mt-5 flex items-center gap-4">
                    {profile?.profile_image_url ? (
                        <img
                            src={mediaUrl(profile.profile_image_url)}
                            alt=""
                            data-testid={IDS.photo}
                            className="h-16 w-16 flex-none rounded-md border border-white/10 object-cover md:h-20 md:w-20"
                        />
                    ) : (
                        <span
                            data-testid={IDS.monogram}
                            aria-hidden="true"
                            className="grid h-16 w-16 flex-none place-items-center rounded-md border border-white/10 bg-white/5 font-serif text-2xl text-muted-foreground md:h-20 md:w-20"
                        >
                            {initialsOf(profile?.name || user?.name)}
                        </span>
                    )}
                    <div className="min-w-0">
                        <h1
                            data-testid={IDS.name}
                            className="font-serif text-3xl leading-none tracking-tight md:text-5xl"
                        >
                            {profile?.name || user?.name}
                        </h1>
                        <span
                            data-testid={IDS.badge(status)}
                            className={
                                "mt-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] " +
                                meta.tone
                            }
                        >
                            <meta.Icon className="h-3.5 w-3.5" />
                            {meta.label}
                        </span>
                    </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
                    {handle ? (
                        <a
                            href={
                                profile?.instagram_profile_url ||
                                `https://instagram.com/${handle}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            data-testid={IDS.handle}
                            className="inline-flex items-center gap-1.5 transition-colors duration-200 hover:text-ember-500"
                        >
                            <Instagram className="h-4 w-4" />@{handle}
                        </a>
                    ) : (
                        <span data-testid={IDS.handleEmpty}>No Instagram handle yet</span>
                    )}
                    {profile?.follower_count != null && (
                        <>
                            <span className="text-muted-foreground/50">·</span>
                            <span data-testid={IDS.followers}>
                                {formatCompact(profile.follower_count)} followers
                            </span>
                            {/* Said plainly. The figure is the creator's own until
                                there is a source we're permitted to measure with. */}
                            <span
                                data-testid={IDS.followersNote}
                                className="text-xs text-muted-foreground/70"
                            >
                                (self-reported)
                            </span>
                        </>
                    )}
                </div>

                <div className="mt-7 flex flex-wrap gap-3">
                    <Link to="/onboarding/creator" data-testid={IDS.editProfile}>
                        <Button
                            variant="outline"
                            className="h-11 rounded-full border-white/15 bg-transparent hover:bg-white/5"
                        >
                            Edit profile
                        </Button>
                    </Link>
                    <Link to="/campaigns" data-testid={IDS.browse}>
                        <Button className="group h-11 rounded-full bg-ember-500 text-black hover:bg-ember-400">
                            Browse campaigns
                            <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                        </Button>
                    </Link>
                </div>
            </div>

            <div className="md:col-span-5">
                <div className="rounded-md border border-white/10 bg-card p-6 md:p-7">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        Earned with WeAre
                    </p>
                    <Money
                        symbolClass="h-6 w-6 md:h-7 md:w-7"
                        className="mt-4 font-serif text-5xl leading-none tracking-tight md:text-6xl"
                    >
                        <CountUp value={lifetime} testid={IDS.lifetime} />
                    </Money>
                    <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                        Paid out to you, after our fee.
                    </p>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-4">
                    <SmallStat label="Campaigns done" testid={IDS.completed}>
                        {earnings?.campaigns_completed ?? 0}
                    </SmallStat>
                    <SmallStat label="On its way" testid={IDS.pending}>
                        <Money symbolClass="h-4 w-4">
                            {formatRupees(earnings?.pending_earnings ?? 0)}
                        </Money>
                    </SmallStat>
                </div>
            </div>
        </header>
    );
}
