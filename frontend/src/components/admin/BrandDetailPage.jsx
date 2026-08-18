// One brand, at /admin/brands/:id.
//
// A brand is a claim until somebody checks it, so this page is arranged around
// checking: what they say they are, the documents that prove it, the named
// person asking on their behalf, and then what they have actually run with us.
import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExternalLink, FileText, Globe, Instagram } from "lucide-react";

import { api, formatApiError, API_BASE } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { isBarter } from "@/lib/compensation";
import { Button } from "@/components/ui/button";
import {
    ADMIN_BRAND_PAGE as IDS,
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
    CAMPAIGN_STATUS_META,
    Pill,
    formatDate,
    formatDateTime,
    formatRupees,
} from "@/components/admin/shared";
import { ConfirmDialog } from "@/components/admin/dialogs";
import { CampaignLink } from "@/components/admin/links";
import { PerformanceRollup } from "@/components/admin/Performance";
import { ViewAsButton } from "@/components/admin/ViewAsButton";
import BrandAvatar from "@/components/BrandAvatar";
import { useAdminConsole } from "@/pages/AdminConsole";

const STATE_LABEL = {
    unsubmitted: "Not submitted",
    pending_verification: "Waiting on us",
    verified: "Verified",
    rejected: "Rejected",
};

