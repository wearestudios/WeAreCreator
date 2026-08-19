import React, { useMemo, useState } from "react";
import { SIGNUP } from "@/constants/testIds";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { notifySuccess } from "@/lib/feedback";
import { Camera, Building2 } from "lucide-react";
import { useAuth, isBrandSide } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import OtpForm from "@/components/OtpForm";
import PlaceholderImage from "@/components/marketing/PlaceholderImage";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { CONTACT_ROLES, OTHER_ROLE } from "@/lib/contactRoles";

const ROLE_OPTIONS = [
    {
        value: "creator",
        title: "I'm a Creator",
        subtitle: "Storytellers across F&B, retail, real estate, fashion, travel and lifestyle.",
        Icon: Camera,
    },
    {
        value: "brand",
        title: "I'm a Brand",
        subtitle: "Café, restaurant, hotel, retail, real estate, fashion or travel brand.",
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
    // A brand registers one named person, who becomes its only login. Asked
    // here rather than later because the audit log should say a name from the
    // first action, and because verification asks for exactly these three.
    const [managerName, setManagerName] = useState("");
    // A picked role, plus the box "Other" opens. What gets sent is one
    // string either way — the server keeps this free text, so an unusual role
    // is still a role rather than a value the form has no slot for.
    const [roleOption, setRoleOption] = useState("");
    const [roleOther, setRoleOther] = useState("");
    const managerDesignation =
        roleOption === OTHER_ROLE ? roleOther : roleOption;
    const [managerEmail, setManagerEmail] = useState("");
    const isBrand = role === "brand";
    // Consent is recorded against the account, so it has to be an actual act.
    const [acceptedTerms, setAcceptedTerms] = useState(false);
    // Which fields the person has finished with. Validation appears on blur,
    // not on the first keystroke: flagging "P" as too short while somebody is
    // still typing "Priya" is correct and useless.
    const [touched, setTouched] = useState({});
    const touch = (k) => setTouched((t) => ({ ...t, [k]: true }));

    const nameProblem = !name.trim()
        ? `${role === "brand" ? "Brand name" : "Your name"} is required.`
        : name.trim().length < 2
          ? "That looks too short."
          : null;
    const managerNameProblem =
        isBrand && !managerName.trim() ? "We need the name of the person running this." : null;
    // Advice, not a refusal: the server does not require a work email, and a
    // café on Gmail is a real business.
    const managerEmailProblem =
        isBrand && managerEmail.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(managerEmail.trim())
            ? "That doesn't look like an email address."
            : null;
    const termsProblem = !acceptedTerms ? "Accept the terms to continue." : null;

    // What to tell somebody whose Send button is off. First unmet thing only —
    // a list of four problems at once reads as a wall.
    const blockedReason =
        [nameProblem, managerNameProblem, managerEmailProblem, termsProblem].find(Boolean) || null;

    // Sent on both OTP steps, so a code requested and verified minutes apart
    // still lands the contact. Empty for creators, who have no such concept.
    const brandContact = isBrand
        ? {
              manager_name: managerName.trim() || undefined,
              manager_designation: managerDesignation.trim() || undefined,
              manager_email: managerEmail.trim() || undefined,
          }
        : {};

    return (
        <div data-testid="signup-page" className="grid min-h-screen grid-cols-1 md:grid-cols-2">
            <div className="relative hidden md:block">
                <PlaceholderImage
                    // PLACEHOLDER IMAGE: Creator setting up a shot at a Bengaluru cafe, portrait crop for the auth aside.
                    note="Creator setting up a shot at a Bengaluru cafe, portrait crop for the auth aside"
                    fill
                    className="opacity-60"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-background/40 via-background/60 to-background" />
                <div className="relative flex h-full flex-col justify-between p-12">
                    <Link to="/" className="-my-2 min-h-[2.75rem] py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:my-0 md:min-h-0 md:py-0 inline-flex items-center font-serif text-2xl transition-colors duration-200 hover:text-ember-500">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <div className="max-w-md">
                        {/* Was "Invite-only" over "Get on the list", which
                            describes a product we do not have: signup is open,
                            there is no waitlist and no invite gate. What is
                            true is the review — a creator is checked before
                            they can apply to a brief — so that is what it
                            says. Telling somebody they are queueing for
                            admission at the moment they are filling in the
                            form is also the worst possible place to say it. */}
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">Free to join</p>
                        <p className="mt-4 font-serif text-4xl leading-tight">
                            Sign up in a minute. Every profile is reviewed by our team
                            before you can apply to a brief.
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-center bg-background p-6 md:p-12">
                <div className="w-full max-w-md">
                    <Link to="/" className="mb-10 -my-2 inline-flex min-h-[2.75rem] items-center py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background font-serif text-xl md:hidden">
                        WeAre <span className="text-ember-500">Creators</span>
                    </Link>
                    <p className="text-xs uppercase tracking-[0.22em] text-ember-500/90">
                        <span className="mr-2 inline-block h-px w-6 translate-y-[-3px] bg-ember-500/80 align-middle" />
                        Create account
                    </p>
                    <h1 className="mt-5 font-serif text-fluid-5xl leading-[0.95] tracking-tight">
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
                                                : "border-white/10 bg-card grain-surface hover:border-white/25")
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
                        canSubmitPhoneStep={!blockedReason}
                        blockedReason={blockedReason}
                        onRequest={(p) =>
                            requestOtp({
                                phone: p,
                                purpose: "signup",
                                name: name.trim(),
                                role,
                                accept_terms: acceptedTerms,
                                ...brandContact,
                            })
                        }
                        onVerify={(code) => verifyOtp({
                            phone: phone.trim().replace(/[\s\-()]/g, ""),
                            code,
                            purpose: "signup",
                            name: name.trim(),
                            role,
                            ...brandContact,
                            accept_terms: acceptedTerms,
                        })}
                        onVerified={(user) => {
                            notifySuccess("Account created — welcome to WeAre.");
                            const next =
                                user?.role === "creator"
                                    ? "/onboarding/creator"
                                    : isBrandSide(user?.role)
                                    ? "/onboarding/brand"
                                    : "/dashboard";
                            navigate(next, { replace: true });
                        }}
                        hint="We'll WhatsApp a 6-digit code to verify this number."
                        extraTop={
                            <>
                                <div>
                                    <Label htmlFor="name" className="text-xs uppercase tracking-[0.15em] text-muted-foreground">
                                        {role === "brand" ? "Brand name" : "Full name"}
                                    </Label>
                                    <Input
                                        id="name"
                                        data-testid={SIGNUP.nameInput}
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        onBlur={() => touch("name")}
                                        aria-invalid={(touched.name && Boolean(nameProblem)) || undefined}
                                        className={
                                            "mt-2 h-11 bg-card/60 focus-visible:ring-ember-500 " +
                                            (touched.name && nameProblem
                                                ? "border-destructive/60"
                                                : "border-white/10")
                                        }
                                        placeholder={isBrand ? "e.g. Toit Brewpub" : "e.g. Priya Rao"}
                                    />
                                    {touched.name && nameProblem && (
                                        <p
                                            data-testid={SIGNUP.nameError}
                                            className="mt-2 text-xs text-destructive"
                                        >
                                            {nameProblem}
                                        </p>
                                    )}
                                </div>

                                {isBrand && (
                                    <div
                                        data-testid="signup-brand-contact"
                                        className="flex flex-col gap-4 rounded-md border border-white/10 bg-card/40 p-4"
                                    >
                                        <p className="text-xs leading-relaxed text-muted-foreground">
                                            One person runs the account. This number is their
                                            login, and their name is what creators and our
                                            team see on your campaigns.
                                        </p>
                                        <div>
                                            <Label
                                                htmlFor="manager-name"
                                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                            >
                                                Your full name
                                            </Label>
                                            <Input
                                                id="manager-name"
                                                data-testid={SIGNUP.managerNameInput}
                                                value={managerName}
                                                onChange={(e) => setManagerName(e.target.value)}
                                                onBlur={() => touch("managerName")}
                                                aria-invalid={
                                                    (touched.managerName &&
                                                        Boolean(managerNameProblem)) ||
                                                    undefined
                                                }
                                                className={
                                                    "mt-2 h-11 bg-card/60 focus-visible:ring-ember-500 " +
                                                    (touched.managerName && managerNameProblem
                                                        ? "border-destructive/60"
                                                        : "border-white/10")
                                                }
                                                placeholder="e.g. Priya Rao"
                                            />
                                            {touched.managerName && managerNameProblem && (
                                                <p
                                                    data-testid={SIGNUP.managerNameError}
                                                    className="mt-2 text-xs text-destructive"
                                                >
                                                    {managerNameProblem}
                                                </p>
                                            )}
                                        </div>
                                        <div>
                                            <Label
                                                htmlFor="manager-designation"
                                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                            >
                                                Your role there
                                            </Label>
                                            <Select
                                                value={roleOption}
                                                onValueChange={setRoleOption}
                                            >
                                                <SelectTrigger
                                                    id="manager-designation"
                                                    data-testid="signup-manager-designation-input"
                                                    className="mt-2 h-11 border-white/10 bg-card/60 focus:ring-ember-500"
                                                >
                                                    <SelectValue placeholder="Pick one" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {CONTACT_ROLES.map((r) => (
                                                        <SelectItem
                                                            key={r}
                                                            value={r}
                                                            data-testid={`signup-role-${r
                                                                .toLowerCase()
                                                                .replace(/\s+/g, "-")}`}
                                                        >
                                                            {r}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            {/* "Other" stored as the word
                                                "Other" tells a reviewer
                                                nothing, so it opens a box
                                                instead of ending the
                                                question. */}
                                            {roleOption === OTHER_ROLE && (
                                                <Input
                                                    data-testid="signup-manager-role-other"
                                                    value={roleOther}
                                                    onChange={(e) => setRoleOther(e.target.value)}
                                                    className="mt-2 h-11 border-white/10 bg-card/60 focus-visible:ring-ember-500"
                                                    placeholder="e.g. Head of Partnerships"
                                                />
                                            )}
                                        </div>
                                        <div>
                                            <Label
                                                htmlFor="manager-email"
                                                className="text-xs uppercase tracking-[0.15em] text-muted-foreground"
                                            >
                                                Work email
                                            </Label>
                                            <Input
                                                id="manager-email"
                                                type="email"
                                                inputMode="email"
                                                autoComplete="email"
                                                data-testid={SIGNUP.managerEmailInput}
                                                value={managerEmail}
                                                onChange={(e) => setManagerEmail(e.target.value)}
                                                onBlur={() => touch("managerEmail")}
                                                aria-invalid={
                                                    (touched.managerEmail &&
                                                        Boolean(managerEmailProblem)) ||
                                                    undefined
                                                }
                                                className={
                                                    "mt-2 h-11 bg-card/60 focus-visible:ring-ember-500 " +
                                                    (touched.managerEmail && managerEmailProblem
                                                        ? "border-destructive/60"
                                                        : "border-white/10")
                                                }
                                                placeholder="e.g. priya@toit.in"
                                            />
                                            {touched.managerEmail && managerEmailProblem && (
                                                <p
                                                    data-testid={SIGNUP.managerEmailError}
                                                    className="mt-2 text-xs text-destructive"
                                                >
                                                    {managerEmailProblem}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}
                                <label
                                    htmlFor="accept-terms"
                                    className="-my-2 flex min-h-[2.75rem] cursor-pointer items-start gap-3 py-2 text-xs leading-relaxed text-muted-foreground"
                                >
                                    <Checkbox
                                        id="accept-terms"
                                        data-testid="signup-terms-checkbox"
                                        checked={acceptedTerms}
                                        onCheckedChange={(v) => setAcceptedTerms(v === true)}
                                        className="mt-0.5 h-5 w-5 flex-none border-white/25 focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background data-[state=checked]:border-ember-500 data-[state=checked]:bg-ember-500 data-[state=checked]:text-black"
                                    />
                                    <span>
                                        I agree to the{" "}
                                        <Link
                                            to="/terms"
                                            data-testid="signup-terms-link"
                                            className="text-ember-500 underline-offset-4 hover:underline"
                                        >
                                            terms
                                        </Link>{" "}
                                        and{" "}
                                        <Link
                                            to="/privacy"
                                            data-testid="signup-privacy-link"
                                            className="text-ember-500 underline-offset-4 hover:underline"
                                        >
                                            privacy policy
                                        </Link>
                                        , including how WeAre stores my contact details.
                                    </span>
                                </label>
                            </>
                        }
                    />

                    <p className="mt-8 text-xs text-muted-foreground">
                        We record when you accepted, so you always know what you agreed to.
                    </p>
                </div>
            </div>
        </div>
    );
}
