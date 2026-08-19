// The logged-out bar, for the marketing site only.
//
// **A variant, not an edit.** `components/Navbar.jsx` is on nineteen surfaces —
// every dashboard, the console, the manager screens, onboarding — where it
// carries role links, the notification bell and the creator's avatar menu, and
// where it must keep behaving exactly as it does. This one has a single
// audience and one job: the four pages, the two auth actions, and the studio
// endorsement.
//
// So it does not read `useAuth` at all. The marketing pages are the signed-out
// site; a signed-in visitor who lands on `/for-brands` sees the same bar and
// the same two buttons, which is correct — they can still get to their
// dashboard through Log in, and the alternative is this component growing a
// second mode and drifting into being the shared one.
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StudioEndorsement } from "@/components/StudioEndorsement";
import { MARKETING_LINKS } from "@/lib/siteNav";
import { MARKETING as IDS, LANDING_STUDIO as STUDIO_IDS } from "@/constants/testIds";
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet";

const LINK =
    "text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground";

export function MarketingNavbar() {
    const [open, setOpen] = useState(false);

    return (
        <header
            data-testid={IDS.navbar}
            // Glassmorphism per the component rules: never transparent, a
            // delicate inner stroke, and the same 4rem height the shared bar
            // uses so `STICKY`'s offsets still describe the page.
            className="sticky top-0 z-40 w-full border-b border-white/10 bg-black/60 backdrop-blur-xl"
        >
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
                <div className="flex items-center gap-3">
                    <Link
                        to="/"
                        data-testid={IDS.navLogo}
                        className="-my-1 flex min-h-[2.75rem] items-center gap-2 py-1 transition-colors duration-200 hover:text-ember-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0"
                    >
                        <span className="grid h-8 w-8 place-items-center rounded-md bg-ember-500 font-serif text-lg font-semibold text-black">
                            W
                        </span>
                        <span className="font-serif text-xl tracking-tight">
                            WeAre <span className="text-ember-500">Creators</span>
                        </span>
                    </Link>
                    <span aria-hidden className="hidden h-4 w-px bg-white/15 sm:block" />
                    {/* Outside the <Link>, so tapping the logo can only ever go
                        to Creators' own home. An endorsement, not a co-brand. */}
                    <StudioEndorsement
                        testid={STUDIO_IDS.nav}
                        className="hidden sm:block"
                    />
                </div>

                <nav aria-label="Marketing" className="hidden items-center gap-7 md:flex">
                    {MARKETING_LINKS.map((l) => (
                        <Link key={l.to} to={l.to} data-testid={l.testId} className={LINK}>
                            {l.label}
                        </Link>
                    ))}
                </nav>

                <div className="flex items-center gap-3">
                    <Link
                        to="/login"
                        data-testid={IDS.navSignIn}
                        className={`hidden sm:inline ${LINK}`}
                    >
                        Sign in
                    </Link>
                    {/* "Join" rather than "Sign up as a creator": the menu
                        beside it names two audiences, and a creator-specific
                        button tells a brand the bar is not for them. /signup
                        carries a role picker and defaults to creator. */}
                    <Link to="/signup" data-testid={IDS.navJoin}>
                        <Button className="rounded-full bg-ember-500 px-5 text-black transition-colors duration-200 hover:bg-ember-400">
                            Join
                        </Button>
                    </Link>

                    {/* Everything above collapses below md; this is the way in,
                        and it is the only navigation on a phone — anything
                        missing here is unreachable there. */}
                    <Sheet open={open} onOpenChange={setOpen}>
                        <SheetTrigger asChild>
                            <button
                                type="button"
                                data-testid={IDS.navMenuButton}
                                aria-label="Open menu"
                                className="grid h-11 w-11 place-items-center rounded-md text-muted-foreground transition-colors duration-200 hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:hidden"
                            >
                                <Menu className="h-5 w-5" />
                            </button>
                        </SheetTrigger>
                        <SheetContent
                            side="right"
                            data-testid={IDS.navMenu}
                            aria-describedby={undefined}
                            className="w-[86%] border-l border-white/10 bg-background p-0 sm:max-w-sm"
                        >
                            <SheetTitle className="sr-only">Menu</SheetTitle>
                            <div className="flex h-full flex-col">
                                <div className="flex flex-col gap-1 border-b border-white/10 px-6 py-5">
                                    <span className="font-serif text-xl tracking-tight">
                                        WeAre <span className="text-ember-500">Creators</span>
                                    </span>
                                    <StudioEndorsement testid={STUDIO_IDS.navMobile} />
                                </div>

                                <nav className="flex-1 overflow-y-auto px-6 py-7">
                                    <div className="flex flex-col">
                                        {MARKETING_LINKS.map((l) => (
                                            <SheetClose asChild key={l.to}>
                                                <Link
                                                    to={l.to}
                                                    data-testid={`${l.testId}-mobile`}
                                                    className="border-b border-white/10 py-3.5 font-serif text-2xl leading-tight text-foreground transition-colors duration-200 hover:text-ember-500"
                                                >
                                                    {l.label}
                                                </Link>
                                            </SheetClose>
                                        ))}
                                    </div>
                                </nav>

                                <div className="flex flex-col gap-3 border-t border-white/10 px-6 py-6">
                                    <SheetClose asChild>
                                        <Link to="/signup" data-testid={`${IDS.navJoin}-mobile`}>
                                            <Button className="h-11 w-full rounded-full bg-ember-500 text-black transition-colors duration-200 hover:bg-ember-400">
                                                Join
                                            </Button>
                                        </Link>
                                    </SheetClose>
                                    <SheetClose asChild>
                                        <Link
                                            to="/login"
                                            data-testid={`${IDS.navSignIn}-mobile`}
                                            className="py-2 text-center text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
                                        >
                                            Sign in
                                        </Link>
                                    </SheetClose>
                                </div>
                            </div>
                        </SheetContent>
                    </Sheet>
                </div>
            </div>
        </header>
    );
}

export default MarketingNavbar;
