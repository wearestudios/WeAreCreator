import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import AdminLogin from "@/pages/AdminLogin";
import Dashboard from "@/pages/Dashboard";
import CreatorOnboarding from "@/pages/CreatorOnboarding";
import BrandOnboarding from "@/pages/BrandOnboarding";
import PostCampaign from "@/pages/PostCampaign";
import Campaigns from "@/pages/Campaigns";
import CampaignDetail from "@/pages/CampaignDetail";
import AdminConsole from "@/pages/AdminConsole";
import BrandCreatorDirectory from "@/pages/BrandCreatorDirectory";

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
                        <Route
                            path="/onboarding/brand"
                            element={
                                <ProtectedRoute roles={["brand"]}>
                                    <BrandOnboarding />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/campaigns/new"
                            element={
                                <ProtectedRoute roles={["brand"]}>
                                    <PostCampaign />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/brand/creators"
                            element={
                                <ProtectedRoute roles={["brand", "admin"]}>
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
                                <ProtectedRoute roles={["creator", "brand", "admin"]}>
                                    <CampaignDetail />
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
                <Toaster
                    theme="dark"
                    position="top-right"
                    toastOptions={{
                        style: {
                            background: "hsl(24 8% 8%)",
                            color: "hsl(30 12% 96%)",
                            border: "1px solid hsl(24 6% 16%)",
                        },
                    }}
                />
            </AuthProvider>
        </div>
    );
}

export default App;
