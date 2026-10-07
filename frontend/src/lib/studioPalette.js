// The parent studio's colours — used in exactly one place.
//
// The closing band on every marketing page is a full-bleed field of the studio
// coral with white type and a black CTA block. It is the family handshake: the
// one moment the page says out loud that Creators comes from WeAre Studios.
// **Everywhere else stays in our dark system with the ember accent**, because
// a palette used twice is a co-brand rather than an endorsement, and Creators
// has its own identity to keep.
//
// What is inherited is the confidence and the motion, not the assets. No
// studio copy, no studio photography, no studio logo treatment — that would be
// borrowing someone else's page rather than building ours.
//
// ---------------------------------------------------------------------------
// NEEDS THE REAL HEX, AND NOW URGENTLY. `CORAL` below is a considered
// stand-in, not the studio's registered brand colour — nothing in this
// repository carries that value and inventing precision would be worse than
// saying so.
//
// **The rebrand made this worse rather than better.** The stand-in was picked
// to sit beside the old ember (#F05D14) without reading as a second orange.
// Creators' brand red is now #FF2731, and #E1483C beside it does not read as
// a second brand at all — it reads as the first one rendered wrong. A
// handshake whose whole job is to say "this comes from somewhere else" cannot
// be a near-miss of the colour it is standing next to.
//
// It is left unchanged rather than nudged, because any value invented here
// would be a guess competing with a real one, and a guess that *looks*
// deliberate is harder to dislodge than one flagged as a placeholder. Swap it
// for the studio's registered value; this is still the only line to change.
// ---------------------------------------------------------------------------

/** The band's field. */
export const CORAL = "#E1483C";

/** A half-step darker, for the band's own hairlines and hover states. */
export const CORAL_DEEP = "#C33A30";

/** The CTA block sitting on the coral. Near-black, never pure #000 — the
 *  tinted-grey rule holds even inside the handshake. */
export const CORAL_INK = "#091426";
