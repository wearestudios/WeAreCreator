// Which of your brands you are looking at.
//
// A team member's console shows **all their assigned brands at once** — that
// is the default and the point, because the work arrives mixed and a console
// that made you pick a brand first would be a console you had to visit three
// times a morning. This is the narrowing on top of it.
//
// **It writes to the URL, not to state.** `?brand=<id>` is the filter the
// campaigns list already reads, so a narrowed console is a link somebody can
// send — and a reload keeps it, which a `useState` in the shell would not.
// That was the exact bug the old tab-switching shell had.
//
// It renders nothing for somebody on one brand: a picker with a single option
// is a control that cannot change anything, sitting in a header that is short
// of room already.
import React, { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useSearchParams } from "react-router-dom";
import { ADMIN_BRAND_FILTER as IDS } from "@/constants/testIds";
import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";

export default function BrandFilter() {
    const [brands, setBrands] = useState([]);
    const [params, setParams] = useSearchParams();
    const selected = params.get("brand") || "";

    useEffect(() => {
        // The brand list is already scoped on the server, so this is the
        // caller's own brands and nothing else — there is no client-side
        // filtering here to get wrong.
        api.get("/admin/brands")
            .then(({ data }) => setBrands(Array.isArray(data) ? data : []))
            .catch(() => setBrands([]));
    }, []);

    if (brands.length < 2) return null;

    const choose = (value) => {
        const next = new URLSearchParams(params);
        if (value) next.set("brand", value);
        else next.delete("brand");
        // `replace`: narrowing and widening a filter is a correction, not a
        // series of places to go back through.
        setParams(next, { replace: true });
    };

    return (
        <label className="flex min-w-0 items-center gap-2">
            <span className="sr-only">Brand</span>
            <select
                value={selected}
                onChange={(e) => choose(e.target.value)}
                data-testid={IDS.root}
                className={`h-7 min-w-0 max-w-[10rem] rounded border border-white/10 bg-background px-1.5 ${TEXT.meta} text-muted-foreground ${CALM} ${FOCUS}`}
            >
                <option value="">All your brands</option>
                {brands.map((b) => (
                    <option
                        key={b.user_id}
                        value={b.user_id}
                        data-testid={IDS.option(b.user_id)}
                    >
                        {b.business_name || b.name || "Unnamed brand"}
                    </option>
                ))}
            </select>
        </label>
    );
}
