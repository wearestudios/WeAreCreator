import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
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
            <div className="relative hidden md:block">
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
                        className="font-serif text-2xl transition-colors duration-200 hover:text-ember-500"
                    >
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <div className="max-w-md">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">Bengaluru</p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            The city's most curated creator-brand network.
                        </p>
                    </div>
                </div>
            </div>

            {/* Right form */}
            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link to="/" className="mb-10 inline-block font-serif text-xl md:hidden">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>

                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Welcome back</p>
                    <h1 className="mt-3 font-serif text-4xl leading-none tracking-tight">
                        Log in with WhatsApp
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
                            toast.success(`Welcome back, ${user.name}`);
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
