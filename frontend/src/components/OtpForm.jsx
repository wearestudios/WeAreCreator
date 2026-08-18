// The WhatsApp sign-in form, shared by Login and Signup.
//
// This is the front door: it is the first thing every creator and every brand
// meets, and the only screen where a confusing failure costs you the user
// entirely. So every branch it can land in has a specific thing to say and a
// specific thing to offer, and the two are chosen from the server's error
// **code** rather than from its prose — a copy edit to a message must never
// change what a button does.
//
// The three rules underneath it:
//
//   1. Validation is inline and live. Telling somebody their number is wrong
//      only after they press Send is telling them late.
//   2. The cooldown is seeded from the server's `retry_after`, never guessed.
//      Before this the form set a flat 30s locally, so a rejection that said
//      "wait 23s" left the resend button enabled and it failed again.
//   3. Advice matches the failure. "Didn't get it? Resend" is right for a
//      missing code and wrong for a mistyped one — they got it.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Loader2, MessageSquare, RefreshCw } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { AUTH as IDS } from "@/constants/testIds";

/**
 * E.164, with an Indian number treated as the common case.
 *
 * Returns a message or null. Deliberately not a boolean: the caller shows what
 * comes back, so there is one place that decides both whether a number is
 * usable and how to say that it isn't.
 */
export function validatePhone(raw) {
    const v = (raw || "").trim().replace(/[\s\-()]/g, "");
    if (!v) return "Enter your WhatsApp number.";
    if (!v.startsWith("+")) {
        // The single most common mistake, and the one worth naming precisely:
        // people type the number they dial, not the one the world routes.
        return "Start with the country code, like +91 for India.";
    }
    if (!/^\+[1-9]\d{7,14}$/.test(v)) return "That doesn't look like a complete number.";
    // +91 then exactly ten digits, first of which is 6–9. Checked as advice
    // rather than as a refusal, because the field is open to every country.
    if (v.startsWith("+91") && !/^\+91[6-9]\d{9}$/.test(v)) {
        return "An Indian mobile number is +91 followed by 10 digits starting 6–9.";
    }
    return null;
}

export const normalizePhone = (raw) => (raw || "").trim().replace(/[\s\-()]/g, "");

/**
 * What to say and what to offer, per failure.
 *
 * One table rather than a chain of ifs across the component, so "what happens
 * when the code expires" is answerable by reading six lines.
 *
 *   backToPhone — send them to the number step; the code step is a dead end now
 *   offerResend — put a resend in the error itself, not just at the bottom
 *   coolsDown   — the failure carries a wait; seed the countdown from it
 */
const FAILURES = {
    cooldown:       { coolsDown: true },
    hourly_limit:   { backToPhone: true },
    send_failed:    { offerResend: true },
    expired:        { offerResend: true, clearCode: true },
    no_active_code: { offerResend: true, clearCode: true },
    locked_out:     { backToPhone: true, clearCode: true, offerResend: true },
    wrong_code:     { clearCode: true },
    no_account:     { backToPhone: true },
    already_registered: { backToPhone: true },
    admin_uses_password: { backToPhone: true },
};

