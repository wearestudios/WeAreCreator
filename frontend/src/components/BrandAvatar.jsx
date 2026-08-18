// A brand's mark, wherever the brand is named.
//
// Exactly the shape `CreatorAvatar` has, deliberately: the two appear on the
// same screens — an applicant board lists creators under a brand's campaign —
// and two different fallback treatments there would read as two kinds of
// account rather than as one missing picture and one present.
import React, { useState } from "react";

import { mediaUrl } from "@/lib/api";
import { initialOf } from "@/lib/cover";
import { BRAND_LOGO } from "@/constants/testIds";

export default function BrandAvatar({
    brand,
    size = "h-9 w-9",
    className = "",
}) {
    const [broken, setBroken] = useState(false);

    const id = brand?.id || brand?.user_id || brand?.brand_id || "";
    const logo = brand?.logo_url || brand?.brand_logo_url;
    const src = logo ? mediaUrl(logo) : null;
    const monogram = initialOf(
        brand?.business_name,
        brand?.brand_name,
        brand?.name,
        brand?.contact_person,
    );

    if (src && !broken) {
        return (
            <img
                src={src}
                alt=""
                loading="lazy"
                onError={() => setBroken(true)}
                data-testid={BRAND_LOGO.image(id)}
                className={`${size} aspect-square flex-none rounded-md border border-white/10 bg-white/5 object-contain ${className}`}
            />
        );
    }
    return (
        <span
            aria-hidden="true"
            data-testid={BRAND_LOGO.monogram(id)}
            className={`${size} grid flex-none place-items-center rounded-md border border-white/10 bg-ember-500/10 font-serif text-sm text-ember-500 ${className}`}
        >
            {monogram}
        </span>
    );
}
