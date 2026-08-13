import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth, homePathFor } from "@/context/AuthContext";

export const ProtectedRoute = ({ children, roles }) => {
    const { user } = useAuth();

    if (user === null) {
        return (
            <div
                data-testid="auth-loading"
                className="flex min-h-screen items-center justify-center bg-background text-muted-foreground"
            >
                <div className="animate-pulse text-sm tracking-[0.2em] uppercase">
                    Loading…
                </div>
            </div>
        );
    }

    if (user === false) return <Navigate to="/login" replace />;

    if (roles && !roles.includes(user.role)) {
        // Straight to the role's own home, not via /dashboard — an admin bounced
        // there would only be redirected again.
        return <Navigate to={homePathFor(user.role)} replace />;
    }
    return children;
};
