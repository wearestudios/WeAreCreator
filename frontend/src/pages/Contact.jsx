// Contact — the form, the two partners, and the address.
//
// **A React route, not a server-rendered page**, which is the trade
// `/for-brands` makes and the reasoning is in CLAUDE.md under "Why they are
// not server-rendered". The pages the backend renders — `/c/{id}`,
// `/brands/{id}`, `/work` — are written to be *sent* or to be *found*, where
// the shared link is the pitch and a crawler that runs no JavaScript has to
// read it. This one links sideways to the other marketing pages and nobody
// pastes a contact page into a chat as a pitch. The cost is the same one the
// audience pages pay: a non-JS crawler reads `public/index.html`'s static
// tags, so a link to this previews with the site-wide card. `PageMeta` states
// that at the top of its own file and says how to buy it back.
//
// **The form posts to `POST /public/contact`**, which is unauthenticated by
// design — the creator survey is the precedent and the server-side reasoning
// lives beside that route.
//
// Two conventions this inherits rather than reinvents:
//
//   - **`validatePhone` is the OTP form's**, so the one place that knows what
//     an Indian mobile looks like stays one place. It names three distinct
//     problems — no country code, too short, not an Indian mobile — rather
//     than answering all of them with "invalid".
//   - **Validation fires on blur, not on submit**, which is what `OtpForm`
//     sets. Being told at the end that four fields were wrong is being told
//     too late to do anything about it cheaply.
import React, { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, Mail, MessageCircle, Phone } from "lucide-react";

import { MarketingPage } from "@/components/marketing/Sections";
import Reveal from "@/components/marketing/Reveal";
import { Button } from "@/components/ui/button";
import { validatePhone, normalizePhone } from "@/components/OtpForm";
import { useOptimisticAction } from "@/lib/useOptimistic";
import { api } from "@/lib/api";
import { formatApiError } from "@/lib/api";
import {
    CONTACT_EMAIL,
    CONTACT_PEOPLE,
    formatPhone,
    whatsappHref,
} from "@/lib/siteNav";
import { CONTACT as IDS } from "@/constants/testIds";

/**
 * Every word on the page, in one object.
 *
 * The convention every marketing page here holds, so the word budget can be
 * read rather than reconstructed by walking JSX — and so a section that wants
 * to say more has to argue with a number. Under 200.
 */
const COPY = {
    eyebrow: "Get in touch",
    heading: "Tell us what you need.",
    line: "Brands briefing a campaign, creators asking about a brief, or anything else. We answer within one working day.",

    formHeading: "Send a message",
    peopleHeading: "Or reach us directly",
    peopleLine: "Both of us read WhatsApp. It is how this operation runs.",
    emailLabel: "Email",

    nameLabel: "Your name",
    phoneLabel: "WhatsApp number",
    phoneHelp: "With the country code, so we can reply there.",
    emailFieldLabel: "Email (optional)",
    roleLabel: "I'm a…",
    messageLabel: "What is this about?",
    send: "Send message",
    sending: "Sending…",

    doneHeading: "Thanks — that reached us.",
    doneLine: "We answer within one working day, on WhatsApp unless you asked otherwise. Your message is below.",
};

const ROLES = [
    { value: "brand", label: "Brand" },
    { value: "creator", label: "Creator" },
    { value: "other", label: "Something else" },
];

const MESSAGE_MAX = 2000;

/**
 * How long the page must have been open before a submission is believed.
 *
 * **A honeypot and a clock, and no CAPTCHA.** A CAPTCHA taxes every real
 * person to inconvenience a script, on a form whose whole job is to be easy
 * to use. Three seconds is below what anyone can type a name, a number and a
 * sentence in, and far above what a script spends.
 */
const MIN_SECONDS_ON_PAGE = 3;

function Field({ id, label, help, error, children }) {
    return (
        <div>
            <label
                htmlFor={id}
                className="block text-sm font-medium text-foreground"
            >
                {label}
            </label>
            {help ? (
                <p className="mt-1 text-sm text-muted-foreground">{help}</p>
            ) : null}
            <div className="mt-2">{children}</div>
            {/* The slot is reserved whether or not there is an error in it, so
                a message appearing on blur cannot push the next field down. */}
            <p
                data-testid={IDS.error(id)}
                aria-live="polite"
                className="mt-1 min-h-[1.25rem] text-sm text-destructive"
            >
                {error || ""}
            </p>
        </div>
    );
}

const INPUT =
    "h-11 w-full rounded-lg border border-border bg-card px-3 text-foreground " +
    "transition-colors duration-200 placeholder:text-muted-foreground " +
    "focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

