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
import Today from "@/components/admin/Today";
import Analytics from "@/components/admin/Analytics";
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
import AdminDeletions from "@/components/admin/AdminDeletions";
import AdminEnquiries from "@/components/admin/AdminEnquiries";
import PlatformSettings from "@/components/admin/PlatformSettings";
import DisputeQueue from "@/components/admin/DisputeQueue";
import CircumventionQueue from "@/components/admin/CircumventionQueue";
import RetentionPanel from "@/components/admin/RetentionPanel";
import AdminDormant from "@/components/admin/AdminDormant";
import CaseStudies from "@/components/admin/CaseStudies";
import SurveyResults from "@/components/admin/SurveyResults";
import UnfinishedProfiles from "@/components/admin/UnfinishedProfiles";
import { DensityScope } from "@/components/admin/console/density";

/**
 * The overview, with the operational panels above it.
 *
 * Order is the argument: what is going wrong, then what the business is doing,
 * then the numbers, then the exports. Somebody opening the console at 9am wants
 * the first of those, and putting it under a fold of stat cards would mean they
 * find out about an underfilled shoot from the brand instead.
 */
export const OverviewRoute = () => {
    const { reloadCounts, allAccess } = useAdminConsole();
    return (
        // **A density surface since it led with the queue's rows** — see
        // `DENSITY_SURFACES`. Compact tightens the card's rows and the base
        // size under it; the heading and the tiles keep their own sizes.
        <DensityScope surface="overview">
            <div className="space-y-section">
                {/* What needs a person today: the queue's five tiles, its
                    oldest rows, and the figures beside them (board 27). Its
                    own boundary — the campaign table below failing should not
                    also cost the queue. */}
                <SafeSection name="today" label="Today's queue couldn't load">
                    <Today allAccess={allAccess} />
                </SafeSection>
                {/* Every campaign, with the stat cards that filter it. Below
                    the fold now: it is what somebody looks things up in, not
                    what they open the console to find out. */}
                <SafeSection name="overview" label="The overview couldn't load">
                    <Overview onChanged={reloadCounts} />
                </SafeSection>
                <SafeSection name="exports" label="Exports couldn't load">
                    <ExportsPanel allAccess={allAccess} />
                </SafeSection>
            </div>
        </DensityScope>
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

/** The four ratios the business is judged on. */
export const AnalyticsRoute = () => (
    <SafeSection name="analytics" label="Analytics couldn't load">
        <Analytics />
    </SafeSection>
);

export const CreatorReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return (
        <DensityScope surface="creator-reviews">
            <CreatorReviews onChanged={reloadCounts} />
        </DensityScope>
    );
};

export const CampaignReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return (
        <DensityScope surface="campaign-reviews">
            <CampaignReviews onChanged={reloadCounts} />
        </DensityScope>
    );
};

export const BrandReviewsRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return (
        <DensityScope surface="brand-reviews">
            <BrandReviews onChanged={reloadCounts} />
        </DensityScope>
    );
};

export const QueueRoute = () => {
    const { reloadCounts, feePercent, allAccess } = useAdminConsole();
    return (
        <DensityScope surface="queue">
            <ActionQueue
                onChanged={reloadCounts}
                feePercent={feePercent}
                allAccess={allAccess}
            />
        </DensityScope>
    );
};

export const CreatorsRoute = () => (
    <DensityScope surface="creators">
        <AdminCreators />
    </DensityScope>
);

export const AuditRoute = () => (
    <DensityScope surface="audit">
        <AdminAudit />
    </DensityScope>
);

/**
 * Our own staff: the scoped-console role and the campaign managers.
 *
 * The section is out of a team member's sidebar, so `allAccess` is not what
 * keeps them off the screen — it is what keeps the *manager* half off it,
 * because `POST /admin/managers` is admin-only where the team routes beside
 * it are `CONSOLE_ROLES`.
 */
export const TeamRoute = () => {
    const { allAccess } = useAdminConsole();
    return (
        <DensityScope surface="team">
            <AdminTeam allAccess={allAccess} />
        </DensityScope>
    );
};

/** People asking to be forgotten. Admin-only, and irreversible. */
export const DeletionsRoute = () => (
    <DensityScope surface="deletions">
        <AdminDeletions />
    </DensityScope>
);

export const EnquiriesRoute = () => {
    const { reloadCounts } = useAdminConsole();
    return (
        <DensityScope surface="enquiries">
            <AdminEnquiries onChanged={reloadCounts} />
        </DensityScope>
    );
};
export const SettingsRoute = () => <PlatformSettings />;

/** Frozen collaborations, worst-waiting first. Scoped like every list. */
export const DisputesRoute = () => {
    const { allAccess } = useAdminConsole();
    return (
        <DensityScope surface="disputes">
            <DisputeQueue allAccess={allAccess} />
        </DensityScope>
    );
};

/** Collaborations flagged as having gone off-platform. Admin-only: a
 *  creator works across every brand, so their account is not scoped work. */
export const CircumventionRoute = () => (
    <DensityScope surface="circumvention">
        <CircumventionQueue />
    </DensityScope>
);

/** The anonymous creator survey, read back. Admin-only: nobody to scope to. */
export const SurveyRoute = () => (
    <SafeSection name="survey" label="The survey results couldn't load">
        <SurveyResults />
    </SafeSection>
);

/** Signed up, never finished: the onboarding nudge list. */
export const UnfinishedRoute = () => (
    <SafeSection name="unfinished" label="That list couldn't load">
        <UnfinishedProfiles />
    </SafeSection>
);

/** What we keep and for how long, from the same table the code enforces. */
export const RetentionRoute = () => <RetentionPanel />;
export const DormantRoute = () => (
    <DensityScope surface="dormant">
        <AdminDormant />
    </DensityScope>
);

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
        <DensityScope surface="campaigns">
            <AdminCampaigns
                brandFilter={brandFilter}
                onClearBrand={clearBrand}
                onChanged={reloadCounts}
                allAccess={allAccess}
            />
        </DensityScope>
    );
};

export const BrandsRoute = () => {
    const navigate = useNavigate();
    const { reloadCounts, allAccess } = useAdminConsole();
    return (
        <DensityScope surface="brands">
            <AdminBrands
                onChanged={reloadCounts}
                allAccess={allAccess}
                onViewCampaigns={(brandId) =>
                    navigate(`/admin/campaigns?brand=${encodeURIComponent(brandId)}`)
                }
            />
        </DensityScope>
    );
};


/**
 * Case studies.
 *
 * No adapter state and no outlet context: this section owns its own list and
 * its own editor, and there is no badge count for it — nothing *arrives*
 * here. A boundary of its own so a half-written draft that renders badly
 * cannot take the sidebar down with it.
 */
export function CaseStudiesRoute() {
    return (
        <SafeSection name="case-studies" label="Case studies couldn't load">
            <CaseStudies />
        </SafeSection>
    );
}
