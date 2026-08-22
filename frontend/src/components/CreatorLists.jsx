// People you would ask again.
//
// A brand that found four good creators for its launch had no way to keep them
// together: next launch it searched the directory from nothing and hoped it
// recognised the handles. The knowledge a campaign built evaporated the moment
// it finished.
//
// **One component for both audiences**, because the server decides whose lists
// these are — a brand sees its brand's, WeAre staff see WeAre's. It never asks
// what role is looking, the same rule the shared application screen holds.
import React, { useCallback, useEffect, useState } from "react";
import { ListPlus, Loader2, Send, Trash2, Users } from "lucide-react";

import { api } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CREATOR_LISTS as IDS } from "@/constants/testIds";
import { ReliabilityBadge } from "@/components/ReliabilityBadge";
import { CreatorAvatar } from "@/components/admin/shared";

/**
 * @param {string} [props.campaignId]  When given, each list offers "Invite all"
 *   — which is the whole point of a list, and is absent everywhere there is no
 *   campaign to invite them to rather than being present and disabled.
 */
export default function CreatorLists({ campaignId, onInvited }) {
    const [lists, setLists] = useState(null);
    const [name, setName] = useState("");
    const [busy, setBusy] = useState(null);
    const [creating, setCreating] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/brand/creator-lists");
            setLists(data.lists || []);
        } catch (err) {
            notifyError(err, { fallback: "Your lists couldn't load." });
            setLists([]);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const create = async () => {
        if (!name.trim()) return;
        setCreating(true);
        try {
            await api.post("/brand/creator-lists", { name: name.trim(), creator_ids: [] });
            setName("");
            notifySuccess("List created");
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be created." });
        } finally {
            setCreating(false);
        }
    };

    const invite = async (list) => {
        setBusy(list.id);
        try {
            const { data } = await api.post(
                `/brand/campaigns/${campaignId}/invite-list/${list.id}`
            );
            const sent = Object.values(data?.results || {}).filter(
                (r) => r.status === "sent"
            ).length;
            notifySuccess(
                sent
                    ? `Invited ${sent} from “${list.name}”`
                    : `Nobody new to invite from “${list.name}”`
            );
            onInvited?.();
        } catch (err) {
            notifyError(err, { fallback: "Those invitations couldn't go out." });
        } finally {
            setBusy(null);
        }
    };

    const remove = async (list) => {
        setBusy(list.id);
        try {
            await api.delete(`/brand/creator-lists/${list.id}`);
            notifySuccess("List removed");
            await load();
        } catch (err) {
            notifyError(err, { fallback: "That couldn't be removed." });
        } finally {
            setBusy(null);
        }
    };

    return (
        <section data-testid={IDS.panel} className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Saved lists
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Worked well at launches"
                    maxLength={80}
                    data-testid={IDS.name}
                    className="h-10 w-64 border-white/10 bg-background/60"
                />
                <Button
                    size="sm"
                    onClick={create}
                    disabled={creating || !name.trim()}
                    data-testid={IDS.submit}
                    className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                >
                    {creating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    <ListPlus className="mr-1.5 h-3.5 w-3.5" />
                    New list
                </Button>
            </div>

            {lists && lists.length === 0 ? (
                <p data-testid={IDS.empty} className="text-sm text-muted-foreground">
                    No lists yet. Make one, then add creators to it from the directory or an
                    applicant board — next time you brief, they're already together.
                </p>
            ) : (
                <ul className="space-y-3">
                    {(lists || []).map((list) => (
                        <li
                            key={list.id}
                            data-testid={IDS.row(list.id)}
                            className="rounded-md border border-white/10 bg-card p-4"
                        >
                            <div className="flex flex-wrap items-center gap-3">
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm">{list.name}</p>
                                    <p className="mt-0.5 text-xs text-muted-foreground">
                                        {list.member_count}{" "}
                                        {list.member_count === 1 ? "creator" : "creators"}
                                    </p>
                                </div>
                                {/* Absent, not disabled, where there is no
                                    campaign to invite them to — a greyed
                                    button is a question nobody can answer. */}
                                {campaignId && list.member_count > 0 && (
                                    <Button
                                        size="sm"
                                        onClick={() => invite(list)}
                                        disabled={busy === list.id}
                                        data-testid={IDS.invite(list.id)}
                                        className="min-h-[2.75rem] bg-ember-500 text-white hover:bg-ember-600 sm:min-h-0"
                                    >
                                        {busy === list.id && (
                                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                        )}
                                        <Send className="mr-1.5 h-3.5 w-3.5" />
                                        Invite all
                                    </Button>
                                )}
                                <button
                                    type="button"
                                    onClick={() => remove(list)}
                                    disabled={busy === list.id}
                                    data-testid={IDS.remove(list.id)}
                                    title="Remove this list"
                                    className="rounded border border-white/10 p-2 text-muted-foreground transition-colors duration-150 hover:border-destructive/40 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500"
                                >
                                    <Trash2 className="h-3.5 w-3.5" />
                                    <span className="sr-only">Remove list</span>
                                </button>
                            </div>

                            {list.members?.length > 0 && (
                                <ul className="mt-3 flex flex-wrap gap-2">
                                    {list.members.map((m) => (
                                        <li
                                            key={m.user_id}
                                            className="flex items-center gap-2 rounded border border-white/10 px-2 py-1"
                                        >
                                            <CreatorAvatar creator={m} size="h-5 w-5" />
                                            <span className="text-xs">{m.name}</span>
                                            {/* The band, never the counts —
                                                the same rule every other
                                                brand surface holds. */}
                                            <ReliabilityBadge reliability={m.reliability} />
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
