import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { notifySuccess } from "@/lib/feedback";
import { useAuth } from "@/context/AuthContext";
import OtpForm from "@/components/OtpForm";

export default function Login() {
    const { requestOtp, verifyOtp } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [phone, setPhone] = useState("");

    const from = location.state?.from || "/dashboard";

    return (
        <div data-testid="login-page" className="grid min-h-screen grid-cols-1 md:grid-cols-2">
            {/* Left visual */}
            <div className="media-frame relative hidden md:block">
                <img
                    src="https://images.unsplash.com/photo-1726835498689-b4f6dbcdbdfb?auto=format&fit=crop&w=1200&q=80"
                    alt=""
                    className="absolute inset-0 h-full w-full object-cover opacity-60"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-background/40 via-background/60 to-background" />
                <div className="relative flex h-full flex-col justify-between p-12">
                    <Link
                        to="/"
                        data-testid="auth-logo"
                        className="-my-2 min-h-[2.75rem] py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:my-0 md:min-h-0 md:py-0 inline-flex items-center font-serif text-2xl transition-colors duration-200 hover:text-ember-500"
                    >
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <div className="max-w-md">
                        {/* Was "Every city that matters", which is the exact
                            geography overclaim banned everywhere else on the
                            site — the marketing pages are tested for it and
                            this screen sat outside those tests. The network is
                            deepest in Bengaluru and that is what we say. */}
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">Bengaluru</p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            Paid briefs, rates agreed in writing, and a report at the
                            end.
                        </p>
                    </div>
                </div>
            </div>

            {/* Right form */}
            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link to="/" className="mb-10 -my-2 inline-flex min-h-[2.75rem] items-center py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background font-serif text-xl md:hidden">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>

                    <p className="text-xs uppercase tracking-[0.22em] text-ember-500/90">
                        <span className="mr-2 inline-block h-px w-6 translate-y-[-3px] bg-ember-500/80 align-middle" />
                        Welcome back
                    </p>
                    <h1 className="mt-5 font-serif text-fluid-5xl leading-[0.95] tracking-tight">
                        Log in with <span className="italic">WhatsApp</span>
                    </h1>
                    <p className="mt-4 text-sm text-muted-foreground">
                        New here?{" "}
                        <Link
                            to="/signup"
                            data-testid="link-to-signup"
                            className="text-ember-500 underline-offset-4 hover:underline"
                        >
                            Create an account
                        </Link>
                    </p>

                    <OtpForm
                        phone={phone}
                        setPhone={setPhone}
                        onRequest={(p) => requestOtp({ phone: p, purpose: "login" })}
                        onVerify={(code) => verifyOtp({ phone: phone.trim().replace(/[\s\-()]/g, ""), code, purpose: "login" })}
                        onVerified={(user) => {
                            notifySuccess(`Welcome back, ${user.name}`);
                            navigate(from, { replace: true });
                        }}
                        hint="Use the WhatsApp number linked to your account."
                    />

                    <p className="mt-8 text-xs text-muted-foreground">
                        Team admin?{" "}
                        <Link
                            to="/admin/login"
                            data-testid="link-to-admin-login"
                            className="text-ember-500 underline-offset-4 hover:underline"
                        >
                            Use email login
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
