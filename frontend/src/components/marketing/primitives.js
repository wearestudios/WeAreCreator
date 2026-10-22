// The marketing motion vocabulary: three primitives and no more.
//
//   LineEntrance  a headline arriving, once, at load
//   RowWriter     rows written in sequence, once, when first in view
//   CountUp       a number counting, once
//
// **A public page imports its motion from here and nowhere else.** The site
// had grown a reveal on every section, a hover lift, an image zoom and a
// cycling headline — twenty small moments that read as a template. Three
// deliberate ones read as designed. `Reveal`, the `rise`/`fade` variants and
// the rest of `motion.js` stay in the tree only while something outside the
// new pages still uses them (`Reveal` is the creator dashboard's), and
// `test_site_foundations.py` fails a new public page that reaches past this
// file.
export { LineEntrance, RowWriter } from "@/components/marketing/Entrances";
export { CountUp } from "@/components/marketing/CountUp";
