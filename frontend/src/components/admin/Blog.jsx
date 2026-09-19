// Eight years of operator knowledge, published.
//
// **The endpoints without this screen would be the case-study failure again.**
// A publishing surface nobody can reach from the console is a surface where
// nothing gets published — which is exactly the state the company was already
// in, with rate benchmarks and campaign playbooks living in people's heads and
// in WhatsApp threads.
//
// Three decisions:
//
// - **Draft is the only way in, and publishing is its own act.** A post that
//   went live the moment it was created would put half-written thinking on a
//   page a stranger can find, under the company's name.
// - **The body is plain text with two rules** — `## ` for a heading, `- ` for
//   a list — rendered server-side by `_blog_body_html`, which escapes first
//   and then allows exactly those two. A rich-text editor here would be an
//   editor whose output has to be sanitised on the way out, which is a much
//   harder thing to be sure about than two rules.
// - **A published post cannot be deleted**, only unpublished. The link may
//   already be out there, and the rule `case_studies` settled applies for the
//   same reason. The server refuses it; this offers Unpublish instead.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ExternalLink, Loader2, Plus } from "lucide-react";

import { api, formatApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/feedback";
import { DataTable } from "@/components/admin/console/DataTable";
import { StatusTag } from "@/components/admin/console/StatusTag";
import { DENSITY, TEXT } from "@/components/admin/console/tokens";
import { relative } from "@/components/admin/console/format";
import { ListEmptyState } from "@/components/data/DenseView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const BLANK = {
    title: "",
    summary: "",
    body: "",
    category: "rate-benchmarks",
    author_name: "",
};

function Field({ label, hint, children }) {
    return (
        <label className="block">
            <Label
                className={`${TEXT.meta} uppercase tracking-[0.15em] text-muted-foreground`}
            >
                {label}
            </Label>
            <div className="mt-1.5">{children}</div>
            {hint && <p className="mt-1 text-sm text-muted-foreground">{hint}</p>}
        </label>
    );
}

