import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { TOAST_DURATION } from "@/lib/feedback";
import { AuthProvider, BRAND_ROLES } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ImpersonationBanner } from "@/components/ImpersonationBanner";
import ErrorBoundary from "@/components/ErrorBoundary";
import { installGlobalErrorHandlers } from "@/lib/globalErrors";
import { installOfflineQueue } from "@/lib/offlineQueue";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import AdminLogin from "@/pages/AdminLogin";
import Dashboard from "@/pages/Dashboard";
import ShootCalendar from "@/pages/ShootCalendar";
import SelfCheckIn from "@/pages/SelfCheckIn";
import InstagramCallback from "@/pages/InstagramCallback";
import CreatorOnboarding from "@/pages/CreatorOnboarding";
import BrandOnboarding from "@/pages/BrandOnboarding";
import PostCampaign from "@/pages/PostCampaign";
import Campaigns from "@/pages/Campaigns";
import CampaignDetail from "@/pages/CampaignDetail";
import AdminConsole from "@/pages/AdminConsole";
import {
    AuditRoute,
    BrandReviewsRoute,
    BrandsRoute,
    CampaignReviewsRoute,
    CampaignsRoute,
    CreatorReviewsRoute,
    CreatorsRoute,
    OverviewRoute,
    QueueRoute,
} from "@/components/admin/routes";
import AdminCampaignDetail from "@/components/admin/CampaignDetailPage";
import AdminCreatorDetail from "@/components/admin/CreatorDetailPage";
import AdminBrandDetail from "@/components/admin/BrandDetailPage";
import AdminCollaborationDetail from "@/components/admin/CollaborationDetailPage";
import ApplicationDetail from "@/components/application/ApplicationDetail";
import CreatorProfile from "@/pages/CreatorProfile";
import ManagerHome from "@/pages/ManagerHome";
import ManagerCampaign from "@/pages/ManagerCampaign";
import BrandCreatorDirectory from "@/pages/BrandCreatorDirectory";
import BrandCampaignApplicants from "@/pages/BrandCampaignApplicants";
import { Terms, Privacy } from "@/pages/Legal";

// Attached at module load rather than in an effect, so a rejection thrown
// while the first render is still in flight is already covered.
installGlobalErrorHandlers();
// Drains anything a previous session left behind before the first render, so a
// manager whose phone died mid-shift finds their check-ins already sent.
installOfflineQueue();

/**
 * The second layer: a crash inside a page, caught below the router.
 *
 * The root boundary would also catch this, but it cannot un-catch it — the
 * fallback would stay until a manual reload, even after the user navigated
 * somewhere that works. This one resets on the pathname, so leaving the broken
 * screen is enough. It also sits below `ImpersonationBanner`, which therefore
 * survives a page crash — an admin must never be left acting as somebody else
 * with nothing on screen saying so.
 */
function RouteBoundary({ children }) {
    const { pathname } = useLocation();
    return (
        <ErrorBoundary variant="page" name="route" resetOn={pathname}>
            {children}
        </ErrorBoundary>
    );
}

