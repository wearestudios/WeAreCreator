import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Camera, Building2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import OtpForm from "@/components/OtpForm";

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
    const { requestOtp, verifyOtp } = useAuth();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const initialRole = useMemo(() => {
        const r = params.get("role");
        return r === "brand" ? "brand" : "creator";
    }, [params]);

    const [role, setRole] = useState(initialRole);
    const [name, setName] = useState("");
    const [phone, setPhone] = useState("");

    return (
        <div data-testid="signup-page" className="grid min-h-screen grid-cols-1 md:grid-cols-2">
            <div className="relative hidden md:block">
                <img
                    src="https://images.unsplash.com/photo-1596797038530-2c107229654b?auto=format&fit=crop&w=1200&q=80"
                    alt=""
                    className="absolute inset-0 h-full w-full object-cover opacity-55"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-background/40 via-background/60 to-background" />
                <div className="relative flex h-full flex-col justify-between p-12">
                    <Link to="/" className="font-serif text-2xl transition-colors duration-200 hover:text-ember-500">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <div className="max-w-md">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">Invite-only</p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            Get on the list. Applications are reviewed by the WeAre team.
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link to="/" className="mb-10 inline-block font-serif text-xl md:hidden">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <p className="text-xs uppercase tracking-[0.22em] text-ember-500/90">
                        <span className="mr-2 inline-block h-px w-6 translate-y-[-3px] bg-ember-500/80 align-middle" />
                        Create account
                    </p>
                    <h1 className="mt-5 font-serif text-5xl leading-[0.95] tracking-tight">
                        Join <span className="italic">WeAre</span> Creators
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

                    <div className="mt-8">
                        <p className="mb-3 text-xs uppercase tracking-[0.15em] text-muted-foreground">I am a</p>
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
                                        <Icon className={"h-5 w-5 " + (active ? "text-ember-500" : "text-muted-foreground")} />
                                        <div className="mt-3 text-sm font-medium text-foreground">{title}</div>
                                        <div className="mt-1 text-xs text-muted-foreground">{subtitle}</div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <OtpForm
                        phone={phone}
                        setPhone={setPhone}
                        canSubmitPhoneStep={name.trim().length > 0}
                        onRequest={(p) => requestOtp({ phone: p, purpose: "signup", name: name.trim(), role })}
                        onVerify={(code) => verifyOtp({
                            phone: phone.trim().replace(/[\s\-()]/g, ""),
                            code,
                            purpose: "signup",
                            name: name.trim(),
                            role,
                        })}
                        onVerified={(user) => {
                            toast.success("Account created — welcome to WeAre.");
                            const next =
                                user?.role === "creator"
                                    ? "/onboarding/creator"
                                    : user?.role === "brand"
                                    ? "/onboarding/brand"
                                    : "/dashboard";
                            navigate(next, { replace: true });
                        }}
                        hint="We'll WhatsApp a 6-digit code to verify this number."
                        extraTop={
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
                        }
                    />

                    <p className="mt-8 text-xs text-muted-foreground">
                        By signing up you agree to our terms & privacy.
                    </p>
                </div>
            </div>
        </div>
    );
}
