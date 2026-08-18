// constants/testIds/ — central registry of data-testid values used by the
// end-to-end tests to locate and interact with UI elements. UI without
// testids cannot be automatically verified.
//
// Structure: each feature lives in its own file (auth.js, cart.js, ...) and
// is re-exported from here, so consumers can do a single import like
// `import { LOGIN, CART } from '@/constants/testIds'` (or relative).
//
// Adding a new feature:
//   1. Create constants/testIds/<feature>.js
//   2. Export named objects (e.g. `export const PROFILE = { ... }`)
//   3. Re-export here: `export * from './<feature>';`

export * from './address';
export * from './admin';
export * from './application';
export * from './auth';
export * from './brand';
export * from './dense';
export * from './execution';
export * from './creator';
export * from './landing';
export * from './manager';
