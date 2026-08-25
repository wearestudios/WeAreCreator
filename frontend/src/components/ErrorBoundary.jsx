// The thing that stands between a render error and a white screen.
//
// React unmounts the entire tree when a render throws and nothing catches it,
// so before this a single bad field on one panel took down the navbar, the
// router and the impersonation banner with it. The user's evidence was a blank
// page, which is indistinguishable from a network failure, a deploy, or the app
// not existing.
//
// Two variants, because the two failures are not the same:
//
//   `page`    — the whole app is gone. A full-page apology, a reload, and a
//               link home. Deliberately uses plain anchors and
//               `location.reload()`, never react-router: if the router is what
//               broke, a <Link> in the fallback breaks with it.
//   `section` — one panel of a working page. An inline card the size of the
//               thing it replaced, with a Try again that re-mounts just that
//               subtree. The rest of the page keeps working, which is the
//               whole point of putting one here.
//
// And one case that is neither, decided by the error rather than by the call
// site: a **chunk that never arrived**. Since the app was split by route, a
// page can fail before any of its code has run — the network dropped, or a
// deploy replaced the hashed file this tab was still asking for. "Something on
// our side broke" is wrong about both, and a soft Try again cannot fix either,
// because `React.lazy` memoises the rejection and will not re-request the
// file. So that one says what happened and reloads.
import React from "react";
import { AlertTriangle, CloudOff, Home, RotateCw } from "lucide-react";

import { logError } from "@/lib/errorLog";
import { isChunkError } from "@/lib/lazyRoute";
import { ERROR_BOUNDARY as IDS } from "@/constants/testIds";

