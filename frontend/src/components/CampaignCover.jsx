// The picture on a brief.
//
// One component for the card, the detail page and anywhere else a campaign is
// drawn, because the fallback has to be the same picture in all of them — a
// brief that is a green rectangle in the list and a blue one on its own page
// reads as two different briefs.
//
// The frame reserves its box before anything loads (`aspect-ratio`, which is
// on the container rather than the image so an image that never arrives still
// occupies the space it claimed). Nothing below it moves when the file lands.
import React, { useState } from "react";

import { mediaUrl } from "@/lib/api";
import { coverGradient, initialOf } from "@/lib/cover";
import { COVER } from "@/constants/testIds";

/**
 * @param campaign  the campaign, for its id, cover and brand name
 * @param ratio     tailwind aspect class; 16/9 on a card, wider on a hero
 * @param rounded   the corner, so a cover that sits flush in a card can drop
 *                  its bottom radius without this component knowing about cards
 */
export default function CampaignCover({
    campaign,
    ratio = "aspect-[16/9]",
    rounded = "rounded-lg",
    className = "",
    priority = false,
}) {
    const [broken, setBroken] = useState(false);

    const id = campaign?.id || campaign?._id || "";
    const src = campaign?.cover_image_url ? mediaUrl(campaign.cover_image_url) : null;
    const initial = initialOf(campaign?.brand_name, campaign?.business_name, campaign?.title);

    const frame = `relative w-full overflow-hidden border border-white/10 ${ratio} ${rounded} ${className}`;

    if (src && !broken) {
        return (
            // `media-frame` tints and grains the reserved box, so an empty one
            // reads as a surface rather than a hole — correct here, and
            // deliberately absent from the generated branch below: both it and
            // the gradient set `background-image`, and one would silently win.
            <div className={`media-frame ${frame}`} data-testid={COVER.frame(id)}>
                <img
                    src={src}
                    alt=""
                    loading={priority ? "eager" : "lazy"}
                    decoding="async"
                    onError={() => setBroken(true)}
                    data-testid={COVER.image(id)}
                    className="absolute inset-0 h-full w-full object-cover"
                />
            </div>
        );
    }

    // Generated rather than a stock placeholder: the tint comes from the id, so
    // two briefs next to each other in a list are never the same rectangle. No
    // `media-frame` here — see above.
    return (
        <div
            className={frame}
            style={coverGradient(id)}
            data-testid={COVER.frame(id)}
        >
            <span
                aria-hidden="true"
                data-testid={COVER.fallback(id)}
                className="absolute inset-0 grid place-items-center font-serif text-[clamp(2.5rem,9vw,4.5rem)] leading-none text-white/45"
            >
                {initial}
            </span>
        </div>
    );
}
