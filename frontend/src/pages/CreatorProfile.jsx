// A creator's own profile, read-only, at /profile.
//
// Until this, the only route to your own details was the edit form — so
// "what does my profile actually say" meant opening a builder and reading it
// out of input boxes, and there was no way to check what a brand sees without
// risking changing it. Editing is now a separate state you choose, reached
// from here, rather than the only way to look.
//
// It also carries the re-check notice. A creator who changes their handle or
// their UPI can no longer pitch on anything new until we have looked again,
// and the one place they are certain to see that is the page about them.
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
    AlertTriangle,
    Facebook,
    Instagram,
    MapPin,
    Pencil,
    Youtube,
} from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { payoutMethodLabel } from "@/lib/payout";
import DeleteAccount from "@/components/account/DeleteAccount";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { DetailPageSkeleton } from "@/components/data/PageSkeleton";
import { StatePill } from "@/components/creator/shared";
import { formatLatLng, googleMapsLink, staticMapUrl } from "@/lib/googleMaps";
import { ADDRESS, CREATOR_PROFILE as IDS } from "@/constants/testIds";

const Row = ({ label, children, testid }) => (
    <div>
        <dt className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {label}
        </dt>
        <dd data-testid={testid} className="mt-1.5 text-sm text-foreground/90">
            {children || <span className="text-muted-foreground">—</span>}
        </dd>
    </div>
);

const Chips = ({ values, testid }) =>
    values?.length ? (
        <div data-testid={testid} className="flex flex-wrap gap-2">
            {values.map((v) => (
                <span
                    key={v}
                    className="inline-flex items-center rounded-full border border-white/10 px-3 py-1 text-xs uppercase tracking-[0.15em] text-muted-foreground"
                >
                    {v}
                </span>
            ))}
        </div>
    ) : (
        <span className="text-sm text-muted-foreground">—</span>
    );

const Section = ({ title, children, testid }) => (
    <section data-testid={testid} className="mt-10">
        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">{title}</p>
        <div className="mt-4 rounded-md border border-white/10 bg-card p-6 grain-surface">
            {children}
        </div>
    </section>
);

