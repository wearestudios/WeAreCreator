/**
 * Whether a page is inside a shell that has its own navigation.
 *
 * Its own module, and the only thing in `components/app/` a public page may
 * import: the shared `Navbar` reads it to render nothing inside a shell, and
 * importing it from `SideNav.jsx` would drag the sidebar's parts into every
 * public page that has a navbar.
 */
import { createContext, useContext, useEffect } from "react";

export const ShellContext = createContext(false);
export const useInShell = () => useContext(ShellContext);

/** How a page hands the sidebar a count it already has. See `useShellBadges`. */
export const BadgeContext = createContext(() => {});

/**
 * A page publishes counts it already has — the dashboard's open invitations,
 * say — and the sidebar shows them. The sidebar never fetches a count of its
 * own: every number on it comes from a response a page was making anyway.
 * Published counts outlive the page, because the shell does, until the next
 * page that knows better publishes again. Outside a shell it does nothing.
 */
export function useShellBadges(badges) {
    const publish = useContext(BadgeContext);
    const key = JSON.stringify(badges || {});
    useEffect(() => {
        publish(JSON.parse(key));
    }, [publish, key]);
}
