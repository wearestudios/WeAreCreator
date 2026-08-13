import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    // null = checking, false = anonymous, object = authenticated
    const [user, setUser] = useState(null);

    const fetchMe = useCallback(async () => {
        try {
            const { data } = await api.get("/auth/me");
            setUser(data);
        } catch {
            setUser(false);
        }
    }, []);

    useEffect(() => {
        fetchMe();
    }, [fetchMe]);

    // Admin-only email/password login
    const loginAdmin = async (email, password) => {
        try {
            const { data } = await api.post("/auth/login", { email, password });
            setUser(data);
            return { ok: true, user: data };
        } catch (e) {
            return { ok: false, error: formatApiError(e) };
        }
    };

    // WhatsApp OTP — request a code
    const requestOtp = async ({ phone, purpose, name, role }) => {
        try {
            const { data } = await api.post("/auth/otp/request", {
                phone,
                purpose,
                name,
                role,
            });
            return { ok: true, ...data };
        } catch (e) {
            return { ok: false, error: formatApiError(e), status: e?.response?.status };
        }
    };

    // WhatsApp OTP — verify code (logs in or completes signup)
    const verifyOtp = async ({ phone, code, purpose, name, role }) => {
        try {
            const { data } = await api.post("/auth/otp/verify", {
                phone,
                code,
                purpose,
                name,
                role,
            });
            setUser(data);
            return { ok: true, user: data };
        } catch (e) {
            return { ok: false, error: formatApiError(e), status: e?.response?.status };
        }
    };

    const logout = async () => {
        try {
            await api.post("/auth/logout");
        } catch {
            /* ignore */
        }
        setUser(false);
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loginAdmin,
                requestOtp,
                verifyOtp,
                logout,
                refresh: fetchMe,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
};
