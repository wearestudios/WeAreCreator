// Where Instagram sends the creator back to.
//
// The code lands in the URL, this page hands it to the server, and the server
// does the two token exchanges — the code never becomes a token in the
// browser. All this page decides is what to say about the outcome, and the
// outcome that matters is the personal-account one: it is the most common
// failure and the most fixable, so it gets the whole screen rather than a
// line of red text.
import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AlertCircle, BadgeCheck, Instagram, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/Navbar";
import { api, apiErrorCode, formatApiError } from "@/lib/api";
import { NotProfessionalHelp } from "@/components/creator/InstagramConnect";
import { CREATOR_INSTAGRAM_CALLBACK as IDS } from "@/constants/testIds";

export default function InstagramCallback() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    // React 18's StrictMode double-invokes effects in development, and the
    // state is single-use — a second exchange would always fail. Guard it.
    const started = useRef(false);
    const [state, setState] = useState({ phase: "working", message: "", username: null });
    const [retrying, setRetrying] = useState(false);

    useEffect(() => {
        if (started.current) return;
        started.current = true;

        const code = params.get("code");
        const oauthState = params.get("state");
        const denied = params.get("error");

        if (denied) {
            setState({
                phase: "error",
                message:
                    params.get("error_description") ||
                    "Instagram didn't complete the connection. Nothing has changed on your profile.",
            });
            return;
        }
        if (!code || !oauthState) {
            setState({
                phase: "error",
                message: "That link is missing something. Start the connection again from your profile.",
            });
            return;
        }

        (async () => {
            try {
                const { data } = await api.post("/creator/instagram/callback", {
                    code,
                    state: oauthState,
                });
                setState({ phase: "success", message: "", username: data.username });
                toast.success("Instagram connected — your numbers are verified");
                // Long enough to read the confirmation, short enough not to
                // feel like a dead end.
                setTimeout(() => navigate("/onboarding/creator", { replace: true }), 1800);
            } catch (e) {
                setState({
                    phase: apiErrorCode(e) === "not_professional" ? "not_professional" : "error",
                    message: formatApiError(e),
                });
            }
        })();
    }, [params, navigate]);

    const retry = async () => {
        setRetrying(true);
        try {
            const { data } = await api.post("/creator/instagram/connect");
            window.location.assign(data.authorize_url);
        } catch (e) {
            setState({ phase: "error", message: formatApiError(e) });
            setRetrying(false);
        }
    };

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background grain-page">
            <Navbar />
            <main className="mx-auto max-w-xl px-5 py-16 md:px-6 md:py-24">
                <p className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                    <Instagram className="h-3.5 w-3.5" />
                    Instagram
                </p>

                {state.phase === "working" && (
                    <div data-testid={IDS.working} className="mt-6 flex items-center gap-3">
                        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
                        <p className="font-serif text-2xl leading-tight">Connecting your account…</p>
                    </div>
                )}

                {state.phase === "success" && (
                    <div data-testid={IDS.success} className="mt-6">
                        <h1 className="font-serif text-3xl leading-tight tracking-tight">
                            Connected.
                        </h1>
                        <p className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-300">
                            <BadgeCheck className="h-4 w-4" />
                            {state.username ? `@${state.username}` : "Your account"} is verified.
                        </p>
                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                            Brands will see your real follower count from now on. We
                            refresh it every 12 hours — taking you back to your profile.
                        </p>
                    </div>
                )}

                {state.phase === "not_professional" && (
                    <div className="mt-6 space-y-6">
                        <h1 className="font-serif text-3xl leading-tight tracking-tight">
                            Almost — one setting to change.
                        </h1>
                        <NotProfessionalHelp testid={IDS.notProfessional} message={state.message} />
                        <div className="flex flex-wrap items-center gap-3">
                            <Button
                                type="button"
                                onClick={retry}
                                disabled={retrying}
                                data-testid={IDS.retry}
                                className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                {retrying ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <Instagram className="mr-2 h-4 w-4" />
                                )}
                                I've switched — try again
                            </Button>
                            <Link
                                to="/onboarding/creator"
                                data-testid={IDS.back}
                                className="inline-flex min-h-[3rem] items-center text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                            >
                                Back to my profile
                            </Link>
                        </div>
                    </div>
                )}

                {state.phase === "error" && (
                    <div data-testid={IDS.error} className="mt-6 space-y-6">
                        <h1 className="font-serif text-3xl leading-tight tracking-tight">
                            That didn't go through.
                        </h1>
                        <p className="flex items-start gap-2 rounded-md border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm leading-relaxed text-red-200">
                            <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
                            {state.message}
                        </p>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                            Nothing has changed on your profile, and your self-reported
                            follower count is still what brands see.
                        </p>
                        <div className="flex flex-wrap items-center gap-3">
                            <Button
                                type="button"
                                onClick={retry}
                                disabled={retrying}
                                data-testid={IDS.retry}
                                className="h-12 rounded-full bg-ember-500 text-black hover:bg-ember-400"
                            >
                                {retrying ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <Instagram className="mr-2 h-4 w-4" />
                                )}
                                Try again
                            </Button>
                            <Link
                                to="/onboarding/creator"
                                data-testid={IDS.back}
                                className="inline-flex min-h-[3rem] items-center text-sm text-muted-foreground transition-colors duration-200 hover:text-ember-500"
                            >
                                Back to my profile
                            </Link>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
