# WeAre Creators — PRD

## Original problem statement
Two-sided marketplace web app for Bengaluru connecting food & lifestyle content creators
with restaurants, cafés, and lifestyle brands for paid collaboration campaigns. Three user
roles: CREATOR, BRAND, ADMIN. Dark premium theme, burnt-orange accent, elegant serif +
clean sans, mobile-first. Foundation only for first build: auth + DB + role-based access +
placeholder home + login/signup. GitHub sync via Emergent UI.

## Stack (confirmed)
- Backend: FastAPI + Motor (MongoDB), JWT email/password auth, bcrypt
- Frontend: React 19 + Tailwind + Shadcn UI, framer-motion, sonner
- DB: MongoDB (managed)
- Fonts: Instrument Serif (headings) + DM Sans (body)
- Accent: Burnt Orange `#F05D14`
- Background: near-black tinted grey `hsl(20 8% 4%)`

## User personas
- Creator: Bengaluru food/lifestyle content creator applying to paid briefs.
- Brand: Restaurant/café/lifestyle brand posting briefs.
- Admin: WeAre Monk internal team curating both sides.

## Core requirements (static)
- Role-based access: creator | brand | admin
- Email + password auth (WhatsApp OTP planned for later phase)
- Mobile-first, premium dark editorial UI
- All backend routes prefixed with `/api`

## Implemented (v0 — Feb 2026)
- JWT auth: register/login/logout/me/refresh, httpOnly cookies, bcrypt hashing
- Admin auto-seed from env on startup
- MongoDB unique index on `users.email`
- Role guard dependency (`require_roles`) + sample `/api/admin/ping`
- Frontend: Landing page, Login, Signup with role toggle (creator/brand), role-aware
  Dashboard shell, ProtectedRoute, Navbar, AuthContext
- Design system: Instrument Serif + DM Sans, burnt-orange accent, dark tinted-grey base

## Prioritized backlog
- P0: WhatsApp OTP login (replace/augment email+password)
- P0: Creator profile & portfolio screen
- P0: Brand profile screen
- P0: Brief creation flow (brand) & Brief discovery feed (creator)
- P1: Application flow, chat between brand & creator
- P1: Admin approval console (creator/brand vetting)
- P2: Payments (Razorpay/Stripe), invoices, ratings & reviews
- P2: Email/SMS notifications

## Next tasks
- User picks the next screen (creator profile, brief creation, or WhatsApp OTP)