export default function BrandDetailPage() {
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
            const { data } = await api.get(`/admin/brands/${id}`);
            setData(data);
            setError("");
        } catch (err) {
            if (err?.response?.status === 404) setNotFound(true);
            else setError(formatApiError(err));
        }
    }, [id]);

    const loadAudit = useCallback(async () => {
        try {
            // brand_id rather than subject: a brand's history lands on its
            // campaigns and collaborations as much as on the profile itself.
            const { data } = await api.get("/admin/audit", {
                params: { brand_id: id, limit: 200 },
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

    const brand = data?.brand;

    return (
        <DetailShell
            testid={IDS.page}
            backTo="/admin/brands"
            backLabel="All brands"
            crumbs={[
                { key: "console", label: "Console", to: "/admin" },
                { key: "brands", label: "Brands", to: "/admin/brands" },
                { key: "brand", label: brand?.business_name || "Brand" },
            ]}
            kicker="Brand"
            title={brand?.business_name || "Brand"}
            avatar={brand && <BrandAvatar brand={brand} size="h-11 w-11" />}
            loading={!data && !error && !notFound}
            error={error}
            notFound={notFound}
            notFoundMessage="This brand doesn't exist, or its profile was removed."
            subtitle={
                brand && (
                    <>
                        <span
                            className={
                                "rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] " +
                                (brand.verified
                                    ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                                    : brand.verification_state === "rejected"
                                      ? "border-red-500/25 bg-red-500/10 text-red-300/80"
                                      : "border-amber-500/30 bg-amber-500/15 text-amber-300")
                            }
                        >
                            {STATE_LABEL[brand.verification_state] || brand.verification_state}
                        </span>
                        {brand.category && <span>{brand.category}</span>}
                        {brand.areas?.length > 0 && <span>{brand.areas.join(", ")}</span>}
                        <span>Signed up {formatDate(brand.signed_up_at)}</span>
                    </>
                )
            }
            aside={
                brand && (
                    <>
                        {!brand.verified && (
                            <Button
                                data-testid={DIDS.action("verify")}
                                disabled={busy === "verify"}
                                onClick={() =>
                                    act(
                                        "verify",
                                        () => api.post(`/admin/brands/${id}/verify`),
                                        "Brand verified",
                                    )
                                }
                                className="rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                Verify
                            </Button>
                        )}
                        {brand.verified && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("unverify")}
                                onClick={() => setDialog({ kind: "unverify" })}
                                className="rounded-full border-white/15 bg-transparent hover:bg-white/5"
                            >
                                Unverify
                            </Button>
                        )}
                        {/* A brand has exactly one login, and this is it —
                            so "view as this brand" and "view as their manager"
                            are the same thing. */}
                        <ViewAsButton
                            userId={brand.user_id}
                            name={brand.manager_name || brand.business_name}
                            role={brand.manager_role || "brand_manager"}
                        />
                        {brand.verification_state !== "rejected" && (
                            <Button
                                variant="outline"
                                data-testid={DIDS.action("reject")}
                                onClick={() => setDialog({ kind: "reject" })}
                                className="rounded-full border-destructive/30 bg-transparent text-destructive hover:bg-destructive/10"
                            >
                                Reject
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
                            testid={DIDS.stat("spend")}
                            label="Total spend"
                            value={`₹${formatRupees(data.totals.total_spend)}`}
                        />
                        <Stat
                            testid={DIDS.stat("campaigns")}
                            label="Campaigns"
                            value={data.totals.campaign_count}
                        />
                        <Stat
                            testid={DIDS.stat("active")}
                            label="Active now"
                            value={data.totals.active_campaign_count}
                            highlight={data.totals.active_campaign_count > 0}
                        />
                        <Stat
                            testid={DIDS.stat("booked")}
                            label="Creators booked"
                            value={data.totals.creators_booked}
                        />
                    </div>

                    <div className="grid gap-8 lg:grid-cols-3">
                        <Section id="business" title="The business" className="lg:col-span-2">
                            <Panel>
                                <dl className="grid gap-5 sm:grid-cols-2">
                                    <Field label="Trading name">{brand.business_name}</Field>
                                    <Field label="Legal entity">
                                        {brand.legal_entity_name}
                                    </Field>
                                    <Field label="Business type">{brand.business_type}</Field>
                                    <Field label="GST number">{brand.gst_number}</Field>
                                    <Field label="Registered address" className="sm:col-span-2">
                                        {brand.registered_address}
                                    </Field>
                                    <Field label="Website">
                                        {brand.website && (
                                            <a
                                                href={brand.website}
                                                target="_blank"
                                                rel="noreferrer noopener"
                                                className="inline-flex items-center gap-1.5 break-all text-ember-500 hover:text-ember-400"
                                            >
                                                <Globe className="h-3.5 w-3.5 flex-none" />
                                                {brand.website}
                                            </a>
                                        )}
                                    </Field>
                                    <Field label="Instagram">
                                        {brand.instagram_handle && (
                                            <span className="inline-flex items-center gap-1.5">
                                                <Instagram className="h-3.5 w-3.5" />@
                                                {brand.instagram_handle}
                                            </span>
                                        )}
                                    </Field>
                                </dl>
                                {brand.verification_reason && (
                                    <p className="mt-6 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-200">
                                        Last decision: {brand.verification_reason}
                                    </p>
                                )}
                            </Panel>
                        </Section>

                        <Section id="manager" title="Brand manager">
                            <Panel data-testid={IDS.manager}>
                                <p className="font-serif text-xl">
                                    {brand.manager_name || "Nobody named"}
                                </p>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    {brand.manager_designation || "—"}
                                </p>
                                <dl className="mt-6 space-y-4 border-t border-white/10 pt-5">
                                    <Field label="WhatsApp (their login)">
                                        {brand.manager_phone}
                                    </Field>
                                    <Field label="Work email">{brand.manager_email}</Field>
                                    <Field label="Account status">{brand.status}</Field>
                                </dl>
                                {brand.contact_email_is_free_domain && (
                                    <p className="mt-5 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-200">
                                        That's a free mail address. Not a problem on its own —
                                        plenty of real small businesses use one — but a domain
                                        address is the cheapest evidence somebody works there.
                                    </p>
                                )}
                                <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
                                    One login per brand. There is no way to add a second.
                                </p>
                            </Panel>
                        </Section>
                    </div>

                    <PerformanceRollup performance={data.performance} scope="brand" />

                    <Section id="documents" title="Documents" count={data.documents.length}>
                        {data.documents.length === 0 ? (
                            <p
                                data-testid={IDS.documentsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
                            >
                                Nothing uploaded. A brand needs at least one — GST certificate,
                                business registration, FSSAI licence or shop &amp; establishment
                                licence — before we'll look.
                            </p>
                        ) : (
                            <ul className="divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
                                {data.documents.map((d) => (
                                    <li
                                        key={d.id}
                                        data-testid={IDS.document(d.id)}
                                        className="flex flex-col gap-2 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                    >
                                        <span className="inline-flex min-w-0 flex-1 items-center gap-2.5 text-sm">
                                            <FileText className="h-4 w-4 flex-none text-ember-500" />
                                            <span className="min-w-0">
                                                {d.doc_label}
                                                <span className="block truncate text-xs text-muted-foreground">
                                                    {d.original_name}
                                                </span>
                                            </span>
                                        </span>
                                        <span className="flex-none text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                            {d.status}
                                        </span>
                                        <span className="w-32 flex-none text-xs text-muted-foreground">
                                            {formatDate(d.uploaded_at)}
                                        </span>
                                        {/* The only route these are reachable
                                            through: admin-only, audited, and
                                            no-store. There is no public URL. */}
                                        <a
                                            href={`${API_BASE}/admin/brands/${id}/documents/${d.id}`}
                                            target="_blank"
                                            rel="noreferrer noopener"
                                            className="inline-flex flex-none items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                                        >
                                            <ExternalLink className="h-3.5 w-3.5" />
                                            Open
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>

                    <Section id="campaigns" title="Campaigns" count={data.campaigns.length}>
                        {data.campaigns.length === 0 ? (
                            <p
                                data-testid={IDS.campaignsEmpty}
                                className="rounded-md border border-white/10 bg-card px-6 py-8 text-sm text-muted-foreground grain-surface"
                            >
                                They haven't posted anything yet.
                            </p>
                        ) : (
                            <ul className="divide-y divide-white/10 rounded-md border border-white/10 bg-card grain-surface">
                                {data.campaigns.map((c) => (
                                    <li
                                        key={c.id}
                                        data-testid={IDS.campaign(c.id)}
                                        className="flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                    >
                                        <span className="min-w-0 flex-1 text-sm">
                                            <CampaignLink id={c.id} title={c.title} />
                                            <span className="block text-xs text-muted-foreground">
                                                {c.area}
                                                {c.manager_name ? ` · ${c.manager_name}` : ""}
                                            </span>
                                        </span>
                                        <span className="flex-none text-xs text-muted-foreground">
                                            {c.filled_slots}/{c.creators_needed} filled
                                        </span>
                                        <span className="w-24 flex-none text-sm">
                                            {isBarter(c) ? "Barter" : `₹${formatRupees(c.spend)}`}
                                        </span>
                                        <Pill
                                            meta={CAMPAIGN_STATUS_META}
                                            value={c.status}
                                            testid={`admin-brand-campaign-status-${c.id}`}
                                        />
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>

                    <Section id="audit" title="Everything that happened" count={audit?.length}>
                        <AuditTrail
                            rows={audit}
                            formatWhen={formatDateTime}
                            emptyMessage="Nothing recorded against this brand yet."
                        />
                    </Section>
                </>
            )}

            <ConfirmDialog
                open={dialog.kind === "reject"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Reject"
                title={brand?.business_name}
                description="The brand is told what you write here, and it's what they'll fix before resubmitting."
                confirmLabel="Reject"
                submitting={busy === "reject"}
                onSubmit={(body) =>
                    act(
                        "reject",
                        () => api.post(`/admin/brands/${id}/reject`, body),
                        "Brand rejected",
                    )
                }
            />
            <ConfirmDialog
                open={dialog.kind === "unverify"}
                onOpenChange={(v) => !v && setDialog({ kind: null })}
                kicker="Unverify"
                title={brand?.business_name}
                description="Takes the brand back behind the gate. Their live campaigns stop reaching creators — publishing, inviting and the creator directory all close."
                confirmLabel="Unverify"
                destructive
                submitting={busy === "unverify"}
                onSubmit={(body) =>
                    act(
                        "unverify",
                        () => api.post(`/admin/brands/${id}/unverify`, body),
                        "Brand unverified",
                    )
                }
            />
        </DetailShell>
    );
}
