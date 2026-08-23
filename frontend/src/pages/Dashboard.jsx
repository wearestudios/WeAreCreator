// `/dashboard`, which is two surfaces behind one path.
//
// A creator and a brand manager both land here and see entirely different
// products — the creator's home and the brand's console. This file is only the
// dispatch, and **both branches are lazy**, each in its own audience's chunk.
//
// While the creator's home lived in this file, a brand opening their own
// dashboard downloaded the whole creator home to reach it, and a creator
// downloaded the brand console. That is the same leak the route split exists
// to close, one level down: the path is shared, the code is not.
//
// The role decision stays here rather than in `App.js` — one place deciding
// what `/dashboard` means, which is also where `justOnboarded` and the admin
// redirect belong.
import React, { Suspense, lazy } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth, homePathFor, isBrandSide } from "@/context/AuthContext";
import RouteFallback from "@/components/RouteFallback";
import { retryImport } from "@/lib/lazyRoute";

const CreatorHome = lazy(() =>
    retryImport(() => import(/* webpackChunkName: "creator" */ "@/pages/CreatorHome")),
);
const BrandDashboardView = lazy(() =>
    retryImport(() => import(/* webpackChunkName: "brand" */ "@/pages/BrandDashboardView")),
);

export default function Dashboard() {
    const { user } = useAuth();
    const location = useLocation();
    if (!user || user === false) return null;
    const justOnboarded = Boolean(location.state?.justOnboarded);

    // Its own Suspense rather than the router's: the boundary above `Routes`
    // has already resolved by the time this renders. A chunk that fails here
    // still reaches the route boundary, which is what turns it into a retry
    // rather than a blank screen.
    return (
        <Suspense fallback={<RouteFallback />}>
            {isBrandSide(user.role) ? (
                <BrandDashboardView user={user} justOnboarded={justOnboarded} />
            ) : user.role === "creator" ? (
                <CreatorHome user={user} justOnboarded={justOnboarded} />
            ) : (
                // Admins have no dashboard of their own — the console is their home.
                <Navigate to={homePathFor(user.role)} replace />
            )}
        </Suspense>
    );
}
