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
// NEEDS THE REAL HEX. `CORAL` below is a considered stand-in, not the studio's
// registered brand colour — nothing in this repository carries that value and
// inventing precision would be worse than saying so. It is a warm red that
// sits beside ember (#F05D14) without reading as a second orange, and it
// clears 4.5:1 against white at this weight. Swap it for the brand value when
// somebody has it; this is the only line that has to change.
// ---------------------------------------------------------------------------

/** The band's field. */
export const CORAL = "#E1483C";

/** A half-step darker, for the band's own hairlines and hover states. */
export const CORAL_DEEP = "#C33A30";

/** The CTA block sitting on the coral. Near-black, never pure #000 — the
 *  tinted-grey rule holds even inside the handshake. */
export const CORAL_INK = "#12100F";
