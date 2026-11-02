// Our own staff, and what each of them runs.
//
// **Two staff roles, two blocks, and they must not read as one.** Both are
// accounts an admin creates and both sign in with email and password — which
// is the whole case for one screen — but what they can *see* is different, and
// that is the only fact a person choosing between them needs:
//
//   - `weare_team` is the console with a scope around it: the same sidebar,
//     queue, entity pages and actions, filtered on the server to the brands
//     that person is assigned to.
//   - `campaign_manager` is scoped per assigned *campaign* and reads the
//     roster and the daysheet — **creators' phone numbers** — because that is
//     the job of the person standing at the door.
//
// So each block says what the role sees rather than what it is called. A
// screen that offered "add staff" and a role dropdown would make the phone
// numbers a detail inside a picker.
//
// **Creating an account is here; assigning it is elsewhere.** A team member
// goes on a brand from the brand's own page; a manager goes on a campaign from
// the campaign's. That is the way round the work actually goes — somebody is
// put on a brand when the brand is being talked about — and it is why both
// tables' assignment columns are *readouts* rather than editors.
//
// Both halves are admin-only on the server. The team half is safe to draw
// anyway because the whole section is out of a team member's sidebar; the
// manager half is additionally gated on `allAccess`, because `POST
// /admin/managers` is `require_roles("admin")` where much of this console is
// `CONSOLE_ROLES` — and a form that 403s is worse than one that is absent.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, KeyRound, UserCog, Users } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    ADMIN_MANAGERS as MANAGER_IDS,
    ADMIN_TEAM as IDS,
    ADMIN_TABLE as TABLE_IDS,
} from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";

import DataTable, { sortRows } from "./console/DataTable";
import { BrandLink } from "./links";
import { TimeAgo } from "./console/format";
import { DENSITY, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";

const DEFAULTS = { sort: { key: "created_at", dir: "desc" } };

const BLANK = { name: "", email: "", password: "", phone: "" };

/**
 * A password somebody can read out over a phone and type once.
 *
 * Generated in the browser from `crypto.getRandomValues`, never from
 * `Math.random`, and never sent anywhere but the create call. The alphabet
 * leaves out the characters that get misread when this is dictated — no
 * `O`/`0`, no `l`/`1`/`I` — because the first thing that happens to it is
 * somebody reading it to the person it belongs to.
 */
const SAFE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";

function generatePassword(length = 16) {
    const bytes = new Uint32Array(length);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (n) => SAFE_CHARS[n % SAFE_CHARS.length]).join("");
}

/**
 * The one place a created password is on screen, and it is on screen once.
 *
 * **The server never returns it and nothing here logs it.** `POST
 * /admin/managers` answers with the account and no credential, so this is the
 * value the browser generated a moment ago, held in state until the admin
 * dismisses it. Reloading the screen loses it, which is the honest behaviour:
 * there is no second copy to go and read.
 */
function IssuedPassword({ account, password, onDismiss }) {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(password);
            setCopied(true);
        } catch {
            // No clipboard permission. The value is on screen to be typed,
            // which is why it is rendered as text rather than only copied.
            setCopied(false);
        }
    };

    return (
        <div
            data-testid={MANAGER_IDS.issued}
            className={`${PANEL} space-y-3 border-primary/30 bg-primary/5 p-3`}
        >
            <p className={`${TEXT.body} font-medium`}>
                {account.name}&apos;s account is ready — copy this password now
            </p>
            <p className={`${TEXT.meta} text-muted-foreground`}>
                It is not stored anywhere you can read it again. Send it to them,
                then dismiss this. If it is lost, make a new account.
            </p>
            <div className="flex flex-wrap items-center gap-2">
                <code className="select-all rounded-md border border-tint/15 bg-background/70 px-3 py-2 font-mono text-sm tracking-wider">
                    {password}
                </code>
                <Button
                    type="button"
                    variant="outline"
                    onClick={copy}
                    data-testid={MANAGER_IDS.copy}
                >
                    {copied ? (
                        <>
                            <Check className="mr-2 h-4 w-4" />
                            Copied
                        </>
                    ) : (
                        <>
                            <Copy className="mr-2 h-4 w-4" />
                            Copy
                        </>
                    )}
                </Button>
                <button
                    type="button"
                    onClick={onDismiss}
                    data-testid={MANAGER_IDS.dismiss}
                    className={`${TEXT.meta} min-h-[2.75rem] px-2 uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-150 hover:text-foreground`}
                >
                    Done
                </button>
            </div>
        </div>
    );
}

