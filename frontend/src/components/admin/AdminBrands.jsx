// Every brand, with the two numbers that matter (what they've run, what
// they've actually paid) and the verification decision inline. Rejection
// demands a reason — the brand is told, and the audit log keeps it.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { BadgeCheck, Building2, IndianRupee, Search, XCircle } from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ADMIN_BRANDS as IDS } from "@/constants/testIds";
import { ConfirmDialog } from "./dialogs";
import {
    EmptyState,
    FilterSelect,
    ListSkeleton,
    Pill,
    SectionHeader,
    formatRupees,
    timeAgo,
} from "./shared";

const BRAND_STATUS_META = {
    verified: { label: "Verified", tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
    pending: { label: "Pending", tone: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
    rejected: { label: "Rejected", tone: "bg-red-500/10 text-red-300/80 border-red-500/25" },
};

const STATUS_OPTIONS = [
    { value: "verified", label: "Verified" },
    { value: "pending", label: "Pending" },
    { value: "rejected", label: "Rejected" },
];

const brandStatus = (b) =>
    b.verified ? "verified" : b.verification_reason ? "rejected" : "pending";

export default function AdminBrands({ onChanged, onViewCampaigns }) {
    const [rows, setRows] = useState(null);
    const [q, setQ] = useState("");
    const [status, setStatus] = useState("");
    const [busyId, setBusyId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [confirm, setConfirm] = useState(null);

    const load = useCallback(async () => {
        setRows(null);
        try {
            // /admin/brands carries the counts and spend; /admin/brands/pending
            // carries the rejection reasons. One merged list, one mental model.
            const [all, pending] = await Promise.all([
                api.get("/admin/brands"),
                api.get("/admin/brands/pending"),
            ]);
            const reasonById = Object.fromEntries(
                pending.data.map((p) => [p.user_id, p]),
            );
            setRows(
                all.data.map((b) => ({
                    ...b,
                    verification_reason: reasonById[b.user_id]?.verification_reason,
                })),
            );
        } catch (e) {
            toast.error(formatApiError(e));
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const run = async (id, fn, msg) => {
        setBusyId(id);
        setSubmitting(true);
        try {
            await fn();
            toast.success(msg);
            setConfirm(null);
            await load();
            onChanged?.();
        } catch (e) {
            toast.error(formatApiError(e));
        } finally {
            setBusyId(null);
            setSubmitting(false);
        }
    };

    const verify = (b) =>
        run(b.user_id, () => api.post(`/admin/brands/${b.user_id}/verify`), "Brand verified");

    const reject = (b) =>
        setConfirm({
            brand: b,
            title: `Reject ${b.business_name || "this brand"}?`,
            onSubmit: (body) =>
                run(
                    b.user_id,
                    () => api.post(`/admin/brands/${b.user_id}/reject`, body),
                    "Brand rejected",
                ),
        });

    const unverify = (b) =>
        setConfirm({
            brand: b,
            unverify: true,
            title: `Take ${b.business_name || "this brand"} back to unverified?`,
            onSubmit: (body) =>
                run(
                    b.user_id,
                    () => api.post(`/admin/brands/${b.user_id}/unverify`, body),
                    "Brand un-verified",
                ),
        });

    const visible = useMemo(() => {
        const term = q.trim().toLowerCase();
        return (rows || []).filter((b) => {
            if (status && brandStatus(b) !== status) return false;
            if (!term) return true;
            return [b.business_name, b.email, b.phone]
                .filter(Boolean)
                .some((v) => v.toLowerCase().includes(term));
        });
    }, [rows, q, status]);

    return (
        <section data-testid={IDS.section}>
            <SectionHeader
                kicker="Brands"
                title="Every brand"
                blurb="Verification, what they've run and what they've actually paid. Spend only counts money that left the bank."
                onRefresh={load}
                refreshTestId={IDS.refresh}
            />

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative min-w-0 flex-1 sm:min-w-[16rem]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        data-testid={IDS.search}
                        placeholder="Business name, email or phone"
                        aria-label="Search brands"
                        className="h-10 rounded-md border-white/10 bg-background/60 pl-9 focus-visible:ring-ember-500"
                    />
                </div>
                <FilterSelect
                    label="Any status"
                    value={status}
                    onChange={setStatus}
                    options={STATUS_OPTIONS}
                    testid={IDS.filterStatus}
                />
            </div>

            <div className="mt-6 rounded-md border border-white/10 bg-card">
                {!rows ? (
                    <ListSkeleton rows={5} testid={IDS.skeleton} />
                ) : visible.length === 0 ? (
                    <EmptyState testid={IDS.empty} Icon={Building2}>
                        {rows.length === 0
                            ? "No brand has signed up yet."
                            : "No brand matches that."}
                    </EmptyState>
                ) : (
                    <ul data-testid={IDS.list} className="divide-y divide-white/10">
                        {visible.map((b) => {
                            const s = brandStatus(b);
                            const busy = busyId === b.user_id;
                            return (
                                <li
                                    key={b.user_id}
                                    data-testid={IDS.row(b.user_id)}
                                    className="flex flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:gap-6"
                                >
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-3">
                                            <p className="truncate font-serif text-lg leading-tight">
                                                {b.business_name || "Unnamed brand"}
                                            </p>
                                            <Pill
                                                meta={BRAND_STATUS_META}
                                                value={s}
                                                testid={IDS.rowStatus(b.user_id)}
                                            />
                                        </div>
                                        <p className="mt-1 truncate text-xs text-muted-foreground">
                                            {[
                                                b.category,
                                                b.email || b.phone,
                                                b.created_at ? `joined ${timeAgo(b.created_at)} ago` : null,
                                            ]
                                                .filter(Boolean)
                                                .join(" · ")}
                                        </p>
                                        {s === "rejected" && b.verification_reason && (
                                            <p
                                                data-testid={IDS.rowReason(b.user_id)}
                                                className="mt-1.5 text-xs text-red-300/80"
                                            >
                                                Rejected: {b.verification_reason}
                                            </p>
                                        )}
                                    </div>

                                    <div className="flex flex-none flex-wrap items-center gap-4 md:justify-end">
                                        <button
                                            type="button"
                                            onClick={() => onViewCampaigns?.(b.user_id)}
                                            data-testid={IDS.viewCampaigns(b.user_id)}
                                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                                        >
                                            {b.campaign_count}{" "}
                                            {b.campaign_count === 1 ? "campaign" : "campaigns"}
                                            {b.active_campaign_count > 0
                                                ? ` · ${b.active_campaign_count} live`
                                                : ""}
                                        </button>
                                        <span
                                            data-testid={IDS.rowSpend(b.user_id)}
                                            className="inline-flex items-baseline text-sm"
                                        >
                                            <IndianRupee className="h-3 w-3 text-ember-500" />
                                            {formatRupees(b.total_spend)}
                                        </span>

                                        {s === "verified" ? (
                                            <Button
                                                type="button"
                                                variant="outline"
                                                disabled={busy}
                                                onClick={() => unverify(b)}
                                                data-testid={IDS.unverify(b.user_id)}
                                                className="h-8 rounded-full border-white/15 bg-transparent px-3 text-xs hover:bg-white/5"
                                            >
                                                Un-verify
                                            </Button>
                                        ) : (
                                            <>
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    disabled={busy}
                                                    onClick={() => reject(b)}
                                                    data-testid={IDS.reject(b.user_id)}
                                                    className="h-8 rounded-full border-red-500/30 bg-transparent px-3 text-xs text-red-300 hover:bg-red-500/10 hover:text-red-200"
                                                >
                                                    <XCircle className="mr-1.5 h-3.5 w-3.5" />
                                                    Reject
                                                </Button>
                                                <Button
                                                    type="button"
                                                    disabled={busy}
                                                    onClick={() => verify(b)}
                                                    data-testid={IDS.verify(b.user_id)}
                                                    className="h-8 rounded-full bg-ember-500 px-4 text-xs text-black hover:bg-ember-400"
                                                >
                                                    <BadgeCheck className="mr-1.5 h-3.5 w-3.5" />
                                                    Verify
                                                </Button>
                                            </>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {rows && (
                <p
                    data-testid={IDS.count}
                    className="mt-4 text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                    {visible.length} of {rows.length} shown
                </p>
            )}

            <ConfirmDialog
                open={Boolean(confirm)}
                onOpenChange={(v) => !v && setConfirm(null)}
                submitting={submitting}
                kicker={confirm?.unverify ? "Un-verify brand" : "Reject brand"}
                title={confirm?.title || ""}
                description={
                    confirm?.unverify
                        ? "They can keep drafting but can't submit campaigns until re-verified. Live campaigns are untouched."
                        : "They're told why, any briefs of theirs waiting for review go back to draft, and they can't submit until we verify them."
                }
                placeholder="What should they fix?"
                confirmLabel={confirm?.unverify ? "Un-verify" : "Reject brand"}
                destructive
                onSubmit={(body) => confirm?.onSubmit(body)}
            />
        </section>
    );
}
