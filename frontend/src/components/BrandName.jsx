// A brand, named and linked.
//
// A creator could see a campaign and learn nothing about who was posting it.
// The name is now the way in — and it is one component rather than a link at
// each of the places a brand is named, because the twentieth place is the one
// that forgets.
//
// Renders plain text when there is no id, like `components/admin/links.jsx`: a
// row whose brand we cannot identify should read as a name, not as a promise
// that 404s.
import React from "react";

import BrandAvatar from "@/components/BrandAvatar";
import { brandPageUrl } from "@/lib/brandPage";
import { BRAND_PAGE } from "@/constants/testIds";

const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm";

export default function BrandName({
    brand,
    // The id is usually on the campaign as `brand_id`; a brand profile carries
    // it as `user_id`. Taking it explicitly keeps this from guessing.
    brandId,
    avatar = true,
    avatarSize = "h-7 w-7",
    className = "",
    // Set on a card whose own click target sits behind an overlay, so the link
    // is reachable rather than covered by it.
    lift = false,
    // Callers with their own registry name (the application page) pass it;
    // everywhere else gets the default so the element is still findable.
    testid,
}) {
    const id = brandId || brand?.brand_id || brand?.user_id || null;
    const label = brand?.brand_name || brand?.business_name || "Brand";
    const href = brandPageUrl(id);

    const inner = (
        <>
            {avatar && <BrandAvatar brand={brand} size={avatarSize} />}
            <span className="truncate">{label}</span>
        </>
    );

    const shared = `flex min-w-0 items-center gap-2 ${lift ? "relative z-10 " : ""}${className}`;

    if (!href) {
        return (
            <span data-testid={testid || BRAND_PAGE.name(id || "unknown")} className={shared}>
                {inner}
            </span>
        );
    }

    return (
        <a
            href={href}
            data-testid={testid || BRAND_PAGE.link(id)}
            // The card around this is often a link too. Stopping the click here
            // is what makes tapping the brand open the brand rather than the
            // brief sitting underneath it.
            onClick={(e) => e.stopPropagation()}
            className={`${shared} ${FOCUS} transition-colors duration-200 hover:text-ember-500`}
        >
            {inner}
        </a>
    );
}
