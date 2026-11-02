// The marketing motion vocabulary: five primitives and no more.
//
//   WipeWord   one word revealed left to right, once, at load
//   RowWriter  rows written in sequence, once, when first in view
//   CountUp    a number counting, once
//   FillText   one sentence inking in with scroll position
//   Marquee    a continuous row of names; pauses on hover and focus
//
// **A public page imports its motion from here and nowhere else.** The site
// had grown a reveal on every section, a hover lift, an image zoom and a
// cycling headline — twenty small moments that read as a template. Five
// deliberate ones read as designed. `Reveal` and the rest of `motion.js` stay
// in the tree only while something outside the public pages still uses them,
// and `test_site_foundations.py` fails a public page that reaches past this
// file.
export { WipeWord, RowWriter } from "@/components/marketing/Entrances";
export { CountUp } from "@/components/marketing/CountUp";
export { FillText } from "@/components/marketing/FillText";
export { Marquee } from "@/components/marketing/Marquee";
