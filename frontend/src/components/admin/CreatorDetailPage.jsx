// One creator, at /admin/creators/:id.
//
// Everything we hold about a person, in the order somebody deciding about them
// asks for it: who they are, whether their numbers are measured or claimed, what
// they have actually done here, and what we owe them.
import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Instagram, MapPin, Send, Youtube } from "lucide-react";

import { googleMapsLink } from "@/lib/googleMaps";
import { ADDRESS } from "@/constants/testIds";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import {
    ADMIN_CREATOR_PAGE as IDS,
    ADMIN_DETAIL as DIDS,
} from "@/constants/testIds";
import {
    AuditTrail,
    DetailShell,
    Field,
    Panel,
    Section,
    Stat,
} from "@/components/admin/DetailPage";
import {
    CreatorAvatar,
    Pill,
    StatePill,
    VERIFICATION_META,
    formatCompact,
    formatDate,
    formatDateTime,
    formatRupees,
} from "@/components/admin/shared";
import { ConfirmDialog } from "@/components/admin/dialogs";
import { CampaignLink, CollaborationLink } from "@/components/admin/links";
import { ViewAsButton } from "@/components/admin/ViewAsButton";
import { useAdminConsole } from "@/pages/AdminConsole";

const COLLAB_GROUPS = [
    { key: "ongoing", label: "In flight" },
    { key: "applied", label: "Applied" },
    { key: "completed", label: "Completed" },
    { key: "ended", label: "Declined & cancelled" },
];

