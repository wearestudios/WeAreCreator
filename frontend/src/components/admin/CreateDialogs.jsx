// Creating a record from the console.
//
// **We are the operator as well as the platform.** Some campaigns are ours to
// run for our own clients, some briefs are barter, and some brands and
// creators arrive through a conversation rather than a signup form. Until
// these three dialogs existed there was no way in: an admin could review,
// edit, publish and close, but the record itself had to be created by the
// person it belonged to — so an internal client had to be walked through a
// signup screen for an account nobody would ever log into.
//
// Three dialogs rather than three pages, because each is opened from the list
// the new row lands in, and a full-page form would lose that list. The
// campaign one carries what the payload requires and no more: an admin can
// edit everything else on the campaign's own page a moment later, and a
// twenty-field dialog is a form somebody abandons.
//
// Admin-only, and the server holds it: minting a *verified* brand or creator
// is a statement about a check that happened, and a scoped console could
// otherwise create the brand it then gets assigned to.
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, formatApiError } from "@/lib/api";
import { notifySuccess } from "@/lib/feedback";
import { ALL_COMPENSATION_OPTIONS } from "@/lib/compensation";
import { CATEGORY_OPTIONS } from "@/lib/categories";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import DeliverablePicker, {
    toDeliverableItems,
} from "@/components/DeliverablePicker";
import { ADMIN_CREATE as IDS } from "@/constants/testIds";
import { TEXT } from "@/components/admin/console/tokens";

/** A labelled control. The console's density, not the marketing form's. */
const Row = ({ label, hint, children, className = "" }) => (
    <label className={"block min-w-0 " + className}>
        <span className={`${TEXT.meta} block uppercase tracking-[0.14em] text-muted-foreground`}>
            {label}
        </span>
        {hint ? (
            <span className={`${TEXT.meta} mt-0.5 block text-muted-foreground/70`}>
                {hint}
            </span>
        ) : null}
        <span className="mt-1 block">{children}</span>
    </label>
);

const select =
    "h-9 w-full rounded border border-white/10 bg-background px-2 text-sm transition-colors duration-150";

/**
 * The shell all three share: a title, a body, one primary action, and the
 * server's own refusal rendered where it can be read rather than as a toast
 * that has scrolled away by the time somebody looks up.
 */
