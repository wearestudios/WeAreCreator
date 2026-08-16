import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";

const AuthContext = createContext(null);

/**
 * The two role names a brand's own login can hold.
 *
 * `brand_manager` is the named person a brand registers behind and its only
 * login; `brand` is what that role used to be called, and accounts created
 * before the rename still carry it. Every route guard and role check on the
 * brand side spreads this rather than naming a string, because naming one
 * string is how a whole role gets locked out of its own product.
 */
export const BRAND_ROLES = ["brand", "brand_manager"];

export const isBrandSide = (role) => BRAND_ROLES.includes(role);

/**
 * Where a signed-in user belongs after login, or when they land somewhere their
 * role can't see. Admins have no dashboard — the console is their only surface —
 * so sending them to /dashboard just bounced them straight back out.
 *
 * Exported from here so the navbar, the route guard and the dashboard root all
 * agree; three copies of this rule is how you get a redirect loop.
 */
export const homePathFor = (role) =>
    role === "admin" ? "/admin" : role === "campaign_manager" ? "/manager" : "/dashboard";

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
    const requestOtp = async ({
        phone,
        purpose,
        name,
        role,
        accept_terms,
        // A brand registers one named person, who becomes its only login.
        // Passed straight through; the server ignores them for creators.
        manager_name,
        manager_designation,
        manager_email,
    }) => {
        try {
            const { data } = await api.post("/auth/otp/request", {
                phone,
                purpose,
                name,
                role,
                accept_terms,
                manager_name,
                manager_designation,
                manager_email,
            });
            return { ok: true, ...data };
        } catch (e) {
            return { ok: false, error: formatApiError(e), status: e?.response?.status };
        }
    };

    // WhatsApp OTP — verify code (logs in or completes signup)
    const verifyOtp = async ({
        phone,
        code,
        purpose,
        name,
        role,
        accept_terms,
        manager_name,
        manager_designation,
        manager_email,
    }) => {
        try {
            const { data } = await api.post("/auth/otp/verify", {
                phone,
                code,
                purpose,
                name,
                role,
                accept_terms,
                manager_name,
                manager_designation,
                manager_email,
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

    /**
     * Leave a view-as session and return to being yourself.
     *
     * A full reload rather than a re-fetch: every page in the app has state
     * loaded as the impersonated user — dashboards, lists, counts — and
     * re-rendering with a new identity over the top of it would leave one
     * person's numbers on another person's screen.
     */
    const stopImpersonating = useCallback(async () => {
        try {
            await api.post("/auth/impersonate/stop");
        } finally {
            window.location.assign("/admin");
        }
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                loginAdmin,
                requestOtp,
                verifyOtp,
                logout,
                refresh: fetchMe,
                // Read straight off /auth/me rather than remembered from when
                // the session started: a second tab, or a session that expired
                // while this one sat open, would otherwise show the wrong
                // thing. Null when nobody is being impersonated.
                impersonation: user && user !== false ? user.impersonation || null : null,
                // The one question the whole UI asks: may this session change
                // anything? The server refuses regardless — this is only so
                // buttons do not offer what would be refused.
                readOnly: Boolean(
                    user && user !== false && user.impersonation?.read_only,
                ),
                stopImpersonating,
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