export default class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { error: null, resetKey: 0 };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error, info) {
        logError(error, {
            source: "react-boundary",
            boundary: this.props.variant || "section",
            component: this.props.name,
            componentStack: info?.componentStack,
        });
        this.props.onError?.(error, info);
    }

    componentDidUpdate(prev) {
        // Navigating away from a broken screen should not leave the fallback
        // on the next one. The caller passes `resetOn` (a pathname, usually)
        // and a change to it clears the error.
        if (this.state.error && prev.resetOn !== this.props.resetOn) {
            this.setState({ error: null });
        }
    }

    retry = () => {
        // Bumping the key remounts the children, so a component that threw on
        // bad state gets a fresh one rather than the state that broke it.
        this.setState((s) => ({ error: null, resetKey: s.resetKey + 1 }));
    };

    render() {
        const { error } = this.state;
        const { children, variant = "section", name, label } = this.props;

        if (!error) {
            return <React.Fragment key={this.state.resetKey}>{children}</React.Fragment>;
        }

        // **Decided by the error, not by which boundary caught it.** A chunk
        // can fail under the route boundary or under a section one, and the
        // honest answer is the same in both places.
        if (isChunkError(error)) {
            return (
                <div
                    data-testid={IDS.chunk}
                    className="grid min-h-screen place-items-center bg-background px-6 text-foreground grain-page"
                >
                    <div className="w-full max-w-lg">
                        <p className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-ember-500">
                            <CloudOff className="h-4 w-4" />
                            Connection
                        </p>
                        <h1 className="mt-5 font-serif text-fluid-4xl leading-tight tracking-tight">
                            This part didn't finish downloading.
                        </h1>
                        <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
                            The app loads each section as you open it, and this
                            one didn't arrive — usually a dropped connection, or
                            an update that landed while this tab was open.
                            Nothing you'd saved is affected.
                        </p>

                        <div className="mt-9 flex flex-col-reverse gap-3 sm:flex-row">
                            <a
                                href="/"
                                data-testid={IDS.pageHome}
                                className="inline-flex h-12 min-h-[2.75rem] items-center justify-center gap-2 rounded-full border border-white/15 px-6 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-white/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            >
                                <Home className="h-4 w-4" />
                                Go to the home page
                            </a>
                            {/* A real reload, not a remount. The failed import
                                is memoised, so re-rendering asks nobody for
                                anything; and after a deploy the file this tab
                                wants is genuinely gone, which only a fresh
                                index.html can fix. */}
                            <button
                                type="button"
                                onClick={() => window.location.reload()}
                                data-testid={IDS.chunkRetry}
                                className="inline-flex h-12 min-h-[2.75rem] flex-1 items-center justify-center gap-2 rounded-full bg-ember-500 px-6 text-xs uppercase tracking-[0.15em] text-black transition-colors duration-200 hover:bg-ember-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            >
                                <RotateCw className="h-4 w-4" />
                                Try again
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        if (variant === "page") {
            return (
                <div
                    data-testid={IDS.page}
                    className="grid min-h-screen place-items-center bg-background px-6 text-foreground grain-page"
                >
                    <div className="w-full max-w-lg">
                        <p className="text-xs uppercase tracking-[0.2em] text-ember-500">
                            WeAre Creators
                        </p>
                        <h1 className="mt-5 font-serif text-fluid-4xl leading-tight tracking-tight">
                            Something on our side broke.
                        </h1>
                        <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
                            Not you — this screen hit an error it didn't know how
                            to handle. Reloading usually clears it, and nothing
                            you'd already saved is affected.
                        </p>

                        <div className="mt-9 flex flex-col-reverse gap-3 sm:flex-row">
                            {/* A real navigation, not a router push: a full load
                              * throws away whatever state caused this. */}
                            <a
                                href="/"
                                data-testid={IDS.pageHome}
                                className="inline-flex h-12 min-h-[2.75rem] items-center justify-center gap-2 rounded-full border border-white/15 px-6 text-xs uppercase tracking-[0.15em] text-muted-foreground transition-colors duration-200 hover:border-white/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            >
                                <Home className="h-4 w-4" />
                                Go to the home page
                            </a>
                            <button
                                type="button"
                                onClick={() => window.location.reload()}
                                data-testid={IDS.pageReload}
                                className="inline-flex h-12 min-h-[2.75rem] flex-1 items-center justify-center gap-2 rounded-full bg-ember-500 px-6 text-xs uppercase tracking-[0.15em] text-black transition-colors duration-200 hover:bg-ember-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            >
                                <RotateCw className="h-4 w-4" />
                                Reload this page
                            </button>
                        </div>

                        <p className="mt-8 border-t border-white/10 pt-6 text-xs leading-relaxed text-muted-foreground">
                            Still stuck? Message us on WhatsApp and say what you
                            were doing — we can see the error from here.
                        </p>
                    </div>
                </div>
            );
        }

        // Section. Sized and bordered like the panels around it, so a broken
        // one reads as "this panel is broken" rather than as a page-wide alarm.
        return (
            <div
                data-testid={name ? IDS.section(name) : IDS.sectionAny}
                role="alert"
                className="rounded-md border border-amber-500/30 bg-amber-500/10 p-6"
            >
                <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-amber-300" />
                    <div className="min-w-0 flex-1">
                        <p className="text-xs uppercase tracking-[0.2em] text-amber-200">
                            {label || "This section couldn't load"}
                        </p>
                        <p className="mt-2 text-sm leading-relaxed text-amber-100/80">
                            The rest of the page is fine. Try again, or reload if
                            it keeps happening.
                        </p>
                        <button
                            type="button"
                            onClick={this.retry}
                            data-testid={name ? IDS.sectionRetry(name) : IDS.sectionRetryAny}
                            className="mt-4 inline-flex min-h-[2.75rem] items-center gap-2 rounded-full border border-amber-400/40 px-4 text-xs uppercase tracking-[0.15em] text-amber-200 transition-colors duration-200 hover:border-amber-300 hover:text-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background md:min-h-0 md:py-2"
                        >
                            <RotateCw className="h-3.5 w-3.5" />
                            Try again
                        </button>
                    </div>
                </div>
            </div>
        );
    }
}

/**
 * Wrap one panel without another level of indentation at the call site.
 *
 * `name` is what appears in the log, so it should say which panel — "health",
 * "earnings" — rather than repeating the component's own name.
 */
export function SafeSection({ name, label, children, className = "" }) {
    return (
        <ErrorBoundary variant="section" name={name} label={label}>
            {className ? <div className={className}>{children}</div> : children}
        </ErrorBoundary>
    );
}
