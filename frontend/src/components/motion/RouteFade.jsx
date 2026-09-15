/**
 * The settle between routes.
 *
 * Navigation used to cut: one screen replaced the next on the frame the router
 * committed, which is why the app read as snappy in a bad way. A 190ms fade
 * with a 6px rise makes it arrive instead.
 *
 * **It restarts an animation rather than remounting a subtree, and that is the
 * whole design.** The obvious version is `<div key={pathname}>`, which replays
 * a CSS entrance for free because the animation fires on element creation. It
 * is also wrong here, in a way that does not show up until somebody uses the
 * product: `/admin` is a *layout* route that owns the sidebar, the badge
 * counts and eighteen sections rendered into an `<Outlet>`. Keying the router
 * on the full path would unmount and rebuild that layout on every section
 * change — refetching the counts, dropping the collapse preference, and
 * costing a network round trip for a fade. The same applies to any route that
 * holds state across a child navigation.
 *
 * So the wrapper is stable and the animation is restarted on it by hand:
 * remove the class, force a reflow, add it back. That is the documented way to
 * replay a CSS animation, and it touches nothing React owns.
 *
 * **Keyed on the surface, not the path.** Moving between surfaces — a
 * dashboard to the brief feed to the console — is a whole new screen and gets
 * the whole-screen settle. Moving *within* one, between console sections, is
 * not: fading the sidebar and the header every time somebody presses a section
 * would animate the navigation they are trying to use. That navigation gets
 * its own settle on the `<Outlet>`, where only the content changes.
 *
 * **Marketing is excluded.** Those pages stagger every section in on scroll
 * already, and two motion layers on one page is the same pixels animated twice
 * at two durations, on the page most likely to be opened on mobile data.
 *
 * Reduced motion is handled in `index.css`, which neutralises the class — so
 * there is no branch here, and no way for this to animate for one frame before
 * being told not to.
 */
import React, { useLayoutEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { MARKETING_PATHS } from "@/lib/siteNav";

/** Paths that keep the cut, because they animate themselves. */
const SELF_ANIMATED = new Set(MARKETING_PATHS);

export const isAnimatedRoute = (pathname) => !SELF_ANIMATED.has(pathname);

/**
 * The part of a path that decides whether this is a new screen.
 *
 * The first segment, so `/admin/creators` and `/admin/brands` are one surface
 * and `/dashboard` and `/campaigns` are two. Detail routes are deliberately
 * part of their surface: `/admin/creators` to `/admin/creators/:id` keeps the
 * console around it, and the page underneath settles on its own.
 */
export const surfaceOf = (pathname) => (pathname || "/").split("/")[1] || "/";

export default function RouteFade({ children }) {
    const { pathname } = useLocation();
    const node = useRef(null);
    const surface = surfaceOf(pathname);
    const animated = isAnimatedRoute(pathname);

    // Layout effect, so the class is off and on again before the browser
    // paints the new screen. In a plain effect the first frame of the new
    // route paints at full opacity and the fade then starts from it, which
    // reads as a flash rather than an arrival.
    useLayoutEffect(() => {
        const el = node.current;
        if (!el || !animated) return;
        el.classList.remove("weare-route");
        // Reading a layout property is what forces the style recalculation
        // that lets the class re-apply as a *new* animation. Without it the
        // browser coalesces the remove and the add and nothing plays.
        void el.offsetWidth;
        el.classList.add("weare-route");
    }, [surface, animated]);

    return (
        <div ref={node} className={animated ? "weare-route" : undefined}>
            {children}
        </div>
    );
}
