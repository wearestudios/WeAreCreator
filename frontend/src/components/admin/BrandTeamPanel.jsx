// Who at WeAre runs this brand.
//
// **On the brand's page, deliberately**, because that is where the decision is
// made: somebody is put on a brand while the brand is being talked about, not
// while an account is being created. The accounts themselves come from
// `/admin/team`.
//
// Read by both console roles — a team member should be able to see who else is
// on a brand they run — and **written only by an admin**, which is the rule
// that makes the whole scope mean anything: a role that can widen its own
// scope does not have one. The server holds that line; the picker below is
// simply absent for anybody else, rather than present and refused.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { UserCog, X } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { ADMIN_BRAND_TEAM as IDS } from "@/constants/testIds";
import { CALM, FOCUS, TEXT } from "@/components/admin/console/tokens";

export default function BrandTeamPanel({ brandId, canAssign }) {
    const [members, setMembers] = useState(null);
    const [everyone, setEveryone] = useState([]);
    const [picked, setPicked] = useState("");
    const [busy, setBusy] = useState(null);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/admin/brands/${brandId}/team`);
            setMembers(data);
        } catch {
            // A panel, not the page. Failing to read it must not cost the
            // documents somebody came here to check.
            setMembers([]);
        }
    }, [brandId]);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(() => {
        if (!canAssign) return;
        api.get("/admin/team")
            .then(({ data }) => setEveryone(data))
            .catch(() => setEveryone([]));
    }, [canAssign]);

    // Anybody not already on it. Offering somebody who is would make the
    // button a no-op that reports success — `$addToSet` is idempotent, so the
    // refusal has to be in the list rather than in the response.
    const available = useMemo(() => {
        const on = new Set((members || []).map((m) => m.id));
        return everyone.filter((m) => !on.has(m.id));
    }, [everyone, members]);

    const assign = async () => {
        if (!picked) return;
        setBusy("assign");
        try {
            await api.post(`/admin/brands/${brandId}/team`, { user_id: picked });
            notifySuccess("Added to this brand");
            setPicked("");
            load();
        } catch (err) {
            notifyError(err, { fallback: "They couldn't be added." });
        } finally {
            setBusy(null);
        }
    };

    const remove = async (member) => {
        setBusy(member.id);
        try {
            await api.delete(`/admin/brands/${brandId}/team/${member.id}`);
            notifySuccess(`${member.name || "They"} no longer sees this brand`);
            load();
        } catch (err) {
            notifyError(err, { fallback: "They couldn't be removed." });
        } finally {
            setBusy(null);
        }
    };

    return (
        <div
            data-testid={IDS.section}
            className="rounded-md border border-white/10 bg-card"
        >
            {members === null ? (
                <div className="px-5 py-4" aria-hidden="true">
                    <div className="h-5 w-40 animate-pulse rounded bg-white/5" />
                </div>
            ) : members.length === 0 ? (
                <p
                    data-testid={IDS.empty}
                    className="px-5 py-4 text-sm text-muted-foreground"
                >
                    Nobody at WeAre is on this brand. Its campaigns reach admins
                    only.
                </p>
            ) : (
                <ul className="divide-y divide-white/10">
                    {members.map((m) => (
                        <li
                            key={m.id}
                            data-testid={IDS.member(m.id)}
                            className="flex items-center gap-3 px-5 py-3"
                        >
                            <UserCog
                                aria-hidden="true"
                                className="h-4 w-4 flex-none text-muted-foreground"
                            />
                            <span className="min-w-0 flex-1 text-sm">
                                {m.name || "Unnamed"}
                                <span className={`block ${TEXT.meta} text-muted-foreground`}>
                                    {m.email}
                                </span>
                            </span>
                            {canAssign && (
                                <button
                                    type="button"
                                    onClick={() => remove(m)}
                                    disabled={busy === m.id}
                                    data-testid={IDS.remove(m.id)}
                                    aria-label={`Take ${m.name || "them"} off this brand`}
                                    className={`grid h-8 w-8 flex-none place-items-center rounded ${CALM} text-muted-foreground hover:bg-white/5 hover:text-foreground disabled:opacity-50 ${FOCUS}`}
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            )}
                        </li>
                    ))}
                </ul>
            )}

            {canAssign && (
                <div className="flex flex-col gap-2 border-t border-white/10 px-5 py-3 sm:flex-row sm:items-center">
                    <select
                        value={picked}
                        onChange={(e) => setPicked(e.target.value)}
                        data-testid={IDS.picker}
                        aria-label="Put somebody on this brand"
                        className={`h-9 min-w-0 flex-1 rounded border border-white/10 bg-background px-2 text-sm ${CALM} ${FOCUS}`}
                    >
                        <option value="">Put somebody on this brand…</option>
                        {available.map((m) => (
                            <option key={m.id} value={m.id}>
                                {m.name || m.email}
                            </option>
                        ))}
                    </select>
                    <Button
                        type="button"
                        onClick={assign}
                        disabled={!picked || busy === "assign"}
                        data-testid={IDS.assign}
                        className="flex-none"
                    >
                        {busy === "assign" ? "Adding…" : "Add"}
                    </Button>
                </div>
            )}

            {canAssign && everyone.length === 0 && (
                <p className={`border-t border-white/10 px-5 py-3 ${TEXT.meta} text-muted-foreground`}>
                    No team accounts exist yet — create one under Team.
                </p>
            )}
        </div>
    );
}
