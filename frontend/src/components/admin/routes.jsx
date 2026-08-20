// The console's list screens, adapted to routes.
//
// Each section component already existed and took callbacks from the old
// tab-switching shell. These are the thin adapters that give them what they
// need from the router instead: the outlet context for the badge counts, and
// the query string for filters that ought to survive a reload.
//
// Nothing here holds state. If a wrapper starts wanting some, it belongs in the
// section component or in the URL.
import React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAdminConsole } from "@/pages/AdminConsole";
import { SafeSection } from "@/components/ErrorBoundary";
import Overview from "@/components/admin/Overview";
import {
    ExportsPanel,
    HealthPanel,
    IntelligencePanel,
} from "@/components/admin/Health";
import { BrandReviews, CampaignReviews, CreatorReviews } from "@/components/admin/Reviews";
import ActionQueue from "@/components/admin/ActionQueue";
import AdminCreators from "@/components/admin/AdminCreators";
import AdminCampaigns from "@/components/admin/AdminCampaigns";
import AdminBrands from "@/components/admin/AdminBrands";
import AdminAudit from "@/components/admin/AdminAudit";
import AdminTeam from "@/components/admin/AdminTeam";

/**
 * The overview, with the operational panels above it.
 *
 * Order is the argument: what is going wrong, then what the business is doing,
 * then the numbers, then the exports. Somebody opening the console at 9am wants
 * the first of those, and putting it under a fold of stat cards would mean they
 * find out about an underfilled shoot from the brand instead.
 */
export const OverviewRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return (
        <div className="space-y-8">
            {/* Health and the activity charts moved to sidebar sections of
                their own. They were stacked here because a tab strip could not
                afford two more tabs; a sidebar can, and an admin looking for
                "what is going wrong" should not have to scroll past the stat
                tiles to find it.

                Independent panels behind independent endpoints get independent
                boundaries: the exports failing should not also cost the tiles. */}
            <SafeSection name="overview" label="The overview couldn't load">
                <Overview onChanged={reloadCounts} />
            </SafeSection>
            <SafeSection name="exports" label="Exports couldn't load">
                <ExportsPanel />
            </SafeSection>
        </div>
    );
};

/** What is going wrong, on its own screen. */
export const HealthRoute = () => (
    <SafeSection name="health" label="Health checks couldn't load">
        <HealthPanel />
    </SafeSection>
);

/** What the business is doing — the counted shapes, not the to-do list. */
export const PerformanceRoute = () => (
    <SafeSection name="intelligence" label="Activity charts couldn't load">
        <IntelligencePanel />
    </SafeSection>
);

export const CreatorReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return <CreatorReviews onChanged={reloadCounts} />;
};

export const CampaignReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return <CampaignReviews onChanged={reloadCounts} />;
};

export const BrandReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return <BrandReviews onChanged={reloadCounts} />;
};

export const QueueRoute = () => {
    const { reloadCounts, feePercent, allAccess } = useAdminConsole();
    return (
        <ActionQueue
            onChanged={reloadCounts}
            feePercent={feePercent}
            allAccess={allAccess}
        />
    );
};

export const CreatorsRoute = () => <AdminCreators />;

export const AuditRoute = () => <AdminAudit />;

/** Our own staff, and which brands each of them runs. Admin-only. */
export const TeamRoute = () => <AdminTeam />;

/**
 * The campaigns list, with "just this brand" in the URL.
 *
 * It used to be a `useState` in the shell, set when the Brands tab handed off.
 * That made the filtered list unreachable except by that one click — you could
 * not link somebody to "this brand's campaigns", and a reload dropped the
 * filter silently while leaving the chip on screen.
 */
export const CampaignsRoute = () => {
    const [params, setParams] = useSearchParams();
    const { reloadCounts, allAccess } = useAdminConsole();
    const brandFilter = params.get("brand") || "";

    const clearBrand = () => {
        const next = new URLSearchParams(params);
        next.delete("brand");
        // replace: clearing a filter is a correction, not a place to go back to.
        setParams(next, { replace: true });
    };

    return (
        <AdminCampaigns
            brandFilter={brandFilter}
            onClearBrand={clearBrand}
            onChanged={reloadCounts}
            allAccess={allAccess}
        />
    );
};

export const BrandsRoute = () => {
    const navigate = useNavigate();
    const { reloadCounts, allAccess } = useAdminConsole();
    return (
        <AdminBrands
            onChanged={reloadCounts}
            allAccess={allAccess}
            onViewCampaigns={(brandId) =>
                navigate(`/admin/campaigns?brand=${encodeURIComponent(brandId)}`)
            }
        />
    );
};
