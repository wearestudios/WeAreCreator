// The creator's header.
//
// Who they are on the left, what they have made on the right. The photo is a
// portrait rather than a thumbnail, because creators are the product and the
// page should say whose it is at a glance; the money counts up once, because
// it is the reason anybody keeps a profile here.
//
// The two buttons this used to carry ("Edit profile", "Browse campaigns") are
// the sidebar's "Profile" and "Find briefs" now. A header that repeats the
// navigation beside it spends the fold on a second way to the same two places.
import React from "react";
import { CheckCircle2, Clock, Instagram, XCircle } from "lucide-react";

import { MetaLine, Pill, StatTile } from "@/components/app/ui";
import { mediaUrl } from "@/lib/api";
import { categoryLabel } from "@/lib/categories";
import { CREATOR_HERO as IDS } from "@/constants/testIds";
import { CountUp, formatCompact } from "./shared";

const VERIFICATION_META = {
    pending: { Icon: Clock, label: "Under review", tone: "due" },
    verified: { Icon: CheckCircle2, label: "Verified", tone: "good" },
    rejected: { Icon: XCircle, label: "Needs changes", tone: "warn" },
};

const initialsOf = (name) =>
    (name || "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join("") || "·";

// A niche is free text, but the seed and older profiles carry category values
// ("fnb"), so the category's own words come first and anything else is the
// creator's word with a capital.
const nicheLabel = (value) => {
    const label = categoryLabel(value);
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : "";
};

// The photo box: a 4:5 portrait, 112px tall on a phone and 160px from `md`.
// Both branches hold the same box, because most creators start without a
// photo and the monogram must not be a smaller thing in the same place.
const PHOTO_BOX = "h-28 w-[5.6rem] flex-none rounded-xl md:h-40 md:w-32";

export default function Hero({ user, profile, earnings }) {
    const status = profile?.verification_status || "pending";
    const meta = VERIFICATION_META[status] || VERIFICATION_META.pending;
    const handle = profile?.instagram_handle;
    const niche = nicheLabel((profile?.niches || [])[0]);
    const lifetime = earnings?.lifetime_earned ?? 0;
    const pending = earnings?.pending_earnings ?? 0;

    return (
        <header
            data-testid={IDS.section}
            className="flex flex-col gap-5 xl:flex-row xl:items-center xl:gap-8"
        >
            <div className="flex min-w-0 flex-1 items-center gap-4 md:gap-6">
                {profile?.profile_image_url ? (
                    <span className={"media-frame block overflow-hidden " + PHOTO_BOX}>
                        <img
                            src={mediaUrl(profile.profile_image_url)}
                            alt=""
                            data-testid={IDS.photo}
                            className="h-full w-full object-cover"
                        />
                    </span>
                ) : (
                    <span
                        data-testid={IDS.monogram}
                        aria-hidden="true"
                        className={
                            "grid place-items-center bg-card text-[2rem] font-extrabold text-muted-foreground shadow-card md:text-[2.5rem] " +
                            PHOTO_BOX
                        }
                    >
                        {initialsOf(profile?.name || user?.name)}
                    </span>
                )}

                <div className="min-w-0">
                    <Pill tone={meta.tone} data-testid={IDS.badge(status)}>
                        <meta.Icon aria-hidden="true" className="h-3.5 w-3.5" />
                        {meta.label}
                    </Pill>
                    <h1 data-testid={IDS.name} className="app-title mt-2 break-words">
                        {profile?.name || user?.name}
                    </h1>

                    {/* Handle · niche · city · followers · where the number
                        came from. **Their city, not ours** — this said
                        "Bengaluru" to every creator once, including the ones
                        who had just told us otherwise: `profile?.city`. */}
                    <MetaLine className="mt-2 text-meta font-semibold text-muted-foreground">
                        {handle ? (
                            <a
                                href={profile?.instagram_profile_url || `https://instagram.com/${handle}`}
                                target="_blank"
                                rel="noreferrer"
                                data-testid={IDS.handle}
                                className="-my-2 inline-flex min-h-[2.75rem] items-center gap-1.5 py-2 text-foreground transition-colors duration-200 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:my-0 md:min-h-0 md:py-0"
                            >
                                <Instagram aria-hidden="true" className="h-4 w-4" />@{handle}
                            </a>
                        ) : (
                            <span data-testid={IDS.handleEmpty}>No Instagram handle yet</span>
                        )}
                        {niche}
                        {profile?.city}
                        {profile?.follower_count != null && (
                            <span data-testid={IDS.followers}>
                                {formatCompact(profile.follower_count)} followers
                            </span>
                        )}
                        {/* Where the number came from, always said. A measured
                            figure and a remembered one are worth different
                            amounts to a brand, and showing them identically is
                            how the scraped ones got trusted. */}
                        {profile?.follower_count != null &&
                            (profile.follower_count_verified ? (
                                <span
                                    data-testid={IDS.followersVerified}
                                    title="Read from Instagram, refreshed every 12 hours"
                                    className="text-state-approved"
                                >
                                    from Instagram
                                </span>
                            ) : (
                                <span data-testid={IDS.followersNote}>self-reported</span>
                            ))}
                    </MetaLine>
                </div>
            </div>

            {/* Three tiles, beside the name where there is room and under it
                where there is not. The money counts up once; the count of
                campaigns is a count, and counting a 3 up from 0 is theatre. */}
            {/* From `xl` each tile is as wide as its figure needs and never
                narrower than 9.5rem — a fixed third truncated "₹49,000". */}
            <div className="grid grid-cols-3 gap-2.5 sm:gap-3 xl:flex xl:flex-none">
                <StatTile
                    label="Earned so far"
                    className="xl:min-w-[9.5rem]"
                    value={
                        <>
                            ₹<CountUp value={lifetime} testid={IDS.lifetime} />
                        </>
                    }
                />
                <StatTile
                    label="Campaigns done"
                    className="xl:min-w-[9.5rem]"
                    value={<span data-testid={IDS.completed}>{earnings?.campaigns_completed ?? 0}</span>}
                />
                <StatTile
                    label="On its way"
                    className="xl:min-w-[9.5rem]"
                    value={
                        <>
                            ₹<CountUp value={pending} testid={IDS.pending} />
                        </>
                    }
                />
            </div>
        </header>
    );
}
