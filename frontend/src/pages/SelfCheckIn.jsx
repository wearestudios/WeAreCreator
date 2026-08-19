// Checking yourself in, from the QR on the manager's screen.
//
// This page is opened by a camera, at a venue, on whatever signal the building
// has — so it does one thing on arrival and says the outcome in a sentence.
// There is no form: the code is in the URL and the identity is the session.
//
// **Every check is on the server.** The code is the only part a phone could
// tamper with, so the code is the only part it holds: which slot, signed, and
// valid for ninety seconds. Whether *this* creator has a booking on that slot,
// and whether now is anywhere near it, are answered from the database.
//
// The manager's manual button is untouched and is named here, because the
// honest thing to tell somebody whose scan failed is that a person standing
// ten feet away can do it for them.
import React, { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { CHECKIN as IDS } from "@/constants/testIds";

export default function SelfCheckIn() {
    const { user } = useAuth();
    const [params] = useSearchParams();
    const code = params.get("code") || "";
    const [state, setState] = useState("idle");
    const [message, setMessage] = useState("");

    const submit = useCallback(async () => {
        if (!code) {
            setState("failed");
            setMessage("That link is missing its code. Scan the screen again.");
            return;
        }
        setState("sending");
        setMessage("");
        try {
            await api.post("/creator/check-in", { code });
            setState("done");
        } catch (e) {
            setState("failed");
            setMessage(formatApiError(e));
        }
    }, [code]);

    useEffect(() => {
        // Only once signed in: an anonymous scan has no creator to check in,
        // and firing anyway would spend the code on a 401.
        if (user && user !== false) submit();
    }, [user, submit]);

    return (
        <div
            data-testid={IDS.page}
            className="min-h-screen bg-background text-foreground grain-page"
        >
            <Navbar />
            <main className="mx-auto flex max-w-md flex-col px-6 py-16">
                <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                    Check in
                </p>

                {user === false || !user ? (
                    <>
                        <h1 className="mt-4 font-serif text-fluid-3xl leading-tight">
                            Sign in to check yourself in.
                        </h1>
                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                            We need to know which booking is yours. It's the same number
                            you signed up with.
                        </p>
                        {/* Deliberately no "we'll bring you back here": the
                            code lives ninety seconds and an OTP round trip
                            takes longer, so carrying it through would land
                            somebody on an expired one. Say what actually
                            happens instead. */}
                        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                            Sign in first, then scan the screen again — the code
                            refreshes every minute, so there will be a fresh one waiting.
                        </p>
                        <Link to="/login" className="mt-8">
                            <Button className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                Sign in
                            </Button>
                        </Link>
                    </>
                ) : state === "sending" || state === "idle" ? (
                    <div
                        data-testid={IDS.pending}
                        className="mt-6 flex items-center gap-3 text-sm text-muted-foreground"
                    >
                        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
                        Checking you in…
                    </div>
                ) : state === "done" ? (
                    <div data-testid={IDS.success} className="mt-6">
                        <CheckCircle2 className="h-10 w-10 text-emerald-400" />
                        <h1 className="mt-5 font-serif text-fluid-3xl leading-tight">
                            You're checked in.
                        </h1>
                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                            That's it — enjoy the shoot. Your next step shows up on your
                            dashboard when it's yours.
                        </p>
                        <Link to="/dashboard" className="mt-8 block">
                            <Button className="h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400">
                                Back to your dashboard
                            </Button>
                        </Link>
                    </div>
                ) : (
                    <div data-testid={IDS.failure} className="mt-6">
                        <XCircle className="h-10 w-10 text-red-400" />
                        <h1 className="mt-5 font-serif text-fluid-3xl leading-tight">
                            That didn't work.
                        </h1>
                        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                            {message}
                        </p>
                        {/* Naming the fallback rather than leaving somebody
                            tapping: the person with the clipboard is standing
                            right there and can do this in one tap. */}
                        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                            The campaign manager can check you in from their screen — it
                            takes them a second.
                        </p>
                        <Button
                            type="button"
                            data-testid={IDS.retry}
                            onClick={submit}
                            className="mt-8 h-12 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                        >
                            Try again
                        </Button>
                    </div>
                )}
            </main>
        </div>
    );
}
