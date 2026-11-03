import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { notifySuccess } from "@/lib/feedback";
import { useAuth } from "@/context/AuthContext";
import OtpForm from "@/components/OtpForm";
import { HERO_EYEBROW } from "@/lib/siteNav";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import useWide from "@/lib/useWide";
import Logo from "@/components/brand/Logo";

export default function Login() {
    const { requestOtp, verifyOtp } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [phone, setPhone] = useState("");
    const wide = useWide();

    const from = location.state?.from || "/dashboard";

    return (
        <div data-testid="login-page" className="grid min-h-screen grid-cols-1 md:grid-cols-2">
            {/* Left visual */}
            <div className="relative hidden md:block">
                <PlaceholderImage
                    // PLACEHOLDER IMAGE: Creator and brand manager reviewing a shoot plan on a phone at a venue table, portrait crop for the auth aside.
                    slot="auth-login"
                    fill
                    sizes="50vw"
                    // The first thing on screen from `md`, and not on screen
                    // at all below it: the aside is `hidden` there, and an
                    // eager image inside `display: none` is still fetched —
                    // a phone would download a picture it never draws. Lazy
                    // on a phone is the one way not to.
                    eager={wide}
                    className="opacity-60"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-background/40 via-background/60 to-background" />
                <div className="relative flex h-full flex-col justify-between p-12">
                    <Link
                        to="/"
                        data-testid="auth-logo"
                        className="-my-2 min-h-[2.75rem] py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background md:my-0 md:min-h-0 md:py-0 inline-flex items-center transition-opacity duration-200 hover:opacity-80"
                    >
                        <Logo variant="horizontal" height={32} />
                    </Link>
                    <div className="relative">
                        {/* **The text's own ground.** The eyebrow is 12px red
                            and needs 4.5:1; red on the navy itself is about
                            4.9:1, so it has to sit on navy and not on a
                            picture. Measured against the photograph under the
                            gradient alone it read 2.7–3.0:1 (and 2.4–2.9:1
                            against the drawing it replaced). Raising the
                            whole gradient far enough would black out the
                            middle of the photograph, so this is solid navy
                            under the text block and a 10rem fade above it —
                            anchored to the text, not to the aside, because
                            the headline wraps to more lines on a narrow
                            screen and a fixed height would leave the eyebrow
                            on the picture there. -inset-x-12 is the aside's
                            own padding, so it spans edge to edge. */}
                        <div
                            aria-hidden
                            data-testid="auth-aside-scrim"
                            className="absolute -inset-x-12 -bottom-12 -top-40 bg-[linear-gradient(to_top,hsl(var(--background))_calc(100%_-_10rem),transparent)]"
                        />
                        <div className="relative max-w-md">
                            {/* Two corrections, in order. It said "Every city
                                that matters" — the exact geography overclaim
                                banned everywhere else on the site, which this
                                screen sat outside the tests for. That was replaced
                                with "Bengaluru", which was true and still wrong
                                here: this is the screen somebody signs in from
                                anywhere, and naming one city on it says the
                                product is not for them. It carries the shared
                                eyebrow now, which makes no geographic claim in
                                either direction. */}
                            <p className="text-xs uppercase tracking-[0.2em] text-primary">
                                {HERO_EYEBROW}
                            </p>
                            <p className="mt-4 font-serif text-4xl leading-tight">
                                Paid briefs, rates agreed in writing, and a report at the
                                end.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right form */}
            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link to="/" className="mb-10 -my-2 inline-flex min-h-[2.75rem] items-center py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background md:hidden">
                        <Logo variant="stacked" height={72} />
                    </Link>

                    <p className="text-xs uppercase tracking-[0.22em] text-primary">
                        <span className="mr-2 inline-block h-px w-6 translate-y-[-3px] bg-primary/80 align-middle" />
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
                            className="text-primary underline-offset-4 hover:underline"
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
                            className="text-primary underline-offset-4 hover:underline"
                        >
                            Use email login
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
