// The marketing motion vocabulary: six primitives and no more.
//
//   WipeWord   one word revealed left to right, once, at load
//   RowWriter  rows written in sequence, once, when first in view
//   Rise       a heading or an illustration rising in, once, when in view
//   CountUp    a number counting, once
//   FillText   one sentence inking in with scroll position
//   Marquee    a continuous row of names; pauses on hover and focus
//
// **A public page imports its motion from here and nowhere else.** The site
// had grown a reveal on every section, a hover lift, an image zoom and a
// cycling headline — twenty small moments that read as a template. A few
// deliberate ones read as designed. `Rise` is the sixth, and it is the old
// site's `Reveal` entrance brought back on headings and illustrations only —
// the restoration asked for it, and it is CSS so the homepage still ships no
// animation library.
//
// The explaining pieces — `FeeFlow`, `PayoutClock`, the homepage's process
// spine — and the hero's step deck are components with motion inside them rather
// than primitives a page composes, and are imported directly. `Reveal` and
// the rest of `motion.js` are what those components animate with inside;
// `test_site_foundations.py` fails a public page that reaches for them itself.
export { WipeWord, RowWriter, Rise } from "@/components/marketing/Entrances";
export { CountUp } from "@/components/marketing/CountUp";
export { FillText } from "@/components/marketing/FillText";
export { Marquee } from "@/components/marketing/Marquee";