/**
 * Campaign managers: the people who run a shoot.
 *
 * This had no screen at all, which was not a cosmetic gap. Every
 * brand-posted brief is weare-run, so with no manager account in existence no
 * weare-run campaign could be staffed — no roster, no daysheet, no check-in
 * on any of them — and the campaign page's own assign dialog said "create one
 * first" while pointing at nothing.
 */
function Managers() {
    const [rows, setRows] = useState(null);
    const [form, setForm] = useState(BLANK);
    const [saving, setSaving] = useState(false);
    const [issued, setIssued] = useState(null);
    // Whether the value in the box is one this screen made. Only a generated
    // password is shown back afterwards — one the admin typed is one they
    // already have.
    const [generated, setGenerated] = useState(false);
    // Held so a generated value can be shown after the account exists without
    // reading it back out of the form, which is cleared on success.
    const pendingPassword = useRef("");

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/managers");
            setRows(data);
        } catch (err) {
            notifyError(err, { fallback: "The manager list couldn't load." });
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const create = async (e) => {
        e.preventDefault();
        setSaving(true);
        pendingPassword.current = form.password;
        try {
            const { data } = await api.post("/admin/managers", {
                name: form.name,
                email: form.email,
                password: form.password,
                phone: form.phone || null,
            });
            notifySuccess("Manager account created");
            setForm(BLANK);
            if (generated) setIssued({ account: data, password: pendingPassword.current });
            setGenerated(false);
            load();
        } catch (err) {
            notifyError(err, { fallback: "That account couldn't be created." });
        } finally {
            pendingPassword.current = "";
            setSaving(false);
        }
    };

    const columns = [
        {
            key: "name",
            label: "Name",
            mobile: "primary",
            value: (r) => r.name || "",
            cell: (r) => <span className="truncate">{r.name || "Unnamed"}</span>,
        },
        {
            key: "email",
            label: "Email",
            mobile: "meta",
            value: (r) => r.email || "",
            cell: (r) => (
                <span className="truncate text-muted-foreground">{r.email}</span>
            ),
        },
        {
            key: "active_campaigns",
            label: "Running",
            mobile: "trailing",
            numeric: true,
            // The number you look at before handing somebody a twelfth shoot.
            value: (r) => r.active_campaigns || 0,
            cell: (r) =>
                r.active_campaigns ? (
                    <span className="tabular-nums">{r.active_campaigns}</span>
                ) : (
                    <span className="text-muted-foreground">
                        Nothing yet — assign from a campaign&apos;s page
                    </span>
                ),
        },
    ];

    const sorted = rows ? sortRows(rows, columns, { key: "name", dir: "asc" }) : [];

    return (
        <section data-testid={MANAGER_IDS.section} className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <UserCog className="h-4 w-4 text-muted-foreground" />
                <h2 className={`${TEXT.body} font-medium`}>Campaign managers</h2>
                <span className={`${TEXT.meta} text-muted-foreground`}>
                    Assigned per campaign. On the ones they run they see the roster
                    and the daysheet, which carry creators&apos; phone numbers.
                </span>
            </div>

            {issued && (
                <IssuedPassword
                    account={issued.account}
                    password={issued.password}
                    onDismiss={() => setIssued(null)}
                />
            )}

            <form
                onSubmit={create}
                data-testid={MANAGER_IDS.create}
                className={`${PANEL} ${DENSITY.row} flex flex-col gap-2 p-3 md:flex-row md:items-end`}
            >
                <label className="min-w-0 flex-1">
                    <span className={`${TEXT.meta} block text-muted-foreground`}>Name</span>
                    <Input
                        required
                        data-testid={MANAGER_IDS.name}
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                    />
                </label>
                <label className="min-w-0 flex-1">
                    <span className={`${TEXT.meta} block text-muted-foreground`}>Work email</span>
                    <Input
                        required
                        type="email"
                        data-testid={MANAGER_IDS.email}
                        value={form.email}
                        onChange={(e) => setForm({ ...form, email: e.target.value })}
                    />
                </label>
                <label className="min-w-0 flex-[1.2]">
                    {/* Typed or generated, and either way it is never read back
                        from the server — the create route answers with the
                        account and no credential. */}
                    <span className={`${TEXT.meta} block text-muted-foreground`}>
                        Password <span className="opacity-60">(8 or more)</span>
                    </span>
                    <div className="flex gap-1">
                        <Input
                            required
                            // `text` once generated, so the admin can read the
                            // thing they are about to send to somebody. A
                            // generated value behind dots is a value nobody can
                            // check they copied.
                            type={generated ? "text" : "password"}
                            minLength={8}
                            maxLength={128}
                            data-testid={MANAGER_IDS.password}
                            value={form.password}
                            onChange={(e) => {
                                setGenerated(false);
                                setForm({ ...form, password: e.target.value });
                            }}
                            className={generated ? "font-mono tracking-wider" : undefined}
                        />
                        <Button
                            type="button"
                            variant="outline"
                            title="Generate a password"
                            data-testid={MANAGER_IDS.generate}
                            onClick={() => {
                                setForm((f) => ({ ...f, password: generatePassword() }));
                                setGenerated(true);
                            }}
                            className="flex-none"
                        >
                            <KeyRound className="h-4 w-4" />
                        </Button>
                    </div>
                </label>
                <label className="min-w-0 flex-1">
                    <span className={`${TEXT.meta} block text-muted-foreground`}>
                        WhatsApp <span className="opacity-60">(optional)</span>
                    </span>
                    <Input
                        data-testid={MANAGER_IDS.phone}
                        value={form.phone}
                        onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    />
                </label>
                <Button type="submit" disabled={saving} data-testid={MANAGER_IDS.submit}>
                    {saving ? "Adding…" : "Add"}
                </Button>
            </form>

            <DataTable
                columns={columns}
                rows={sorted}
                rowKey={(r) => r.id}
                rowTestId={(r) => MANAGER_IDS.row(r.id)}
                loading={!rows}
                testid={MANAGER_IDS.table}
                minWidth="min-w-[36rem]"
                empty={
                    <ListEmptyState
                        Icon={UserCog}
                        testid={MANAGER_IDS.empty}
                        emptyTitle="No campaign managers yet"
                        emptyBody="Every brand-posted brief is run by us, and a brief with no manager has no roster, no daysheet and no check-in. Add one above."
                    />
                }
            />
        </section>
    );
}

