// Our own staff, and what each of them runs.
//
// `weare_team` is the console with a scope around it: the same sidebar, the
// same queue, the same entity pages and the same actions, filtered on the
// server to the brands that person is assigned to. This screen is where the
// accounts come from.
//
// **Creating an account is here; assigning it to a brand is on the brand's own
// page.** That is the way round the work actually goes — somebody is put on a
// brand when the brand is being talked about, not when the account is made —
// and it is why this table's brand column is a *readout* rather than an
// editor. There is one row of truth and two places that read it.
//
// Admin-only, and the server holds that line: a scoped role that could widen
// its own scope is not a scope. Nothing here is drawn for a team member,
// because the section itself is not in their sidebar.
import React, { useCallback, useEffect, useState } from "react";
import { UserCog } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ADMIN_TEAM as IDS, ADMIN_TABLE as TABLE_IDS } from "@/constants/testIds";
import { ListEmptyState } from "@/components/data/DenseView";

import DataTable, { sortRows } from "./console/DataTable";
import { BrandLink } from "./links";
import { TimeAgo } from "./console/format";
import { DENSITY, PANEL, TEXT } from "./console/tokens";
import useListState from "./console/useListState";

const DEFAULTS = { sort: { key: "created_at", dir: "desc" } };

const BLANK = { name: "", email: "", password: "", phone: "" };

export default function AdminTeam() {
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
                        No brands yet — assign from a brand's page
                    </span>
                ),
        },
        {
            key: "created_at",
            label: "Added",
            mobile: "meta",
            numeric: true,
            value: (r) => r.created_at || "",
            cell: (r) => <TimeAgo value={r.created_at} />,
        },
    ];

    const sorted = rows ? sortRows(rows, columns, sort) : [];

    return (
        <div data-testid={IDS.page} className="space-y-4">
            <div className="flex items-center gap-2">
                <UserCog className="h-4 w-4 text-muted-foreground" />
                <h1 className={`${TEXT.body} font-medium`}>Team</h1>
                <span className={`${TEXT.meta} text-muted-foreground`}>
                    Staff who run campaigns for our own clients. Each sees the
                    console scoped to the brands they are on.
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
                        WhatsApp-OTP only, and this role reads creators' phone
                        numbers on the brands it runs — which is exactly why
                        there is no self-signup into it. */}
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
                        Icon={UserCog}
                        testid={IDS.empty}
                        emptyTitle="Nobody on the team yet"
                        emptyBody="Add an account above, then put them on a brand from that brand's page."
                    />
                }
            />
        </div>
    );
}