export default function CreatorProfile() {
    const [profile, setProfile] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/creator/profile");
            setProfile(data);
            setError("");
        } catch (err) {
            setError(formatApiError(err));
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const mapsHref = profile
        ? googleMapsLink({
              lat: profile.location_lat,
              lng: profile.location_lng,
              placeId: profile.location_place_id,
              address: profile.full_address,
          })
        : null;
    const staticMap = profile
        ? staticMapUrl({ lat: profile.location_lat, lng: profile.location_lng, height: 180 })
        : null;

    // Verified *and* waiting on us to look again: they keep their place in the
    // directory, but new pitches wait. The server decides this; the page is
    // reading it back, not computing it.
    const rechecking =
        profile?.verification_status === "verified" && profile?.pending_review;

    return (
        <div className="min-h-screen bg-background text-foreground grain-page">
            <Navbar />
            <main
                data-testid={IDS.page}
                className="mx-auto max-w-4xl px-6 py-12 md:py-16"
            >
                {!profile && !error ? (
                    <DetailPageSkeleton />
                ) : error ? (
                    <p className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface">
                        {error}
                    </p>
                ) : (
                    <>
                        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
                            <div className="flex min-w-0 items-start gap-5">
                                <div className="h-20 w-20 flex-none overflow-hidden rounded-full border border-white/10 media-frame">
                                    {profile.profile_image_url && (
                                        <img
                                            src={profile.profile_image_url}
                                            alt=""
                                            width={80}
                                            height={80}
                                            className="h-full w-full object-cover"
                                        />
                                    )}
                                </div>
                                <div className="min-w-0">
                                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                                        Your profile
                                    </p>
                                    <h1
                                        data-testid={IDS.name}
                                        className="mt-2 font-serif text-fluid-4xl leading-none tracking-tight"
                                    >
                                        {profile.name || "Your name"}
                                    </h1>
                                    <div className="mt-3 flex flex-wrap items-center gap-2">
                                        <StatePill
                                            state={profile.verification_status}
                                            testid={IDS.status}
                                        />
                                        {profile.city && (
                                            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <MapPin className="h-3 w-3" />
                                                {profile.city}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            {/* Editing is a state you choose, not the only way
                                to look at your own details. */}
                            <Link to="/onboarding/creator" className="flex-none">
                                <Button
                                    data-testid={IDS.edit}
                                    variant="outline"
                                    className="min-h-[2.75rem] w-full border-white/15 bg-transparent sm:w-auto"
                                >
                                    <Pencil className="mr-2 h-4 w-4" />
                                    Edit profile
                                </Button>
                            </Link>
                        </div>

                        {rechecking && (
                            <div
                                data-testid={IDS.recheckNotice}
                                className="mt-8 flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-5"
                            >
                                <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-amber-300" />
                                <div className="min-w-0 text-sm leading-relaxed text-amber-100/90">
                                    <p className="font-medium text-amber-200">
                                        We're taking another look
                                    </p>
                                    <p className="mt-1">
                                        You changed{" "}
                                        <span data-testid={IDS.recheckFields}>
                                            {(profile.pending_review_fields || []).join(", ") ||
                                                "something on your profile"}
                                        </span>
                                        , so we're checking it before you pitch on anything
                                        new. Reviews usually finish within 48 hours.
                                    </p>
                                    <p className="mt-1 text-amber-100/70">
                                        Work you've already been accepted for carries on as
                                        normal.
                                    </p>
                                </div>
                            </div>
                        )}

                        {profile.about && (
                            <Section title="About you" testid={IDS.about}>
                                <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">
                                    {profile.about}
                                </p>
                            </Section>
                        )}

                        <Section title="Where you post" testid={IDS.channels}>
                            <dl className="grid gap-5 sm:grid-cols-2">
                                <Row label="Instagram" testid={IDS.instagram}>
                                    {profile.instagram_handle && (
                                        <a
                                            href={
                                                profile.instagram_profile_url ||
                                                `https://instagram.com/${profile.instagram_handle}`
                                            }
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1.5 transition-colors duration-200 hover:text-ember-500"
                                        >
                                            <Instagram className="h-3.5 w-3.5" />@
                                            {profile.instagram_handle}
                                        </a>
                                    )}
                                </Row>
                                <Row label="Followers" testid={IDS.followers}>
                                    {profile.follower_count != null
                                        ? profile.follower_count.toLocaleString("en-IN")
                                        : null}
                                </Row>
                                <Row label="YouTube" testid={IDS.youtube}>
                                    {profile.youtube_url && (
                                        <a
                                            href={profile.youtube_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1.5 break-all transition-colors duration-200 hover:text-ember-500"
                                        >
                                            <Youtube className="h-3.5 w-3.5 flex-none" />
                                            {profile.youtube_url}
                                        </a>
                                    )}
                                </Row>
                                <Row label="Facebook" testid={IDS.facebook}>
                                    {profile.facebook_url && (
                                        <a
                                            href={profile.facebook_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1.5 break-all transition-colors duration-200 hover:text-ember-500"
                                        >
                                            <Facebook className="h-3.5 w-3.5 flex-none" />
                                            {profile.facebook_url}
                                        </a>
                                    )}
                                </Row>
                            </dl>
                        </Section>

                        <Section title="What you make" testid={IDS.work}>
                            <dl className="space-y-5">
                                <Row label="Genres">
                                    <Chips values={profile.genres} testid={IDS.genres} />
                                </Row>
                                <Row label="What you cover for brands">
                                    <Chips values={profile.niches} testid={IDS.niches} />
                                </Row>
                                <Row label="Platforms">
                                    <Chips values={profile.platforms} />
                                </Row>
                                <Row label="Your usual rate" testid={IDS.rate}>
                                    {profile.base_rate != null
                                        ? `₹${profile.base_rate.toLocaleString("en-IN")}`
                                        : null}
                                </Row>
                            </dl>
                        </Section>

                        <Section title="Where you are" testid={IDS.location}>
                            <dl className="grid gap-5 sm:grid-cols-2">
                                <Row label="City">{profile.city}</Row>
                                <Row label="Neighbourhood">{profile.address}</Row>
                                <Row label="Email">{profile.email}</Row>
                            </dl>
                            <div className="mt-5 border-t border-white/10 pt-5">
                                <Row label="Full address" testid={IDS.address}>
                                    <span className="whitespace-pre-line">
                                        {profile.full_address}
                                    </span>
                                </Row>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    Only the WeAre team sees this. We use it for physical
                                    invites and delivery campaigns.
                                </p>
                                {/* The saved pin, read-only — a static image, so
                                    this page never loads a map script. */}
                                {staticMap && (
                                    <img
                                        src={staticMap}
                                        alt="Your saved location"
                                        width={640}
                                        height={180}
                                        data-testid={ADDRESS.miniMap}
                                        className="mt-4 w-full rounded-md border border-white/10 media-frame"
                                    />
                                )}
                                {profile.location_lat != null && (
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        Pin at{" "}
                                        <span className="text-foreground/70">
                                            {formatLatLng(
                                                profile.location_lat,
                                                profile.location_lng,
                                            )}
                                        </span>
                                        {mapsHref && (
                                            <>
                                                {" · "}
                                                <a
                                                    href={mapsHref}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    data-testid={ADDRESS.openInMaps}
                                                    className="text-ember-500 transition-colors duration-200 hover:text-ember-400"
                                                >
                                                    Open in Google Maps
                                                </a>
                                            </>
                                        )}
                                    </p>
                                )}
                            </div>
                        </Section>

                        <Section title="Getting paid" testid={IDS.payout}>
                            <dl className="grid gap-5 sm:grid-cols-2">
                                {/* The creator's own screen, so these are the
                                    real values — they are theirs, and checking
                                    a digit against a passbook is the reason
                                    this page exists. Everywhere else they are
                                    masked. */}
                                <Row label="Paid by">
                                    {payoutMethodLabel(profile.payout_method)}
                                </Row>
                                {profile.payout_upi && (
                                    <Row label="UPI ID" testid={IDS.upi}>
                                        {profile.payout_upi}
                                    </Row>
                                )}
                                <Row label="Account name">
                                    {profile.payout_account_name}
                                </Row>
                                {profile.payout_account_number && (
                                    <>
                                        <Row label="Account number">
                                            {profile.payout_account_number}
                                        </Row>
                                        <Row label="IFSC">{profile.payout_ifsc}</Row>
                                    </>
                                )}
                                <Row label="PAN">{profile.pan}</Row>
                                <Row label="GSTIN">{profile.gstin}</Row>
                            </dl>
                            <p className="mt-4 text-xs text-muted-foreground">
                                Changing any of these means we'll re-check your profile
                                before you can pitch on something new.
                            </p>
                        </Section>

                        {/* Last on the page, deliberately: it is a right that
                            has to be reachable, not a thing to put in front of
                            somebody who came here to check their handle. */}
                        <div className="mt-10">
                            <DeleteAccount />
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}
