import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Camera, Building2, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

const ROLE_OPTIONS = [
    {
        value: "creator",
        title: "I'm a Creator",
        subtitle: "Food, café & lifestyle storytellers in Bengaluru.",
        Icon: Camera,
    },
    {
        value: "brand",
        title: "I'm a Brand",
        subtitle: "Restaurant, café, or lifestyle brand looking for creators.",
        Icon: Building2,
    },
];

export default function Signup() {
    const { register } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const initialRole = useMemo(() => {
        const r = params.get("role");
        return r === "brand" ? "brand" : "creator";
    }, [params]);

    const [role, setRole] = useState(initialRole);
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        if (password.length < 8) {
            setError("Password must be at least 8 characters.");
            return;
        }
        setSubmitting(true);
        const res = await register({ email, password, name, role });
        setSubmitting(false);
        if (res.ok) {
            toast.success("Account created — welcome to WeAre.");
            const next =
                res.user?.role === "creator" ? "/onboarding/creator" : "/dashboard";
            navigate(next, { replace: true });
        } else {
            setError(res.error);
        }
    };

    return (
        <div
            data-testid="signup-page"
            className="grid min-h-screen grid-cols-1 md:grid-cols-2"
        >
            <div className="relative hidden md:block">
                <img
                    src="https://images.unsplash.com/photo-1596797038530-2c107229654b?auto=format&fit=crop&w=1200&q=80"
                    alt=""
                    className="absolute inset-0 h-full w-full object-cover opacity-55"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-background/40 via-background/60 to-background" />
                <div className="relative flex h-full flex-col justify-between p-12">
                    <Link
                        to="/"
                        className="font-serif text-2xl transition-colors duration-200 hover:text-ember-500"
                    >
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <div className="max-w-md">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            Invite-only
                        </p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            Get on the list. Applications are reviewed by the WeAre team.
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link
                        to="/"
                        className="mb-10 inline-block font-serif text-xl md:hidden"
                    >
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Create account
                    </p>
                    <h1 className="mt-3 font-serif text-4xl leading-none tracking-tight">
                        Join WeAre Creators
                    </h1>
                    <p className="mt-4 text-sm text-muted-foreground">
                        Already a member?{" "}
                        <Link
                            to="/login"
                            data-testid="link-to-login"
                            className="text-ember-500 underline-offset-4 hover:underline"
                        >
                            Log in
                        </Link>
                    </p>

                    <form onSubmit={onSubmit} className="mt-8 space-y-6">
                        <div>
                            <p className="mb-3 text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                I am a
                            </p>
                            <div className="grid grid-cols-2 gap-3">
                                {ROLE_OPTIONS.map(({ value, title, subtitle, Icon }) => {
                                    const active = role === value;
                                    return (
                                        <button
                                            type="button"
                                            key={value}
                                            data-testid={`role-option-${value}`}
                                            onClick={() => setRole(value)}
                                            aria-pressed={active}
                                            className={
                                                "group relative rounded-md border p-4 text-left transition-colors duration-200 " +
                                                (active
                                                    ? "border-ember-500 bg-ember-500/10"
                                                    : "border-white/10 bg-card hover:border-white/25")
                                            }
                                        >
                                            <Icon
                                                className={
                                                    "h-5 w-5 " +
                                                    (active ? "text-ember-500" : "text-muted-foreground")
                                                }
                                            />
                                            <div className="mt-3 text-sm font-medium text-foreground">
                                                {title}
                                            </div>
                                            <div className="mt-1 text-xs text-muted-foreground">
                                                {subtitle}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div>
                            <Label htmlFor="name" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                {role === "brand" ? "Brand name" : "Full name"}
                            </Label>
                            <Input
                                id="name"
                                data-testid="signup-name-input"
                                required
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder={role === "brand" ? "e.g. Toit Brewpub" : "e.g. Priya Rao"}
                            />
                        </div>
                        <div>
                            <Label htmlFor="email" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Email
                            </Label>
                            <Input
                                id="email"
                                data-testid="signup-email-input"
                                type="email"
                                autoComplete="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="you@studio.in"
                            />
                        </div>
                        <div>
                            <Label htmlFor="password" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                Password
                            </Label>
                            <Input
                                id="password"
                                data-testid="signup-password-input"
                                type="password"
                                autoComplete="new-password"
                                required
                                minLength={8}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                placeholder="At least 8 characters"
                            />
                        </div>

                        {error && (
                            <p
                                data-testid="signup-error"
                                className="text-sm text-destructive"
                            >
                                {error}
                            </p>
                        )}

                        <Button
                            type="submit"
                            data-testid="signup-submit-btn"
                            disabled={submitting}
                            className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Creating account…
                                </>
                            ) : (
                                "Create account"
                            )}
                        </Button>
                    </form>
                </div>
            </div>
        </div>
    );
}