export default function AdminTeam({ allAccess = true }) {
    const [rows, setRows] = useState(null);
    const [form, setForm] = useState(BLANK);
    const [saving, setSaving] = useState(false);
    const { state, patch, scrollRef } = useListState("team", DEFAULTS);
    const { sort } = state;

    const load = useCallback(async () => {
        setRows(null);
        try {
            const { data } = await api.get("/admin/team");
            setRows(data);
        } catch (err) {
            notifyError(err, { fallback: "The team list couldn't load." });
            setRows([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const create = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post("/admin/team", { ...form, brand_ids: [] });
            notifySuccess("Account created");
            setForm(BLANK);
            load();
        } catch (err) {
            notifyError(err, { fallback: "That account couldn't be created." });
        } finally {
            setSaving(false);
        }
    };

    const columns = [
        {
            key: "name",
            label: "Name",
            mobile: "primary",
            value: (r) => r.name || "",
            cell: (r) => <span className="truncate">{r.name || "Unnamed"}</span>,
        },
        {
            key: "email",
            label: "Email",
            mobile: "meta",
            value: (r) => r.email || "",
            cell: (r) => (
                <span className="truncate text-muted-foreground">{r.email}</span>
            ),
        },
        {
            key: "brands",
            label: "Runs",
            mobile: "trailing",
            // Sorted on the count, printed as the names: "who has the most on"
            // is the question a column of brand names cannot answer.
            value: (r) => (r.brands || []).length,
            cell: (r) =>
                (r.brands || []).length ? (
                    <span className="flex min-w-0 flex-wrap gap-x-2">
                        {r.brands.map((b) => (
                            <BrandLink
                                key={b.user_id}
                                id={b.user_id}
                                name={b.business_name}
                            />
                        ))}
                    </span>
                ) : (
                    // Not a dash: nobody assigned yet is a state somebody has
                    // to do something about, and their console is empty until
                    // they do.
                    <span className="text-muted-foreground">
                        No brands yet — assign from a brand&apos;s page
                    </span>
                ),
        },
        {
            key: "created_at",
            label: "Added",
            mobile: "meta",
            numeric: true,
            value: (r) => r.created_at || "",
            cell: (r) => <TimeAgo iso={r.created_at} />,
        },
    ];

    const sorted = rows ? sortRows(rows, columns, sort) : [];

    return (
        <div data-testid={IDS.page} className="space-y-10">
            <section className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <h1 className={`${TEXT.body} font-medium`}>Team</h1>
                    <span className={`${TEXT.meta} text-muted-foreground`}>
                        Assigned per brand. They see this console scoped to the
                        brands they are on, and no creator contact details.
                    </span>
                </div>

                <form
                    onSubmit={create}
                    data-testid={IDS.create}
                    className={`${PANEL} ${DENSITY.row} flex flex-col gap-2 p-3 md:flex-row md:items-end`}
                >
                    <label className="min-w-0 flex-1">
                        <span className={`${TEXT.meta} block text-muted-foreground`}>Name</span>
                        <Input
                            required
                            data-testid={IDS.name}
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                        />
                    </label>
                    <label className="min-w-0 flex-1">
                        <span className={`${TEXT.meta} block text-muted-foreground`}>Work email</span>
                        <Input
                            required
                            type="email"
                            data-testid={IDS.email}
                            value={form.email}
                            onChange={(e) => setForm({ ...form, email: e.target.value })}
                        />
                    </label>
                    <label className="min-w-0 flex-1">
                        {/* Staff sign in with a password. Creators and brands are
                            WhatsApp-OTP only, which is why there is no self-signup
                            into either staff role. */}
                        <span className={`${TEXT.meta} block text-muted-foreground`}>Password</span>
                        <Input
                            required
                            type="password"
                            minLength={8}
                            data-testid={IDS.password}
                            value={form.password}
                            onChange={(e) => setForm({ ...form, password: e.target.value })}
                        />
                    </label>
                    <label className="min-w-0 flex-1">
                        <span className={`${TEXT.meta} block text-muted-foreground`}>
                            WhatsApp <span className="opacity-60">(optional)</span>
                        </span>
                        <Input
                            data-testid={IDS.phone}
                            value={form.phone}
                            onChange={(e) => setForm({ ...form, phone: e.target.value })}
                        />
                    </label>
                    <Button type="submit" disabled={saving} data-testid={IDS.submit}>
                        {saving ? "Adding…" : "Add"}
                    </Button>
                </form>

                <DataTable
                    columns={columns}
                    rows={sorted}
                    rowKey={(r) => r.id}
                    rowTestId={(r) => IDS.row(r.id)}
                    sort={sort}
                    onSortChange={(next) => patch({ sort: next })}
                    loading={!rows}
                    scrollRef={scrollRef}
                    testid={TABLE_IDS.root}
                    minWidth="min-w-[40rem]"
                    empty={
                        <ListEmptyState
                            Icon={Users}
                            testid={IDS.empty}
                            emptyTitle="Nobody on the team yet"
                            emptyBody="Add an account above, then put them on a brand from that brand's page."
                        />
                    }
                />
            </section>

            {/* Admin-only, because the route is. A `weare_team` member reaching
                this section at all would be reaching a form the server refuses. */}
            {allAccess && <Managers />}
        </div>
    );
}