export default function Contact() {
    const [values, setValues] = useState({
        name: "", whatsapp: "", email: "", role: "", message: "",
    });
    const [errors, setErrors] = useState({});
    const [sent, setSent] = useState(null);
    const [refusal, setRefusal] = useState(null);
    const { pending, run } = useOptimisticAction();
    const openedAt = useRef(Date.now());
    // Visually hidden, never focusable, and never shown to anybody. A filled
    // one is a script.
    const honeypot = useRef(null);

    useEffect(() => {
        openedAt.current = Date.now();
    }, []);

    const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }));

    const checkField = (k) => () => {
        setErrors((prev) => ({ ...prev, [k]: fieldError(k, values) }));
    };

    function fieldError(k, v) {
        if (k === "name") return v.name.trim() ? null : "Please tell us your name.";
        if (k === "whatsapp") return validatePhone(v.whatsapp);
        if (k === "role") return v.role ? null : "Pick the one that fits.";
        if (k === "message")
            return v.message.trim() ? null : "Please tell us what this is about.";
        return null;
    }

    async function onSubmit(e) {
        e.preventDefault();
        setRefusal(null);

        const found = {};
        for (const k of ["name", "whatsapp", "role", "message"]) {
            const err = fieldError(k, values);
            if (err) found[k] = err;
        }
        setErrors(found);
        if (Object.keys(found).length) return;

        // The two quiet checks. Both fail silently as a success, because a
        // script learning which one caught it is a script that gets past the
        // next one.
        const tooQuick =
            (Date.now() - openedAt.current) / 1000 < MIN_SECONDS_ON_PAGE;
        if (honeypot.current?.value || tooQuick) {
            setSent({ ...values });
            return;
        }

        await run(
            () =>
                api.post("/public/contact", {
                    name: values.name.trim(),
                    whatsapp: normalizePhone(values.whatsapp),
                    email: values.email.trim() || null,
                    role: values.role,
                    message: values.message.trim(),
                }),
            { onError: (err) => setRefusal(formatApiError(err)) },
        );
        if (!refusal) setSent({ ...values });
    }

    return (
        <MarketingPage
            testid={IDS.page}
            title="Contact WeAre Creators"
            description="Talk to the people who run WeAre Creators. Send a message, or reach either founder directly on WhatsApp. We answer within one working day."
            path="/contact"
        >
            <section
                data-surface="light"
                className="bg-background text-foreground"
            >
                <div className="mx-auto max-w-7xl px-6 py-16 md:py-20">
                    <Reveal>
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            {COPY.eyebrow}
                        </p>
                    </Reveal>
                    <Reveal i={1}>
                        <h1 className="mt-4 max-w-2xl font-serif text-fluid-4xl leading-tight tracking-tight">
                            {COPY.heading}
                        </h1>
                    </Reveal>
                    <Reveal i={2}>
                        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                            {COPY.line}
                        </p>
                    </Reveal>

                    <div className="mt-12 grid gap-12 lg:grid-cols-12 lg:gap-16">
                        {/* The form first in DOM order, so a phone reaches the
                            thing it came to do before the reference details. */}
                        <div className="lg:col-span-7">
                            <h2 className="font-serif text-fluid-2xl leading-tight">
                                {COPY.formHeading}
                            </h2>

                            {sent ? (
                                /* **The answers stay on screen.** Clearing the
                                   form back to empty reads as the submission
                                   having vanished, which is the one thing a
                                   confirmation has to rule out. */
                                <div
                                    data-testid={IDS.done}
                                    className="mt-6 rounded-lg border border-border bg-card p-6"
                                >
                                    <p className="flex items-center gap-2 font-serif text-fluid-xl leading-tight">
                                        <Check className="h-5 w-5 text-primary" />
                                        {COPY.doneHeading}
                                    </p>
                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                        {COPY.doneLine}
                                    </p>
                                    <p
                                        data-testid={IDS.doneEcho}
                                        className="mt-4 whitespace-pre-wrap border-t border-border pt-4 text-sm text-foreground"
                                    >
                                        {sent.message}
                                    </p>
                                </div>
                            ) : (
                                <form
                                    data-testid={IDS.form}
                                    onSubmit={onSubmit}
                                    noValidate
                                    className="mt-6 space-y-5"
                                >
                                    {/* Off-screen rather than `display:none`,
                                        and `tabIndex={-1}` so it is never
                                        reachable by keyboard. */}
                                    <input
                                        ref={honeypot}
                                        type="text"
                                        name="company"
                                        tabIndex={-1}
                                        autoComplete="off"
                                        aria-hidden="true"
                                        data-testid={IDS.honeypot}
                                        className="pointer-events-none absolute left-[-9999px] h-px w-px opacity-0"
                                    />

                                    <Field id="contact-name" label={COPY.nameLabel} error={errors.name}>
                                        <input
                                            id="contact-name"
                                            data-testid={IDS.name}
                                            value={values.name}
                                            onChange={set("name")}
                                            onBlur={checkField("name")}
                                            autoComplete="name"
                                            className={INPUT}
                                        />
                                    </Field>

                                    <Field
                                        id="contact-whatsapp"
                                        label={COPY.phoneLabel}
                                        help={COPY.phoneHelp}
                                        error={errors.whatsapp}
                                    >
                                        <input
                                            id="contact-whatsapp"
                                            data-testid={IDS.whatsapp}
                                            value={values.whatsapp}
                                            onChange={set("whatsapp")}
                                            onBlur={checkField("whatsapp")}
                                            inputMode="tel"
                                            autoComplete="tel"
                                            placeholder="+91"
                                            className={INPUT}
                                        />
                                    </Field>

                                    <Field id="contact-email" label={COPY.emailFieldLabel}>
                                        <input
                                            id="contact-email"
                                            data-testid={IDS.email}
                                            value={values.email}
                                            onChange={set("email")}
                                            type="email"
                                            autoComplete="email"
                                            className={INPUT}
                                        />
                                    </Field>

                                    <Field id="contact-role" label={COPY.roleLabel} error={errors.role}>
                                        <div className="flex flex-wrap gap-2">
                                            {ROLES.map((r) => (
                                                <button
                                                    key={r.value}
                                                    type="button"
                                                    data-testid={IDS.role(r.value)}
                                                    aria-pressed={values.role === r.value}
                                                    onClick={() => {
                                                        setValues((v) => ({ ...v, role: r.value }));
                                                        setErrors((p) => ({ ...p, role: null }));
                                                    }}
                                                    className={`h-11 rounded-lg border px-4 text-sm transition-colors duration-200 ${
                                                        values.role === r.value
                                                            ? "border-primary bg-primary text-primary-foreground"
                                                            : "border-border bg-card text-foreground hover:border-primary/50"
                                                    }`}
                                                >
                                                    {r.label}
                                                </button>
                                            ))}
                                        </div>
                                    </Field>

                                    <Field id="contact-message" label={COPY.messageLabel} error={errors.message}>
                                        <textarea
                                            id="contact-message"
                                            data-testid={IDS.message}
                                            value={values.message}
                                            onChange={set("message")}
                                            onBlur={checkField("message")}
                                            rows={6}
                                            maxLength={MESSAGE_MAX}
                                            className={`${INPUT} h-auto py-3 leading-relaxed`}
                                        />
                                    </Field>

                                    {refusal ? (
                                        <p
                                            data-testid={IDS.refusal}
                                            role="alert"
                                            className="text-sm text-destructive"
                                        >
                                            {refusal}
                                        </p>
                                    ) : null}

                                    <Button
                                        type="submit"
                                        size="lg"
                                        data-testid={IDS.submit}
                                        disabled={pending}
                                        className="group h-12 w-full rounded-full bg-primary px-7 text-primary-foreground transition-colors duration-200 hover:bg-primary-hover sm:w-auto"
                                    >
                                        {pending ? COPY.sending : COPY.send}
                                        <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                                    </Button>
                                </form>
                            )}
                        </div>

                        <div className="lg:col-span-5">
                            <h2 className="font-serif text-fluid-2xl leading-tight">
                                {COPY.peopleHeading}
                            </h2>
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {COPY.peopleLine}
                            </p>

                            <ul className="mt-6 space-y-4">
                                {CONTACT_PEOPLE.map((person) => (
                                    <li
                                        key={person.phone}
                                        data-testid={IDS.person(person.phone)}
                                        className="rounded-lg border border-border bg-card p-5"
                                    >
                                        <p className="font-medium text-foreground">{person.name}</p>
                                        <p className="text-sm text-muted-foreground">{person.role}</p>
                                        {/* **Both doors.** The stored value is
                                            bare E.164, which is what each href
                                            wants; the spaced form is built
                                            from it rather than kept beside it. */}
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <a
                                                href={whatsappHref(person.phone)}
                                                target="_blank"
                                                rel="noreferrer"
                                                data-testid={IDS.whatsappLink(person.phone)}
                                                className="inline-flex h-11 items-center gap-2 rounded-lg border border-border px-4 text-sm transition-colors duration-200 hover:border-primary/60"
                                            >
                                                <MessageCircle className="h-4 w-4" />
                                                WhatsApp
                                            </a>
                                            <a
                                                href={`tel:${person.phone}`}
                                                data-testid={IDS.telLink(person.phone)}
                                                className="inline-flex h-11 items-center gap-2 rounded-lg border border-border px-4 text-sm transition-colors duration-200 hover:border-primary/60"
                                            >
                                                <Phone className="h-4 w-4" />
                                                {formatPhone(person.phone)}
                                            </a>
                                        </div>
                                    </li>
                                ))}
                            </ul>

                            <div className="mt-6 rounded-lg border border-border bg-card p-5">
                                <p className="text-sm text-muted-foreground">{COPY.emailLabel}</p>
                                <a
                                    href={`mailto:${CONTACT_EMAIL}`}
                                    data-testid={IDS.emailLink}
                                    className="mt-1 inline-flex h-11 items-center gap-2 text-foreground underline-offset-4 transition-colors duration-200 hover:underline"
                                >
                                    <Mail className="h-4 w-4" />
                                    {CONTACT_EMAIL}
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </MarketingPage>
    );
}
