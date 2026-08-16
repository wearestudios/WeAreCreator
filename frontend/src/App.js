import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { TOAST_DURATION } from "@/lib/feedback";
import { AuthProvider, BRAND_ROLES } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import AdminLogin from "@/pages/AdminLogin";
import Dashboard from "@/pages/Dashboard";
import InstagramCallback from "@/pages/InstagramCallback";
import CreatorOnboarding from "@/pages/CreatorOnboarding";
import BrandOnboarding from "@/pages/BrandOnboarding";
import PostCampaign from "@/pages/PostCampaign";
import Campaigns from "@/pages/Campaigns";
import CampaignDetail from "@/pages/CampaignDetail";
import AdminConsole from "@/pages/AdminConsole";
import ManagerHome from "@/pages/ManagerHome";
import ManagerCampaign from "@/pages/ManagerCampaign";
import BrandCreatorDirectory from "@/pages/BrandCreatorDirectory";
import BrandCampaignApplicants from "@/pages/BrandCampaignApplicants";
import { Terms, Privacy } from "@/pages/Legal";

function App() {
    return (
        <div className="App">
            <AuthProvider>
                <BrowserRouter>
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
                        <Route
                            path="/admin"
                            element={
                                <ProtectedRoute roles={["admin"]}>
                                    <AdminConsole />
                                </ProtectedRoute>
                            }
                        />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
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
        </div>
    );
}

export default App;