export default function Blog() {
    const [data, setData] = useState(null);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(BLANK);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const { data: d } = await api.get("/admin/blog");
            setData(d);
        } catch (e) {
            notifyError(e);
            setData({ posts: [], categories: [] });
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const categories = data?.categories || [];
    const set = (key) => (e) =>
        setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }));

    const openNew = () => {
        setForm(BLANK);
        setEditing("new");
        setError("");
    };

    const openEdit = async (row) => {
        setError("");
        try {
            const { data: post } = await api.get(`/admin/blog/${row.id}`);
            setForm({
                title: post.title || "",
                summary: post.summary || "",
                body: post.body || "",
                category: post.category || "rate-benchmarks",
                author_name: post.author_name || "",
            });
            setEditing(row);
        } catch (e) {
            notifyError(e);
        }
    };

    const save = async () => {
        setBusy(true);
        setError("");
        try {
            if (editing === "new") {
                await api.post("/admin/blog", form);
                notifySuccess("Draft created.");
            } else {
                await api.patch(`/admin/blog/${editing.id}`, form);
                notifySuccess("Saved.");
            }
            setEditing(null);
            await load();
        } catch (e) {
            setError(formatApiError(e));
        } finally {
            setBusy(false);
        }
    };

    const act = async (row, verb) => {
        try {
            await api.post(`/admin/blog/${row.id}/${verb}`);
            notifySuccess(verb === "publish" ? "Published." : "Back to draft.");
            await load();
        } catch (e) {
            notifyError(e);
        }
    };

    const remove = async (row) => {
        try {
            await api.delete(`/admin/blog/${row.id}`);
            notifySuccess("Deleted.");
            await load();
        } catch (e) {
            // The server refuses a published post, and its message says why.
            notifyError(e);
        }
    };

    const columns = useMemo(
        () => [
            {
                key: "title",
                header: "Title",
                mobile: "primary",
                value: (r) => r.title,
                cell: (r) => (
                    <button
                        type="button"
                        data-testid={`admin-blog-open-${r.id}`}
                        className="text-left hover:text-primary"
                        onClick={() => openEdit(r)}
                    >
                        {r.title}
                    </button>
                ),
            },
            {
                key: "category",
                header: "Category",
                mobile: "meta",
                value: (r) => r.category_label || "",
                // `value` is what the column sorts on; `cell` is what it
                // draws, and `DataTable` calls it unconditionally. A column
                // with only a `value` throws on the first render with rows in
                // it — which the section boundary catches, so the screen reads
                // "Guides couldn't load" rather than crashing. Caught in a
                // browser, because a list with no rows never reaches it.
                cell: (r) => r.category_label || "—",
            },
            {
                key: "status",
                header: "Status",
                mobile: "trailing",
                value: (r) => r.status,
                cell: (r) => <StatusTag state={r.status} label={r.status} />,
            },
            {
                key: "published_at",
                header: "Published",
                value: (r) => r.published_at || "",
                cell: (r) => (r.published_at ? relative(r.published_at) : "—"),
            },
            {
                key: "actions",
                header: "",
                mobile: "action",
                value: () => "",
                cell: (r) => (
                    <div className="flex items-center gap-2">
                        {r.status === "published" ? (
                            <>
                                <a
                                    href={`/blog/${r.slug}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-muted-foreground hover:text-foreground"
                                    title="View the live post"
                                >
                                    <ExternalLink className="h-4 w-4" />
                                </a>
                                <Button
                                    variant="ghost"
                                    data-testid={`admin-blog-unpublish-${r.id}`}
                                    onClick={() => act(r, "unpublish")}
                                >
                                    Unpublish
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    data-testid={`admin-blog-publish-${r.id}`}
                                    onClick={() => act(r, "publish")}
                                >
                                    Publish
                                </Button>
                                <Button
                                    variant="ghost"
                                    data-testid={`admin-blog-delete-${r.id}`}
                                    onClick={() => remove(r)}
                                >
                                    Delete
                                </Button>
                            </>
                        )}
                    </div>
                ),
            },
        ],
        // `openEdit`, `act` and `remove` are stable enough for a column set
        // rebuilt only when the rows change.
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [],
    );

    const rows = data?.posts || [];

    return (
        <section data-testid="admin-blog">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className={TEXT.heading}>Guides</h1>
                    <p className={`${TEXT.meta} text-muted-foreground`}>
                        {data
                            ? `${rows.length} post${rows.length === 1 ? "" : "s"}`
                            : "Loading…"}
                    </p>
                </div>
                <Button data-testid="admin-blog-new" onClick={openNew}>
                    <Plus className="mr-2 h-4 w-4" />
                    Write one
                </Button>
            </header>

            {data && rows.length === 0 ? (
                <ListEmptyState
                    title="Nothing written yet."
                    body="Rate benchmarks, campaign playbooks and disclosure guidance are what a brand searches for before it searches for us."
                />
            ) : (
                <DataTable
                    rows={rows}
                    columns={columns}
                    rowTestId={(r) => `admin-blog-row-${r.id}`}
                    loading={!data}
                />
            )}

            <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
                <DialogContent className={`${DENSITY.dialog} max-w-2xl`} grain={false}>
                    <DialogHeader>
                        <DialogTitle>
                            {editing === "new" ? "New guide" : "Edit guide"}
                        </DialogTitle>
                        <DialogDescription>
                            Two formatting rules: a line starting <code>##</code> is a
                            heading, and lines starting <code>-</code> are a list.
                            Everything else is a paragraph.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        <Field label="Title">
                            <Input
                                data-testid="admin-blog-title"
                                value={form.title}
                                onChange={set("title")}
                                placeholder="What a reel costs in Bengaluru"
                            />
                        </Field>
                        <Field
                            label="Summary"
                            hint="This is the search description and the line under the headline."
                        >
                            <Textarea
                                data-testid="admin-blog-summary"
                                rows={2}
                                value={form.summary}
                                onChange={set("summary")}
                            />
                        </Field>
                        <Field label="Category">
                            <select
                                data-testid="admin-blog-category"
                                value={form.category}
                                onChange={set("category")}
                                className="h-10 w-full rounded-md border border-tint/15 bg-card px-3 text-sm"
                            >
                                {categories.map((c) => (
                                    <option key={c.value} value={c.value}>
                                        {c.label}
                                    </option>
                                ))}
                            </select>
                        </Field>
                        <Field label="Body">
                            <Textarea
                                data-testid="admin-blog-body"
                                rows={14}
                                value={form.body}
                                onChange={set("body")}
                                className="font-mono text-sm"
                            />
                        </Field>
                        <Field label="Author" hint="Optional. Blank publishes it under WeAre Creators.">
                            <Input
                                data-testid="admin-blog-author"
                                value={form.author_name}
                                onChange={set("author_name")}
                            />
                        </Field>
                        {error && (
                            <p className="text-sm text-destructive" role="alert">
                                {error}
                            </p>
                        )}
                    </div>

                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setEditing(null)}>
                            Cancel
                        </Button>
                        <Button
                            data-testid="admin-blog-save"
                            disabled={busy}
                            onClick={save}
                        >
                            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Save draft
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </section>
    );
}
