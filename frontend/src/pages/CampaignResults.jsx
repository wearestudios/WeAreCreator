// A campaign's results dashboard, at two addresses off one component:
// `/brand/campaigns/:id/results` for the brand that ran it, and
// `/admin/campaigns/:id/results` inside the console for an admin looking at
// any campaign. The server decides who may read which campaign; this only
// supplies the chrome each audience already has around it.
import React from "react";
import { useParams } from "react-router-dom";

import { Navbar } from "@/components/Navbar";
import CampaignDashboard from "@/components/dashboard/CampaignDashboard";

export default function CampaignResults() {
    const { id } = useParams();
    return (
        <div className="min-h-screen bg-background grain-page">
            <Navbar />
            <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-14">
                <CampaignDashboard
                    campaignId={id}
                    backTo={`/brand/campaigns/${id}/applicants`}
                    backLabel="Back to the campaign"
                />
            </main>
        </div>
    );
}

/** Inside the console: no navbar, the console is the chrome. */
export function AdminCampaignResults() {
    const { id } = useParams();
    return (
        <CampaignDashboard
            campaignId={id}
            backTo={`/admin/campaigns/${id}`}
            backLabel="Back to the campaign"
        />
    );
}