export default function OtpForm({
    phone,
    setPhone,
    onRequest,
    onVerify,
    onVerified,
    canSubmitPhoneStep = true,
    blockedReason = null,
    hint = "We'll WhatsApp a 6-digit code to this number.",
    extraTop = null,
}) {
    const [step, setStep] = useState("phone");
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(null); // "sending" | "verifying" | null
    const [failure, setFailure] = useState(null); // { message, code, offerResend }
    const [notice, setNotice] = useState("");
    const [cooldown, setCooldown] = useState(0);
    // Validation shows once the field has been left, not on the first
    // keystroke — flagging "+9" as invalid while somebody is still typing it
    // is technically true and useless.
    const [touched, setTouched] = useState(false);
    const codeRef = useRef(null);

    const normalized = useMemo(() => normalizePhone(phone), [phone]);
    const phoneProblem = validatePhone(phone);
    const showPhoneProblem = touched && Boolean(phoneProblem);

    useEffect(() => {
        if (cooldown <= 0) return undefined;
        const t = setTimeout(() => setCooldown((s) => s - 1), 1000);
        return () => clearTimeout(t);
    }, [cooldown]);

    useEffect(() => {
        if (step === "code") codeRef.current?.focus();
    }, [step]);

    const applyFailure = useCallback((res) => {
        const rule = FAILURES[res.code] || {};
        setNotice("");
        setFailure({
            message: res.offline
                ? "That didn't reach us. Check your connection and try again."
                : res.error || "Something went wrong. Try again.",
            code: res.code,
            // A network failure is always worth retrying; a refusal is only
            // worth retrying when the rule says so.
            offerResend: res.offline || Boolean(rule.offerResend),
        });
        if (rule.coolsDown && res.retryAfter) setCooldown(res.retryAfter);
        if (rule.clearCode) setCode("");
        if (rule.backToPhone) {
            setStep("phone");
            setTouched(true);
        }
    }, []);

    const send = useCallback(
        async ({ isResend = false } = {}) => {
            setFailure(null);
            setNotice("");
            setTouched(true);
            if (phoneProblem) return;
            setBusy("sending");
            const res = await onRequest(normalized);
            setBusy(null);
            if (!res.ok) return applyFailure(res);
            setStep("code");
            // The server's number, not ours.
            setCooldown(res.resend_available_in || 30);
            setNotice(
                // Most specific first. `test_mode` implies simulation, so the
                // plain simulation notice would otherwise win and send somebody
                // to the log to read a code they were told at setup.
                res.test_mode
                    ? "Test mode — this environment issues one fixed code. Never enabled in production."
                    : res.mode === "simulation"
                      ? "Simulation mode — the code is in the server log, not on WhatsApp."
                      : isResend
                        ? "New code sent."
                        : "Code sent.",
            );
        },
        [applyFailure, normalized, onRequest, phoneProblem],
    );

    const verify = useCallback(
        async (e) => {
            e?.preventDefault();
            setFailure(null);
            if (!/^\d{6}$/.test(code)) {
                setFailure({ message: "Enter all 6 digits.", code: "short_code" });
                return;
            }
            setBusy("verifying");
            const res = await onVerify(code);
            setBusy(null);
            if (!res.ok) return applyFailure(res);
            onVerified?.(res.user);
        },
        [applyFailure, code, onVerify, onVerified],
    );

    const sending = busy === "sending";
    const verifying = busy === "verifying";

    const Failure = () =>
        failure && (
            <div
                data-testid={IDS.error}
                role="alert"
                className="flex items-start gap-2.5 rounded-md border border-destructive/30 bg-destructive/10 p-3.5"
            >
                <AlertCircle className="mt-0.5 h-4 w-4 flex-none text-destructive" />
                <div className="min-w-0 text-sm leading-relaxed text-destructive">
                    {failure.message}
                    {/* The way out, in the same breath as the problem. Only
                        where it is actually the right next move. */}
                    {failure.offerResend && (
                        <button
                            type="button"
                            onClick={() => send({ isResend: true })}
                            disabled={cooldown > 0 || sending}
                            data-testid={IDS.errorResend}
                            className="ml-2 whitespace-nowrap underline underline-offset-4 transition-colors duration-200 hover:text-destructive/80 disabled:no-underline disabled:opacity-60"
                        >
                            {cooldown > 0 ? `Resend in ${cooldown}s` : "Send a new code"}
                        </button>
                    )}
                </div>
            </div>
        );

    return (
        <div>
            {step === "phone" && (
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        send();
                    }}
                    noValidate
                    className="mt-8 space-y-5"
                    data-testid={IDS.phoneStep}
                >
                    {extraTop}
                    <div>
                        <Label
                            htmlFor="phone"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            WhatsApp number
                        </Label>
                        <Input
                            id="phone"
                            data-testid={IDS.phoneInput}
                            type="tel"
                            inputMode="tel"
                            autoComplete="tel"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            onBlur={() => setTouched(true)}
                            aria-invalid={showPhoneProblem || undefined}
                            aria-describedby="phone-help"
                            className={
                                "mt-2 h-11 bg-card/60 text-foreground focus-visible:ring-ember-500 " +
                                (showPhoneProblem
                                    ? "border-destructive/60"
                                    : "border-white/10")
                            }
                            placeholder="+91 98765 43210"
                        />
                        <p
                            id="phone-help"
                            data-testid={showPhoneProblem ? IDS.phoneError : IDS.phoneHint}
                            className={
                                "mt-2 text-xs leading-relaxed " +
                                (showPhoneProblem ? "text-destructive" : "text-muted-foreground")
                            }
                        >
                            {showPhoneProblem ? phoneProblem : hint}
                        </p>
                    </div>

                    <Failure />

                    {/* Why the button is off, when it is off for a reason the
                        person can fix. A disabled control with no explanation
                        is the most common dead end in a signup form. */}
                    {blockedReason && !canSubmitPhoneStep && (
                        <p
                            data-testid={IDS.blockedReason}
                            className="text-xs leading-relaxed text-muted-foreground"
                        >
                            {blockedReason}
                        </p>
                    )}

                    <Button
                        type="submit"
                        data-testid={IDS.sendBtn}
                        disabled={sending || !canSubmitPhoneStep || Boolean(phoneProblem)}
                        className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {sending ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Sending code…
                            </>
                        ) : (
                            <>
                                <MessageSquare className="mr-2 h-4 w-4" />
                                Send WhatsApp code
                            </>
                        )}
                    </Button>
                </form>
            )}

            {step === "code" && (
                <form onSubmit={verify} noValidate className="mt-8 space-y-5" data-testid={IDS.codeStep}>
                    {/* Which number it went to, so a typo is caught here
                        rather than being blamed on WhatsApp. */}
                    <div className="rounded-md border border-white/10 bg-card/60 p-3.5 text-sm">
                        <span className="text-muted-foreground">Code sent to </span>
                        <span data-testid={IDS.sentTo} className="text-foreground">
                            {normalized}
                        </span>
                        <button
                            type="button"
                            data-testid={IDS.changePhone}
                            onClick={() => {
                                setStep("phone");
                                setCode("");
                                setFailure(null);
                                setNotice("");
                            }}
                            className="ml-2 text-ember-500 underline-offset-4 transition-colors duration-200 hover:underline"
                        >
                            Change
                        </button>
                    </div>

                    <div>
                        <Label
                            htmlFor="code"
                            className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                        >
                            6-digit code
                        </Label>
                        <Input
                            id="code"
                            ref={codeRef}
                            data-testid={IDS.codeInput}
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            maxLength={6}
                            value={code}
                            onChange={(e) => {
                                setCode(e.target.value.replace(/\D/g, "").slice(0, 6));
                                // Clearing on edit: leaving "that code isn't
                                // right" above the digits they are currently
                                // fixing reads as a verdict on the new ones.
                                if (failure) setFailure(null);
                            }}
                            className="mt-2 h-11 border-white/10 bg-card/60 text-foreground tracking-[0.35em] focus-visible:ring-ember-500"
                            placeholder="••••••"
                        />
                    </div>

                    {notice && !failure && (
                        <p data-testid={IDS.notice} className="text-xs text-muted-foreground">
                            {notice}
                        </p>
                    )}

                    <Failure />

                    <Button
                        type="submit"
                        data-testid={IDS.verifyBtn}
                        disabled={verifying || code.length !== 6}
                        className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {verifying ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Checking…
                            </>
                        ) : (
                            "Verify and continue"
                        )}
                    </Button>

                    <button
                        type="button"
                        data-testid={IDS.resendBtn}
                        onClick={() => send({ isResend: true })}
                        disabled={cooldown > 0 || sending || verifying}
                        className="inline-flex min-h-[2.75rem] w-full items-center justify-center gap-2 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:text-ember-500 disabled:text-muted-foreground/50 disabled:hover:text-muted-foreground/50 md:min-h-0"
                    >
                        {sending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
                    </button>
                </form>
            )}
        </div>
    );
}
