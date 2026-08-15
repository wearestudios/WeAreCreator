// The parent brand.
//
// WeAre Creators is an offering of WeAre Studios and shares the studio's site,
// so the studio is credited — an endorsement, not a co-brand. Creators keeps
// the wordmark, the ember accent and the type; the studio gets one small line
// beside the nav logo and one in the footer.
//
// The URL comes from the environment because it isn't ours to hardcode. When
// it's unset the endorsement still renders, just as plain text rather than a
// link that goes nowhere.
export const STUDIO_NAME = process.env.REACT_APP_STUDIO_NAME || "WeAre Studios";

export const STUDIO_URL = (process.env.REACT_APP_STUDIO_URL || "").trim();
