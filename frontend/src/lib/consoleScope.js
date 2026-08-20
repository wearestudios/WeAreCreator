// Who reaches the console, and how much of it.
//
// The mirror of `CONSOLE_ROLES` / `is_all_access` in `server.py`, and the same
// arrangement `followerTiers.js` and `shootWindows.js` use: one copy each side
// and a unit test that fails if they drift.
//
// **This decides what is drawn, never what is allowed.** Every one of the
// sections below is enforced server-side — an admin-only endpoint answers 403
// whoever asks, and a scoped one filters in its query. Hiding a section a
// person cannot use is a courtesy on top of that, which is the only thing a
// client-side role check is ever permitted to be here.

/** The two roles the admin console is built for. */
export const CONSOLE_ROLES = ["admin", "weare_team"];

/** Everything, and only ever `admin`. */
export const isAllAccess = (role) => role === "admin";

/** Is this person looking at the console at all? */
export const isConsoleRole = (role) => CONSOLE_ROLES.includes(role);

/**
 * What the header says the console *is*.
 *
 * A team member's console is the admin console with a scope around it, and a
 * bar reading "WeAre · Admin" over a list that is quietly missing half the
 * platform is a bar that has lied about why. Naming the scope is what makes
 * "where is Blue Tokai" a question with an answer on screen.
 */
export const consoleLabel = (role) =>
    isAllAccess(role) ? "WeAre · Admin" : "WeAre · Team";

/** Said once, on the sections a scoped console cannot reach past. */
export const SCOPE_NOTE = "Your brands only.";