function CreateShell({ open, onOpenChange, title, blurb, testid, onSubmit, submitLabel, children }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (open) setError("");
    }, [open]);

    const submit = async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
            await onSubmit();
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {/* The shared dialog primitive grains itself and is on nineteen
                other surfaces, so the grain comes off here rather than there.
                `!` because the two utilities sit in the same layer and class
                order does not decide it — measured, the plain form lost. */}
            <DialogContent
                data-testid={testid}
                className="max-h-[90vh] overflow-y-auto rounded-md border border-white/10 bg-card ![background-image:none] sm:max-w-xl"
            >
                <DialogHeader className="text-left">
                    <DialogTitle>{title}</DialogTitle>
                    {blurb ? (
                        <DialogDescription className="text-sm text-muted-foreground">
                            {blurb}
                        </DialogDescription>
                    ) : null}
                </DialogHeader>

                <form onSubmit={submit} className="space-y-3">
                    {children}
                    {error ? (
                        <p
                            data-testid={IDS.error}
                            className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200"
                        >
                            {error}
                        </p>
                    ) : null}
                    <DialogFooter className="gap-2">
                        <Button
                            type="button"
                            variant="ghost"
                            data-testid={IDS.cancel}
                            onClick={() => onOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={busy} data-testid={IDS.submit}>
                            {busy ? "Creating…" : submitLabel}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// ---------------------------------------------------------------------------
// A brand
// ---------------------------------------------------------------------------

const BLANK_BRAND = {
    business_name: "",
    manager_name: "",
    manager_phone: "",
    manager_email: "",
    manager_designation: "",
    category: "",
    city: "",
};

export function CreateBrandDialog({ open, onOpenChange, onCreated }) {
    const [form, setForm] = useState(BLANK_BRAND);
    const navigate = useNavigate();
    useEffect(() => {
        if (open) setForm(BLANK_BRAND);
    }, [open]);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    return (
        <CreateShell
            open={open}
            onOpenChange={onOpenChange}
            testid={IDS.brandDialog}
            title="New brand"
            // Said plainly, because it is the consequential part: this is not a
            // way around verification, it is the record of one.
            blurb="Enters verified — only create one you have actually checked. The WhatsApp number is their login."
            submitLabel="Create brand"
            onSubmit={async () => {
                const body = Object.fromEntries(
                    Object.entries(form).map(([k, v]) => [k, v.trim() || null]),
                );
                const { data } = await api.post("/admin/brands", body);
                notifySuccess(`${data.business_name} created`);
                onOpenChange(false);
                onCreated?.(data);
                navigate(`/admin/brands/${data.user_id}`);
            }}
        >
            <Row label="Business name">
                <Input
                    required
                    data-testid={IDS.brandName}
                    value={form.business_name}
                    onChange={set("business_name")}
                />
            </Row>
            <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Contact person">
                    <Input
                        required
                        data-testid={IDS.brandManager}
                        value={form.manager_name}
                        onChange={set("manager_name")}
                    />
                </Row>
                <Row label="Their designation">
                    <Input
                        data-testid={IDS.brandDesignation}
                        value={form.manager_designation}
                        onChange={set("manager_designation")}
                    />
                </Row>
                <Row label="WhatsApp" hint="Their login. In full, with +91.">
                    <Input
                        required
                        placeholder="+919876543210"
                        data-testid={IDS.brandPhone}
                        value={form.manager_phone}
                        onChange={set("manager_phone")}
                    />
                </Row>
                <Row label="Work email">
                    <Input
                        type="email"
                        data-testid={IDS.brandEmail}
                        value={form.manager_email}
                        onChange={set("manager_email")}
                    />
                </Row>
                <Row label="Category">
                    <select
                        className={select}
                        data-testid={IDS.brandCategory}
                        value={form.category}
                        onChange={set("category")}
                    >
                        <option value="">—</option>
                        {CATEGORY_OPTIONS.map((c) => (
                            <option key={c.value} value={c.value}>
                                {c.label}
                            </option>
                        ))}
                    </select>
                </Row>
                <Row label="City">
                    <Input
                        placeholder="Bengaluru"
                        data-testid={IDS.brandCity}
                        value={form.city}
                        onChange={set("city")}
                    />
                </Row>
            </div>
        </CreateShell>
    );
}

// ---------------------------------------------------------------------------
// A creator
// ---------------------------------------------------------------------------

const BLANK_CREATOR = { name: "", phone: "", instagram_handle: "", city: "" };

export function CreateCreatorDialog({ open, onOpenChange, onCreated }) {
    const [form, setForm] = useState(BLANK_CREATOR);
    const navigate = useNavigate();
    useEffect(() => {
        if (open) setForm(BLANK_CREATOR);
    }, [open]);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    return (
        <CreateShell
            open={open}
            onOpenChange={onOpenChange}
            testid={IDS.creatorDialog}
            title="New creator"
            // The rest of the profile is theirs to fill in. Saying so here is
            // what stops somebody typing a follower count they half-remember.
            blurb="Enters verified. A name and a number is all we take — the rest of the profile is built in the builder, by them."
            submitLabel="Create creator"
            onSubmit={async () => {
                const body = Object.fromEntries(
                    Object.entries(form).map(([k, v]) => [k, v.trim() || null]),
                );
                const { data } = await api.post("/admin/creators", body);
                notifySuccess(`${data.name} created`);
                onOpenChange(false);
                onCreated?.(data);
                navigate(`/admin/creators/${data.user_id}`);
            }}
        >
            <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Name">
                    <Input
                        required
                        data-testid={IDS.creatorName}
                        value={form.name}
                        onChange={set("name")}
                    />
                </Row>
                <Row label="WhatsApp" hint="Their login. In full, with +91.">
                    <Input
                        required
                        placeholder="+919876543210"
                        data-testid={IDS.creatorPhone}
                        value={form.phone}
                        onChange={set("phone")}
                    />
                </Row>
                <Row label="Instagram handle">
                    <Input
                        placeholder="asha.eats"
                        data-testid={IDS.creatorHandle}
                        value={form.instagram_handle}
                        onChange={set("instagram_handle")}
                    />
                </Row>
                <Row label="City">
                    <Input
                        placeholder="Bengaluru"
                        data-testid={IDS.creatorCity}
                        value={form.city}
                        onChange={set("city")}
                    />
                </Row>
            </div>
        </CreateShell>
    );
}

// ---------------------------------------------------------------------------
// A campaign
// ---------------------------------------------------------------------------

const BLANK_CAMPAIGN = {
    brand_id: "",
    title: "",
    brief: "",
    budget_per_creator: "",
    compensation_type: "fixed",
    execution_owner: "weare",
    category: "fnb",
    area: "",
    city: "Bengaluru",
    creators_needed: 1,
    campaign_type: "personal_table",
    event_date: "",
    start_date: "",
    end_date: "",
    status: "open",
};

const EVENT_TYPES = ["launch", "group_event"];

/** A `yyyy-mm-dd` from a date input, as the instant the server stores. */
const asInstant = (value) => (value ? new Date(value).toISOString() : null);

export function CreateCampaignDialog({ open, onOpenChange, onCreated }) {
    const [form, setForm] = useState(BLANK_CAMPAIGN);
    const [deliverables, setDeliverables] = useState({ reel: 1 });
    const [brands, setBrands] = useState([]);
    const navigate = useNavigate();

    useEffect(() => {
        if (!open) return;
        setForm(BLANK_CAMPAIGN);
        setDeliverables({ reel: 1 });
        api.get("/admin/brands")
            .then(({ data }) => setBrands(Array.isArray(data) ? data : []))
            .catch(() => setBrands([]));
    }, [open]);

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
    const isEvent = EVENT_TYPES.includes(form.campaign_type);
    // Barter has no fee, so asking for one would be asking for a number that
    // means nothing — the same rule `_resolve_agreed_amount` holds later.
    const isBarter = form.compensation_type === "barter";
    const items = useMemo(() => toDeliverableItems(deliverables), [deliverables]);

    return (
        <CreateShell
            open={open}
            onOpenChange={onOpenChange}
            testid={IDS.campaignDialog}
            title="New campaign"
            // Both halves of what makes this route different, in one line.
            blurb="Goes live without a review — we are the reviewer. Ours to run and barter-capable by default; edit the rest on the campaign's page."
            submitLabel="Create campaign"
            onSubmit={async () => {
                const body = {
                    brand_id: form.brand_id,
                    title: form.title.trim(),
                    brief: form.brief.trim(),
                    deliverable_items: items,
                    // **Whatever was typed, even on barter.** A barter brief
                    // keeps the budget it was posted with so that switching it
                    // back to cash is not lossy — zeroing it here would make
                    // the conversion produce a ₹0 brief.
                    budget_per_creator: Number(form.budget_per_creator || 0),
                    compensation_type: form.compensation_type,
                    execution_owner: form.execution_owner,
                    category: form.category,
                    area: form.area.trim(),
                    city: form.city.trim() || "Bengaluru",
                    creators_needed: Number(form.creators_needed || 1),
                    campaign_type: form.campaign_type,
                    status: form.status,
                    // The payload refuses the pair that does not belong to the
                    // type, so they are omitted rather than sent empty.
                    // **As an instant, not a bare date** — the same conversion
                    // the brand's form makes, so two campaigns posted on the
                    // same day from the two forms carry the same stored value.
                    // The payload refuses the pair that does not belong to the
                    // type, so they are omitted rather than sent empty.
                    ...(isEvent
                        ? { event_date: asInstant(form.event_date) }
                        : {
                              start_date: asInstant(form.start_date),
                              end_date: asInstant(form.end_date),
                          }),
                };
                const { data } = await api.post("/admin/campaigns", body);
                notifySuccess(
                    data.status === "draft" ? "Draft created" : "Campaign is live",
                );
                onOpenChange(false);
                onCreated?.(data);
                navigate(`/admin/campaigns/${data.id}`);
            }}
        >
            <Row label="Brand" hint="Whose brief this is.">
                <select
                    required
                    className={select}
                    data-testid={IDS.campaignBrand}
                    value={form.brand_id}
                    onChange={set("brand_id")}
                >
                    <option value="">Pick a brand…</option>
                    {brands.map((b) => (
                        <option key={b.user_id} value={b.user_id}>
                            {b.business_name || b.name || "Unnamed brand"}
                            {b.verified ? "" : " — not verified"}
                        </option>
                    ))}
                </select>
            </Row>

            <Row label="Title">
                <Input
                    required
                    data-testid={IDS.campaignTitle}
                    value={form.title}
                    onChange={set("title")}
                />
            </Row>
            <Row label="Brief">
                <Textarea
                    required
                    rows={3}
                    data-testid={IDS.campaignBrief}
                    value={form.brief}
                    onChange={set("brief")}
                />
            </Row>

            <Row label="Deliverables" hint="Zero is how you say no to a format.">
                <DeliverablePicker
                    value={deliverables}
                    onChange={setDeliverables}
                    testid={IDS.campaignDeliverables}
                />
            </Row>

            <div className="grid gap-3 sm:grid-cols-2">
                <Row label="Compensation">
                    {/* The one other control in the product that can set
                        barter. The brand's form imports the paid-only list, so
                        the option is absent there rather than disabled. */}
                    <select
                        className={select}
                        data-testid={IDS.campaignCompensation}
                        value={form.compensation_type}
                        onChange={set("compensation_type")}
                    >
                        {ALL_COMPENSATION_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                </Row>
                <Row
                    label="Fee per creator"
                    hint={isBarter ? "Barter — no fee." : "In rupees."}
                >
                    <Input
                        type="number"
                        min="0"
                        disabled={isBarter}
                        data-testid={IDS.campaignBudget}
                        value={isBarter ? "" : form.budget_per_creator}
                        onChange={set("budget_per_creator")}
                    />
                </Row>
                <Row label="Who runs it">
                    <select
                        className={select}
                        data-testid={IDS.campaignExecution}
                        value={form.execution_owner}
                        onChange={set("execution_owner")}
                    >
                        {/* Said from where the admin sits. `EXECUTION_OPTIONS`
                            is the brand's wording — "we'll run it ourselves"
                            means the brand there and would mean WeAre here,
                            which is the same two words for opposite parties. */}
                        <option value="weare">The WeAre team</option>
                        <option value="brand">The brand</option>
                    </select>
                </Row>
                <Row label="Creators needed">
                    <Input
                        type="number"
                        min="1"
                        data-testid={IDS.campaignCreatorsNeeded}
                        value={form.creators_needed}
                        onChange={set("creators_needed")}
                    />
                </Row>
                <Row label="Category">
                    <select
                        className={select}
                        data-testid={IDS.campaignCategory}
                        value={form.category}
                        onChange={set("category")}
                    >
                        {CATEGORY_OPTIONS.map((c) => (
                            <option key={c.value} value={c.value}>
                                {c.label}
                            </option>
                        ))}
                    </select>
                </Row>
                <Row label="Neighbourhood">
                    <Input
                        required
                        placeholder="Indiranagar"
                        data-testid={IDS.campaignArea}
                        value={form.area}
                        onChange={set("area")}
                    />
                </Row>
                <Row label="Kind">
                    <select
                        className={select}
                        data-testid={IDS.campaignType}
                        value={form.campaign_type}
                        onChange={set("campaign_type")}
                    >
                        <option value="personal_table">Personal table (a window)</option>
                        <option value="launch">Launch (one day)</option>
                        <option value="group_event">Group event (one day)</option>
                    </select>
                </Row>
                <Row label="Post as">
                    <select
                        className={select}
                        data-testid={IDS.campaignStatus}
                        value={form.status}
                        onChange={set("status")}
                    >
                        <option value="open">Live</option>
                        <option value="draft">Draft</option>
                    </select>
                </Row>

                {/* An event has a day; a personal table has a window. The
                    payload refuses the other pair outright, so the form asks
                    for exactly one of them rather than greying the other. */}
                {isEvent ? (
                    <Row label="Day" className="sm:col-span-2">
                        <Input
                            type="date"
                            required
                            data-testid={IDS.campaignEventDate}
                            value={form.event_date}
                            onChange={set("event_date")}
                        />
                    </Row>
                ) : (
                    <>
                        <Row label="Opens">
                            <Input
                                type="date"
                                required
                                data-testid={IDS.campaignStart}
                                value={form.start_date}
                                onChange={set("start_date")}
                            />
                        </Row>
                        <Row label="Closes">
                            <Input
                                type="date"
                                required
                                data-testid={IDS.campaignEnd}
                                value={form.end_date}
                                onChange={set("end_date")}
                            />
                        </Row>
                    </>
                )}
            </div>
        </CreateShell>
    );
}