export default function CreatorDetailPage() {
    const { id } = useParams();
    const { reloadCounts } = useAdminConsole();

    const [data, setData] = useState(null);
    const [audit, setAudit] = useState(null);
    const [error, setError] = useState("");
    const [notFound, setNotFound] = useState(false);
    const [busy, setBusy] = useState(null);
    const [dialog, setDialog] = useState({ kind: null });

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/admin/creators/${id}`);
            setData(data);
            setError("");
        } catch (err) {
            if (err?.response?.status === 404) setNotFound(true);
            else setError(formatApiError(err));
        }
    }, [id]);

    const loadAudit = useCallback(async () => {
        try {
            // Two subjects carry a creator's history: the profile (verification)
            // and the account (suspension). Asked for by id, which the log
            // stores for both.
            const { data } = await api.get("/admin/audit", {
                params: { subject_id: id, limit: 100 },
            });
            setAudit(data);
        } catch {
            setAudit([]);
        }
    }, [id]);

    useEffect(() => {
        setData(null);
        setAudit(null);
        setNotFound(false);
        load();
        loadAudit();
    }, [id, load, loadAudit]);

    const act = async (key, request, message) => {
        setBusy(key);
        try {
            await request();
            notifySuccess(message);
            setDialog({ kind: null });
            await Promise.all([load(), loadAudit()]);
            reloadCounts?.();
        } catch (err) {
            notifyError(err, { onRetry: () => act(key, request, message) });
        } finally {
            setBusy(null);
        }
    };

    const creator = data?.creator;

    // A pin when we have one, a text search when we don't — either beats
    // copying an address out by hand at the point somebody is trying to find
    // a flat.
    const mapsLink = creator
        ? googleMapsLink({
              lat: creator.location_lat,
              lng: creator.location_lng,
              placeId: creator.location_place_id,
              address: creator.full_address,
          })
        : null;
    const ig = data?.instagram;
    const suspended = creator?.status === "suspended";

    return (
        <DetailShell
            testid={IDS.page}
            backTo="/admin/creators"
            backLabel="All creators"
            crumbs={[
                { key: "console", label: "Console", to: "/admin" },
                { key: "creators", label: "Creators", to: "/admin/creators" },
                { key: "creator", label: creator?.name || "Creator" },
            ]}
            kicker={creator?.reference ? `Creator · ${creator.reference}` : "Creator"}
            title={creator?.name || "Creator"}
            loading={!data && !error && !notFound}
            error={error}
            notFound={notFound}
            notFoundMessage="This creator doesn't exist, or their profile was removed."
            subtitle={
                creator && (
                    <>
                        <Pill
                            meta={VERIFICATION_META}
                            value={creator.verification_status}
                            testid={DIDS.stat("verification")}
                        />
                        {suspended && (
                            <span className="rounded-full border border-red-500/25 bg-red-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-red-300/80">
                                Suspended
                            </span>
                        )}
                        {creator.city && (
                            <span className="inline-flex items-center gap-1.5">
                                <MapPin className="h-3.5 w-3.5" />
                                {creator.city}
                            </span>
                        )}
                        <span>Joined {formatDate(creator.joined_at)}</span>
                    </>
                )
            }
            aside={
                creator && (
                    <>
                        {creator.verification_status !== "verified" && (
                            <Button
                                data-testid={DIDS.action("approve")}
                                disabled={busy === "approve"}
                                onClick={() =>
                                    act(
                                        "approve",
                                        () => api.post(`/admin/creators/${id}/approve`),
                                        "Creator verified",
                                    )
                                }
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                Approve
                            </Button>
                        )}
                        {creator.verification_status !== "rejected" && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("reject")}
                                onClick={() => setDialog({ kind: "reject" })}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Reject
                            </Button>
                        )}
                        <ViewAsButton
                            userId={creator.user_id}
                            name={creator.name}
                            role="creator"
                        />
                        {suspended ? (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("reinstate")}
                                onClick={() => setDialog({ kind: "reinstate" })}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Reinstate
                            </Button>
                        ) : (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("suspend")}
                                onClick={() => setDialog({ kind: "suspend" })}
                                className="rounded-full border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10"
                            >
                                Suspend
                            </Button>
                        )}
                    </>
                )
            }
        >
            {data && (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <Stat
                            testid={DIDS.stat("earned")}
                            label="Lifetime earned"
                            value={`₹${formatRupees(data.totals.lifetime_earned)}`}
                        />
                        <Stat
                            testid={DIDS.stat("committed")}
                            label="Pending"
                            value={`₹${formatRupees(data.totals.committed)}`}
                            highlight={data.totals.committed > 0}
                        />
                        <Stat
                            testid={DIDS.stat("completed")}
                            label="Completed"
                            value={data.totals.campaigns_completed}
                        />
                        <Stat
                            testid={DIDS.stat("ongoing")}
                            label="In flight"
                            value={data.totals.collaborations_ongoing}
                        />
                    </div>

                    <div className="grid gap-8 lg:grid-cols-3">
                        <Section id="profile" title="Profile" className="lg:col-span-2">
                            <Panel>
                                <div className="flex items-start gap-5">
                                    <CreatorAvatar creator={creator} size="h-16 w-16" />
                                    <div className="min-w-0">
                                        <p className="font-serif text-xl">{creator.name}</p>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            {creator.email || "No email"}
                                            {creator.phone ? ` · ${creator.phone}` : ""}
                                        </p>
                                    </div>
                                </div>
                                {/* Their own words, before the fields somebody
                                    else chose the shape of. This is most of
                                    what a reviewer is actually judging. */}
                                {creator.about && (
                                    <p
                                        data-testid="admin-creator-about"
                                        className="mt-6 whitespace-pre-line border-t border-white/10 pt-6 text-sm leading-relaxed text-foreground/90"
                                    >
                                        {creator.about}
                                    </p>
                                )}
                                <dl className="mt-7 grid gap-5 border-t border-white/10 pt-6 sm:grid-cols-3">
                                    <Field label="Base rate">
                                        {creator.base_rate != null
                                            ? `₹${formatRupees(creator.base_rate)}`
                                            : null}
                                    </Field>
                                    <Field label="Followers">
                                        {formatCompact(creator.follower_count)}
                                    </Field>
                                    <Field label="Where it came from">
                                        {/* Measured or claimed, never presented
                                            as the same thing. */}
                                        {creator.follower_count_verified
                                            ? "Measured via Instagram"
                                            : "Self-reported"}
                                    </Field>
                                    <Field label="Niches">
                                        {creator.niches?.join(", ")}
                                    </Field>
                                    <Field label="Genres">
                                        {creator.genres?.join(", ")}
                                    </Field>
                                    <Field label="Platforms">
                                        {creator.platforms?.join(", ")}
                                    </Field>
                                    <Field label="Payout ready">
                                        {creator.payout_ready ? "Yes" : "No — UPI or PAN missing"}
                                    </Field>
                                    <Field label="City">{creator.city}</Field>
                                    <Field label="Neighbourhood">{creator.address}</Field>
                                    <Field label="Address" className="sm:col-span-3">
                                        <span className="block whitespace-pre-line">
                                            {creator.full_address || "—"}
                                        </span>
                                        {/* The label is what gets printed; the
                                            pin is what somebody navigates to,
                                            and they are routinely not the same
                                            spot. One tap to the real one. */}
                                        {mapsLink && (
                                            <a
                                                href={mapsLink}
                                                target="_blank"
                                                rel="noreferrer"
                                                data-testid={ADDRESS.openInMaps}
                                                className="mt-1.5 inline-flex min-h-[2.75rem] items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-ember-500 transition-colors duration-150 hover:text-ember-400 md:min-h-0"
                                            >
                                                <MapPin className="h-3.5 w-3.5" />
                                                {creator.location_lat != null
                                                    ? "Open the pin in Google Maps"
                                                    : "Search this address in Google Maps"}
                                            </a>
                                        )}
                                    </Field>
                                    <Field label="UPI">{creator.payout_upi}</Field>
                                    <Field label="PAN">{creator.pan}</Field>
                                </dl>
                                {creator.verification_reason && (
                                    <p className="mt-6 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-relaxed text-amber-200">
                                        Last decision: {creator.verification_reason}
                                    </p>
                                )}
                            </Panel>
                        </Section>

                        <Section id="channels" title="Channels">
                            <div className="space-y-4">
                                <Panel data-testid={IDS.instagram}>
                                    <p className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        <Instagram className="h-3.5 w-3.5" />
                                        Instagram
                                    </p>
                                    {!ig?.configured ? (
                                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                                            Not configured on this deployment — follower counts
                                            stay self-reported.
                                        </p>
                                    ) : ig.connected ? (
                                        <dl className="mt-4 space-y-4">
                                            <Field label="Account">@{ig.username}</Field>
                                            <Field label="Type">{ig.account_type}</Field>
                                            <Field label="Followers">
                                                {formatCompact(ig.stats?.followers_count)}
                                            </Field>
                                            <Field label="Posts">
                                                {formatCompact(ig.stats?.media_count)}
                                            </Field>
                                            <Field label="Engagement">
                                                {ig.stats?.engagement_rate != null
                                                    ? `${ig.stats.engagement_rate}%`
                                                    : null}
                                            </Field>
                                            <Field label="Last read">
                                                {formatDateTime(ig.last_refreshed_at)}
                                            </Field>
                                        </dl>
                                    ) : (
                                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                                            {ig.status === "stale"
                                                ? "Connection expired — they've been asked to reconnect."
                                                : "Not connected."}
                                            {creator.instagram_handle
                                                ? ` Handle on file: @${creator.instagram_handle}.`
                                                : ""}
                                        </p>
                                    )}
                                </Panel>

                                <Panel data-testid={IDS.youtube}>
                                    <p className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        <Youtube className="h-3.5 w-3.5" />
                                        YouTube
                                    </p>
                                    {data.youtube?.url ? (
                                        <a
                                            href={data.youtube.url}
                                            target="_blank"
                                            rel="noreferrer noopener"
                                            className="mt-4 block break-all text-sm text-ember-500 transition-colors duration-150 hover:text-ember-400"
                                        >
                                            {data.youtube.url}
                                        </a>
                                    ) : (
                                        <p className="mt-4 text-sm text-muted-foreground">
                                            No channel given.
                                        </p>
                                    )}
                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                        A link, not a connection — we have no numbers for
                                        YouTube.
                                    </p>
                                </Panel>
                            </div>
                        </Section>
                    </div>

                    <Section
                        id="bookings"
                        title="Slot bookings"
                        count={data.slot_bookings?.length}
                    >
                        {!data.slot_bookings?.length ? (
                            <p
                                data-testid={IDS.bookingsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground"
                            >
                                Nothing booked. A slot is taken once a fee is agreed.
                            </p>
                        ) : (
                            <ul className="divide-y divide-white/10 rounded-md border border-white/10 bg-card">
                                {data.slot_bookings.map((b) => (
                                    <li
                                        key={b.id}
                                        data-testid={IDS.booking(b.id)}
                                        className="flex flex-col gap-2 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                    >
                                        <span className="w-56 flex-none text-sm">
                                            {formatDateTime(b.starts_at)}
                                        </span>
                                        <CollaborationLink
                                            id={b.collaboration_id}
                                            className="min-w-0 flex-1 text-sm"
                                        >
                                            {b.campaign_title || "Campaign"}
                                        </CollaborationLink>
                                        <StatePill state={b.state} />
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>

                    <Section id="collaborations" title="Every collaboration">
                        <div className="space-y-8">
                            {COLLAB_GROUPS.filter(
                                (g) => (data.collaborations[g.key] || []).length > 0,
                            ).map((g) => (
                                <div key={g.key} data-testid={IDS.collabGroup(g.key)}>
                                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                                        {g.label}
                                        <span className="ml-2 text-ember-500">
                                            {data.collaborations[g.key].length}
                                        </span>
                                    </p>
                                    <ul className="mt-3 divide-y divide-white/10 rounded-md border border-white/10 bg-card">
                                        {data.collaborations[g.key].map((c) => (
                                            <li
                                                key={c.id}
                                                data-testid={IDS.collab(c.id)}
                                                className="flex flex-col gap-2 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                            >
                                                <span className="min-w-0 flex-1 text-sm">
                                                    <CampaignLink
                                                        id={c.campaign_id}
                                                        title={c.campaign_title}
                                                    />
                                                    <span className="block text-sm text-muted-foreground">
                                                        {c.brand_name}
                                                        <CollaborationLink
                                                            id={c.id}
                                                            className="ml-2 uppercase tracking-[0.15em]"
                                                        >
                                                            application
                                                        </CollaborationLink>
                                                    </span>
                                                </span>
                                                <span className="flex-none text-sm text-muted-foreground">
                                                    {c.agreed_amount != null
                                                        ? `₹${formatRupees(c.agreed_amount)}`
                                                        : c.quoted_rate != null
                                                          ? `quoted ₹${formatRupees(c.quoted_rate)}`
                                                          : "—"}
                                                </span>
                                                <StatePill state={c.state} />
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                            {COLLAB_GROUPS.every(
                                (g) => (data.collaborations[g.key] || []).length === 0,
                            ) && (
                                <p className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground">
                                    They haven't applied to anything yet.
                                </p>
                            )}
                        </div>
                    </Section>

                    <Section id="audit" title="Everything that happened" count={audit?.length}>
                        <AuditTrail
                            rows={audit}
                            formatWhen={formatDateTime}
                            emptyMessage="No decisions recorded against this creator yet."
                        />
                    </Section>
                </>
            )}

            <ConfirmDialog
                open={dialog.kind === "reject"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Reject"
                title={creator?.name}
                description="They're told what you write here, and it's what they'll fix before asking again."
                confirmLabel="Reject"
                submitting={busy === "reject"}
                onSubmit={(body) =>
                    act(
                        "reject",
                        () => api.post(`/admin/creators/${id}/reject`, body),
                        "Creator rejected",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "suspend"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Suspend"
                title={creator?.name}
                description="Stops the account. Work already under way is untouched — decide on those separately. Their verification is left exactly as it is."
                confirmLabel="Suspend"
                destructive
                submitting={busy === "suspend"}
                onSubmit={(body) =>
                    act(
                        "suspend",
                        () => api.post(`/admin/creators/${id}/suspend`, body),
                        "Account suspended",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "reinstate"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Reinstate"
                title={creator?.name}
                description="Puts the account back. They can apply to briefs again."
                confirmLabel="Reinstate"
                submitting={busy === "reinstate"}
                onSubmit={(body) =>
                    act(
                        "reinstate",
                        () => api.post(`/admin/creators/${id}/reinstate`, body),
                        "Account reinstated",
                    )
                }
            />
        </DetailShell>
    );
}
