// The admin console: a left nav and five working surfaces. The action queue is
// the landing view — one prioritised list of everything waiting on us — and the
// other four are for looking things up and acting on them in place.
//
// Anything destructive or reversible (reject, cancel, revert, refund, pause,
// close) goes through a confirmation dialog with a required reason, and that
// reason surfaces again in the audit section.
import React, { useCallback, useEffect, useState } from "react";
import {
    Building2,
    Inbox,
    Menu,
    ScrollText,
    Sparkles,
    Users,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { api } from "@/lib/api";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { ADMIN_SHELL as IDS } from "@/constants/testIds";
import ActionQueue from "@/components/admin/ActionQueue";
import AdminCreators from "@/components/admin/AdminCreators";
import AdminCampaigns from "@/components/admin/AdminCampaigns";
import AdminBrands from "@/components/admin/AdminBrands";
import AdminAudit from "@/components/admin/AdminAudit";

const SECTIONS = [
    { key: "queue", label: "Action queue", Icon: Inbox },
    { key: "creators", label: "Creators", Icon: Users },
    { key: "campaigns", label: "Campaigns", Icon: Sparkles },
    { key: "brands", label: "Brands", Icon: Building2 },
    { key: "audit", label: "Audit log", Icon: ScrollText },
];

function NavItems({ active, badge, onSelect }) {
    return (
        <nav className="flex flex-col gap-1">
            {SECTIONS.map(({ key, label, Icon }) => {
                const on = active === key;
                return (
                    <button
                        key={key}
                        type="button"
                        aria-current={on ? "page" : undefined}
                        onClick={() => onSelect(key)}
                        data-testid={IDS.navItem(key)}
                        className={
                            "flex items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition-colors duration-200 " +
                            (on
                                ? "bg-ember-500/10 text-ember-500"
                                : "text-muted-foreground hover:bg-white/5 hover:text-foreground")
                        }
                    >
                        <Icon className="h-4 w-4 flex-none" />
                        <span className="flex-1">{label}</span>
                        {key === "queue" && badge > 0 && (
                            <span
                                data-testid={IDS.navBadge(key)}
                                className="grid h-5 min-w-[1.25rem] flex-none place-items-center rounded-full bg-ember-500 px-1.5 text-[10px] font-medium text-black"
                            >
                                {badge > 99 ? "99+" : badge}
                            </span>
                        )}
                    </button>
                );
            })}
        </nav>
    );
}

export default function AdminConsole() {
    const [active, setActive] = useState("queue");
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const [pendingCount, setPendingCount] = useState(0);
    const [feePercent, setFeePercent] = useState(null);
    // Set when the Brands section hands off to Campaigns filtered to one brand.
    const [brandFilter, setBrandFilter] = useState("");

    // One metrics call feeds the queue badge and the fee preview. Refreshed
    // after any action, so the badge tracks what's actually left.
    const loadMetrics = useCallback(async () => {
        try {
            const { data } = await api.get("/admin/metrics");
            setPendingCount(data.awaiting_admin_action ?? 0);
            setFeePercent(data.platform_fee_percent);
        } catch {
            /* the badge is a convenience, not a feature that may fail loudly */
        }
    }, []);

    useEffect(() => {
        loadMetrics();
    }, [loadMetrics]);

    const select = (key) => {
        setActive(key);
        setMobileNavOpen(false);
        if (key !== "campaigns") setBrandFilter("");
    };

    const viewBrandCampaigns = (brandId) => {
        setBrandFilter(brandId);
        setActive("campaigns");
    };

    const activeMeta = SECTIONS.find((s) => s.key === active);

    return (
        <div data-testid={IDS.page} className="min-h-screen bg-background">
            <Navbar />
            <div className="mx-auto flex max-w-7xl gap-10 px-6 py-10 md:py-14">
                {/* Desktop nav */}
                <aside
                    data-testid={IDS.nav}
                    className="hidden w-52 flex-none md:block"
                >
                    <p className="px-3 text-xs uppercase tracking-[0.2em] text-ember-500">
                        Admin
                    </p>
                    <h1
                        data-testid={IDS.heading}
                        className="mt-2 px-3 font-serif text-2xl leading-tight tracking-tight"
                    >
                        Console
                    </h1>
                    <div className="mt-8">
                        <NavItems active={active} badge={pendingCount} onSelect={select} />
                    </div>
                </aside>

                <main className="min-w-0 flex-1">
                    {/* Mobile: current section + a hamburger opening the nav */}
                    <div className="mb-8 flex items-center justify-between md:hidden">
                        <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Admin console
                            </p>
                            <h1 className="mt-1 font-serif text-2xl leading-tight tracking-tight">
                                {activeMeta?.label}
                            </h1>
                        </div>
                        <button
                            type="button"
                            onClick={() => setMobileNavOpen(true)}
                            aria-label="Open sections"
                            data-testid={IDS.mobileNavOpen}
                            className="relative grid h-10 w-10 place-items-center rounded-md border border-white/10 bg-card text-foreground transition-colors duration-200 hover:border-white/25"
                        >
                            <Menu className="h-4 w-4" />
                            {pendingCount > 0 && active !== "queue" && (
                                <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-ember-500" />
                            )}
                        </button>
                    </div>

                    <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
                        <SheetContent
                            side="left"
                            data-testid={IDS.mobileNav}
                            className="w-64 border-r border-white/10 bg-background p-6"
                        >
                            <SheetTitle className="sr-only">Console sections</SheetTitle>
                            <SheetDescription className="sr-only">
                                Switch between the admin console's sections.
                            </SheetDescription>
                            <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                                Admin console
                            </p>
                            <div className="mt-6">
                                <NavItems
                                    active={active}
                                    badge={pendingCount}
                                    onSelect={select}
                                />
                            </div>
                        </SheetContent>
                    </Sheet>

                    {/* Sections stay mounted-on-demand: each loads its own data
                        when shown, and actions bump the shared badge. */}
                    <div data-testid={IDS.section(active)}>
                        {active === "queue" && (
                            <ActionQueue onChanged={loadMetrics} feePercent={feePercent} />
                        )}
                        {active === "creators" && <AdminCreators />}
                        {active === "campaigns" && (
                            <AdminCampaigns
                                brandFilter={brandFilter}
                                onClearBrand={() => setBrandFilter("")}
                                onChanged={loadMetrics}
                            />
                        )}
                        {active === "brands" && (
                            <AdminBrands
                                onChanged={loadMetrics}
                                onViewCampaigns={viewBrandCampaigns}
                            />
                        )}
                        {active === "audit" && <AdminAudit />}
                    </div>
                </main>
            </div>
        </div>
    );
}
