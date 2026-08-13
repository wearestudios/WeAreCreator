import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const from = location.state?.from || "/dashboard";

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        const res = await login(email, password);
        setSubmitting(false);
        if (res.ok) {
            toast.success(`Welcome back, ${res.user.name}`);
            navigate(from, { replace: true });
        } else {
            setError(res.error);
        }
    };

    return (
        <div
            data-testid="login-page"
            className="grid min-h-screen grid-cols-1 md:grid-cols-2"
        >
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
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Bengaluru
                        </p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            The city's most curated creator-brand network.
                        </p>
                    </div>
                </div>
            </div>

            {/* Right form */}
            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link
                        to="/"
                        className="mb-10 inline-block font-serif text-xl md:hidden"
                    >
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>

                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Welcome back
                    </p>
                    <h1 className="mt-3 font-serif text-4xl leading-none tracking-tight">
                        Log in to your account
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

                    <form onSubmit={onSubmit} className="mt-10 space-y-5">
                        <div>
                            <Label htmlFor="email" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Email
                            </Label>
                            <Input
                                id="email"
                                data-testid="login-email-input"
                                type="email"
                                autoComplete="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 text-foreground focus-visible:ring-ember-500"
                                placeholder="you@studio.in"
                            />
                        </div>
                        <div>
                            <Label htmlFor="password" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Password
                            </Label>
                            <Input
                                id="password"
                                data-testid="login-password-input"
                                type="password"
                                autoComplete="current-password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 text-foreground focus-visible:ring-ember-500"
                                placeholder="••••••••"
                            />
                        </div>

                        {error && (
                            <p
                                data-testid="login-error"
                                className="text-sm text-destructive"
                            >
                                {error}
                            </p>
                        )}

                        <Button
                            type="submit"
                            data-testid="login-submit-btn"
                            disabled={submitting}
                            className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Signing in…
                                </>
                            ) : (
                                "Log in"
                            )}
                        </Button>
                    </form>

                    <p className="mt-8 text-xs text-muted-foreground">
                        By logging in you agree to our terms & privacy.
                    </p>
                </div>
            </div>
        </div>
    );
}
