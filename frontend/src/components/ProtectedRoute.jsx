import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

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
        return <Navigate to="/dashboard" replace />;
    }
    return children;
};
