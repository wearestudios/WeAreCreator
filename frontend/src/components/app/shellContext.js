/**
 * Whether a page is inside a shell that has its own navigation.
 *
 * Its own module, and the only thing in `components/app/` a public page may
 * import: the shared `Navbar` reads it to render nothing inside a shell, and
 * importing it from `SideNav.jsx` would drag the sidebar's parts into every
 * public page that has a navbar.
 */
import { createContext, useContext } from "react";

export const ShellContext = createContext(false);
export const useInShell = () => useContext(ShellContext);
