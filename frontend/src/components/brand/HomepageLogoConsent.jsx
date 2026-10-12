// Permission to put this brand's logo on the public home page.
//
// **A logo is a trademark, so this is a permission rather than a preference.**
// One checkbox, and the text beside it is the server's — frozen into the
// brand's record at the moment it is ticked, the way `platform_terms` is
// frozen at acceptance. What matters in a year is not what the wording says
// then but what it said when somebody agreed to it, and a form holding its own
// copy of the sentence is a form that can show a different one.
//
// **It asks nothing for itself.** Whether they have consented, whether we have
// approved, whether they have actually finished a campaign, and the consent
// text all arrive on `GET /brand/profile`. A checkbox working out its own
// eligibility would be a second copy of `_brand_wall_eligible`, and the two
// would disagree the first time the rule moved.
//
// The three states it has to tell apart are genuinely different, and collapsing
// them is how a control becomes a support ticket:
//
//   - not ticked — nothing to say beyond the offer;
//   - ticked, and live — say so, and make withdrawing obviously available;
//   - ticked, and not live yet — say *why*, because the two reasons are ours
//     and theirs respectively: either we have not approved it, or they have
//     not finished a campaign. "Not showing" with no reason reads as broken.
import React from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { BRAND_WALL_CONSENT as IDS } from "@/constants/testIds";

export default function HomepageLogoConsent({ block, checked, onChange }) {
    // The block arrives with the profile. Before it does there is nothing
    // honest to render — not an unticked box, which would read as "you have
    // not agreed to this" to somebody who has.
    if (!block) return null;

    const { approved, campaigns_run: campaignsRun, eligible, terms } = block;

    // Why it is not on the wall, when they have said yes. Ours first: if we
    // have not approved it, that is the thing they cannot do anything about
    // and the thing they should not be told to go and fix.
    let pending = null;
    if (checked && !eligible) {
        if (!approved) {
            pending = "We will add it once someone here has checked it over.";
        } else if (!campaignsRun) {
            pending =
                "It goes up once your first campaign is finished — the wall is " +
                "businesses that have actually run one.";
        }
    }

    return (
        <div
            data-testid={IDS.consent}
            className="rounded-lg border border-white/10 bg-card p-5"
        >
            <label className="flex cursor-pointer items-start gap-3">
                <Checkbox
                    checked={!!checked}
                    onCheckedChange={(v) => onChange(!!v)}
                    data-testid={IDS.consentCheckbox}
                    className="mt-0.5"
                />
                <span className="text-sm leading-relaxed">
                    <span className="font-medium">
                        Show our name and logo on the WeAre Creators website
                    </span>
                    {/* **The terms, verbatim from the server.** This is the
                        text that gets frozen into the record, so it is the
                        text that has to be on screen — paraphrasing it here
                        would mean storing one sentence and showing another. */}
                    <span
                        data-testid={IDS.consentTerms}
                        className="mt-2 block text-muted-foreground"
                    >
                        {terms}
                    </span>
                </span>
            </label>

            {checked && eligible && (
                <p
                    data-testid={IDS.consentLive}
                    className="mt-4 text-sm text-muted-foreground"
                >
                    Your logo is on the home page now. Unticking this removes it
                    immediately.
                </p>
            )}
            {pending && (
                <p
                    data-testid={IDS.consentPending}
                    className="mt-4 text-sm text-muted-foreground"
                >
                    {pending}
                </p>
            )}
        </div>
    );
}
