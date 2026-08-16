import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function AdminLogin() {
    const { loginAdmin } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const from = location.state?.from || "/admin";

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        const res = await loginAdmin(email, password);
        setSubmitting(false);
        if (res.ok) {
            toast.success(`Welcome, ${res.user.name}`);
            navigate(from, { replace: true });
        } else {
            setError(res.error);
        }
    };

    return (
        <div data-testid="admin-login-page" className="grid min-h-screen place-items-center bg-background p-6 grain-page">
            <div className="w-full max-w-md">
                <Link to="/" className="mb-8 inline-block font-serif text-2xl">
                    WeAre <span className="text-ember-500">Creators</span>
                </Link>
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Team admin</p>
                <h1 className="mt-3 font-serif text-4xl leading-none tracking-tight">
                    Sign in to the console
                </h1>
                <p className="mt-4 text-sm text-muted-foreground">
                    Creators and brands, please{" "}
                    <Link to="/login" data-testid="link-to-login" className="text-ember-500 underline-offset-4 hover:underline">
                        log in with WhatsApp
                    </Link>
                    .
                </p>

                <form onSubmit={onSubmit} className="mt-10 space-y-5">
                    <div>
                        <Label htmlFor="email" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Email
                        </Label>
                        <Input
                            id="email"
                            data-testid="admin-login-email-input"
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="mt-2 h-11 border-white/10 bg-card/60 text-foreground focus-visible:ring-ember-500"
                            placeholder="you@wearemonk.in"
                        />
                    </div>
                    <div>
                        <Label htmlFor="password" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            Password
                        </Label>
                        <Input
                            id="password"
                            data-testid="admin-login-password-input"
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
                        <p data-testid="admin-login-error" className="text-sm text-destructive">
                            {error}
                        </p>
                    )}

                    <Button
                        type="submit"
                        data-testid="admin-login-submit-btn"
                        disabled={submitting}
                        className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {submitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Signing in…
                            </>
                        ) : (
                            "Log in"
                        )}
                    </Button>
                </form>
            </div>
        </div>
    );
}