function App() {
    return (
        <div className="App">
            {/* Outside AuthProvider and the router on purpose — those two can
                throw as easily as anything else, and a boundary inside them
                would go down with them. The fallback uses plain anchors and a
                real reload for exactly the same reason: it must not need the
                router it may be standing in for. */}
            <ErrorBoundary variant="page" name="app">
            <AuthProvider>
                <BrowserRouter>
                    {/* Above the router on purpose. Inside it, a route could
                        be added tomorrow that never renders the banner, and
                        the one requirement of view-as is that you always know
                        you are in it. */}
                    <ImpersonationBanner />
                    <RouteBoundary>
                    <Routes>
                        <Route path="/" element={<Landing />} />
                        <Route path="/login" element={<Login />} />
                        <Route path="/signup" element={<Signup />} />
                        <Route path="/admin/login" element={<AdminLogin />} />
                        <Route path="/terms" element={<Terms />} />
                        <Route path="/privacy" element={<Privacy />} />
                        <Route
                            path="/dashboard"
                            element={
                                <ProtectedRoute>
                                    <Dashboard />
                                </ProtectedRoute>
                            }
                        />
                        {/* The shoot calendar. One page, three scopes — the
                            endpoint decides what each role sees, so the route
                            takes the union of the three rather than three
                            near-identical routes. */}
                        <Route
                            path="/calendar"
                            element={
                                <ProtectedRoute
                                    roles={[...BRAND_ROLES, "campaign_manager", "admin"]}
                                >
                                    <ShootCalendar />
                                </ProtectedRoute>
                            }
                        />
                        {/* Opened by a camera at a venue. Creator-only: the
                            code checks a booking, and nobody else has one. */}
                        <Route
                            path="/check-in"
                            element={
                                <ProtectedRoute roles={["creator"]}>
                                    <SelfCheckIn />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/onboarding/creator"
                            element={
                                <ProtectedRoute roles={["creator"]}>
                                    <CreatorOnboarding />
                                </ProtectedRoute>
                            }
                        />
                        {/* Where Instagram redirects back to after OAuth.
                            Must match INSTAGRAM_REDIRECT_URI on the server. */}
                        <Route
                            path="/onboarding/creator/instagram"
                            element={
                                <ProtectedRoute roles={["creator"]}>
                                    <InstagramCallback />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/onboarding/brand"
                            element={
                                <ProtectedRoute roles={BRAND_ROLES}>
                                    <BrandOnboarding />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/campaigns/new"
                            element={
                                <ProtectedRoute roles={BRAND_ROLES}>
                                    <PostCampaign />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/campaigns/:id/edit"
                            element={
                                <ProtectedRoute roles={BRAND_ROLES}>
                                    <PostCampaign />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/brand/campaigns/:id/applicants"
                            element={
                                <ProtectedRoute roles={[...BRAND_ROLES, "admin"]}>
                                    <BrandCampaignApplicants />
                                </ProtectedRoute>
                            }
                        />
                        {/* Your own profile, read-only. Editing lives at
                            /onboarding/creator and is reached from here — it
                            used to be the only way to see your own details. */}
                        <Route
                            path="/profile"
                            element={
                                <ProtectedRoute roles={["creator"]}>
                                    <CreatorProfile />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/brand/applications/:id"
                            element={
                                <ProtectedRoute roles={[...BRAND_ROLES, "admin"]}>
                                    <ApplicationDetail
                                        backTo="/brand/dashboard"
                                        backLabel="Dashboard"
                                        standalone
                                    />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/brand/creators"
                            element={
                                <ProtectedRoute roles={[...BRAND_ROLES, "admin"]}>
                                    <BrandCreatorDirectory />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/campaigns"
                            element={
                                <ProtectedRoute roles={["creator", "admin"]}>
                                    <Campaigns />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/campaigns/:id"
                            element={
                                <ProtectedRoute roles={["creator", ...BRAND_ROLES, "admin"]}>
                                    <CampaignDetail />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/manager"
                            element={
                                <ProtectedRoute roles={["campaign_manager", "admin"]}>
                                    <ManagerHome />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/manager/campaigns/:id"
                            element={
                                <ProtectedRoute roles={["campaign_manager", "admin"]}>
                                    <ManagerCampaign />
                                </ProtectedRoute>
                            }
                        />
                        {/* The console is a layout, and everything under it is
                            its own address. `/admin/login` is declared above
                            this block and stays a separate page — it is the
                            only /admin path that must not require an admin. */}
                        <Route
                            path="/admin"
                            element={
                                <ProtectedRoute roles={["admin"]}>
                                    <AdminConsole />
                                </ProtectedRoute>
                            }
                        >
                            <Route index element={<OverviewRoute />} />
                            <Route path="creator-reviews" element={<CreatorReviewsRoute />} />
                            <Route path="campaign-reviews" element={<CampaignReviewsRoute />} />
                            <Route path="brand-reviews" element={<BrandReviewsRoute />} />
                            <Route path="queue" element={<QueueRoute />} />

                            {/* List, then detail. Nested rather than sibling
                                paths so the tab strip stays put and only the
                                panel under it changes. */}
                            <Route path="campaigns" element={<CampaignsRoute />} />
                            <Route path="campaigns/:id" element={<AdminCampaignDetail />} />
                            <Route path="creators" element={<CreatorsRoute />} />
                            <Route path="creators/:id" element={<AdminCreatorDetail />} />
                            <Route path="brands" element={<BrandsRoute />} />
                            <Route path="brands/:id" element={<AdminBrandDetail />} />
                            {/* No list route: collaborations are reached from
                                the queue, a campaign or a creator, which is
                                where the question about one always starts. */}
                            <Route
                                path="collaborations/:id"
                                element={<AdminCollaborationDetail />}
                            />
                            {/* One application, on its own page. Same
                                component as the brand's route below — the two
                                consoles reading one application through one
                                implementation is what stops them describing it
                                differently. */}
                            <Route
                                path="applications/:id"
                                element={
                                    <ApplicationDetail
                                        backTo="/admin/campaigns"
                                        backLabel="Campaigns"
                                        crumbs={[
                                            { label: "Console", to: "/admin" },
                                            { label: "Applications" },
                                        ]}
                                        entityLinks
                                    />
                                }
                            />
                            <Route path="audit" element={<AuditRoute />} />
                            {/* A bad path under /admin lands on the console
                                rather than the marketing site. */}
                            <Route path="*" element={<Navigate to="/admin" replace />} />
                        </Route>
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                    </RouteBoundary>
                </BrowserRouter>
                {/* One position for every toast in the app.
                    top-center rather than a corner: on a phone a corner toast
                    is either under the notch or over the bottom-anchored
                    primary action, and this product is mostly used on phones.
                    Durations and the success/error treatments come from
                    lib/feedback.js, so no call site sets its own. */}
                <Toaster
                    theme="dark"
                    position="top-center"
                    closeButton
                    duration={TOAST_DURATION.success}
                    toastOptions={{
                        classNames: {
                            toast:
                                "group rounded-lg border border-white/10 bg-background/95 " +
                                "text-foreground shadow-xl shadow-black/50 backdrop-blur-xl grain-surface",
                            title: "text-sm leading-snug",
                            description: "text-xs text-muted-foreground",
                            // Success and failure must be distinguishable
                            // without reading — a green rule and a red one,
                            // on the leading edge where the eye lands first.
                            success: "border-l-2 border-l-emerald-400",
                            error: "border-l-2 border-l-red-400",
                            info: "border-l-2 border-l-sky-400",
                            warning: "border-l-2 border-l-amber-400",
                            actionButton:
                                "rounded-full bg-ember-500 px-3 text-black hover:bg-ember-400",
                            closeButton:
                                "border-white/15 bg-card text-muted-foreground hover:text-foreground",
                        },
                    }}
                />
            </AuthProvider>
            </ErrorBoundary>
        </div>
    );
}

export default App;
