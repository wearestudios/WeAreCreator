import React, { useEffect, useState, useRef } from "react";
import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

/**
 * A two-step WhatsApp OTP form used by both Login and Signup pages.
 *
 * Props:
 * - phone / setPhone: controlled phone state (E.164 e.g. +919876543210)
 * - onRequest: async () => { ok, error, status, mode?, resend_available_in? }
 * - onVerify:  async (code) => { ok, error, status, user? }
 * - onVerified: (user) => void — called after successful verification
 * - hint: optional text under the phone label
 * - extraTop: optional ReactNode rendered above the form (e.g. name field)
 */
export default function OtpForm({
    phone,
    setPhone,
    onRequest,
    onVerify,
    onVerified,
    canSubmitPhoneStep = true,
    hint = "We'll WhatsApp a 6-digit code to this number.",
    extraTop = null,
}) {
    const [step, setStep] = useState("phone"); // "phone" | "code"
    const [code, setCode] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [cooldown, setCooldown] = useState(0);
    const codeRef = useRef(null);

    // resend countdown
    useEffect(() => {
        if (cooldown <= 0) return;
        const t = setTimeout(() => setCooldown((s) => s - 1), 1000);
        return () => clearTimeout(t);
    }, [cooldown]);

    // autofocus OTP input once we enter code step
    useEffect(() => {
        if (step === "code") codeRef.current?.focus();
    }, [step]);

    const normalizedPhone = phone.trim().replace(/[\s\-()]/g, "");

    const doRequest = async ({ isResend = false } = {}) => {
        setError("");
        setNotice("");
        if (!/^\+[1-9]\d{7,14}$/.test(normalizedPhone)) {
            setError("Enter your number in E.164 format, e.g. +919876543210.");
            return;
        }
        setSubmitting(true);
        const res = await onRequest(normalizedPhone);
        setSubmitting(false);
        if (res.ok) {
            setStep("code");
            setCooldown(res.resend_available_in || 30);
            setNotice(
                res.mode === "simulation"
                    ? "Simulation mode — check the server log for the code."
                    : isResend
                    ? "New code sent on WhatsApp."
                    : "Code sent on WhatsApp."
            );
        } else {
            setError(res.error || "Could not send code.");
        }
    };

    const onSubmitPhone = async (e) => {
        e.preventDefault();
        await doRequest();
    };

    const onSubmitCode = async (e) => {
        e.preventDefault();
        setError("");
        if (!/^\d{6}$/.test(code)) {
            setError("Enter the 6-digit code.");
            return;
        }
        setSubmitting(true);
        const res = await onVerify(code);
        setSubmitting(false);
        if (res.ok) {
            onVerified?.(res.user);
        } else {
            setError(res.error || "Could not verify code.");
            // If backend says too many wrong attempts, kick back to phone step.
            if (res.status === 429) {
                setStep("phone");
                setCode("");
            }
        }
    };

    return (
        <div>
            {step === "phone" && (
                <form onSubmit={onSubmitPhone} className="mt-8 space-y-5" data-testid="otp-phone-step">
                    {extraTop}
                    <div>
                        <Label htmlFor="phone" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            WhatsApp number
                        </Label>
                        <Input
                            id="phone"
                            data-testid="otp-phone-input"
                            type="tel"
                            inputMode="tel"
                            autoComplete="tel"
                            required
                            value={phone}
                            onChange={(e) => setPhone(e.target.value)}
                            className="mt-2 h-11 border-white/10 bg-card/60 text-foreground focus-visible:ring-ember-500"
                            placeholder="+91 98xxx xxxxx"
                        />
                        <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
                    </div>

                    {error && (
                        <p data-testid="otp-error" className="text-sm text-destructive">
                            {error}
                        </p>
                    )}

                    <Button
                        type="submit"
                        data-testid="otp-send-btn"
                        disabled={submitting || !canSubmitPhoneStep}
                        className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {submitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Sending code…
                            </>
                        ) : (
                            "Send WhatsApp code"
                        )}
                    </Button>
                </form>
            )}

            {step === "code" && (
                <form onSubmit={onSubmitCode} className="mt-8 space-y-5" data-testid="otp-code-step">
                    <div className="text-sm text-muted-foreground">
                        We sent a code to <span className="text-foreground">{normalizedPhone}</span>.
                        <button
                            type="button"
                            data-testid="otp-change-phone-btn"
                            onClick={() => {
                                setStep("phone");
                                setCode("");
                                setError("");
                                setNotice("");
                            }}
                            className="ml-2 text-ember-500 underline-offset-4 hover:underline"
                        >
                            Change number
                        </button>
                    </div>

                    <div>
                        <Label htmlFor="code" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                            6-digit code
                        </Label>
                        <Input
                            id="code"
                            ref={codeRef}
                            data-testid="otp-code-input"
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            required
                            maxLength={6}
                            value={code}
                            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                            className="mt-2 h-11 border-white/10 bg-card/60 text-foreground tracking-[0.35em] focus-visible:ring-ember-500"
                            placeholder="••••••"
                        />
                    </div>

                    {notice && (
                        <p data-testid="otp-notice" className="text-xs text-muted-foreground">
                            {notice}
                        </p>
                    )}

                    {error && (
                        <p data-testid="otp-error" className="text-sm text-destructive">
                            {error}
                            {" "}
                            <span className="text-muted-foreground">
                                Didn't get it? Use resend below.
                            </span>
                        </p>
                    )}

                    <Button
                        type="submit"
                        data-testid="otp-verify-btn"
                        disabled={submitting}
                        className="h-11 w-full rounded-full bg-ember-500 text-black hover:bg-ember-400"
                    >
                        {submitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Verifying…
                            </>
                        ) : (
                            "Verify and continue"
                        )}
                    </Button>

                    <button
                        type="button"
                        data-testid="otp-resend-btn"
                        onClick={() => doRequest({ isResend: true })}
                        disabled={cooldown > 0 || submitting}
                        className="w-full text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors hover:text-ember-500 disabled:text-muted-foreground/50 disabled:hover:text-muted-foreground/50"
                    >
                        {cooldown > 0
                            ? `Resend WhatsApp code in ${cooldown}s`
                            : "Resend WhatsApp code"}
                    </button>
                </form>
            )}
        </div>
    );
}
