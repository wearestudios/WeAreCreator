from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import asyncio
import csv
import io
import json
from html import escape as html_escape
import os
import re
import sys
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlencode
from typing import Optional, Literal, Annotated

import bcrypt
import httpx
import jwt
from bson import ObjectId
from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Depends,
    File,
    Form,
    Request,
    Response,
    UploadFile,
)
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, EmailStr, Field, BeforeValidator, ConfigDict, model_validator

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("wearecreators")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
#
# Three variables have no default and no sensible fallback: without them the
# process cannot connect to a database or sign a cookie. They used to surface
# as a bare `KeyError: 'JWT_SECRET'` — MONGO_URL and DB_NAME at import, but
# JWT_SECRET only when somebody tried to log in, because `_jwt_secret()` reads
# it per call. A deploy missing it looked healthy, served the marketing page,
# and 500'd the first person who tried to sign in.
#
# So they are checked here, before the first read below, and the process
# refuses to start with all of them named at once — one boot, one list, rather
# than fixing them one restart at a time.
_ENV_REQUIRED = (
    ("MONGO_URL", "MongoDB connection string, e.g. mongodb://localhost:27017"),
    ("DB_NAME", "Database name, e.g. wearecreators"),
    ("JWT_SECRET", "Signs the auth cookies. Any long random string."),
)

# These have defaults that let the process start, and each one silently breaks
# something a person will notice long after boot. They warn rather than exit:
# a laptop and the unit suite legitimately run without an admin account, and
# refusing to boot over CORS would be worse than saying so loudly when the
# real cause might be a proxy setting the header instead.
_ENV_PRODUCTION = (
    ("ADMIN_EMAIL", "no admin account is seeded, so nobody can sign in at /admin"),
    ("ADMIN_PASSWORD", "no admin account is seeded, so nobody can sign in at /admin"),
    ("CORS_ORIGINS", "the browser will block every call from the frontend"),
)


def _is_production() -> bool:
    """Same signal `_simulation_allowed` uses, read the same way."""
    env = os.environ.get("APP_ENV", os.environ.get("ENV", "")).strip().lower()
    return env not in ("dev", "development", "local", "test")


def validate_environment(*, exit_on_missing: bool = True) -> list:
    """Name everything missing, once, at boot.

    Returns the list of missing required variables so a test can call it
    without ending the process.
    """
    missing = [(k, why) for k, why in _ENV_REQUIRED if not os.environ.get(k, "").strip()]

    if missing:
        lines = [
            "",
            "Refusing to start: required environment variables are missing.",
            "",
        ]
        lines += [f"  {k:<12} {why}" for k, why in missing]
        lines += [
            "",
            f"Set them in {ROOT_DIR / '.env'} (copy .env.example) or in the",
            "host's environment, then start again. See backend/.env.example for",
            "every variable this app reads.",
            "",
        ]
        print("\n".join(lines), file=sys.stderr, flush=True)
        if exit_on_missing:
            raise SystemExit(1)

    # Warnings are worth having even when something is missing above, so the
    # operator fixes everything in one pass rather than discovering the next
    # problem after the next restart.
    if _is_production():
        for key, breaks in _ENV_PRODUCTION:
            if not os.environ.get(key, "").strip():
                logger.warning(
                    "%s is not set — %s. Set APP_ENV=development to silence this "
                    "on a local machine.",
                    key,
                    breaks,
                )
    return missing


validate_environment()

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MIN = 60 * 24  # 1 day
REFRESH_TOKEN_DAYS = 7

# campaign_manager is staff: created by an admin, signs in with email +
# password, and sees only the campaigns they are assigned to.
#
# brand_manager is the named human who runs a brand's campaigns. There is
# exactly one per brand and it is the brand's only login — the person captured
# at registration, not an extra seat. `brand` is what that role used to be
# called; both are accepted everywhere a brand acts (BRAND_ROLES) so accounts
# created before the rename keep working, and startup migrates them over.
Role = Literal["creator", "brand", "brand_manager", "admin", "campaign_manager"]

# Every guard on a brand-facing endpoint uses this rather than naming the
# strings, so a third spelling can never drift into existence.
BRAND_ROLES = ("brand", "brand_manager")


def _pyobjectid_validator(v):
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_pyobjectid_validator)]


# ---------------------------------------------------------------------------
# Password + JWT
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _jwt_secret() -> str:
    """The signing key, guaranteed present by `validate_environment()` at boot.

    Kept as a lookup rather than a frozen constant so a test can set the
    variable and have it take effect; the RuntimeError is unreachable in a
    process that started normally, and exists so that if it ever is reached it
    says which variable rather than raising a bare KeyError from inside a
    login request.
    """
    secret = os.environ.get("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set. The process should not have started; "
            "see validate_environment()."
        )
    return secret


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MIN),
        "type": "access",
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_MIN * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


# ---------------------------------------------------------------------------
# Impersonation ("view as")
#
# A support tool: an admin sees the app exactly as one creator, brand manager
# or campaign manager sees it, so "I can't find the button" can be answered by
# looking rather than by guessing.
#
# It is **read-only, and that is enforced in middleware**, not in the UI. The
# banner and the hidden buttons are a courtesy; `_reject_impersonated_writes`
# is the guarantee. Anything else means the guarantee is "every route
# remembered", which is not a guarantee.
#
# The token is a third cookie rather than a swap of the admin's own. Three
# consequences, all wanted:
#   - the admin's real session is never destroyed, so stopping is instant and
#     cannot strand them logged out;
#   - it is impossible to confuse an impersonated request for a real one,
#     because the two arrive in differently-named cookies;
#   - it expires on its own. A forgotten view-as session ends by itself.
# ---------------------------------------------------------------------------

IMPERSONATION_COOKIE = "impersonation_token"
# Deliberately short. This is for looking at one screen with somebody on the
# phone, not for working inside another account.
IMPERSONATION_MIN = 30

# Who an admin may look through. Not other admins: an admin already sees
# everything an admin sees, so the only thing it would add is a way to act as a
# colleague, and that is the one thing this must never be.
IMPERSONATABLE_ROLES = ("creator", "brand", "brand_manager", "campaign_manager")

# The methods that cannot change anything. Everything else is refused while a
# view-as session is active.
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# The single exception, and the reason it is safe: it only clears the
# impersonation cookie and writes the audit line closing the session. It
# touches no business data at all.
IMPERSONATION_STOP_PATH = "/api/auth/impersonate/stop"


def create_impersonation_token(target_id: str, actor: dict) -> str:
    payload = {
        "sub": target_id,
        # Who is really behind this request. Carried in the token rather than
        # looked up, so an audit line written during impersonation can name the
        # admin even though the acting user is somebody else.
        "act": str(actor["_id"]),
        "act_name": actor.get("name"),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_MIN),
        "type": "impersonation",
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _decode_impersonation(request: Request) -> Optional[dict]:
    """The active view-as claim, or None.

    Never raises. An expired or malformed impersonation cookie means "not
    impersonating" — the admin's own session is still in `access_token` and
    takes over, which is exactly the behaviour wanted when a view-as session
    times out mid-look.
    """
    token = request.cookies.get(IMPERSONATION_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "impersonation":
        return None
    return payload


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class UserPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    name: str
    role: Role
    phone: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    role: Literal["creator", "brand"]  # admins can only be seeded
    phone: Optional[str] = Field(default=None, max_length=20)
    accept_terms: bool = False


# Bumped whenever the terms change, so we can tell who accepted what.
TERMS_VERSION = os.environ.get("TERMS_VERSION", "2026-08-13")


class LoginInput(BaseModel):
    email: EmailStr
    password: str


# --- OTP (WhatsApp) ---------------------------------------------------------

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def _normalize_phone(raw: str) -> str:
    """Normalize a phone number to E.164. Raises HTTPException(400) on invalid."""
    if not raw:
        raise HTTPException(status_code=400, detail="Phone number is required.")
    p = re.sub(r"[\s\-()]", "", raw.strip())
    if not p.startswith("+"):
        raise HTTPException(
            status_code=400,
            detail="Phone must be in international format, e.g. +9198…",
        )
    if not E164_RE.match(p):
        raise HTTPException(
            status_code=400,
            detail="Phone must be in E.164 format, e.g. +919876543210",
        )
    return p


OtpPurpose = Literal["login", "signup"]


# What the brand's one named person is called, on the user document. Kept in
# one tuple because it is read off a Pydantic payload, off a stored OTP row and
# off the user itself, and three hand-written lists would drift.
BRAND_CONTACT_FIELDS = ("manager_name", "manager_designation", "manager_email")


def _brand_contact_from(source) -> dict:
    """The named-contact fields off a signup payload or a stored OTP row.

    Absent keys are omitted rather than written as null, so the verify step can
    fall back to whatever the request step captured: a client that sends the
    contact once shouldn't have to send it twice.
    """
    getter = source.get if isinstance(source, dict) else lambda f: getattr(source, f, None)
    out = {}
    for field in BRAND_CONTACT_FIELDS:
        value = getter(field)
        value = (str(value).strip() if value is not None else "") or None
        if value:
            out[field] = value
    return out


class BrandContactSignup(BaseModel):
    """The one named person a brand registers behind.

    Every brand has exactly one login and it belongs to a human, not to a
    mailbox the whole office shares. Capturing who they are at registration is
    what makes the audit log say a name rather than "the brand", and what lets
    a campaign default its manager to somebody real.

    All three are optional here so an existing signup screen keeps working, but
    they are not optional for long: `_BRAND_REQUIRED_FIELDS` demands the same
    three before a brand can be submitted for verification, and verification is
    required before anything the brand does can reach a creator.
    """

    manager_name: Optional[str] = Field(default=None, max_length=80)
    manager_designation: Optional[str] = Field(default=None, max_length=80)
    manager_email: Optional[EmailStr] = None


class OtpRequestInput(BrandContactSignup):
    phone: str = Field(min_length=8, max_length=20)
    purpose: OtpPurpose = "login"
    # required for signup only
    name: Optional[str] = Field(default=None, max_length=80)
    role: Optional[Literal["creator", "brand"]] = None
    accept_terms: bool = False


class OtpVerifyInput(BrandContactSignup):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(pattern=r"^\d{6}$")
    purpose: OtpPurpose = "login"
    name: Optional[str] = Field(default=None, max_length=80)
    role: Optional[Literal["creator", "brand"]] = None
    # Required for signup — recorded against the account, not just asserted in copy.
    accept_terms: bool = False


CATEGORY_LITERAL = Literal[
    "fnb",
    "hospitality",
    "retail",
    "real_estate",
    "fashion",
    "travel",
    "wellness",
    "lifestyle",
]


# Where a creator actually publishes. Deliberately a closed list: "youtube"
# and "YT" in the same column makes the directory unsearchable.
CreatorPlatform = Literal["instagram", "youtube"]
CREATOR_PLATFORMS = ("instagram", "youtube")


# What a creator makes and covers, offered as suggestions.
#
# These were food and nothing but food — cafe, brunch, bakery, brewery, home
# chef — which is a list that tells a fashion or gaming creator this platform
# is not for them before they have typed anything. We take creators of every
# category, so the suggestions have to span every category, with the food
# subcategories kept *inside* the food group rather than standing in for the
# whole taxonomy.
#
# Grouped rather than flat because fifteen headings with subcategories under
# them is scannable and ninety chips are not. The values stay lowercase free
# text — `niches`/`genres` are not enums and a creator may still type their
# own — so this is a starting point, not a constraint.
CREATOR_TAXONOMY = (
    ("Food & Drink", (
        "food", "cafe", "brunch", "bakery", "fine dining", "street food",
        "coffee", "desserts", "cocktails", "brewery", "home chef", "vegan",
    )),
    ("Fashion", ("fashion", "streetwear", "ethnic wear", "thrift", "styling", "luxury")),
    ("Beauty", ("beauty", "skincare", "makeup", "haircare", "fragrance", "grooming")),
    ("Travel", ("travel", "hotels", "weekend trips", "adventure", "solo travel", "budget travel")),
    ("Fitness & Wellness", ("fitness", "gym", "yoga", "running", "nutrition", "mental health")),
    ("Tech", ("tech", "gadgets", "phones", "apps", "ai", "photography gear")),
    ("Gaming", ("gaming", "esports", "mobile gaming", "streaming", "game reviews")),
    ("Home & Interiors", ("home", "interiors", "decor", "diy", "plants", "organisation")),
    ("Parenting", ("parenting", "new parents", "kids activities", "family", "baby products")),
    ("Finance", ("finance", "investing", "personal finance", "startups", "career")),
    ("Art & Design", ("art", "design", "illustration", "crafts", "photography")),
    ("Music", ("music", "singing", "instruments", "production", "gigs")),
    ("Comedy", ("comedy", "sketch", "standup", "memes", "relatable")),
    ("Automotive", ("automotive", "cars", "bikes", "ev", "reviews")),
    ("Pets", ("pets", "dogs", "cats", "pet care")),
)

# Flat, for anything that needs to ask "is this a term we know".
CREATOR_TAXONOMY_TERMS = tuple(
    term for _, terms in CREATOR_TAXONOMY for term in terms
)


# The cities a creator can say they are in. A closed list because free text
# cannot be reconciled: "Bangalore", "bangalore", "Bengaluru " and "BLR" are
# four rows in a filter and one city in reality, and a brand filtering the
# directory finds a quarter of the people each time.
#
# The product is Bengaluru-first, which is why it leads; the rest are open for
# where we expand next rather than a claim to operate there today.
# Where a campaign runs unless the brand says otherwise. The product is
# Bengaluru-first, so this is what it is rather than a placeholder.
DEFAULT_CAMPAIGN_CITY = "Bengaluru"

INDIAN_CITIES = (
    "Bengaluru",
    "Mumbai",
    "Delhi NCR",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Jaipur",
    "Chandigarh",
    "Kochi",
    "Goa",
    "Lucknow",
    "Indore",
    "Coimbatore",
    "Surat",
    "Nagpur",
    "Bhubaneswar",
    "Guwahati",
    "Dehradun",
)


class CreatorProfileUpdate(BaseModel):
    """Payload for the creator profile builder.

    Every field is optional, and only the keys actually present in the request
    body are written. Signup asks for a name and a number and nothing else, so
    the profile is built up over however many sittings it takes — a save that
    demanded the whole thing at once would just mean nobody ever saved.

    That makes an omitted key mean "leave it alone" and an explicit null mean
    "clear it", which are genuinely different intentions on a form somebody is
    filling in a bit at a time.
    """

    name: Optional[str] = Field(default=None, max_length=120)
    instagram_handle: Optional[str] = Field(default=None, max_length=60)
    instagram_profile_url: Optional[str] = Field(default=None, max_length=300)
    # Where the channel actually lives. Kept separate from the Instagram pair
    # rather than a generic "links" bag, because completeness has to be able to
    # ask for the one that matches a platform they said they post on.
    youtube_url: Optional[str] = Field(default=None, max_length=300)
    # Optional, like YouTube. Some creators' audience is on Facebook and
    # nowhere else; asking for it costs nothing and not asking loses them.
    facebook_url: Optional[str] = Field(default=None, max_length=300)
    # In their own words. Everything else about a creator on this form is a
    # field somebody else chose the shape of; this is the one place they get to
    # say what they actually do.
    about: Optional[str] = Field(default=None, max_length=1500)
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(default=None, max_length=80)
    # `address` is the neighbourhood a brand filters on ("Indiranagar");
    # `full_address` is where post actually goes. Two different questions, so
    # two fields rather than one overloaded one.
    address: Optional[str] = Field(default=None, max_length=500)
    full_address: Optional[str] = Field(default=None, max_length=500)
    # The pin, from Google Places or dragged by the creator.
    #
    # The text address is what gets printed on a delivery label; this is what
    # somebody actually navigates to. They are not the same thing and neither
    # replaces the other — autocomplete routinely lands on the street rather
    # than the building, which is exactly the error a courier cannot recover
    # from at 9pm.
    location_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    location_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    location_place_id: Optional[str] = Field(default=None, max_length=300)
    niches: list[str] = Field(default_factory=list, max_length=25)
    # What they make (food, travel, comedy) as opposed to `niches`, which is
    # what they cover for a brand (cafe, brunch). Kept apart because a brand
    # searches on one and briefs on the other.
    genres: list[str] = Field(default_factory=list, max_length=25)
    platforms: list[CreatorPlatform] = Field(default_factory=list, max_length=5)
    base_rate: Optional[float] = Field(default=None, ge=0)
    follower_count: Optional[int] = Field(default=None, ge=0)
    # Payout identity. Optional at onboarding, required before payment.
    payout_upi: Optional[str] = Field(default=None, max_length=120)
    payout_account_name: Optional[str] = Field(default=None, max_length=140)
    pan: Optional[str] = Field(default=None, max_length=10)
    gstin: Optional[str] = Field(default=None, max_length=15)


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$")
UPI_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,64}@[a-zA-Z][a-zA-Z0-9]{1,30}$")


class ApplyPayload(BaseModel):
    """Payload for a creator applying to a campaign."""

    pitch: str = Field(min_length=1, max_length=1000)
    quoted_rate: float = Field(ge=0)


class SubmitContentPayload(BaseModel):
    """Payload for a creator submitting their published content URL(s)."""

    # Preferred field — a list of one or more URLs.
    content_urls: Optional[list[str]] = Field(default=None, max_length=25)
    # Legacy single-URL field (still accepted for backward compatibility).
    content_url: Optional[str] = Field(default=None, min_length=1, max_length=500)


# Indian entity types, because "business type" with a free-text box is a field
# nobody can review. `other` exists so an unusual structure isn't a dead end.
BusinessType = Literal[
    "sole_proprietorship",
    "partnership",
    "llp",
    "private_limited",
    "public_limited",
    "trust",
    "society",
    "other",
]

# What a brand can hand us to prove it is the business it says it is. Any one
# of these is enough — a small café has a shop establishment licence and no
# GST; a company has a certificate of incorporation and no FSSAI.
BrandDocumentType = Literal[
    "gst_certificate",
    "business_registration",
    "fssai_licence",
    "shop_establishment_licence",
]

# Enough for several proofs plus a re-scan after a rejection, and low enough
# that the collection can't be used as free file storage.
MAX_BRAND_DOCUMENTS = 12

BRAND_DOCUMENT_LABELS = {
    "gst_certificate": "GST certificate",
    "business_registration": "Business registration",
    "fssai_licence": "FSSAI licence",
    "shop_establishment_licence": "Shop & establishment licence",
}

# Where a brand stands with us. `verified` is kept as a boolean alongside this
# because a great deal of code already gates on it; this says *why* it is
# false, which the boolean never could.
BrandVerificationState = Literal[
    "unsubmitted",
    "pending_verification",
    "verified",
    "rejected",
]


class BrandOutlet(BaseModel):
    """One place the business actually is.

    Deliberately separate from `registered_address`, which is where the company
    is registered — often a director's home for a small business, and one of the
    things the verification documents carry. That one is never public. An outlet
    is a shopfront: somewhere a creator is going to be asked to turn up, so it
    is exactly what belongs on a page strangers can read.
    """

    name: Optional[str] = Field(default=None, max_length=140)
    address: Optional[str] = Field(default=None, max_length=500)
    area: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=80)
    # The pin, same three fields and the same reasoning as the creator's: a
    # text address is what gets read, a coordinate is what gets navigated to.
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    place_id: Optional[str] = Field(default=None, max_length=200)


class BrandProfileUpdate(BaseModel):
    """Payload for brand onboarding / profile edits.

    Same partial-save rule as the creator builder: every field is optional and
    only the keys actually present in the body are written, so a brand can fill
    this in over several sittings without a later step blanking an earlier one.
    Submitting for verification is what checks the set is complete.
    """

    business_name: Optional[str] = Field(default=None, max_length=140)
    category: Optional[CATEGORY_LITERAL] = None
    areas: list[str] = Field(default_factory=list, max_length=30)

    # The creator-facing half: what this business is, in its own words, and
    # where it actually is. None of it is evidence of anything — it exists so a
    # creator deciding whether to pitch has something to read besides a name.
    about: Optional[str] = Field(default=None, max_length=1500)
    city: Optional[str] = Field(default=None, max_length=80)
    outlets: list[BrandOutlet] = Field(default_factory=list, max_length=25)

    # The name on the paperwork, which is often not the name on the door —
    # "Third Wave Coffee" trades, "Third Wave Coffee Roasters Pvt Ltd" signs.
    # A reviewer needs both to match a document against a profile.
    legal_entity_name: Optional[str] = Field(default=None, max_length=200)
    gst_number: Optional[str] = Field(default=None, max_length=15)
    business_type: Optional[BusinessType] = None
    registered_address: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = Field(default=None, max_length=300)

    # The accounts we can check the business against. Not proof on their own —
    # anyone can type a handle — but a reviewer comparing a handle to a
    # licence catches the obvious impersonation.
    instagram_handle: Optional[str] = Field(default=None, max_length=60)
    facebook_url: Optional[str] = Field(default=None, max_length=300)
    linkedin_url: Optional[str] = Field(default=None, max_length=300)

    # Who is actually asking, and on what authority. The whole point of this
    # feature: an account is a person claiming to represent a business.
    contact_person_name: Optional[str] = Field(default=None, max_length=140)
    contact_person_designation: Optional[str] = Field(default=None, max_length=140)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=20)


# The shape of the work decides the shape of the dates. A launch or a group
# event happens on one day; a personal table runs over a window a creator books
# into. Storing both shapes on every campaign and trusting the UI to fill the
# right ones is how a brief ends up with an event date *and* a window.
CampaignType = Literal["launch", "group_event", "personal_table"]
EVENT_CAMPAIGN_TYPES = ("launch", "group_event")


# What a creator is actually being offered.
#
#   fixed       the budget on the brief is the fee, take it or leave it
#   negotiated  the budget is a guide; the real number is agreed offline and
#               recorded against the collaboration (see work notes)
#   barter      no money — a meal, a stay, a product
#
# The distinction is not cosmetic. Barter is the arrangement most likely to
# waste a creator's day for nothing, so it is ours to make and not a checkbox on
# a self-serve form: a brand posts paid work or it does not post.
CompensationType = Literal["fixed", "negotiated", "barter"]
# The only two a brand may put on its own brief. Named as the allow-list rather
# than as "not barter" so that adding a fourth kind later has to be a decision
# about who can post it, not something that quietly inherits brand access.
BRAND_COMPENSATION_TYPES = ("fixed", "negotiated")
# Campaigns written before this field existed were all brand briefs with a cash
# budget, so this is what they were, not merely a safe guess.
DEFAULT_COMPENSATION_TYPE = "fixed"


def _compensation_type(campaign: dict) -> str:
    """What this campaign pays in. The one reader — a bare `.get()` returns None
    for every pre-field document, and None is not a third kind of money."""
    return (campaign or {}).get("compensation_type") or DEFAULT_COMPENSATION_TYPE


def _is_barter(campaign: dict) -> bool:
    return _compensation_type(campaign) == "barter"


# Who actually runs the campaign — books the creators, stands at the door,
# chases the content.
#
#   brand   the brand's own manager runs it; applications go to them
#   weare   we run it; applications go to the WeAre team
#
# This decides where an application is *sent*, which is the thing that was
# missing: every new application went to the brand's manager whether or not the
# brand had handed execution over, so a brand that asked us to run a campaign
# still got the pager.
#
# It is also what a creator most wants to know before applying — whose WhatsApp
# they will be dealing with on the day.
ExecutionOwner = Literal["brand", "weare"]
EXECUTION_OWNERS = ("brand", "weare")
# Campaigns written before this field existed were brand briefs run by the
# brand's own manager unless an admin had handed one to a WeAre manager, which
# is what the startup backfill looks for. Absent means brand.
DEFAULT_EXECUTION_OWNER = "brand"


def _execution_owner(campaign: dict) -> str:
    """Who runs this campaign. The one reader.

    Pure and DB-free, exactly like `_compensation_type`: an unrecognised or
    missing value reads as the default rather than travelling as None, because
    every surface that shows this has to say one of two words and "unknown" is
    not one of them.
    """
    value = (campaign or {}).get("execution_owner")
    return value if value in EXECUTION_OWNERS else DEFAULT_EXECUTION_OWNER


def _weare_runs(campaign: dict) -> bool:
    return _execution_owner(campaign) == "weare"


def _execution_owner_query(value: str) -> dict:
    """A Mongo filter for one execution owner, matching pre-field documents.

    "brand" has to be `$ne: "weare"` rather than an equality test: campaigns
    written before this field existed have no value at all, and they were
    brand-run. The startup backfill fills them in, but a filter that only works
    after a migration has run is a filter that silently returns nothing on a
    box that has not restarted yet. Same reasoning as `showcase`'s `$ne: True`.
    """
    if value == "weare":
        return {"execution_owner": "weare"}
    return {"execution_owner": {"$ne": "weare"}}


# --- Campaign visibility -----------------------------------------------------
#
# "public" is the shop window: every verified creator can find it, and it may
# also be promoted to the open internet through /c/{id} and the brand's page.
# "private" is invite-only: it never appears in browse, search, suggestions,
# the share page, the sitemap or the filter options, and only creators who were
# actually invited — or who already hold an application on it, because a brand
# may flip a live brief private after people applied — can read or pitch on it.
#
# The gate is server-side on every campaign read and on apply, never only in
# the UI. Admins see everything; a brand always sees its own, which the
# ownership checks already guarantee.

CampaignVisibility = Literal["public", "private"]
CAMPAIGN_VISIBILITIES = ("public", "private")
# Campaigns written before this field existed were all findable, so absent
# reads as public — and every filter matches on `$ne: "private"` rather than
# equality, the same pre-migration trap as execution_owner and showcase.
DEFAULT_CAMPAIGN_VISIBILITY = "public"


def _campaign_visibility(campaign: dict) -> str:
    """The one reader. Pure and DB-free, like `_execution_owner`."""
    value = (campaign or {}).get("visibility")
    return value if value in CAMPAIGN_VISIBILITIES else DEFAULT_CAMPAIGN_VISIBILITY


def _is_private(campaign: dict) -> bool:
    return _campaign_visibility(campaign) == "private"


# The clause every open-shelf query carries. A helper rather than an inline
# dict so the next listing surface gets the `$ne` shape by importing the rule,
# not by remembering it.
PUBLIC_CAMPAIGN_QUERY = {"visibility": {"$ne": "private"}}


async def _visible_campaign_ids_for_creator(creator_oid: ObjectId) -> list:
    """Private campaigns this creator may see anyway.

    Two doors: an invitation row, or an application they already hold — a brand
    flipping a live brief private must not vanish it from the people already on
    it. Ids, not documents: the caller folds them into its own query so status
    filters and pagination still apply once, in one place.
    """
    invited = await db.campaign_invitations.distinct(
        "campaign_id", {"creator_id": creator_oid}
    )
    applied = await db.collaborations.distinct(
        "campaign_id", {"creator_id": creator_oid, "active": True}
    )
    return list({*invited, *applied})


async def _creator_may_see(campaign: dict, creator_oid: ObjectId) -> bool:
    """May this creator read this one campaign? Public: yes. Private: only
    through one of the two doors above."""
    if not _is_private(campaign):
        return True
    cid = campaign["_id"]
    if await db.campaign_invitations.find_one(
        {"campaign_id": cid, "creator_id": creator_oid}, {"_id": 1}
    ):
        return True
    return bool(
        await db.collaborations.find_one(
            {"campaign_id": cid, "creator_id": creator_oid, "active": True}, {"_id": 1}
        )
    )


class PostCampaignPayload(BaseModel):
    """Payload for a brand posting a new campaign."""

    title: str = Field(min_length=1, max_length=140)
    brief: str = Field(min_length=1, max_length=5000)
    deliverables: str = Field(min_length=1, max_length=1000)
    budget_per_creator: float = Field(ge=0)
    category: CATEGORY_LITERAL
    area: str = Field(min_length=1, max_length=80)
    creators_needed: int = Field(ge=1, le=100)
    campaign_type: CampaignType
    # Which city this runs in, from the same canonical list creators pick from
    # — a filter that compares a campaign's free text against a creator's
    # dropdown value matches nothing. Defaults to Bengaluru because that is
    # where the operation is; `area` stays the free-text neighbourhood inside it.
    city: str = DEFAULT_CAMPAIGN_CITY
    # Typed as the full enum rather than the brand subset on purpose: a payload
    # that rejects "barter" as an unknown value would answer with pydantic's
    # "Input should be 'fixed' or 'negotiated'", which reads like a typo. The
    # handler refuses it with the actual reason instead.
    compensation_type: CompensationType = DEFAULT_COMPENSATION_TYPE
    # Run it themselves, or hand it to us. Defaults to the brand, because that
    # is what posting a brief means unless you say otherwise — and because a
    # campaign silently landing in the WeAre queue is work nobody agreed to.
    execution_owner: ExecutionOwner = DEFAULT_EXECUTION_OWNER
    # Findable by every verified creator, or invite-only. Defaults to public
    # because that is what posting a brief means unless you say otherwise.
    visibility: CampaignVisibility = DEFAULT_CAMPAIGN_VISIBILITY
    event_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    # Where creators actually show up. Optional at draft time — a brand can
    # brief before the venue is confirmed — but part of the campaign, not the
    # chat thread it would otherwise live in.
    venue_address: Optional[str] = Field(default=None, max_length=500)
    venue_instructions: Optional[str] = Field(default=None, max_length=1000)
    on_site_contact: Optional[str] = Field(default=None, max_length=200)
    # "open" is accepted by the schema only so the handler can explain why it is
    # refused. A brand saves a draft or submits for review; an admin publishes.
    status: Literal["draft", "pending_review", "open"] = "draft"

    @model_validator(mode="after")
    def _dates_match_the_type(self):
        if self.campaign_type in EVENT_CAMPAIGN_TYPES:
            if self.event_date is None:
                raise ValueError(
                    f"A {self.campaign_type.replace('_', ' ')} happens on a day — "
                    "event_date is required."
                )
            if self.start_date is not None or self.end_date is not None:
                raise ValueError(
                    "An event campaign has an event_date, not a start/end window. "
                    "Leave start_date and end_date out."
                )
        else:  # personal_table
            if self.start_date is None or self.end_date is None:
                raise ValueError(
                    "A personal table runs over a window — start_date and "
                    "end_date are both required."
                )
            if self.event_date is not None:
                raise ValueError(
                    "A personal table has a booking window, not an event_date. "
                    "Leave event_date out."
                )
            if self.end_date < self.start_date:
                raise ValueError("End date cannot be before start date")
        return self


class UpdateCampaignPayload(BaseModel):
    """Payload for editing an existing campaign. Every field is optional so a
    brand can correct one thing without resubmitting the whole brief."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=140)
    brief: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    deliverables: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    budget_per_creator: Optional[float] = Field(default=None, ge=0)
    category: Optional[CATEGORY_LITERAL] = None
    area: Optional[str] = Field(default=None, min_length=1, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    creators_needed: Optional[int] = Field(default=None, ge=1, le=100)
    # campaign_type is deliberately absent: the type decides which date fields
    # exist, so changing it mid-flight would orphan whichever dates were set.
    #
    # compensation_type is present but gated — this model serves both the brand
    # edit and the admin one, and only the admin route lets barter through.
    compensation_type: Optional[CompensationType] = None
    # Who runs it. A brand may change its mind while the brief is still a
    # draft; once it is live, handing execution over is a conversation, not a
    # dropdown — `_refuse_late_execution_handover` is what enforces that, and
    # the admin route skips it.
    execution_owner: Optional[ExecutionOwner] = None
    # A brand may open a private brief up or pull a public one back at any
    # editable stage. Going private does not evict anyone: creators who already
    # applied, and everyone invited, keep read and apply access — the doors are
    # in _creator_may_see, not here.
    visibility: Optional[CampaignVisibility] = None
    event_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    venue_address: Optional[str] = Field(default=None, max_length=500)
    venue_instructions: Optional[str] = Field(default=None, max_length=1000)
    on_site_contact: Optional[str] = Field(default=None, max_length=200)


class CreateManagerPayload(BaseModel):
    """An admin creating a campaign-manager account. Staff, so email+password."""

    name: str = Field(min_length=1, max_length=140)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=20)


class AssignManagerPayload(BaseModel):
    """Point a campaign at the manager who runs it."""

    manager_user_id: str


class SlotPayload(BaseModel):
    """One bookable slot (or window) on a campaign.

    For launch/group_event this is a time on the event day; for personal_table
    it is an availability window, so ends_at is required there and optional
    otherwise — the handler enforces the per-type rule since it knows the
    campaign.
    """

    starts_at: datetime
    ends_at: Optional[datetime] = None
    capacity: int = Field(ge=1, le=500)

    @model_validator(mode="after")
    def _window_runs_forward(self):
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("A slot has to end after it starts.")
        return self


class CreateSlotPayload(SlotPayload):
    """A slot created against a campaign named in the body."""

    campaign_id: str


class UpdateSlotPayload(BaseModel):
    """Move a slot or resize it. Every field optional — a manager usually
    changes one thing."""

    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    capacity: Optional[int] = Field(default=None, ge=1, le=500)


class NoShowPayload(BaseModel):
    """A creator who didn't turn up. The note is what the admin reads when
    deciding whether anything is owed, so it is required."""

    note: str = Field(min_length=3, max_length=500)


class ReschedulePayload(BaseModel):
    """Move a creator to a different slot on the same campaign."""

    slot_id: str
    reason: Optional[str] = Field(default=None, max_length=500)


class CreatorBookSlotPayload(BaseModel):
    """A creator taking a place on a slot.

    `preferred_time` only means anything on a personal table, where the slot is
    a window of availability rather than a fixed sitting. On a launch or a
    group event everyone arrives together and the field is refused, so a
    stray value can't quietly put one creator at the venue on their own.
    """

    slot_id: str
    preferred_time: Optional[datetime] = None


class CreatorCancelSlotPayload(BaseModel):
    """Handing a booked slot back. The reason is optional — we would rather
    know early without one than have the seat held because a form asked a
    question the creator didn't want to answer."""

    reason: Optional[str] = Field(default=None, max_length=500)


class BroadcastPayload(BaseModel):
    """One WhatsApp message to everyone confirmed on a campaign."""

    message: str = Field(min_length=3, max_length=1000)


class CampaignInvitePayload(BaseModel):
    """Payload for inviting a hand-picked set of creators to a campaign."""

    creator_ids: list[str] = Field(min_length=1, max_length=100)
    note: Optional[str] = Field(default=None, max_length=500)


class DecisionPayload(BaseModel):
    """Payload for a decision that ends or redirects a collaboration."""

    reason: Optional[str] = Field(default=None, max_length=500)


class AgreedAmountPayload(BaseModel):
    """The fee settled offline, written back against the collaboration.

    The note is optional but wanted: "agreed on the call, includes the reel"
    is the difference between a number and a record of a conversation. It ends
    up in the audit log and, when supplied, in the work notes thread.
    """

    # Optional because a barter brief has no figure to send. Which of the three
    # kinds may — or must — carry one is decided by `_resolve_agreed_amount`
    # against the campaign, not by this model, which cannot see it.
    agreed_amount: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=1000)


class DocumentReviewPayload(BaseModel):
    """One document, accepted or rejected. A rejection has to say why, because
    the brand is told what to re-upload."""

    status: Literal["accepted", "rejected"]
    reason: Optional[str] = Field(default=None, max_length=500)


class BrandAcceptPayload(BaseModel):
    """Payload for a brand accepting an applicant onto a campaign."""

    # Lets the brand accept at a number other than the creator's quote.
    agreed_amount: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class ScheduleSlotPayload(BaseModel):
    """Payload for booking the creator's slot."""

    scheduled_at: datetime
    location_note: Optional[str] = Field(default=None, max_length=300)


# Why a collaboration ended. Recorded separately from the free-text reason so
# no-shows can be counted rather than read.
CANCELLATION_TYPES = ("creator_no_show", "brand_cancelled", "admin_cancelled")
CancellationType = Literal["creator_no_show", "brand_cancelled", "admin_cancelled"]


class MarkPaidPayload(BaseModel):
    """Payload recording an actual payout that happened outside the platform."""

    payment_reference: str = Field(min_length=1, max_length=140)


class ReasonPayload(BaseModel):
    """A decision somebody has to be able to explain afterwards.

    Distinct from `DecisionPayload`, where the reason is optional: these are the
    actions that undo, stop or claw back something, and an unexplained one is
    unreadable a week later.
    """

    reason: str = Field(min_length=3, max_length=500)


class CancelCollabPayload(ReasonPayload):
    """Why a collaboration ended, in both a countable and a readable form."""

    # Defaults to the admin doing it, which is true whenever nobody says
    # otherwise, and keeps older callers working.
    cancellation_type: CancellationType = "admin_cancelled"


class RefundPayload(ReasonPayload):
    """A payout being clawed back. The reference is how it reconciles."""

    refund_reference: Optional[str] = Field(default=None, max_length=140)


# --- Domain models (schema-only; used for validation & docs) ---------------

UserStatus = Literal["pending", "active", "suspended"]
VerificationStatus = Literal["pending", "verified", "rejected"]
CampaignStatus = Literal[
    "draft",
    "pending_review",
    "upcoming",
    "open",
    "in_progress",
    # Off the feed but not over: work already under way carries on, and it can
    # be resumed. A campaign we had to stop is not the same as one that ended.
    "paused",
    "completed",
    "closed",
]
CollabState = Literal[
    "applied",
    "verified",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
    # Terminal exits — a collaboration that ends without reaching payment.
    "declined",
    "cancelled",
]
# "cancelled" is a payout that will never happen; "refunded" is one that
# happened and was clawed back. Reporting has to be able to tell them apart.
PaymentState = Literal["pending", "paid", "cancelled", "refunded"]
BrandInvoiceState = Literal["pending", "sent", "settled", "void"]

# The happy path, in order. `declined` / `cancelled` are exits, not steps, so
# they deliberately do not appear here.
COLLAB_STATE_ORDER = [
    "applied",
    "verified",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
]

# Once a collaboration is in one of these, nothing may move it again.
TERMINAL_COLLAB_STATES = ("closed", "declined", "cancelled")

# How a creator's history reads back to an admin. Every state belongs to exactly
# one group, so nothing can silently vanish from a creator's record.
COLLAB_GROUP_APPLIED = ("applied", "verified")
COLLAB_GROUP_ONGOING = (
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
)
COLLAB_GROUP_COMPLETED = ("closed",)

# Delivered = the content exists. `attended` is not enough — somebody turned up
# and shot something, but there is no link yet and so nothing to measure. This
# is the set a report describes and the set performance is recorded against.
DELIVERED_COLLAB_STATES = (
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
)
COLLAB_GROUP_ENDED = ("declined", "cancelled")

# States where the next move is the admin's. Deliberately not derived from
# _BRAND_OWNED_TRANSITIONS: `attended` and `content_submitted` are waiting on the
# creator and the brand respectively, even though the advance endpoint would
# technically let an admin push them.
ADMIN_ACTION_STATES = (
    "applied",            # needs vetting before the brand sees it
    "accepted",           # needs the fee agreed
    "commercial_agreed",  # needs a slot booked
    "slot_booked",        # needs attendance marked
    "content_approved",   # needs moving into payment
)

# A campaign in one of these states is visible on the creator feed.
# `pending_review` is deliberately absent: a brief nobody has read yet must
# never reach a creator.
LIVE_CAMPAIGN_STATUSES = ("open", "upcoming")

# Still running, from the brand's point of view: taking applications or
# mid-delivery. Wider than LIVE_CAMPAIGN_STATUSES, which is about the feed.
ACTIVE_CAMPAIGN_STATUSES = ("upcoming", "open", "in_progress")

# What a brand may ask for when it creates a campaign. Going live is not on the
# list — that is the admin's call, made in `approve_campaign`.
BRAND_SETTABLE_CAMPAIGN_STATUSES = ("draft", "pending_review")

# Waiting on us to read it.
CAMPAIGN_REVIEW_STATUS = "pending_review"


# How a connection can be. `stale` is recoverable by reconnecting; it is not
# the same as disconnected, and the difference is what the UI needs to say.
InstagramConnectionStatus = Literal["connected", "stale"]


class BrandDocument(BaseModel):
    """Collection: brand_documents — proof that a brand is the business it claims.

    Files live in PRIVATE_UPLOAD_DIR, which is deliberately not the static
    upload directory: these carry registered addresses and directors' names,
    and there is no public path to them. `stored_name` is ours and random; the
    uploader's filename is kept only as a label and never touches the disk.
    """

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    brand_id: PyObjectId
    doc_type: BrandDocumentType
    stored_name: str
    original_name: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None
    status: Literal["submitted", "accepted", "rejected"] = "submitted"
    review_note: Optional[str] = None
    created_at: Optional[datetime] = None


class InstagramConnection(BaseModel):
    """Collection: instagram_connections (1:1 with creators who connected).

    Kept out of `creator_profiles` on purpose. The access token is the most
    sensitive thing we hold about a creator, and a separate collection means
    no profile serializer can leak it by accident — there is simply no branch
    where the field is in scope.
    """

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    ig_user_id: str
    username: Optional[str] = None
    # BUSINESS or MEDIA_CREATOR. A personal account can't authorise this API.
    account_type: Optional[str] = None
    # Fernet ciphertext over INSTAGRAM_TOKEN_KEY. Never returned by any route.
    access_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    scopes: list[str] = Field(default_factory=list)
    status: InstagramConnectionStatus = "connected"
    # Why it went stale, in words a creator can act on.
    stale_reason: Optional[str] = None
    stats: Optional[dict] = None
    stats_fetched_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None


class CreatorProfile(BaseModel):
    """Collection: creator_profiles (1:1 with users where role='creator')."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    name: str
    instagram_handle: Optional[str] = None
    instagram_profile_url: Optional[str] = None
    youtube_url: Optional[str] = None
    # Set by the upload endpoint, not by the profile PUT — see upload_profile_image.
    profile_image_url: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    address: Optional[str] = None
    niches: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    full_address: Optional[str] = None
    base_rate: Optional[float] = None
    follower_count: Optional[int] = None
    # Where that number came from. "instagram_verified" while an Instagram
    # connection is live, "self_reported" otherwise; the figure they typed is
    # kept alongside so disconnecting falls back to it rather than to nothing.
    follower_count_source: Literal["self_reported", "instagram_verified"] = "self_reported"
    follower_count_self_reported: Optional[int] = None
    follower_count_verified_at: Optional[datetime] = None
    verification_status: VerificationStatus = "pending"
    # True when an already-verified creator edits something material. They stay
    # verified (and visible to brands) but surface in a separate admin queue.
    pending_review: bool = False
    # When the creator asked us to look, via /creator/profile/submit-for-review.
    # This — not a stub row or a stray handle — is what puts them in the queue.
    submitted_for_review_at: Optional[datetime] = None
    # Set once by the 3-day nudge, so nobody gets chased twice.
    onboarding_nudge_sent_at: Optional[datetime] = None
    # Payout identity — required before a collaboration can enter payment.
    payout_upi: Optional[str] = None
    payout_account_name: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrandProfile(BaseModel):
    """Collection: brand_profiles (1:1 with users where role='brand')."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    business_name: str
    category: Optional[CATEGORY_LITERAL] = None
    areas: list[str] = Field(default_factory=list)
    verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Campaign(BaseModel):
    """Collection: campaigns. Owned by a brand user."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    brand_id: PyObjectId  # references users._id (role=brand)
    title: str = Field(min_length=1, max_length=140)
    brief: str
    deliverables: str
    budget_per_creator: float = Field(ge=0)
    category: Optional[str] = None
    area: Optional[str] = None
    creators_needed: int = Field(ge=1, default=1)
    # launch / group_event carry event_date; personal_table carries the window.
    campaign_type: Optional[CampaignType] = None  # None on pre-types documents
    # Read through _compensation_type, never off the document — None here means
    # "written before the field existed", which is a fixed-fee brand brief.
    compensation_type: Optional[CompensationType] = None
    event_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    venue_address: Optional[str] = None
    venue_instructions: Optional[str] = None
    on_site_contact: Optional[str] = None
    # The assigned campaign manager — differs across concurrent campaigns, so
    # it lives here and not on the brand. Snapshot of the manager user at
    # assignment time, plus the linking id for RBAC.
    manager_id: Optional[PyObjectId] = None
    manager_name: Optional[str] = None
    manager_phone: Optional[str] = None
    manager_email: Optional[str] = None
    status: CampaignStatus = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Collaboration(BaseModel):
    """Collection: collaborations. Join of a creator to a campaign."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    campaign_id: PyObjectId
    creator_id: PyObjectId  # references users._id (role=creator)
    pitch: Optional[str] = None
    quoted_rate: Optional[float] = None
    agreed_amount: Optional[float] = None
    # Who signed off on the agreed amount, and when. Without this the agreed
    # figure is one unattributed number.
    agreed_at: Optional[datetime] = None
    agreed_by: Optional[PyObjectId] = None
    content_url: Optional[str] = None
    content_urls: list[str] = Field(default_factory=list)
    # Set when the collaboration reaches slot_booked.
    scheduled_at: Optional[datetime] = None
    location_note: Optional[str] = None
    # Why a collaboration was declined or cancelled — shown to the creator.
    exit_reason: Optional[str] = None
    # Feedback attached when a brand/admin sends content back for changes.
    revision_note: Optional[str] = None
    state: CollabState = "applied"
    # False once declined/cancelled. The unique (campaign_id, creator_id) index
    # is partial on this flag, so a declined creator may apply again.
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Payment(BaseModel):
    """Collection: payments. One payment per collaboration."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    collaboration_id: PyObjectId
    agreed_amount: float = Field(ge=0)
    platform_fee: float = Field(ge=0, default=0)
    creator_payout: float = Field(ge=0)
    # What the brand owes: the creator's fee plus our margin on top.
    brand_invoice_amount: float = Field(ge=0, default=0)
    brand_invoice_state: BrandInvoiceState = "pending"
    # Snapshot of where the money was sent, taken at payout time so a later
    # profile edit can't rewrite payment history.
    payout_snapshot: Optional[dict] = None
    state: PaymentState = "pending"
    paid_at: Optional[datetime] = None
    payment_reference: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def get_current_user(request: Request) -> dict:
    # A view-as session wins over the admin's own, so every downstream guard,
    # query and serializer sees the target user and nothing has to know that
    # impersonation exists. `_impersonation` is attached for the two things
    # that do care: /auth/me, which draws the banner, and audit(), which names
    # who was really behind the request.
    claim = _decode_impersonation(request)
    if claim:
        try:
            target = await db.users.find_one({"_id": ObjectId(claim["sub"])})
        except Exception:
            target = None
        if target:
            target["_id"] = str(target["_id"])
            target.pop("password_hash", None)
            target["_impersonation"] = {
                "actor_id": claim.get("act"),
                "actor_name": claim.get("act_name"),
                "expires_at": claim.get("exp"),
            }
            return target
        # The target was deleted mid-session. Fall through to the admin's own
        # token rather than 401ing them out of their own account.

    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    try:
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    return user


def require_roles(*roles: str):
    async def _guard(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _guard


def is_brand_side(user: dict) -> bool:
    """True for the brand's own login, whichever of the two role names it holds."""
    return (user or {}).get("role") in BRAND_ROLES


def _brand_scope(user: dict) -> ObjectId:
    """The brand this caller acts for.

    Every brand-scoped query goes through here instead of reaching for
    `user["_id"]` directly. Today a brand manager *is* the brand's login, so
    the two are the same id; routing it through one function means that if a
    brand ever gains a second seat, the scope is one edit rather than a hunt
    through forty queries — and a missed one would have been a brand reading
    another brand's campaigns.
    """
    return ObjectId(user.get("brand_id") or user["_id"])


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def _as_oid(value) -> Optional[ObjectId]:
    """Best-effort ObjectId. Audit context is never worth raising over."""
    if value is None or isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


async def audit(
    actor: dict,
    action: str,
    subject_type: str,
    subject_id,
    *,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    note: Optional[str] = None,
    brand_id=None,
    campaign_id=None,
) -> None:
    """Record who changed what. Every state-changing admin or brand action goes
    through here — without it a payout is a click with no author.

    `brand_id` and `campaign_id` are the context the subject alone doesn't
    carry. A brand manager's actions land on collaborations, payments and
    slots as often as on the campaign itself, and "everything this brand did"
    or "everything that happened on this brief" is the question actually asked
    of the log — answering it by walking each subject back to its campaign is
    both slow and lossy once a row is deleted.
    """
    try:
        await db.audit_log.insert_one(
            {
                "actor_id": ObjectId(actor["_id"]) if actor.get("_id") else None,
                "actor_role": actor.get("role"),
                "actor_name": actor.get("name"),
                "action": action,
                "subject_type": subject_type,
                "subject_id": subject_id if isinstance(subject_id, ObjectId) else str(subject_id),
                "brand_id": _as_oid(brand_id),
                "campaign_id": _as_oid(campaign_id),
                "before": before,
                "after": after,
                "note": note,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:  # never let logging break the operation
        logger.error("audit write failed for %s/%s: %s", action, subject_id, exc)


def _campaign_audit_context(campaign: Optional[dict]) -> dict:
    """The brand/campaign kwargs for `audit`, read off a campaign document.

    A helper rather than two inline lookups at each call site, because the
    failure mode of doing it by hand is an audit line that is silently missing
    its context — which nobody notices until they need it.
    """
    if not campaign:
        return {}
    return {"brand_id": campaign.get("brand_id"), "campaign_id": campaign.get("_id")}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

# Events we tell people about. Each maps to an AiSensy template configured via
# AISENSY_TEMPLATE_<EVENT>; when the env var is missing the event is still
# recorded and readable in-app, it just isn't pushed to WhatsApp.
NOTIFY_EVENTS = {
    "application_declined": "Your application wasn't taken forward",
    "application_accepted": "A brand accepted your pitch",
    "commercial_agreed": "Your fee has been agreed",
    "slot_booked": "Your slot is confirmed",
    "content_changes_requested": "The brand asked for a change",
    "content_approved": "Your content was approved",
    "payment_sent": "Your payment has been sent",
    "new_applicant": "A creator applied to your campaign",
    "creator_verified": "You're verified — briefs are open to you",
    "creator_rejected": "We couldn't approve your profile yet",
    # Suspension is not a verification decision — see suspend_creator.
    "creator_suspended": "Your account is on hold",
    "creator_reinstated": "Your account is active again",
    "campaign_invite": "A brand invited you to a campaign",
    "brand_verified": "Your brand is verified",
    "brand_rejected": "We couldn't verify your brand yet",
    "campaign_approved": "Your campaign is live",
    "campaign_rejected": "Your campaign needs a change before it goes live",
    "manager_assigned": "You've been assigned a campaign",
    "slot_confirmed": "Your slot is booked",
    "manager_slot_booked": "A creator booked a slot",
    "manager_slot_released": "A creator gave up a slot",
    "campaign_broadcast": "A message from your campaign manager",
    "profile_submitted": "Your profile is with the team",
    "profile_nudge": "Your profile is still half-finished",
    "instagram_disconnected": "Reconnect Instagram to keep your verified stats",
    "brand_verification_submitted": "Your business details are with the team",
    # The brand manager's own feed. A brand runs its campaigns from a phone
    # between other work, so anything that changes what they have to do next
    # reaches them rather than waiting to be discovered on a dashboard.
    "brand_new_application": "A creator applied to your campaign",
    "brand_slot_booked": "A creator booked a slot",
    "brand_slot_cancelled": "A creator gave up their slot",
    "brand_slot_rescheduled": "A creator's slot moved",
    "brand_content_submitted": "Content is waiting for your review",
    "brand_creator_cancelled": "A creator dropped off your campaign",
    "brand_creator_no_show": "A creator didn't turn up",
    "brand_campaign_updated": "WeAre changed something on your campaign",
    # The question channel, both directions. Who receives campaign_question
    # follows execution_owner, exactly like a new application.
    "campaign_question": "A creator asked a question",
    "question_answered": "Your question was answered",
}


async def _send_aisensy_template(
    phone: str, name: str, template: str, params: list[str]
) -> bool:
    api_key = os.environ.get("AISENSY_API_KEY", "").strip()
    if not api_key or not template:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
            resp = await http.post(
                "https://backend.aisensy.com/campaign/t1/api/v2",
                json={
                    "apiKey": api_key,
                    "campaignName": template,
                    "destination": phone,
                    "userName": name or "User",
                    "templateParams": params,
                },
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.error("notification send failed (%s): %s", template, exc)
        return False
    if resp.status_code != 200:
        logger.error(
            "notification rejected (%s): status=%s body=%s",
            template,
            resp.status_code,
            resp.text[:200],
        )
        return False
    return True


async def record_notification(
    user_id,
    event: str,
    *,
    title: str,
    body: str,
    link: Optional[str] = None,
    delivered: bool = False,
) -> None:
    """Write the in-app notification row, without touching WhatsApp.

    Split out of `notify` so a caller that has already sent its own WhatsApp
    message — the campaign invite uses a utility template of its own — still
    leaves the same in-app trail, and does not send a second message by going
    back through `notify`. Never raises.
    """
    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    except Exception:
        logger.error("record_notification called with unusable user_id %r", user_id)
        return
    try:
        await db.notifications.insert_one(
            {
                "user_id": oid,
                "event": event,
                "title": title,
                "body": body,
                "link": link,
                "read": False,
                "delivered_on_whatsapp": delivered,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:
        logger.error("notification write failed for %s/%s: %s", event, user_id, exc)


async def notify(
    user_id,
    event: str,
    *,
    title: str,
    body: str,
    params: Optional[list[str]] = None,
    link: Optional[str] = None,
) -> None:
    """Record a notification for a user and push it over WhatsApp if a template
    is configured. Never raises — a failed notification must not roll back the
    state change that triggered it."""
    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    except Exception:
        logger.error("notify called with unusable user_id %r", user_id)
        return

    delivered = False
    try:
        user = await db.users.find_one({"_id": oid})
        template = os.environ.get(f"AISENSY_TEMPLATE_{event.upper()}", "").strip()
        if user and user.get("phone") and template:
            delivered = await _send_aisensy_template(
                user["phone"], user.get("name") or "there", template, params or [body]
            )
    except Exception as exc:
        logger.error("notify failed for %s/%s: %s", event, user_id, exc)

    await record_notification(
        oid, event, title=title, body=body, link=link, delivered=delivered
    )


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

# Where uploaded files land. Served back out at /uploads by the static mount.
# NOTE: this is local disk. On an ephemeral container it does not survive a
# restart — point UPLOAD_DIR at a mounted volume, or swap _store_upload for
# object storage, before relying on it in production.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT_DIR / "uploads")))
UPLOAD_URL_PREFIX = "/uploads"

# Declared content types are client-controlled, so these are matched against
# the file's actual leading bytes rather than the header.
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
)


def max_upload_bytes() -> int:
    try:
        mb = float(os.environ.get("MAX_UPLOAD_MB", "5"))
    except ValueError:
        mb = 5.0
    return int(max(0.1, min(mb, 25)) * 1024 * 1024)


# Derived from the signature table for the same reason ACCEPTED_DOCUMENT_MIMES
# is: an `accept=` attribute that offers a format the sniffer will reject invites
# the file and then refuses it, which on a phone is a minute of upload wasted.
ACCEPTED_IMAGE_MIMES = frozenset(
    [mime for _, mime, _ in _IMAGE_SIGNATURES]
    + ["image/webp"]  # two-part magic, so it isn't in _IMAGE_SIGNATURES
)


def sniff_image_type(head: bytes) -> Optional[tuple]:
    """Identify an image from its leading bytes.

    Returns (mime, extension) or None. WebP needs a two-part check: 'RIFF'
    at 0 and 'WEBP' at 8.
    """
    for magic, mime, ext in _IMAGE_SIGNATURES:
        if head.startswith(magic):
            return mime, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


async def _store_upload(file: UploadFile, *, prefix: str) -> tuple:
    """Validate and write an uploaded image. Returns (public_url, disk_path).

    Reads in chunks so an oversized upload is rejected without first pulling the
    whole thing into memory.
    """
    limit = max_upload_bytes()
    chunk_size = 64 * 1024

    first = await file.read(chunk_size)
    if not first:
        raise HTTPException(status_code=422, detail="That file is empty.")

    sniffed = sniff_image_type(first)
    if not sniffed:
        raise HTTPException(
            status_code=422,
            detail="Please upload a JPEG, PNG, WebP or GIF image.",
        )
    mime, ext = sniffed

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # The client's filename is never trusted — the extension comes from the
    # bytes, and the stem is random so uploads can't be guessed or overwritten.
    filename = f"{prefix}-{_secrets.token_urlsafe(16)}{ext}"
    path = UPLOAD_DIR / filename

    written = 0
    try:
        with open(path, "wb") as out:
            chunk = first
            while chunk:
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Images must be under {limit // (1024 * 1024)}MB.",
                    )
                out.write(chunk)
                chunk = await file.read(chunk_size)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        path.unlink(missing_ok=True)
        logger.error("upload write failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save that image.")
    finally:
        await file.close()

    logger.info("stored upload %s (%s, %d bytes)", filename, mime, written)
    return f"{UPLOAD_URL_PREFIX}/{filename}", path


# ---------------------------------------------------------------------------
# Private uploads — verification documents
# ---------------------------------------------------------------------------
#
# A separate directory from UPLOAD_DIR, which is mounted as static files and
# therefore world-readable by design. A GST certificate carries a registered
# address and a director's name; it must never be one guessable URL away from
# the public internet. Nothing serves this directory — the only way out is an
# authenticated admin route that streams the bytes.
PRIVATE_UPLOAD_DIR = Path(
    os.environ.get("PRIVATE_UPLOAD_DIR", str(ROOT_DIR / "private_uploads"))
)

# The same sniffing rule as the profile-image upload — the extension comes from
# the bytes, never from the client — plus PDF, because that is what a licence
# is usually downloaded as.
_DOCUMENT_SIGNATURES = ((b"%PDF-", "application/pdf", ".pdf"),)

# Derived from the signature tables rather than typed out, so the list the
# upload form offers and the list `sniff_document_type` will actually accept
# cannot come apart. An `accept=` attribute that promises a format the sniffer
# rejects is worse than no attribute: it invites the file and then refuses it.
ACCEPTED_DOCUMENT_MIMES = frozenset(
    [mime for _, mime, _ in _DOCUMENT_SIGNATURES]
    + [mime for _, mime, _ in _IMAGE_SIGNATURES]
    + ["image/webp"]  # two-part magic, so it isn't in _IMAGE_SIGNATURES
)


def sniff_document_type(head: bytes) -> Optional[tuple]:
    """Identify a document from its leading bytes: PDF, or any image we accept."""
    for magic, mime, ext in _DOCUMENT_SIGNATURES:
        if head.startswith(magic):
            return mime, ext
    return sniff_image_type(head)


async def _store_private_upload(file: UploadFile, *, prefix: str) -> dict:
    """Validate and write a document outside the public upload directory.

    Returns the stored metadata. Deliberately never returns a URL: there isn't
    one, and a caller that can't accidentally be handed a link can't
    accidentally render it.
    """
    limit = max_upload_bytes()
    chunk_size = 64 * 1024

    first = await file.read(chunk_size)
    if not first:
        raise HTTPException(status_code=422, detail="That file is empty.")

    sniffed = sniff_document_type(first)
    if not sniffed:
        raise HTTPException(
            status_code=422,
            detail="Please upload a PDF, JPEG, PNG, WebP or GIF.",
        )
    mime, ext = sniffed

    PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{prefix}-{_secrets.token_urlsafe(20)}{ext}"
    path = PRIVATE_UPLOAD_DIR / stored_name

    written = 0
    try:
        with open(path, "wb") as out:
            chunk = first
            while chunk:
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Documents must be under {limit // (1024 * 1024)}MB.",
                    )
                out.write(chunk)
                chunk = await file.read(chunk_size)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        path.unlink(missing_ok=True)
        logger.error("private upload write failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save that document.")
    finally:
        await file.close()

    # The original filename is kept only to show the uploader what they sent;
    # it never touches the filesystem, so a "../../etc/passwd" is just a label.
    original = (file.filename or "document")[:200]
    logger.info("stored private upload %s (%s, %d bytes)", stored_name, mime, written)
    return {
        "stored_name": stored_name,
        "original_name": original,
        "mime": mime,
        "size": written,
    }


def _private_upload_path(stored_name: Optional[str]) -> Optional[Path]:
    """Resolve a stored document, refusing anything that escapes the directory.

    The names are ours and random, but this is the one place a path is built
    from stored data, so it checks rather than assumes.
    """
    if not stored_name or "/" in stored_name or "\\" in stored_name:
        return None
    if stored_name in ("", ".", ".."):
        return None
    path = (PRIVATE_UPLOAD_DIR / stored_name).resolve()
    try:
        path.relative_to(PRIVATE_UPLOAD_DIR.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def _delete_private_upload(stored_name: Optional[str]) -> None:
    path = _private_upload_path(stored_name)
    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("could not delete private upload %s: %s", stored_name, exc)


def _delete_upload(public_url: Optional[str]) -> None:
    """Remove a previously stored upload. Never raises — a leftover file is a
    smaller problem than a failed request."""
    if not public_url or not public_url.startswith(f"{UPLOAD_URL_PREFIX}/"):
        return
    name = public_url.rsplit("/", 1)[-1]
    # Defend the directory boundary even though the name is generated by us.
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        return
    try:
        (UPLOAD_DIR / name).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("could not delete upload %s: %s", name, exc)


def platform_fee_percent() -> float:
    """The margin charged to the brand, on top of the creator's fee."""
    try:
        pct = float(os.environ.get("PLATFORM_FEE_PERCENT", "15"))
    except ValueError:
        logger.warning("PLATFORM_FEE_PERCENT is not a number — falling back to 15")
        return 15.0
    if pct < 0 or pct > 100:
        logger.warning("PLATFORM_FEE_PERCENT out of range (%s) — falling back to 15", pct)
        return 15.0
    return pct


def compute_fee(agreed_amount: float, override: Optional[float] = None) -> float:
    """Fee for a collaboration. `override` lets an admin agree a one-off number;
    everything else comes from central config, not a hardcoded frontend default."""
    if override is not None:
        return round(float(override), 2)
    return round(float(agreed_amount) * platform_fee_percent() / 100.0, 2)


# ---------------------------------------------------------------------------
# App + Router
# ---------------------------------------------------------------------------

app = FastAPI(title="WeAre Creators API")
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@app.middleware("http")
async def _reject_impersonated_writes(request: Request, call_next):
    """**The read-only guarantee for view-as.**

    Not a route dependency and not a check inside `get_current_user`: those
    would both be per-route promises, and a promise every route has to remember
    is one a new route will forget. This sees the method before routing
    happens, so a handler added tomorrow is covered by having been written at
    all.

    It keys on the *method*, not on a list of dangerous endpoints. An allow-list
    of mutations would have to be maintained; "GET, HEAD and OPTIONS cannot
    change anything, so everything else is refused" does not.

    One exception, and it is the reason the feature can be left safely: the stop
    endpoint. It clears the cookie and writes the closing audit line and touches
    no business data, so allowing it cannot be used to change anything — and
    without it an admin could not get out without waiting for the token to
    expire.
    """
    if request.method not in SAFE_METHODS and request.url.path != IMPERSONATION_STOP_PATH:
        if _decode_impersonation(request) is not None:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "You're viewing as somebody else. This is read-only — "
                        "stop viewing as them to make changes."
                    ),
                    "code": "impersonation_read_only",
                },
            )
    return await call_next(request)


@api_router.get("/")
async def root():
    return {"message": "WeAre Creators API", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# --- Auth endpoints --------------------------------------------------------


@auth_router.post("/register")
async def register(payload: RegisterInput, response: Response):
    email = payload.email.lower().strip()
    if not payload.accept_terms:
        raise HTTPException(
            status_code=400,
            detail="Please accept the terms and privacy policy to create an account.",
        )
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "role": payload.role,
        "phone": (payload.phone or "").strip() or None,
        "status": "pending",
        "terms_accepted_at": now,
        "terms_version": TERMS_VERSION,
        "created_at": now,
    }
    result = await db.users.insert_one(doc)
    user_id = result.inserted_id

    # Auto-create the role-specific profile stub so relationships are wired up.
    if payload.role == "creator":
        await db.creator_profiles.insert_one(
            {
                "user_id": user_id,
                "name": doc["name"],
                "instagram_handle": None,
                "instagram_profile_url": None,
                "email": email,
                "address": None,
                "niches": [],
                "base_rate": None,
                "follower_count": None,
                "verification_status": "pending",
                "created_at": now,
                "updated_at": now,
            }
        )
    elif payload.role == "brand":
        await db.brand_profiles.insert_one(
            {
                "user_id": user_id,
                "business_name": doc["name"],
                "category": None,
                "areas": [],
                "verified": False,
                "created_at": now,
                "updated_at": now,
            }
        )

    user_id_str = str(user_id)
    access = create_access_token(user_id_str, email, payload.role)
    refresh = create_refresh_token(user_id_str)
    _set_auth_cookies(response, access, refresh)

    return {
        "id": user_id_str,
        "email": email,
        "name": doc["name"],
        "role": doc["role"],
        "phone": doc["phone"],
        "status": doc["status"],
        "created_at": doc["created_at"].isoformat(),
    }


@auth_router.post("/login")
async def login(payload: LoginInput, response: Response):
    """Email + password login. Reserved for admin users only.
    Creators and brands must sign in via WhatsApp OTP (/auth/otp/*).
    """
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Staff sign in here; creators and brands use WhatsApp OTP.
    if user.get("role") not in ("admin", "campaign_manager"):
        raise HTTPException(
            status_code=403,
            detail="Please sign in with your WhatsApp number.",
        )

    user_id = str(user["_id"])
    access = create_access_token(user_id, email, user["role"])
    refresh = create_refresh_token(user_id)
    _set_auth_cookies(response, access, refresh)

    return {
        "id": user_id,
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "phone": user.get("phone"),
        "status": user.get("status"),
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
    }


@auth_router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    _clear_auth_cookies(response)
    return {"success": True}


@auth_router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    imp = user.get("_impersonation")
    return {
        "id": user["_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "phone": user.get("phone"),
        "status": user.get("status"),
        "created_at": user["created_at"].isoformat() if isinstance(user.get("created_at"), datetime) else user.get("created_at"),
        # Present only during a view-as session. The frontend draws its banner
        # off this rather than off anything it stored when it started, so a
        # session resumed in a second tab — or one that expired while the tab
        # sat open — still shows the truth.
        "impersonation": {
            "active": True,
            "actor_id": imp.get("actor_id"),
            "actor_name": imp.get("actor_name"),
            "expires_at": _iso(datetime.fromtimestamp(imp["expires_at"], tz=timezone.utc))
            if imp.get("expires_at")
            else None,
            "read_only": True,
        }
        if imp
        else None,
    }


@auth_router.post("/impersonate/stop")
async def stop_impersonating(request: Request, response: Response):
    """End a view-as session and hand the admin back their own.

    The one non-GET route reachable while impersonating — see
    `_reject_impersonated_writes`. It clears a cookie and writes an audit line;
    it touches no business data, which is what makes allowing it safe.

    Deliberately does not require a role: the caller *is* the impersonated
    creator as far as every guard is concerned, so `require_roles("admin")`
    would lock the admin inside the session it exists to leave. The token
    itself is the authorisation — only `impersonate_user` mints one, and only
    an admin can call that.
    """
    claim = _decode_impersonation(request)
    response.delete_cookie(IMPERSONATION_COOKIE, path="/")
    if not claim:
        # Already out, or the token expired on its own. Not an error: the
        # button should work whatever state the tab was left in.
        return {"success": True, "was_impersonating": False}

    target = await db.users.find_one({"_id": ObjectId(claim["sub"])})
    actor = await db.users.find_one({"_id": ObjectId(claim["act"])}) if claim.get("act") else None
    if actor:
        actor["_id"] = str(actor["_id"])
        await audit(
            actor,
            "admin.impersonate.stop",
            "user",
            ObjectId(claim["sub"]),
            after={
                "target_user_id": claim["sub"],
                "target_name": (target or {}).get("name"),
                "target_role": (target or {}).get("role"),
            },
        )
    return {"success": True, "was_impersonating": True}


@auth_router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(str(user["_id"]), user["email"], user["role"])
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_MIN * 60,
        path="/",
    )
    return {"success": True}


# --- OTP endpoints ---------------------------------------------------------

import secrets as _secrets


def _otp_ttl() -> int:
    return int(os.environ.get("OTP_TTL_SECONDS", "300"))


def _otp_cooldown() -> int:
    return int(os.environ.get("OTP_RESEND_COOLDOWN_SECONDS", "30"))


def _otp_hourly_limit() -> int:
    return int(os.environ.get("OTP_HOURLY_LIMIT", "5"))


def _otp_max_attempts() -> int:
    return int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))


def _simulation_allowed() -> bool:
    """OTP simulation logs real login codes, so it is opt-in and never the
    default outside an explicitly non-production environment."""
    if os.environ.get("ALLOW_OTP_SIMULATION", "").strip().lower() in ("1", "true", "yes"):
        return True
    env = os.environ.get("APP_ENV", os.environ.get("ENV", "")).strip().lower()
    return env in ("dev", "development", "local", "test")


def _aisensy_configured() -> bool:
    """Whether anything at all is set up to really send WhatsApp messages.

    Deliberately `or`, not `and`, even though `_send_aisensy_otp` needs both
    before it will send: this reads as "is there any sign real delivery is
    wired up here", and it gates the fixed test code. Being too strict costs
    somebody a confusing staging setup; being too loose sends a code everybody
    knows to a real phone.
    """
    return bool(
        os.environ.get("AISENSY_API_KEY", "").strip()
        or os.environ.get("AISENSY_CAMPAIGN_NAME", "").strip()
    )


# A code that never changes turns "read the OTP out of the Railway log" into
# "type 123456", which is the difference between testing signup once and
# testing it twenty times. It is also, obviously, a login bypass for anybody
# who knows the number — so it is fenced in on four sides, and every one of
# them has to be open before a fixed code is used.
_OTP_TEST_CODE_RE = re.compile(r"^\d{6}$")

# Only the names that mean production. Not `_is_production()`, which treats an
# unset APP_ENV as production too — that is the right default for deciding
# whether to warn about a missing admin account, but it would refuse the fixed
# code on a staging box labelled APP_ENV=staging, which is exactly where this
# is meant to be usable.
_PRODUCTION_ENV_NAMES = ("production", "prod", "live")


def _fixed_test_otp_refusal() -> Optional[str]:
    """Why OTP_TEST_CODE must not be honoured, or None if it may be.

    Returns None when the variable is unset — there is nothing to refuse.
    Split out from `_fixed_test_otp` so both the startup warning and the tests
    can ask the question without a side effect.
    """
    raw = os.environ.get("OTP_TEST_CODE", "").strip()
    if not raw:
        return None

    if not _OTP_TEST_CODE_RE.match(raw):
        return (
            "it is not six digits, and the form and the WhatsApp template both "
            "assume a 6-digit code"
        )
    env = os.environ.get("APP_ENV", os.environ.get("ENV", "")).strip().lower()
    if env in _PRODUCTION_ENV_NAMES:
        return f"APP_ENV/ENV is {env!r}"
    if _aisensy_configured():
        return (
            "AiSensy is configured, so codes are really being delivered to real "
            "phones — a fixed one would be a login bypass"
        )
    if not _simulation_allowed():
        return "OTP simulation is not permitted in this environment"
    return None


def _fixed_test_otp() -> Optional[str]:
    """The fixed code to issue instead of a random one, or None.

    Loud on both branches on purpose. When it is refused that is a
    misconfiguration somebody needs to see; when it is used, every single OTP
    says so, because the failure mode this is guarding against is a staging
    setting quietly riding along into production.
    """
    raw = os.environ.get("OTP_TEST_CODE", "").strip()
    if not raw:
        return None

    refusal = _fixed_test_otp_refusal()
    if refusal:
        logger.error(
            "OTP_TEST_CODE is set but is being IGNORED because %s. A random code "
            "was issued instead. Unset OTP_TEST_CODE to silence this.",
            refusal,
        )
        return None

    logger.warning(
        "FIXED TEST OTP in use — never enable in production. Every code issued "
        "from this process is the same one, so anybody who knows a phone number "
        "can sign in as them. Unset OTP_TEST_CODE before this environment is "
        "reachable by anyone else."
    )
    return raw


def warn_about_fixed_test_otp() -> None:
    """Say at boot whether OTP_TEST_CODE is on, so it can't ride along unseen.

    Called from the startup event rather than from `validate_environment()`,
    which runs at import before these helpers are defined. The point is that
    the state is announced once per deploy, in the first few lines of the log,
    where somebody reading a deploy notices it — rather than only in the middle
    of a request nobody is watching.
    """
    raw = os.environ.get("OTP_TEST_CODE", "").strip()
    if not raw:
        return
    refusal = _fixed_test_otp_refusal()
    if refusal:
        logger.error(
            "OTP_TEST_CODE is set but will be IGNORED because %s. Every code will "
            "be random. Unset it to silence this.",
            refusal,
        )
    else:
        logger.warning(
            "FIXED TEST OTP is ENABLED — never enable in production. Every OTP "
            "this process issues will be the same fixed code. This must not be "
            "set anywhere real users can sign in."
        )


# Every OTP refusal the client has to behave differently about carries a code,
# not just a sentence. The prose is for the person; the code is for the form,
# which has to decide whether to start a countdown, offer a resend, or send
# somebody back to the number field — and pattern-matching English to decide
# that is how a copy edit breaks a login screen.
#
# Same `{"detail": ..., "code": ...}` shape the Instagram and impersonation
# refusals already use.
def _otp_error(status: int, code: str, message: str, **extra):
    return HTTPException(
        status_code=status, detail={"message": message, "code": code, **extra}
    )


def _hash_otp_code(phone: str, code: str) -> str:
    """Bcrypt-hash the OTP so raw codes never sit in the database."""
    salted = f"{phone}:{code}".encode("utf-8")
    return bcrypt.hashpw(salted, bcrypt.gensalt()).decode("utf-8")


def _verify_otp_code(phone: str, code: str, code_hash: str) -> bool:
    salted = f"{phone}:{code}".encode("utf-8")
    try:
        return bcrypt.checkpw(salted, code_hash.encode("utf-8"))
    except Exception:
        return False


async def _send_aisensy_otp(phone: str, name: str, code: str) -> str:
    """Send OTP over WhatsApp via AiSensy.

    Returns the provider mode ("aisensy" or "simulation").
    In simulation mode (creds missing) the code is logged and no HTTP call is made.
    Raises HTTPException on provider failure so the caller can surface a resend option.
    """
    api_key = os.environ.get("AISENSY_API_KEY", "").strip()
    campaign = os.environ.get("AISENSY_CAMPAIGN_NAME", "").strip()

    if not api_key or not campaign:
        # Simulation writes live login codes to the server log. That is fine on
        # a laptop and a backdoor anywhere else, so it has to be asked for.
        if not _simulation_allowed():
            logger.error(
                "OTP requested but AiSensy is not configured, and simulation mode "
                "is not permitted in this environment. Set AISENSY_API_KEY and "
                "AISENSY_CAMPAIGN_NAME, or set ALLOW_OTP_SIMULATION=true for local dev."
            )
            raise _otp_error(
                503, "send_failed",
                "We couldn't send your code. Try again.",
            )
        logger.warning(
            "AISENSY simulation mode — OTP for %s is %s (do NOT enable in prod)",
            phone,
            code,
        )
        return "simulation"

    payload = {
        "apiKey": api_key,
        "campaignName": campaign,
        "destination": phone,
        "userName": name or "User",
        "templateParams": [code],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client_http:
            resp = await client_http.post(
                "https://backend.aisensy.com/campaign/t1/api/v2",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.error("AiSensy request failed: %s", exc)
        raise _otp_error(
            503, "send_failed", "We couldn't send your code. Try again."
        )

    if resp.status_code == 200:
        return "aisensy"

    logger.error(
        "AiSensy rejected OTP for %s — status=%s body=%s",
        phone,
        resp.status_code,
        resp.text[:400],
    )
    if resp.status_code in (408, 425, 429) or resp.status_code >= 500:
        raise _otp_error(
            503, "send_failed", "We couldn't send your code. Try again."
        )
    raise _otp_error(
        502, "send_failed",
        "We couldn't send your code. Try again, or use a different number.",
    )


async def _send_aisensy_utility(
    phone: str, name: str, template: str, params: list[str]
) -> str:
    """Send a utility-template WhatsApp message via AiSensy.

    Same provider, endpoint and payload shape as `_send_aisensy_otp`, and the
    same simulation fallback when credentials are missing — but for the utility
    templates that carry campaign information rather than a login code, so the
    template name is passed in rather than read from AISENSY_CAMPAIGN_NAME.

    Returns the mode ("aisensy" or "simulation"). Raises HTTPException when the
    provider refuses, so a batch caller can record one failure and carry on
    rather than losing the whole send.
    """
    api_key = os.environ.get("AISENSY_API_KEY", "").strip()

    if not api_key or not template:
        # Simulation is gated exactly as it is for OTP. An invite carries no
        # secret, but silently "sending" nothing in production would report
        # success to an admin while no creator was ever messaged — a louder
        # failure is the safer one.
        if not _simulation_allowed():
            logger.error(
                "utility message requested but AiSensy is not configured. Set "
                "AISENSY_API_KEY and the template name, or set "
                "ALLOW_OTP_SIMULATION=true for local dev."
            )
            raise HTTPException(
                status_code=503,
                detail="WhatsApp messaging is unavailable right now. Please try again shortly.",
            )
        logger.warning(
            "AISENSY simulation mode — utility message to %s (%s): %s",
            phone,
            template or "no template configured",
            params,
        )
        return "simulation"

    payload = {
        "apiKey": api_key,
        "campaignName": template,
        "destination": phone,
        "userName": name or "User",
        "templateParams": params,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client_http:
            resp = await client_http.post(
                "https://backend.aisensy.com/campaign/t1/api/v2",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.error("AiSensy utility request failed (%s): %s", template, exc)
        raise HTTPException(
            status_code=503,
            detail="Could not reach WhatsApp right now. Please try again.",
        )

    if resp.status_code == 200:
        return "aisensy"

    logger.error(
        "AiSensy rejected utility message for %s (%s) — status=%s body=%s",
        phone,
        template,
        resp.status_code,
        resp.text[:400],
    )
    if resp.status_code in (408, 425, 429) or resp.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp delivery is temporarily unavailable. Please try again.",
        )
    raise HTTPException(
        status_code=502,
        detail="WhatsApp delivery failed for this number.",
    )


async def notify_over_utility_template(
    user_id,
    event: str,
    *,
    title: str,
    body: str,
    params: list[str],
    link: Optional[str] = None,
) -> dict:
    """Send a moderation decision over WhatsApp and record it in-app.

    The WhatsApp side goes through `_send_aisensy_utility` (its own template,
    its own simulation fallback) rather than `notify`, because `notify` picks
    its template from the event name and would send a second message.

    Never raises: a decision that has already been written to the database must
    not be undone by a messaging failure. Returns what happened, so the endpoint
    can tell the admin whether the brand was actually reached.
    """
    template = os.environ.get(f"AISENSY_TEMPLATE_{event.upper()}", "").strip()
    delivered = False
    mode = None
    error = None

    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    except Exception:
        logger.error("notify_over_utility_template got an unusable user_id %r", user_id)
        return {"delivered": False, "mode": None, "error": "Unusable user id."}

    account = await db.users.find_one({"_id": oid})
    phone = (account or {}).get("phone")
    if not phone:
        error = "No WhatsApp number on file."
    else:
        try:
            mode = await _send_aisensy_utility(
                phone, (account or {}).get("name") or "there", template, params
            )
            delivered = mode == "aisensy"
        except HTTPException as exc:
            error = exc.detail
        except Exception as exc:  # never let a send break the decision
            logger.error("utility notify failed for %s: %s", event, exc)
            error = "WhatsApp delivery failed."

    await record_notification(
        oid, event, title=title, body=body, link=link, delivered=delivered
    )
    return {"delivered": delivered, "mode": mode, "error": error}


async def _tell_manager_a_seat_freed(collab: dict, how: str) -> None:
    """A seat coming back on sale is the manager's problem, not the admin's —
    they are the one who has to fill it or re-plan the day. The brand hears
    about it too: it is their table sitting empty."""
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if not campaign:
        return
    profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    name = (profile or {}).get("name") or "A creator"
    await notify_campaign_manager(
        campaign,
        "manager_slot_released",
        title="A slot opened up",
        body=f"{name}'s booking on {campaign.get('title')} was {how} — their place is free again.",
    )
    await _tell_brand_manager_unless_managed(
        campaign,
        "brand_slot_cancelled",
        title="A slot opened up",
        body=f"{name}'s booking on “{campaign.get('title')}” was {how} — "
        "their place is free again.",
    )


async def notify_brand_manager(
    brand_id,
    event: str,
    *,
    title: str,
    body: str,
    link: Optional[str] = None,
    skip_user_id=None,
) -> None:
    """Tell the brand's one named manager that something moved.

    `skip_user_id` drops the message when the manager is the person who caused
    it — telling somebody what they just did themselves trains them to ignore
    the channel, and the channel is WhatsApp.

    Silent when a brand has no manager account yet (a demo row, or a brand
    seeded before the role existed). Never raises: `notify` swallows delivery
    failures, and a message that didn't send must not roll back the state
    change that earned it.
    """
    manager = await _brand_manager_user(_as_oid(brand_id))
    if not manager:
        return
    if skip_user_id is not None and manager["_id"] == _as_oid(skip_user_id):
        return
    await notify(manager["_id"], event, title=title, body=body, link=link)


async def _tell_brand_manager_about_campaign(
    campaign: Optional[dict], *, actor: dict, event: str, title: str, body: str
) -> None:
    """The campaign-shaped case of the above, with the link filled in.

    Used wherever WeAre changes something on a brand's brief: the brand asked
    for the campaign and is answerable for it, so a decision made about it
    without telling them is a decision they find out about from a creator.
    """
    if not campaign:
        return
    await notify_brand_manager(
        campaign.get("brand_id"),
        event,
        title=title,
        body=body,
        link=f"/brand/campaigns/{str(campaign['_id'])}/applicants",
        skip_user_id=(actor or {}).get("_id"),
    )


async def _tell_brand_manager_unless_managed(
    campaign: Optional[dict], event: str, *, title: str, body: str
) -> None:
    """Tell the brand's manager about something a creator did on their campaign.

    Skipped when the campaign's assigned manager *is* the brand's manager and
    has already been told through `notify_campaign_manager` — that is the
    default arrangement, and two WhatsApps for one booking is how a channel
    stops being read. Once an admin hands the campaign to a WeAre manager the
    two are different people and the brand still hears about it, which is the
    case this exists for.
    """
    if not campaign:
        return
    manager = await _brand_manager_user(campaign.get("brand_id"))
    if not manager:
        return
    if campaign.get("manager_id") == manager["_id"]:
        return
    await notify(
        manager["_id"],
        event,
        title=title,
        body=body,
        link=f"/brand/campaigns/{str(campaign['_id'])}/applicants",
    )


async def notify_weare_team(campaign: dict, event: str, *, title: str, body: str) -> None:
    """Reach whoever at WeAre is responsible for a campaign we run.

    The assigned manager if there is one; every admin if there is not. A brand
    can hand us a campaign before we have staffed it, and without this that is
    the one arrangement where an application reaches nobody at all — the brand
    is told it is not theirs to action, and no WeAre manager exists to tell.
    """
    if (campaign or {}).get("manager_id"):
        await notify_campaign_manager(campaign, event, title=title, body=body)
        return
    admin_ids = await db.users.distinct("_id", {"role": "admin"})
    for admin_id in admin_ids:
        await notify(
            admin_id,
            event,
            title=title,
            body=body,
            link=f"/admin/campaigns/{str(campaign['_id'])}",
        )


async def notify_campaign_manager(campaign: dict, event: str, *, title: str, body: str) -> None:
    """Tell the assigned manager something changed on their campaign.

    Silent when nobody is assigned yet — a campaign without a manager has no
    one to tell, and that is not an error worth failing a booking over.
    """
    manager_id = (campaign or {}).get("manager_id")
    if not manager_id:
        return
    await notify(
        manager_id,
        event,
        title=title,
        body=body,
        link=f"/manager/campaigns/{str(campaign['_id'])}",
    )


@auth_router.post("/otp/request")
async def request_otp(payload: OtpRequestInput):
    """Generate a 6-digit code and deliver it to the phone over WhatsApp."""
    phone = _normalize_phone(payload.phone)
    now = datetime.now(timezone.utc)

    # Purpose-specific pre-checks (so we don't spam OTPs to the wrong flow).
    existing_user = await db.users.find_one({"phone": phone})
    if payload.purpose == "login":
        if not existing_user:
            raise _otp_error(
                404, "no_account",
                "No account found for this number. Sign up first.",
            )
        if existing_user.get("role") == "admin":
            raise _otp_error(
                403, "admin_uses_password",
                "Admins sign in with email and password.",
            )
    else:  # signup
        if existing_user:
            raise _otp_error(
                409, "already_registered",
                "This number is already registered. Log in instead.",
            )
        if not payload.name or not payload.role:
            raise _otp_error(
                400, "missing_fields",
                "Name and role are required to sign up.",
            )

    # Rate limits ---------------------------------------------------------
    cooldown = _otp_cooldown()
    hourly_limit = _otp_hourly_limit()
    last = await db.otp_codes.find_one({"phone": phone}, sort=[("created_at", -1)])
    if last:
        last_created = last["created_at"]
        if last_created.tzinfo is None:
            last_created = last_created.replace(tzinfo=timezone.utc)
        elapsed = (now - last_created).total_seconds()
        if elapsed < cooldown:
            retry_after = int(cooldown - elapsed)
            # retry_after is the whole point: the form seeds its countdown from
            # it rather than guessing, so the resend button stays disabled for
            # exactly as long as the server will go on refusing it.
            raise _otp_error(
                429, "cooldown",
                f"Wait {retry_after}s before asking for another code.",
                retry_after=retry_after,
            )

    hour_ago = now - timedelta(hours=1)
    count_recent = await db.otp_codes.count_documents(
        {"phone": phone, "created_at": {"$gte": hour_ago}}
    )
    if count_recent >= hourly_limit:
        # A different 429 from the 30-second cooldown, and the form has to
        # treat it differently: no countdown will clear this one inside the
        # session, so it says "try later" rather than ticking down to nothing.
        raise _otp_error(
            429, "hourly_limit",
            f"That's {hourly_limit} codes for this number in an hour. "
            "Try again later, or contact us if you're stuck.",
        )

    # Generate + send -----------------------------------------------------
    # The fixed test code replaces the *value* and nothing else: it is hashed,
    # stored, expired, counted and locked out exactly like a random one, so the
    # TTL, the attempt limit and both rate limits stay on and stay testable.
    # There is deliberately no shortcut in the verify path — a fixed code is
    # accepted there because it is the code that was issued, not because
    # anything checks for it.
    fixed_code = _fixed_test_otp()
    code = fixed_code or f"{_secrets.randbelow(1_000_000):06d}"
    if payload.name:
        display_name = payload.name
    elif existing_user:
        display_name = existing_user.get("name") or "User"
    else:
        display_name = "User"
    mode = await _send_aisensy_otp(phone, display_name, code)

    await db.otp_codes.insert_one(
        {
            "phone": phone,
            "code_hash": _hash_otp_code(phone, code),
            "purpose": payload.purpose,
            "name": (payload.name or "").strip() or None,
            "role": payload.role,
            "accept_terms": bool(payload.accept_terms),
            # Carried through the code so the verify step can write the named
            # contact even when the client only sent it once, at request time.
            **_brand_contact_from(payload),
            "attempts": 0,
            "verified": False,
            "provider_mode": mode,
            "created_at": now,
            "expires_at": now + timedelta(seconds=_otp_ttl()),
        }
    )

    return {
        "success": True,
        "mode": mode,
        "resend_available_in": cooldown,
        "expires_in": _otp_ttl(),
        # Says only *that* a fixed code is in force, never what it is. The
        # screen needs to explain why the same six digits keep working; it does
        # not need to be told them, and a response body is the one place a code
        # must never appear — it is what a browser extension, a proxy log or a
        # screenshot picks up.
        "test_mode": bool(fixed_code),
    }


@auth_router.post("/otp/verify")
async def verify_otp(payload: OtpVerifyInput, response: Response):
    phone = _normalize_phone(payload.phone)
    now = datetime.now(timezone.utc)

    record = await db.otp_codes.find_one(
        {"phone": phone, "purpose": payload.purpose, "verified": False},
        sort=[("created_at", -1)],
    )
    if not record:
        raise _otp_error(
            400, "no_active_code", "That code has expired. Ask for a new one."
        )

    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise _otp_error(400, "expired", "That code has expired. Ask for a new one.")

    max_attempts = _otp_max_attempts()
    if record["attempts"] >= max_attempts:
        raise _otp_error(
            429, "locked_out",
            "Too many wrong attempts. Ask for a new code to try again.",
        )

    if not _verify_otp_code(phone, payload.code, record["code_hash"]):
        await db.otp_codes.update_one({"_id": record["_id"]}, {"$inc": {"attempts": 1}})
        remaining = max_attempts - (record["attempts"] + 1)
        if remaining <= 0:
            raise _otp_error(
                429, "locked_out",
                "Too many wrong attempts. Ask for a new code to try again.",
            )
        # `remaining` travels separately so the form can say "2 tries
        # left" in its own words and colour it as it likes.
        raise _otp_error(
            400, "wrong_code",
            f"That code isn't right. {remaining} "
            f"{'try' if remaining == 1 else 'tries'} left.",
            remaining=remaining,
        )

    # Mark verified & consume all other pending codes for this phone.
    await db.otp_codes.update_one(
        {"_id": record["_id"]}, {"$set": {"verified": True, "verified_at": now}}
    )
    await db.otp_codes.delete_many(
        {"phone": phone, "verified": False}
    )

    # Login flow ----------------------------------------------------------
    if payload.purpose == "login":
        user = await db.users.find_one({"phone": phone})
        if not user:
            raise _otp_error(404, "no_account", "Account not found. Sign up first.")
        if user.get("role") == "admin":
            raise _otp_error(
                403, "admin_uses_password",
                "Admins sign in with email and password.",
            )
    else:  # signup
        existing_user = await db.users.find_one({"phone": phone})
        if existing_user:
            raise _otp_error(
                409, "already_registered", "This number is already registered."
            )

        signup_name = (record.get("name") or payload.name or "").strip()
        signup_role = record.get("role") or payload.role
        if not signup_name or signup_role not in ("creator", "brand"):
            raise HTTPException(status_code=400, detail="Missing signup details.")
        if not (payload.accept_terms or record.get("accept_terms")):
            raise HTTPException(
                status_code=400,
                detail="Please accept the terms and privacy policy to create an account.",
            )

        # The named contact, from whichever step carried it. The verify call
        # wins where both did, so a corrected spelling on the second screen is
        # the one that sticks.
        contact = {**_brand_contact_from(record), **_brand_contact_from(payload)}

        user_doc = {
            "email": None,
            "password_hash": None,
            "name": signup_name,
            # A brand's login is its one named manager. Signing up is the only
            # way to become one — there is no endpoint that mints a second.
            "role": "brand_manager" if signup_role == "brand" else signup_role,
            "phone": phone,
            "status": "pending",
            "terms_accepted_at": now,
            "terms_version": TERMS_VERSION,
            "created_at": now,
        }
        result = await db.users.insert_one(user_doc)
        user_id = result.inserted_id
        if signup_role == "brand":
            # Self-registered, so the brand it manages is itself. Stored
            # explicitly rather than inferred, because `_brand_scope` reads it
            # and an implicit rule is one refactor away from being wrong.
            await db.users.update_one(
                {"_id": user_id}, {"$set": {"brand_id": user_id, **contact}}
            )

        if signup_role == "creator":
            await db.creator_profiles.insert_one(
                {
                    "user_id": user_id,
                    "name": signup_name,
                    # Signup asks for a name and a number. Everything else is
                    # the profile builder's job, so the stub is deliberately
                    # empty rather than half-guessed.
                    "instagram_handle": None,
                    "instagram_profile_url": None,
                    "youtube_url": None,
                    "email": None,
                    "city": None,
                    "address": None,
                    "full_address": None,
                    "niches": [],
                    "genres": [],
                    "platforms": [],
                    "base_rate": None,
                    "follower_count": None,
                    "verification_status": "pending",
                    "pending_review": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        else:
            await db.brand_profiles.insert_one(
                {
                    "user_id": user_id,
                    "business_name": signup_name,
                    "category": None,
                    "areas": [],
                    "verified": False,
                    "verification_state": "unsubmitted",
                    # The person who signed up is the brand's manager, and the
                    # same three facts are what verification asks for — so they
                    # land on the profile straight away rather than being typed
                    # twice. `contact_phone` is the login number by definition.
                    "contact_person_name": contact.get("manager_name") or None,
                    "contact_person_designation": contact.get("manager_designation"),
                    "contact_email": contact.get("manager_email"),
                    "contact_phone": phone,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        user = await db.users.find_one({"_id": user_id})

    user_id_str = str(user["_id"])
    access = create_access_token(user_id_str, user.get("email") or "", user["role"])
    refresh = create_refresh_token(user_id_str)
    _set_auth_cookies(response, access, refresh)

    return {
        "id": user_id_str,
        "email": user.get("email"),
        "name": user["name"],
        "role": user["role"],
        "phone": user.get("phone"),
        "status": user.get("status"),
        "created_at": user["created_at"].isoformat() if isinstance(user.get("created_at"), datetime) else user.get("created_at"),
    }


api_router.include_router(auth_router)


# --- Creator endpoints -----------------------------------------------------

creator_router = APIRouter(prefix="/creator", tags=["creator"])


def _serialize_creator_profile(doc: dict) -> dict:
    """Convert a raw mongo doc to a JSON-safe response."""
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "name": doc.get("name"),
        "instagram_handle": doc.get("instagram_handle"),
        "instagram_profile_url": doc.get("instagram_profile_url"),
        "youtube_url": doc.get("youtube_url"),
        "facebook_url": doc.get("facebook_url"),
        "about": doc.get("about"),
        "profile_image_url": doc.get("profile_image_url"),
        "email": doc.get("email"),
        "city": doc.get("city"),
        "address": doc.get("address"),
        "full_address": doc.get("full_address"),
        "location_lat": doc.get("location_lat"),
        "location_lng": doc.get("location_lng"),
        "location_place_id": doc.get("location_place_id"),
        "niches": doc.get("niches") or [],
        "genres": doc.get("genres") or [],
        "platforms": doc.get("platforms") or [],
        "base_rate": doc.get("base_rate"),
        "follower_count": doc.get("follower_count"),
        **_follower_provenance(doc),
        "verification_status": doc.get("verification_status", "pending"),
        "pending_review": bool(doc.get("pending_review", False)),
        # What triggered the re-check, so the screen can say which change did
        # it rather than "something".
        "pending_review_fields": doc.get("pending_review_fields") or [],
        "pending_review_since": _iso(doc.get("pending_review_since")),
        "payout_upi": doc.get("payout_upi"),
        "payout_account_name": doc.get("payout_account_name"),
        "pan": doc.get("pan"),
        "gstin": doc.get("gstin"),
        "payout_ready": payout_ready(doc),
        "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        "updated_at": doc["updated_at"].isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at"),
    }


def payout_ready(profile: dict) -> bool:
    """We can only send money if we know where to send it and who to report it
    against. PAN is the minimum for TDS; GSTIN is only needed if registered."""
    if not profile:
        return False
    return bool(profile.get("payout_upi")) and bool(profile.get("pan"))


YOUTUBE_URL_RE = re.compile(
    r"^https?://(www\.|m\.)?(youtube\.com/(channel/|c/|user/|@)?[\w\-.]+|youtu\.be/[\w\-]+)/?",
    re.IGNORECASE,
)


# Spellings that are the same city. Free text let all of these into the
# directory at once, so a brand filtering on Bengaluru found a fraction of the
# creators actually in Bengaluru. Matching is case- and space-insensitive, so
# only genuinely different words need a line here.
_CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "blr": "Bengaluru",
    "bombay": "Mumbai",
    "new delhi": "Delhi NCR",
    "delhi": "Delhi NCR",
    "gurgaon": "Delhi NCR",
    "gurugram": "Delhi NCR",
    "noida": "Delhi NCR",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "cochin": "Kochi",
    "trivandrum": "Kochi",
    "poona": "Pune",
    "baroda": "Ahmedabad",
    "panaji": "Goa",
    "panjim": "Goa",
}

_CITY_BY_KEY = {c.lower(): c for c in INDIAN_CITIES}


# Changes that need a second look, and the words for them.
#
# One place, deliberately, because the set is a judgement about what we are
# actually verifying: who this person is, where their audience is, and where
# the money goes. Everything else on the form — the About paragraph, the
# neighbourhood, their rate, what they cover — is theirs to change freely, and
# putting a creator back in a queue for fixing a typo is how a profile stops
# being kept up to date at all.
#
# `city` is here because a brand filters on it and a shoot is booked on it.
# `instagram_profile_url` is here because the handle without the link is half
# an identity claim.
MATERIAL_PROFILE_FIELDS = {
    "name": "your name",
    "instagram_handle": "your Instagram handle",
    "instagram_profile_url": "your Instagram link",
    "youtube_url": "your YouTube link",
    "facebook_url": "your Facebook link",
    "city": "your city",
    "payout_upi": "your UPI ID",
    "payout_account_name": "your payout account name",
    "pan": "your PAN",
    "gstin": "your GSTIN",
}


def _material_changes(existing: dict, update: dict) -> list:
    """Which material fields this save actually changes, by their labels.

    Compares against what is stored, so re-sending an unchanged value — which
    a form that round-trips every field does on every save — is not a change.
    """
    changed = []
    for field, label in MATERIAL_PROFILE_FIELDS.items():
        if field not in update:
            continue
        if (existing.get(field) or None) != (update.get(field) or None):
            changed.append(label)
    return changed


def _awaiting_recheck(profile: Optional[dict]) -> bool:
    """Whether this creator is verified but waiting on us to look again.

    Deliberately not a `verification_status` of its own. Sending somebody back
    to `pending` would erase the record that they were ever approved — the same
    reason suspension is separate from rejection — and would empty the admin's
    "edited since approval" queue, which keys on exactly this pair.
    """
    profile = profile or {}
    return (
        profile.get("verification_status") == "verified"
        and bool(profile.get("pending_review"))
    )


def _recheck_message(profile: Optional[dict]) -> str:
    """What changed, that we are looking, and roughly how long."""
    fields = (profile or {}).get("pending_review_fields") or []
    what = ", ".join(fields) if fields else "something on your profile"
    return (
        f"You changed {what}, so we're taking another look before you pitch on "
        "anything new. Reviews usually finish within 48 hours. Work you've "
        "already been accepted for carries on as normal."
    )


def _canonical_city(raw: Optional[str]) -> Optional[str]:
    """One spelling per city, or a refusal naming the ones we know.

    A dropdown on the form is what stops most of this, but the form is not the
    only way in — and a value that arrives by any other route still has to be
    reconcilable, because "which creators are in Bengaluru" is the question the
    directory exists to answer.

    Clearing the field is allowed: the profile is built up over sittings and an
    empty city is an unfinished one, not an invalid one.
    """
    value = (raw or "").strip()
    if not value:
        return None
    key = " ".join(value.lower().split())
    if key in _CITY_BY_KEY:
        return _CITY_BY_KEY[key]
    if key in _CITY_ALIASES:
        return _CITY_ALIASES[key]
    raise HTTPException(
        status_code=422,
        detail=(
            f"We don't have {value!r} on the list yet. Pick the closest city — "
            f"currently {', '.join(INDIAN_CITIES[:6])} and more."
        ),
    )


def _clean_youtube_url(raw: Optional[str]) -> Optional[str]:
    """Normalise a YouTube channel link, or refuse it.

    Checked rather than stored blind because this is what a brand clicks to
    decide whether to book somebody — a link that goes nowhere costs the
    creator the booking, and they never find out why.
    """
    url = (raw or "").strip()
    if not url:
        return None
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    if not YOUTUBE_URL_RE.match(url):
        raise HTTPException(
            status_code=422,
            detail="That doesn't look like a YouTube channel link, e.g. https://youtube.com/@yourchannel.",
        )
    return url


def _clean_payout_fields(payload, only: Optional[set] = None) -> dict:
    """Normalise and validate the payout identity fields.

    Each is optional, but anything supplied has to be well-formed — a typo'd
    UPI ID is a lost payout. `only` limits the result to the keys the caller
    actually sent, so a partial save leaves the rest of the payout identity
    where it was.
    """
    out: dict = {}
    wanted = (lambda key: True) if only is None else (lambda key: key in only)

    upi = (payload.payout_upi or "").strip()
    if not wanted("payout_upi"):
        pass
    elif upi:
        if not UPI_RE.match(upi):
            raise HTTPException(
                status_code=422,
                detail="UPI ID should look like yourname@bank.",
            )
        out["payout_upi"] = upi
    else:
        out["payout_upi"] = None

    if wanted("payout_account_name"):
        out["payout_account_name"] = (payload.payout_account_name or "").strip() or None

    pan = (payload.pan or "").strip().upper()
    if not wanted("pan"):
        pass
    elif pan:
        if not PAN_RE.match(pan):
            raise HTTPException(
                status_code=422,
                detail="PAN should be 10 characters, like ABCDE1234F.",
            )
        out["pan"] = pan
    else:
        out["pan"] = None

    gstin = (payload.gstin or "").strip().upper()
    if not wanted("gstin"):
        pass
    elif gstin:
        if not GSTIN_RE.match(gstin):
            raise HTTPException(
                status_code=422,
                detail="GSTIN should be 15 characters, like 29ABCDE1234F1Z5.",
            )
        out["gstin"] = gstin
    else:
        out["gstin"] = None

    return out


@creator_router.post("/profile/image")
async def upload_profile_image(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("creator")),
):
    """Upload the creator's profile photo.

    Deliberately separate from PUT /profile: the field holds a path we issued,
    so it is set by storing a file rather than by accepting a URL from the
    client. Replacing a photo removes the old file.
    """
    profile = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not profile:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    public_url, _path = await _store_upload(file, prefix=f"creator-{user['_id']}")

    previous = profile.get("profile_image_url")
    now = datetime.now(timezone.utc)
    await db.creator_profiles.update_one(
        {"user_id": ObjectId(user["_id"])},
        {"$set": {"profile_image_url": public_url, "updated_at": now}},
    )
    # Only once the new one is safely recorded.
    if previous and previous != public_url:
        _delete_upload(previous)

    return {"profile_image_url": public_url}


@creator_router.delete("/profile/image")
async def delete_profile_image(user: dict = Depends(require_roles("creator"))):
    profile = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not profile:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    previous = profile.get("profile_image_url")
    await db.creator_profiles.update_one(
        {"user_id": ObjectId(user["_id"])},
        {"$set": {"profile_image_url": None, "updated_at": datetime.now(timezone.utc)}},
    )
    _delete_upload(previous)
    return {"profile_image_url": None}


# ---------------------------------------------------------------------------
# Instagram — official stats, via "Instagram API with Instagram Login"
# ---------------------------------------------------------------------------
#
# Deliberately the Instagram-Login flow and not the Facebook-Login one. The
# Facebook route requires every creator to have a Facebook Page linked to their
# account, which most of ours do not and should not have to create. This flow
# authorises against the Instagram account itself.
#
# Two scopes only, and both are read: `instagram_business_basic` for the
# profile and `instagram_business_manage_insights` for reach and interactions.
# Nothing here can post, reply or change anything on a creator's account, and
# asking for a scope we don't use would be asking for trust we don't need.
#
# The predecessor to this was an Apify scraper, which breached Instagram's
# terms and put the connected Meta Business account at risk. It was removed,
# follower counts fell back to self-reported, and this is the sanctioned way
# to get the real number back.

INSTAGRAM_AUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH = "https://graph.instagram.com"
INSTAGRAM_SCOPES = ("instagram_business_basic", "instagram_business_manage_insights")

# Only a Professional account (Business or Creator) can authorise this API at
# all. Meta has used both spellings for the creator variant over time, so both
# are accepted rather than locking somebody out over a rename.
INSTAGRAM_PROFESSIONAL_TYPES = ("BUSINESS", "MEDIA_CREATOR", "CREATOR")

# A long-lived token is good for 60 days and can be refreshed once it is at
# least 24 hours old. Refreshing a week out leaves room for the job to be down
# for a few days without anybody silently falling off.
INSTAGRAM_TOKEN_TTL_DAYS = 60
INSTAGRAM_REFRESH_WINDOW_DAYS = 7

def _instagram_stats_ttl_hours() -> int:
    """How long a cached reading counts as current.

    Twelve hours by design: the ceiling is 200 calls per user per hour and a
    refresh costs three, so a dashboard-load refresh would burn the budget of
    a creator who simply opened the app a lot, for numbers that move slowly.
    """
    try:
        return max(1, int(os.environ.get("INSTAGRAM_STATS_TTL_HOURS", "12")))
    except ValueError:
        return 12


def _instagram_job_interval_seconds() -> int:
    """How often the refresh loop wakes. Zero disables it."""
    try:
        return max(0, int(os.environ.get("INSTAGRAM_JOB_INTERVAL_SECONDS", "1800")))
    except ValueError:
        return 1800


def _instagram_config() -> Optional[dict]:
    """The Meta app credentials, or None while they're absent.

    Absent is a normal state, not an error: the app is in review, and every
    other part of the product has to keep working meanwhile. Everything below
    checks this and degrades rather than raising at import or startup.
    """
    app_id = os.environ.get("INSTAGRAM_APP_ID", "").strip()
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET", "").strip()
    redirect_uri = os.environ.get("INSTAGRAM_REDIRECT_URI", "").strip()
    if not (app_id and app_secret and redirect_uri):
        return None
    # No key means no way to store the token safely, and a token at rest in
    # plaintext is worse than the feature being off.
    if not os.environ.get("INSTAGRAM_TOKEN_KEY", "").strip():
        logger.warning(
            "Instagram app credentials are set but INSTAGRAM_TOKEN_KEY is not. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
        return None
    return {"app_id": app_id, "app_secret": app_secret, "redirect_uri": redirect_uri}


def instagram_configured() -> bool:
    return _instagram_config() is not None


def _instagram_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            "Instagram connection isn't switched on yet — our Meta app is still "
            "in review. Your self-reported follower count is fine in the meantime."
        ),
    )


def _token_cipher():
    """Fernet over INSTAGRAM_TOKEN_KEY.

    Imported here rather than at module scope so the app (and CI, which
    installs a minimal dependency set) still imports without `cryptography`
    present. It is in requirements.txt; this only keeps its absence from
    taking down everything else.
    """
    key = os.environ.get("INSTAGRAM_TOKEN_KEY", "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError:  # pragma: no cover - present in requirements.txt
        logger.error("cryptography is not installed; Instagram tokens cannot be stored.")
        return None
    try:
        return Fernet(key.encode())
    except Exception as exc:
        logger.error("INSTAGRAM_TOKEN_KEY is not a valid Fernet key: %s", exc)
        return None


def _encrypt_token(raw: str) -> str:
    cipher = _token_cipher()
    if not cipher:
        # Refuse rather than fall back to plaintext. A token that can read a
        # creator's insights is not something to store in the clear because a
        # config value was missing.
        raise _instagram_unavailable()
    return cipher.encrypt(raw.encode()).decode()


def _decrypt_token(blob: Optional[str]) -> Optional[str]:
    cipher = _token_cipher()
    if not cipher or not blob:
        return None
    try:
        return cipher.decrypt(blob.encode()).decode()
    except Exception as exc:
        # A rotated key makes every stored token unreadable. Say so once per
        # call site rather than presenting it as the creator revoking access.
        logger.error("Could not decrypt a stored Instagram token: %s", exc)
        return None


class InstagramCallbackPayload(BaseModel):
    """What the frontend hands back after Instagram redirects to it."""

    code: str = Field(min_length=1, max_length=1000)
    state: str = Field(min_length=1, max_length=200)


def _serialize_instagram(doc: Optional[dict], *, configured: Optional[bool] = None) -> dict:
    """The connection as the creator's own UI sees it.

    The token is not in here, and there is no branch that could put it there —
    which is the point of keeping connections in their own collection rather
    than as fields on the profile that every serializer walks.
    """
    if configured is None:
        configured = instagram_configured()
    if not doc:
        return {
            "configured": configured,
            "connected": False,
            "status": None,
            "username": None,
            "account_type": None,
            "connected_at": None,
            "stats": None,
            "stats_fetched_at": None,
            "stale_reason": None,
        }
    stats = doc.get("stats") or None
    return {
        "configured": configured,
        "connected": doc.get("status") == "connected",
        "status": doc.get("status"),
        "username": doc.get("username"),
        "account_type": doc.get("account_type"),
        "connected_at": _iso(doc.get("connected_at")),
        "last_refreshed_at": _iso(doc.get("last_refreshed_at")),
        "token_expires_at": _iso(doc.get("token_expires_at")),
        "stats": stats,
        "stats_fetched_at": _iso(doc.get("stats_fetched_at")),
        "stale_reason": doc.get("stale_reason"),
    }


async def _instagram_get(path: str, params: dict) -> dict:
    """One GET against the Instagram Graph, with the errors translated.

    Meta returns 200 with an `error` body about as often as it returns a 4xx,
    so both shapes are checked here rather than at every call site.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as http:
        resp = await http.get(f"{INSTAGRAM_GRAPH}{path}", params=params)
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Instagram returned something we couldn't read.")
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        raise HTTPException(
            status_code=502,
            detail=err.get("message") or "Instagram refused the request.",
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Instagram refused the request.")
    return data


def _is_revoked(detail: str) -> bool:
    """Whether an Instagram error means the creator took access away.

    Matched on the message because the Graph reuses code 190 for everything
    from a revoked token to an expired one, and both mean the same thing to
    us: stop trying, ask them to reconnect.
    """
    lowered = (detail or "").lower()
    return any(
        marker in lowered
        for marker in (
            "expired",
            "revoked",
            "invalid oauth",
            "session has been invalidated",
            "not authorized",
            "cannot parse access token",
        )
    )


async def _mark_connection_stale(doc: dict, reason: str) -> None:
    """Keep the row, drop the token, tell the creator.

    Deleting the connection would lose the fact that they once had one, and a
    creator who sees a plain "connect" button after their token expired has no
    idea anything happened. `stale` says it out loud and asks for one tap.
    """
    if doc.get("status") == "stale" and doc.get("stale_reason") == reason:
        return  # already said; don't notify twice
    await db.instagram_connections.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "stale",
                "stale_reason": reason,
                "updated_at": datetime.now(timezone.utc),
            },
            # The token is no good and is the most sensitive thing we hold.
            "$unset": {"access_token": ""},
        },
    )
    await notify(
        doc["user_id"],
        "instagram_disconnected",
        title="Reconnect Instagram",
        body=f"{reason} Reconnect to keep your verified follower count.",
        link="/onboarding/creator",
    )


async def _fetch_instagram_stats(ig_user_id: str, token: str) -> dict:
    """Profile counts plus insights, as one cached snapshot.

    Three calls per creator per refresh, against a limit of 200 per user per
    hour — which is why this is on a 12-hour schedule and never on a dashboard
    load. Insights are best-effort: a brand-new account with no activity has
    no reach to report, and that must not cost us the follower count too.
    """
    profile = await _instagram_get(
        "/me",
        {
            "fields": "user_id,username,account_type,media_count,followers_count",
            "access_token": token,
        },
    )

    async def _insight(metric: str) -> Optional[int]:
        try:
            data = await _instagram_get(
                f"/{ig_user_id}/insights",
                {
                    "metric": metric,
                    "period": "day",
                    "metric_type": "total_value",
                    "access_token": token,
                },
            )
        except HTTPException as exc:
            logger.info("Instagram %s unavailable for %s: %s", metric, ig_user_id, exc.detail)
            return None
        rows = data.get("data") or []
        if not rows:
            return None
        value = (rows[0].get("total_value") or {}).get("value")
        return int(value) if isinstance(value, (int, float)) else None

    reach = await _insight("reach")
    engagement = await _insight("total_interactions")

    return {
        "username": profile.get("username"),
        "account_type": profile.get("account_type"),
        "followers_count": profile.get("followers_count"),
        "media_count": profile.get("media_count"),
        "reach": reach,
        "engagement": engagement,
    }


async def _store_instagram_stats(doc: dict, stats: dict) -> dict:
    """Write a snapshot, and mirror the follower count onto the profile.

    The mirror is what lets the brand directory sort and filter on a real
    number without a join on every query. `follower_count_self_reported` keeps
    what the creator told us, so disconnecting falls back to it rather than to
    nothing.
    """
    now = datetime.now(timezone.utc)
    await db.instagram_connections.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "stats": {
                    "followers_count": stats.get("followers_count"),
                    "media_count": stats.get("media_count"),
                    "reach": stats.get("reach"),
                    "engagement": stats.get("engagement"),
                },
                "stats_fetched_at": now,
                "username": stats.get("username") or doc.get("username"),
                "account_type": stats.get("account_type") or doc.get("account_type"),
                "status": "connected",
                "stale_reason": None,
                "updated_at": now,
            }
        },
    )
    followers = stats.get("followers_count")
    if isinstance(followers, int):
        profile = await db.creator_profiles.find_one({"user_id": doc["user_id"]})
        update = {
            "follower_count": followers,
            "follower_count_source": "instagram_verified",
            "follower_count_verified_at": now,
            "engagement_rate": _engagement_rate(followers, stats.get("engagement")),
            "updated_at": now,
        }
        if profile and profile.get("follower_count_self_reported") is None:
            update["follower_count_self_reported"] = profile.get("follower_count")
        await db.creator_profiles.update_one({"user_id": doc["user_id"]}, {"$set": update})
    return stats


def _engagement_rate(followers, interactions) -> Optional[float]:
    """Interactions per follower, as a percentage, or None.

    Mirrored onto the profile alongside the follower count for the same reason:
    ranking creators for a brief must not become a join per candidate. None
    rather than zero when there is nothing to divide — a creator whose insights
    we couldn't read has an unknown engagement rate, not a bad one, and the
    scorer treats the two very differently.
    """
    if not isinstance(followers, int) or followers <= 0:
        return None
    if not isinstance(interactions, (int, float)) or interactions < 0:
        return None
    return round((float(interactions) / followers) * 100, 2)


def _follower_provenance(profile: Optional[dict]) -> dict:
    """Where a follower count came from.

    Returned as a block rather than a bare string so every surface that shows
    the number shows its provenance with it. A measured figure and a
    self-reported one are worth different amounts to a brand, and presenting
    them identically is how the scraped numbers got trusted in the first place.
    """
    source = (profile or {}).get("follower_count_source") or "self_reported"
    verified = source == "instagram_verified"
    return {
        "follower_count_source": source,
        "follower_count_verified": verified,
        "follower_count_verified_at": _iso((profile or {}).get("follower_count_verified_at")),
        "follower_count_self_reported": (profile or {}).get("follower_count_self_reported"),
        "verified_stats_available": verified,
    }


@creator_router.get("/instagram")
async def get_instagram_connection(user: dict = Depends(require_roles("creator"))):
    """Where this creator's Instagram connection stands. Never the token."""
    doc = await db.instagram_connections.find_one({"user_id": ObjectId(user["_id"])})
    return _serialize_instagram(doc)


@creator_router.post("/instagram/connect")
async def start_instagram_connect(user: dict = Depends(require_roles("creator"))):
    """Hand back the URL to send the creator to, and remember why.

    The state is single-use and stored server-side rather than signed and
    trusted, so a callback can only ever be spent once and only by the account
    that started it.
    """
    config = _instagram_config()
    if not config:
        raise _instagram_unavailable()

    state = _secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    await db.instagram_oauth_states.insert_one(
        {
            "state": state,
            "user_id": ObjectId(user["_id"]),
            "created_at": now,
            "expires_at": now + timedelta(minutes=15),
        }
    )
    params = {
        "client_id": config["app_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": ",".join(INSTAGRAM_SCOPES),
        "state": state,
    }
    return {
        "authorize_url": f"{INSTAGRAM_AUTH_URL}?{urlencode(params)}",
        "state": state,
        "scopes": list(INSTAGRAM_SCOPES),
    }


@creator_router.post("/instagram/callback")
async def finish_instagram_connect(
    payload: InstagramCallbackPayload,
    user: dict = Depends(require_roles("creator")),
):
    """Exchange the code, keep the long-lived token, take a first reading."""
    config = _instagram_config()
    if not config:
        raise _instagram_unavailable()

    creator_oid = ObjectId(user["_id"])
    now = datetime.now(timezone.utc)
    consumed = await db.instagram_oauth_states.find_one_and_delete(
        {"state": payload.state, "user_id": creator_oid}
    )
    if not consumed:
        raise HTTPException(
            status_code=400,
            detail="That Instagram link has already been used or has expired. Start again.",
        )
    expires_at = consumed.get("expires_at")
    if expires_at and _as_utc(expires_at) < now:
        raise HTTPException(status_code=400, detail="That Instagram link expired. Start again.")

    # 1. Code -> short-lived token (one hour).
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as http:
        resp = await http.post(
            INSTAGRAM_TOKEN_URL,
            data={
                "client_id": config["app_id"],
                "client_secret": config["app_secret"],
                "grant_type": "authorization_code",
                "redirect_uri": config["redirect_uri"],
                "code": payload.code,
            },
        )
    try:
        token_body = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Instagram returned something we couldn't read.")
    if resp.status_code >= 400 or token_body.get("error_type") or token_body.get("error"):
        message = (
            token_body.get("error_message")
            or (token_body.get("error") or {}).get("message")
            if isinstance(token_body.get("error"), dict)
            else token_body.get("error_message")
        ) or "Instagram wouldn't complete the connection."
        raise HTTPException(status_code=400, detail=message)

    short_token = token_body.get("access_token")
    ig_user_id = str(token_body.get("user_id") or "")
    if not short_token or not ig_user_id:
        raise HTTPException(status_code=502, detail="Instagram didn't return an account to connect.")

    # 2. Short-lived -> long-lived (60 days).
    long_body = await _instagram_get(
        "/access_token",
        {
            "grant_type": "ig_exchange_token",
            "client_secret": config["app_secret"],
            "access_token": short_token,
        },
    )
    token = long_body.get("access_token") or short_token
    expires_in = int(long_body.get("expires_in") or INSTAGRAM_TOKEN_TTL_DAYS * 86400)

    # 3. First reading — and the only reliable way to find out whether this is
    #    a Professional account, which is the one thing this API needs.
    try:
        stats = await _fetch_instagram_stats(ig_user_id, token)
    except HTTPException as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Connected, but Instagram wouldn't give us your stats: {exc.detail}",
        )

    account_type = (stats.get("account_type") or "").upper()
    if account_type and account_type not in INSTAGRAM_PROFESSIONAL_TYPES:
        # The single most common failure, and the one people get stuck on.
        # It is fixable in about thirty seconds if somebody says where to tap.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "not_professional",
                "message": (
                    "Instagram only shares stats with Professional accounts, and yours "
                    "is still a personal one. In Instagram: Settings → Account type and "
                    "tools → Switch to professional account → pick Creator. It's free, "
                    "it keeps your account public and nothing about your posts changes. "
                    "Then come back and connect again."
                ),
                "account_type": account_type,
            },
        )

    doc = await db.instagram_connections.find_one_and_update(
        {"user_id": creator_oid},
        {
            "$set": {
                "ig_user_id": ig_user_id,
                "username": stats.get("username"),
                "account_type": stats.get("account_type"),
                "access_token": _encrypt_token(token),
                "token_expires_at": now + timedelta(seconds=expires_in),
                "last_refreshed_at": now,
                "scopes": list(INSTAGRAM_SCOPES),
                "status": "connected",
                "stale_reason": None,
                "updated_at": now,
            },
            "$setOnInsert": {"user_id": creator_oid, "connected_at": now, "created_at": now},
        },
        upsert=True,
        return_document=True,
    )
    await _store_instagram_stats(doc, stats)

    await audit(
        user,
        "creator.instagram_connect",
        "creator_profile",
        creator_oid,
        after={"ig_user_id": ig_user_id, "username": stats.get("username")},
    )
    fresh = await db.instagram_connections.find_one({"_id": doc["_id"]})
    return _serialize_instagram(fresh)


@creator_router.delete("/instagram")
async def disconnect_instagram(user: dict = Depends(require_roles("creator"))):
    """Hand access back. The row goes, and so does the token with it."""
    creator_oid = ObjectId(user["_id"])
    existing = await db.instagram_connections.find_one_and_delete({"user_id": creator_oid})
    if not existing:
        return _serialize_instagram(None)

    now = datetime.now(timezone.utc)
    profile = await db.creator_profiles.find_one({"user_id": creator_oid})
    # Back to whatever they told us themselves, which is why it was kept.
    await db.creator_profiles.update_one(
        {"user_id": creator_oid},
        {
            "$set": {
                "follower_count": (profile or {}).get("follower_count_self_reported"),
                "follower_count_source": "self_reported",
                "follower_count_verified_at": None,
                "updated_at": now,
            }
        },
    )
    await audit(
        user,
        "creator.instagram_disconnect",
        "creator_profile",
        creator_oid,
        before={"ig_user_id": existing.get("ig_user_id")},
    )
    return _serialize_instagram(None)


@creator_router.post("/instagram/refresh")
async def refresh_instagram_now(user: dict = Depends(require_roles("creator"))):
    """Pull a fresh reading on demand, within the cache window.

    The scheduled job is the normal path. This exists for the creator who has
    just connected and wants to see the number move — and it still refuses
    inside the cache window, because 200 calls per user per hour is a budget
    somebody hammering a button would spend for no benefit.
    """
    doc = await db.instagram_connections.find_one({"user_id": ObjectId(user["_id"])})
    if not doc:
        raise HTTPException(status_code=404, detail="No Instagram account connected.")
    if doc.get("status") != "connected":
        raise HTTPException(
            status_code=409,
            detail="Your Instagram connection needs renewing — reconnect and we'll pick up again.",
        )

    fetched_at = _as_utc(doc.get("stats_fetched_at"))
    now = datetime.now(timezone.utc)
    if fetched_at and now - fetched_at < timedelta(hours=_instagram_stats_ttl_hours()):
        # Not an error — they already have the current numbers.
        return _serialize_instagram(doc)

    token = _decrypt_token(doc.get("access_token"))
    if not token:
        await _mark_connection_stale(doc, "We lost access to your Instagram connection.")
        raise HTTPException(status_code=409, detail="Reconnect Instagram to refresh your stats.")

    try:
        stats = await _fetch_instagram_stats(doc["ig_user_id"], token)
    except HTTPException as exc:
        if _is_revoked(str(exc.detail)):
            await _mark_connection_stale(doc, "Instagram access was withdrawn or expired.")
            raise HTTPException(status_code=409, detail="Reconnect Instagram to refresh your stats.")
        raise
    await _store_instagram_stats(doc, stats)
    return _serialize_instagram(await db.instagram_connections.find_one({"_id": doc["_id"]}))


@creator_router.get("/profile")
async def get_creator_profile(user: dict = Depends(require_roles("creator"))):
    doc = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not doc:
        # Shouldn't happen (stub created at signup), but handle gracefully.
        raise HTTPException(status_code=404, detail="Creator profile not found")
    # Completeness rides along so the builder never has to re-implement the
    # rule that decides whether its submit button works. One definition, and
    # the client and the server can't disagree about what "done" means.
    return {
        **_serialize_creator_profile(doc),
        "profile_completeness": _profile_completeness(doc),
    }


@creator_router.put("/profile")
async def update_creator_profile(
    payload: CreatorProfileUpdate,
    user: dict = Depends(require_roles("creator")),
):
    existing = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not existing:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    sent = payload.model_fields_set
    now = datetime.now(timezone.utc)
    update: dict = {"updated_at": now}

    # Only what the request actually named. A builder that saves one step at a
    # time would otherwise blank every field the current step doesn't show.
    if "name" in sent:
        update["name"] = (payload.name or "").strip() or None
    if "instagram_handle" in sent:
        raw = (payload.instagram_handle or "").strip()
        if raw:
            # Accepts "@name", "name" or a pasted profile URL; stores the bare
            # handle so the directory has one shape to search.
            handle = _extract_ig_handle(raw)
            if not handle:
                raise HTTPException(
                    status_code=422,
                    detail="That doesn't look like an Instagram handle. Use letters, numbers, dots or underscores.",
                )
            update["instagram_handle"] = handle
        else:
            update["instagram_handle"] = None
    if "instagram_profile_url" in sent:
        update["instagram_profile_url"] = (payload.instagram_profile_url or "").strip() or None
    if "youtube_url" in sent:
        update["youtube_url"] = _clean_youtube_url(payload.youtube_url)
    if "facebook_url" in sent:
        update["facebook_url"] = (payload.facebook_url or "").strip() or None
    if "about" in sent:
        update["about"] = (payload.about or "").strip() or None
    if "email" in sent:
        update["email"] = (payload.email or "").lower().strip() or None
    if "city" in sent:
        update["city"] = _canonical_city(payload.city)
    if "address" in sent:
        update["address"] = (payload.address or "").strip() or None
    if "full_address" in sent:
        update["full_address"] = (payload.full_address or "").strip() or None
    # The pin. Written as a set or not at all: half a coordinate pair is a
    # point in the sea off Ghana, and a place_id with no coordinates is a
    # lookup we would have to make on every read.
    for key in ("location_lat", "location_lng", "location_place_id"):
        if key in sent:
            value = getattr(payload, key)
            if isinstance(value, str):
                value = value.strip() or None
            update[key] = value
    if "niches" in sent:
        update["niches"] = [n.strip().lower() for n in payload.niches if n and n.strip()]
    if "genres" in sent:
        update["genres"] = [g.strip().lower() for g in payload.genres if g and g.strip()]
    if "platforms" in sent:
        # Deduped, order kept, so the list reads the way they entered it.
        update["platforms"] = list(dict.fromkeys(payload.platforms))
    if "base_rate" in sent:
        update["base_rate"] = payload.base_rate
    if "follower_count" in sent:
        # While Instagram is connected the live figure wins, and what they
        # type goes to the self-reported field instead. Otherwise saving any
        # other part of the form would quietly replace a measured number with
        # a remembered one, and nothing on screen would say it had happened.
        if existing.get("follower_count_source") == "instagram_verified":
            update["follower_count_self_reported"] = payload.follower_count
        else:
            update["follower_count"] = payload.follower_count
            update["follower_count_self_reported"] = payload.follower_count
    update.update(_clean_payout_fields(payload, only=sent))

    # A verified creator who fixes a typo should not fall out of the directory.
    # Only a material change — who they are, where their audience is, where the
    # money goes — needs a second look. The set is MATERIAL_PROFILE_FIELDS and
    # lives in one place; it used to be three fields inline here, which missed
    # YouTube, Facebook and every payout detail.
    changed_labels = _material_changes(existing, update)
    if existing.get("verification_status") == "verified":
        was_pending = bool(existing.get("pending_review"))
        update["pending_review"] = bool(changed_labels) or was_pending
        if changed_labels:
            # Kept so we can tell them exactly what triggered it rather than
            # "something changed". Merged with anything already outstanding —
            # two edits before we look is still one review.
            update["pending_review_fields"] = sorted(
                set(existing.get("pending_review_fields") or []) | set(changed_labels)
            )
            update["pending_review_since"] = now
        elif not was_pending:
            update["pending_review_fields"] = []
    else:
        # Editing is no longer the act that asks us to look — that is
        # `/profile/submit-for-review`, which only opens at 100%. Saving a
        # half-built profile must not put anybody in the queue, and a rejected
        # creator stays rejected until they actually resubmit.
        update["pending_review"] = bool(existing.get("submitted_for_review_at"))

    result = await db.creator_profiles.find_one_and_update(
        {"user_id": ObjectId(user["_id"])},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    # Told once, on the way in. Saving again while already pending must not
    # send it a second time — the point is that they know, not that they are
    # reminded every time they touch the form.
    if changed_labels and not bool(existing.get("pending_review")) and (
        existing.get("verification_status") == "verified"
    ):
        await notify(
            ObjectId(user["_id"]),
            "profile_submitted",
            title="We'll take another look",
            body=_recheck_message(result),
            link="/profile",
        )
        await audit(
            user,
            "creator.profile_recheck",
            "creator_profile",
            result["_id"],
            after={"pending_review_fields": update.get("pending_review_fields")},
        )

    # Also mirror the display name onto the user document so it stays in sync.
    if update.get("name") and update["name"] != user.get("name"):
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])}, {"$set": {"name": update["name"]}}
        )

    return _serialize_creator_profile(result)


_UPCOMING_STATES = ("slot_booked",)
_PAYMENT_STATES = ("in_payment",)


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _jsonable(value):
    """Make an arbitrary mongo value safe to return — audit entries capture raw
    before/after snapshots, which can hold ObjectIds and datetimes."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_collab_row(
    collab: dict,
    campaign: Optional[dict],
    brand_name: Optional[str],
    brand_logo_url: Optional[str] = None,
) -> dict:
    state = collab.get("state", "applied")
    return {
        "id": str(collab["_id"]),
        "campaign_id": str(collab["campaign_id"]),
        "campaign_title": (campaign or {}).get("title"),
        "cover_image_url": (campaign or {}).get("cover_image_url"),
        "brand_name": brand_name,
        "brand_logo_url": brand_logo_url,
        "area": (campaign or {}).get("area"),
        "category": (campaign or {}).get("category"),
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "agreed_at": _iso(collab.get("agreed_at")),
        "content_url": collab.get("content_url"),
        "content_urls": collab.get("content_urls")
        or ([collab["content_url"]] if collab.get("content_url") else []),
        "scheduled_at": _iso(collab.get("scheduled_at")),
        "location_note": collab.get("location_note"),
        "exit_reason": collab.get("exit_reason"),
        "revision_note": collab.get("revision_note"),
        "state": state,
        # The creator can submit or re-submit right up until it's approved.
        "can_submit_content": state in ("attended", "content_submitted"),
        "created_at": _iso(collab.get("created_at")),
    }


# What the profile builder asks for, and what each field is called on screen.
# Weighted equally on purpose: a percentage that quietly counts PAN for three
# points and a city for one is a number nobody can act on. Ordered the way the
# builder asks, so "what's missing" reads top to bottom.
#
# Payout details (UPI, PAN) are deliberately absent. They are needed before we
# can pay somebody, not before we can look at them, and putting them here would
# make bank details the price of being reviewed at all.
_PROFILE_COMPLETENESS_FIELDS = (
    ("genres", "What you make"),
    ("platforms", "Where you post"),
    ("city", "City"),
    ("full_address", "Full address"),
    ("email", "Email address"),
    ("niches", "What you cover for brands"),
    ("base_rate", "Your usual rate"),
    ("profile_image_url", "Profile photo"),
)

# Asked for only when the creator says they post there. An Instagram-only
# creator who could never reach 100% could never submit for review at all, so
# a channel is required per platform rather than across the board.
_PLATFORM_COMPLETENESS_FIELDS = {
    "instagram": (
        ("instagram_handle", "Instagram handle"),
        ("instagram_profile_url", "Instagram profile link"),
    ),
    "youtube": (("youtube_url", "YouTube channel link"),),
}


def _completeness_fields_for(profile: dict) -> tuple:
    """The fields this particular creator is being asked for."""
    fields = list(_PROFILE_COMPLETENESS_FIELDS)
    for platform in (profile or {}).get("platforms") or []:
        fields.extend(_PLATFORM_COMPLETENESS_FIELDS.get(platform, ()))
    return tuple(fields)


def _profile_completeness(profile: dict) -> dict:
    """How much of the profile is filled in, and what is left.

    A brand shortlists off this, so an empty field is a real cost to the
    creator rather than a cosmetic one. The list is also the gate on
    submitting for review, which is why it names fields rather than just
    returning a number.
    """
    fields = _completeness_fields_for(profile)
    missing = [
        {"field": field, "label": label}
        for field, label in fields
        if not (profile or {}).get(field)
    ]
    total = len(fields)
    filled = total - len(missing)
    return {
        "percent": round(filled * 100 / total) if total else 0,
        "filled": filled,
        "total": total,
        "complete": not missing,
        "missing": missing,
    }


@creator_router.post("/profile/submit-for-review")
async def submit_profile_for_review(user: dict = Depends(require_roles("creator"))):
    """Hand a finished profile to the team.

    Saving and submitting are separate acts. A stub row exists from the moment
    somebody signs up, so if saving were the trigger the vetting queue would
    fill with half-built profiles nobody could make a decision about — which is
    exactly what it used to do. This is the only thing that puts a creator in
    front of an admin.
    """
    oid = ObjectId(user["_id"])
    profile = await db.creator_profiles.find_one({"user_id": oid})
    if not profile:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    status = profile.get("verification_status", "pending")
    if status == "verified":
        raise HTTPException(
            status_code=409,
            detail="You're already verified. Edits go for a second look on their own.",
        )

    completeness = _profile_completeness(profile)
    if not completeness["complete"]:
        # Name what is missing rather than just refusing — this is the whole
        # reason completeness returns fields and not only a percentage.
        outstanding = ", ".join(row["label"] for row in completeness["missing"])
        raise HTTPException(
            status_code=409,
            detail=f"Your profile is {completeness['percent']}% done. Still needed: {outstanding}.",
        )

    now = datetime.now(timezone.utc)
    updated = await db.creator_profiles.find_one_and_update(
        {"user_id": oid},
        {
            "$set": {
                "verification_status": "pending",
                "pending_review": True,
                "submitted_for_review_at": now,
                # A resubmission after a rejection starts clean; leaving the old
                # reason on screen would read as a fresh verdict.
                "verification_reason": None,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    await audit(
        user,
        "creator.submit_for_review",
        "creator_profile",
        profile["_id"],
        before={"verification_status": status},
        after={"verification_status": "pending", "submitted_for_review_at": _iso(now)},
    )
    await notify(
        oid,
        "profile_submitted",
        title="Profile submitted",
        body="Your profile is with the WeAre team. Reviews usually finish within 48 hours.",
        link="/dashboard",
    )
    return {
        "verification_status": "pending",
        "submitted_for_review_at": _iso(now),
        "profile_completeness": _profile_completeness(updated or profile),
    }


# Collaborations the creator is actually on, as the dashboard groups them.
# `content_approved` and `in_payment` sit here rather than under completed:
# the work is done but the money isn't in, and a creator waiting to be paid is
# not finished with us.
_CREATOR_ACTIVE_STATES = COLLAB_GROUP_ONGOING


def _creator_next_action(collab: dict, campaign: Optional[dict], can_be_paid: bool) -> dict:
    """The one thing this creator has to do next, or who they're waiting on.

    Named from the creator's side: "book your slot", not "awaiting slot". Half
    of these are deliberately "nothing" — telling someone plainly that the ball
    is not in their court is worth as much as telling them it is.
    """
    state = collab.get("state")
    if state == "accepted":
        return {"action": None, "label": "We're agreeing your fee with the brand.", "waiting_on": "weare"}
    if state == "commercial_agreed":
        kind = (campaign or {}).get("campaign_type")
        return {
            "action": "book_slot",
            "label": (
                "Pick a time inside the window."
                if kind == "personal_table"
                else "Book your slot."
            ),
            "waiting_on": "you",
        }
    if state == "slot_booked":
        return {"action": "attend", "label": "Turn up at the venue at your slot time.", "waiting_on": "you"}
    if state == "attended":
        return {"action": "submit_content", "label": "Submit your content.", "waiting_on": "you"}
    if state == "content_submitted":
        return {
            "action": "resubmit_content",
            "label": "The brand is reviewing your content. You can still replace it.",
            "waiting_on": "brand",
        }
    if state in ("content_approved", "in_payment"):
        # The payout gate is the one place a creator can be blocking their own
        # money without being told, so it outranks the reassuring message.
        if not can_be_paid:
            return {
                "action": "add_payout_details",
                "label": "Add your UPI ID and PAN so we can pay you.",
                "waiting_on": "you",
            }
        return {"action": None, "label": "Payment is being processed.", "waiting_on": "weare"}
    return {"action": None, "label": None, "waiting_on": None}


async def _suggested_campaigns(
    profile: dict, exclude_ids: set, limit: int = 6
) -> list[dict]:
    """Open campaigns that look like this creator's work, minus the ones they
    are already on.

    Matched in Python rather than in the query: the reason shown to the creator
    has to name which of their niches, genres or neighbourhood it matched, and
    a `$in` that only answers yes or no can't produce that sentence.
    """
    niches = {n.lower() for n in (profile or {}).get("niches") or [] if n}
    genres = {g.lower() for g in (profile or {}).get("genres") or [] if g}
    places = {
        p.lower().strip()
        for p in ((profile or {}).get("city"), (profile or {}).get("address"))
        if p and p.strip()
    }
    if not (niches or genres or places):
        return []

    docs = (
        await db.campaigns.find(
            {
                "status": {"$in": list(LIVE_CAMPAIGN_STATUSES)},
                "_id": {"$nin": list(exclude_ids)},
                # A recommendation is a disclosure. Private briefs reach a
                # creator through their invitation and the browse list's
                # invited-door, never through "you might like".
                **PUBLIC_CAMPAIGN_QUERY,
            }
        )
        .sort("created_at", -1)
        .to_list(length=200)
    )
    if not docs:
        return []

    scored = []
    for doc in docs:
        category = (doc.get("category") or "").lower().strip()
        area = (doc.get("area") or "").lower().strip()
        reasons = []
        if category and category in niches:
            reasons.append(f"You cover {doc['category']}")
        if category and category in genres:
            reasons.append(f"You make {doc['category']} content")
        # A neighbourhood match is worth saying out loud — most of these are
        # in-person, and a creator won't cross a city for one table.
        if area and area in places:
            reasons.append(f"In {doc['area']}, where you're based")
        if reasons:
            scored.append((len(reasons), doc, reasons))

    scored.sort(key=lambda row: row[0], reverse=True)
    top = scored[:limit]
    brand_map = await _load_brand_map([doc["brand_id"] for _, doc, _ in top])
    return [
        {
            **_serialize_campaign(doc, brand_map.get(doc["brand_id"])),
            "match_reason": " · ".join(reasons),
            "match_score": score,
        }
        for score, doc, reasons in top
    ]


@creator_router.get("/dashboard")
async def get_creator_dashboard(
    user: dict = Depends(require_roles("creator")),
):
    creator_oid = ObjectId(user["_id"])

    # Profile summary.
    profile = await db.creator_profiles.find_one({"user_id": creator_oid})
    profile_summary = {
        "name": (profile or {}).get("name") or user.get("name"),
        "instagram_handle": (profile or {}).get("instagram_handle"),
        "instagram_profile_url": (profile or {}).get("instagram_profile_url"),
        "youtube_url": (profile or {}).get("youtube_url"),
        "profile_image_url": (profile or {}).get("profile_image_url"),
        "verification_status": (profile or {}).get("verification_status", "pending"),
        "pending_review": bool((profile or {}).get("pending_review", False)),
        "pending_review_fields": (profile or {}).get("pending_review_fields") or [],
        # Whether they have actually asked us to look. Without this the UI
        # can't tell "still building" from "waiting on us".
        "submitted_for_review_at": _iso((profile or {}).get("submitted_for_review_at")),
        "niches": (profile or {}).get("niches") or [],
        "genres": (profile or {}).get("genres") or [],
        "platforms": (profile or {}).get("platforms") or [],
        # Their own email, on their own dashboard — it was only ever visible to
        # us, which made "is this the right account?" unanswerable for them.
        "email": (profile or {}).get("email") or user.get("email"),
        "phone": user.get("phone"),
        "city": (profile or {}).get("city"),
        "address": (profile or {}).get("address"),
        "full_address": (profile or {}).get("full_address"),
        "follower_count": (profile or {}).get("follower_count"),
        "base_rate": (profile or {}).get("base_rate"),
        "payout_ready": payout_ready(profile or {}),
        # Where the follower number came from, said out loud. It is measured
        # while Instagram is connected and self-reported otherwise, and the
        # two are never presented as the same thing.
        **_follower_provenance(profile),
    }
    profile_summary["instagram"] = _serialize_instagram(
        await db.instagram_connections.find_one({"user_id": creator_oid})
    )

    # All of this creator's collaborations, newest first.
    collabs = (
        await db.collaborations.find({"creator_id": creator_oid})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    campaign_ids = [c["campaign_id"] for c in collabs]
    campaign_map: dict = {}
    brand_map: dict = {}
    if campaign_ids:
        campaigns = await db.campaigns.find(
            {"_id": {"$in": list({cid for cid in campaign_ids})}}
        ).to_list(length=len(campaign_ids))
        campaign_map = {c["_id"]: c for c in campaigns}
        brand_map = await _load_brand_map([c["brand_id"] for c in campaigns])

    def _row(collab: dict) -> dict:
        camp = campaign_map.get(collab["campaign_id"])
        brand = brand_map.get(camp["brand_id"]) if camp else None
        brand_name = (brand or {}).get("business_name") or (brand or {}).get("name")
        return _serialize_collab_row(
            collab, camp, brand_name, (brand or {}).get("logo_url")
        )

    applications = [_row(c) for c in collabs]
    upcoming = [r for r in applications if r["state"] in _UPCOMING_STATES]

    # Payments: pull from the payments collection joined by collaboration.
    collab_ids = [c["_id"] for c in collabs]
    payment_docs = []
    if collab_ids:
        payment_docs = await db.payments.find(
            {"collaboration_id": {"$in": collab_ids}}
        ).to_list(length=len(collab_ids))
    collab_by_id = {c["_id"]: c for c in collabs}
    payments = []
    for p in payment_docs:
        c = collab_by_id.get(p["collaboration_id"])
        camp = campaign_map.get(c["campaign_id"]) if c else None
        brand = brand_map.get(camp["brand_id"]) if camp else None
        payments.append(
            {
                "id": str(p["_id"]),
                "collaboration_id": str(p["collaboration_id"]),
                "campaign_title": (camp or {}).get("title"),
                "brand_name": (brand or {}).get("business_name")
                or (brand or {}).get("name"),
                "agreed_amount": p.get("agreed_amount"),
                "platform_fee": p.get("platform_fee"),
                "creator_payout": p.get("creator_payout"),
                "state": p.get("state", "pending"),
                "paid_at": p["paid_at"].isoformat()
                if isinstance(p.get("paid_at"), datetime)
                else p.get("paid_at"),
            }
        )

    # Also include collabs currently mid-payment even if payments row not yet created.
    in_payment_collabs = [
        r for r in applications if r["state"] in _PAYMENT_STATES
    ]

    # --- Earnings ----------------------------------------------------------
    #
    # Both figures are what actually reaches the creator — net of the platform
    # fee — because a dashboard that quotes the gross and then pays less is a
    # dashboard nobody trusts twice. Where a payment row exists it is the
    # authority; where one doesn't yet, the fee is computed the same way the
    # payment row will compute it.
    payment_by_collab = {p["collaboration_id"]: p for p in payment_docs}
    lifetime_earned = 0.0
    pending_earnings = 0.0
    for p in payment_docs:
        net = p.get("creator_payout")
        if net is None:
            net = float(p.get("agreed_amount") or 0) - float(p.get("platform_fee") or 0)
        if p.get("state") == "paid":
            lifetime_earned += float(net or 0)
        elif p.get("state") == "pending":
            pending_earnings += float(net or 0)
        # "cancelled" and "refunded" are money that will not arrive. Counting
        # them anywhere would have the creator waiting on nothing.

    for c in collabs:
        if c["_id"] in payment_by_collab or c.get("state") in COLLAB_GROUP_ENDED:
            continue
        agreed = c.get("agreed_amount")
        if agreed:
            pending_earnings += float(agreed) - compute_fee(float(agreed))

    campaigns_completed = sum(
        1 for c in collabs if c.get("state") in COLLAB_GROUP_COMPLETED
    )

    # --- Grouped collaborations -------------------------------------------
    #
    # Every state lands in exactly one bucket, so nothing can drop out of a
    # creator's own record.
    row_by_id = {r["id"]: r for r in applications}
    grouped: dict = {"active": [], "completed": [], "applied": [], "declined": []}
    for c in collabs:
        state = c.get("state")
        if state in _CREATOR_ACTIVE_STATES:
            grouped["active"].append(c)
        elif state in COLLAB_GROUP_COMPLETED:
            grouped["completed"].append(row_by_id[str(c["_id"])])
        elif state in COLLAB_GROUP_ENDED:
            grouped["declined"].append(row_by_id[str(c["_id"])])
        else:
            grouped["applied"].append(row_by_id[str(c["_id"])])

    # Active rows carry everything needed to turn up: who to call, where to go,
    # when they're expected, and what they have to do next. This is the view a
    # creator opens on the way to a venue, so it can't require another request.
    slot_ids = [c["slot_id"] for c in grouped["active"] if c.get("slot_id")]
    slot_map: dict = {}
    if slot_ids:
        slot_docs = await db.campaign_slots.find(
            {"_id": {"$in": list({s for s in slot_ids})}}
        ).to_list(length=len(slot_ids))
        slot_map = {d["_id"]: d for d in slot_docs}

    can_be_paid = payout_ready(profile or {})
    active_rows = []
    for c in grouped["active"]:
        camp = campaign_map.get(c["campaign_id"]) or {}
        slot = slot_map.get(c.get("slot_id")) if c.get("slot_id") else None
        active_rows.append(
            {
                **row_by_id[str(c["_id"])],
                "campaign": _serialize_campaign(
                    camp, brand_map.get(camp.get("brand_id"))
                )
                if camp
                else None,
                "manager": {
                    "name": camp.get("manager_name"),
                    "phone": camp.get("manager_phone"),
                },
                "venue": {
                    "area": camp.get("area"),
                    "address": camp.get("venue_address"),
                    "instructions": camp.get("venue_instructions"),
                },
                "slot": _serialize_slot(slot) if slot else None,
                "slot_starts_at": _iso(c.get("scheduled_at")),
                "can_cancel_slot": bool(c.get("slot_id")),
                "cancel_cutoff_hours": SLOT_CANCEL_CUTOFF_HOURS,
                "next_action": _creator_next_action(c, camp, can_be_paid),
            }
        )
    grouped["active"] = active_rows

    completeness = _profile_completeness(profile or {})
    suggestions = await _suggested_campaigns(
        profile or {}, {c["campaign_id"] for c in collabs}
    )

    return {
        "profile": profile_summary,
        "profile_completeness": completeness,
        "applications": applications,
        "collaborations": grouped,
        "upcoming": upcoming,
        "payments": payments,
        "in_payment_collaborations": in_payment_collabs,
        "earnings": {
            "lifetime_earned": round(lifetime_earned, 2),
            "pending_earnings": round(pending_earnings, 2),
            "campaigns_completed": campaigns_completed,
        },
        "suggested_campaigns": suggestions,
        "totals": {
            "applications": len(applications),
            "upcoming": len(upcoming),
            "payments": len(payments) + len(in_payment_collabs),
            "active": len(grouped["active"]),
            "completed": len(grouped["completed"]),
            "declined": len(grouped["declined"]),
        },
    }



@creator_router.post("/collaborations/{collab_id}/submit_content")
async def submit_collab_content(
    collab_id: str,
    payload: SubmitContentPayload,
    user: dict = Depends(require_roles("creator")),
):
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    # Merge the new (list) + legacy (single) fields into a single ordered, deduped list.
    raw: list[str] = []
    if payload.content_urls:
        raw.extend(payload.content_urls)
    if payload.content_url and payload.content_url not in raw:
        raw.append(payload.content_url)

    urls: list[str] = []
    for u in raw:
        if not isinstance(u, str):
            continue
        u = u.strip()
        if not u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            raise HTTPException(
                status_code=422,
                detail="Each content URL must start with http:// or https://",
            )
        if len(u) > 500:
            raise HTTPException(
                status_code=422, detail="One of the URLs is too long"
            )
        if u not in urls:
            urls.append(u)

    if not urls:
        raise HTTPException(
            status_code=422, detail="At least one content URL is required"
        )
    if len(urls) > 25:
        raise HTTPException(
            status_code=422, detail="Too many URLs (max 25)"
        )

    collab = await db.collaborations.find_one(
        {"_id": oid, "creator_id": ObjectId(user["_id"])}
    )
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    # Submitting is allowed from `attended`, and re-submitting from
    # `content_submitted` — a creator must be able to fix a wrong link, or
    # respond to a change request, without an admin unpicking the state by hand.
    if collab.get("state") not in ("attended", "content_submitted"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Content can be submitted once the collaboration is marked attended, "
                "and changed any time before it's approved."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "content_url": urls[0],          # keep legacy field in sync
                "content_urls": urls,
                "state": "content_submitted",
                # A fresh submission clears any outstanding change request.
                "revision_note": None,
                "updated_at": now,
            }
        },
        return_document=True,
    )

    await audit(
        user,
        "collaboration.submit_content",
        "collaboration",
        oid,
        before={"state": collab.get("state")},
        after={"state": "content_submitted", "content_urls": urls},
    )

    # Tell the brand there's something to look at. Approving content is the
    # brand manager's own decision, so it goes to them by name rather than to
    # the brand account — the same person today, but the routing shouldn't be
    # what depends on that.
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if campaign:
        await notify_brand_manager(
            campaign["brand_id"],
            "brand_content_submitted",
            title="Content submitted for review",
            body=(
                f"{user.get('name') or 'A creator'} submitted content for "
                f"“{campaign.get('title')}”. It's waiting on your approval."
            ),
            link=f"/brand/campaigns/{campaign['_id']}/applicants",
        )

    return {
        "id": collab_id,
        "state": updated["state"],
        "content_url": updated.get("content_url"),
        "content_urls": updated.get("content_urls") or [],
    }


# --- Creator-side slot booking ---------------------------------------------
#
# The atomic claim itself lives in `_claim_slot`, next to the campaigns-router
# booking route, so there is exactly one implementation of it. What lives here
# is the creator's own view of it: their collaborations, addressed by
# collaboration id rather than by slot id, which is what the creator app holds.


# How close to their slot a creator can still hand it back. A venue plans
# staffing and stock off the day's bookings, so a walk-away an hour before is
# the manager's problem, not a self-service action.
SLOT_CANCEL_CUTOFF_HOURS = 24


async def _own_collab_or_404(collab_id: str, user: dict) -> dict:
    """Load a collaboration belonging to the caller.

    Someone else's collaboration is a 404, not a 403 — the same rule the brand
    and manager scopes follow, so an id can't be probed for existence.
    """
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    collab = await db.collaborations.find_one(
        {"_id": oid, "creator_id": ObjectId(user["_id"])}
    )
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    return collab


def _slot_window_note(campaign: dict) -> Optional[str]:
    """What the creator is actually choosing, in their own words.

    A launch has a start time everyone shares; a personal table is a window the
    creator picks a time inside. The distinction changes what the form asks
    for, so the API says which it is rather than leaving the UI to infer it.
    """
    if campaign.get("campaign_type") == "personal_table":
        return "Pick the time inside the window that suits you."
    return "The time is fixed by the campaign manager."


@creator_router.get("/campaigns/{campaign_id}/slots")
async def list_creator_slots(
    campaign_id: str,
    user: dict = Depends(require_roles("creator")),
):
    """The slots this creator can actually take a place on.

    Gated on being on the campaign, not on having heard of it: a slot list
    names dates, capacity and the rhythm of a venue, which is not an
    applicant's to read. Slots with no room left are still returned, marked
    full — hiding them makes a half-empty schedule look broken.
    """
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = await db.campaigns.find_one({"_id": oid})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    collab = await db.collaborations.find_one(
        {"campaign_id": oid, "creator_id": ObjectId(user["_id"]), "active": True}
    )
    if not collab or collab.get("state") not in _ONBOARD_COLLAB_STATES:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # An invitation isn't required to book — a creator who applied off the open
    # list is just as much on the campaign — but where one exists it is the
    # reason they are here, so it comes back with the schedule.
    invitation = await db.campaign_invitations.find_one(
        {"campaign_id": oid, "creator_id": ObjectId(user["_id"])}
    )

    docs = (
        await db.campaign_slots.find({"campaign_id": oid})
        .sort("starts_at", 1)
        .to_list(length=500)
    )
    booked_id = collab.get("slot_id")
    slots = []
    for d in docs:
        row = _serialize_slot(d)
        row["is_mine"] = bool(booked_id) and d["_id"] == booked_id
        row["is_full"] = row["spots_left"] <= 0 and not row["is_mine"]
        slots.append(row)

    return {
        "campaign_id": campaign_id,
        "campaign_title": campaign.get("title"),
        "campaign_type": campaign.get("campaign_type"),
        "collaboration_id": str(collab["_id"]),
        "state": collab.get("state"),
        # Booking is the step out of commercial_agreed; the flag saves the UI
        # re-deriving the state machine to decide whether to show the button.
        "can_book": collab.get("state") == "commercial_agreed",
        "picks_own_time": campaign.get("campaign_type") == "personal_table",
        "how_it_works": _slot_window_note(campaign),
        "booked_slot_id": str(booked_id) if booked_id else None,
        "scheduled_at": _iso(collab.get("scheduled_at")),
        "cancel_cutoff_hours": SLOT_CANCEL_CUTOFF_HOURS,
        "invited": bool(invitation),
        "invitation_note": (invitation or {}).get("note"),
        "slots": slots,
    }


@creator_router.post("/collaborations/{collab_id}/book-slot")
async def creator_book_slot(
    collab_id: str,
    payload: CreatorBookSlotPayload,
    user: dict = Depends(require_roles("creator")),
):
    """Take a place on a slot on one of my collaborations."""
    collab = await _own_collab_or_404(collab_id, user)
    state = collab.get("state")
    if state == "slot_booked":
        raise HTTPException(status_code=409, detail="You already have a slot booked.")
    if state != "commercial_agreed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Booking opens once your fee is agreed."
                if state in ("applied", "verified", "accepted")
                else f"Your collaboration is {state} — there's nothing to book."
            ),
        )

    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if not campaign or campaign.get("status") not in ACTIVE_CAMPAIGN_STATUSES:
        raise HTTPException(
            status_code=409, detail="This campaign isn't taking bookings right now."
        )

    try:
        soid = ObjectId(payload.slot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Slot not found")
    slot = await db.campaign_slots.find_one({"_id": soid})
    # Another campaign's slot is not a slot as far as this collaboration goes.
    if not slot or slot["campaign_id"] != collab["campaign_id"]:
        raise HTTPException(status_code=404, detail="Slot not found")

    preferred = None
    if campaign.get("campaign_type") == "personal_table":
        if payload.preferred_time is None:
            raise HTTPException(
                status_code=422,
                detail="Pick the time you want inside the window.",
            )
        preferred = _as_utc(payload.preferred_time)
        starts, ends = _as_utc(slot.get("starts_at")), _as_utc(slot.get("ends_at"))
        if (starts and preferred < starts) or (ends and preferred > ends):
            raise HTTPException(
                status_code=422,
                detail="That time is outside the window you picked.",
            )
    elif payload.preferred_time is not None:
        # Everyone arrives together on a launch or a group event; letting one
        # creator write their own time would put them at the venue alone.
        raise HTTPException(
            status_code=422,
            detail="The time on this campaign is set by the manager — you can't choose one.",
        )

    return await _claim_slot(user, collab, campaign, slot, preferred_time=preferred)


@creator_router.post("/collaborations/{collab_id}/cancel-slot")
async def creator_cancel_slot(
    collab_id: str,
    payload: CreatorCancelSlotPayload,
    user: dict = Depends(require_roles("creator")),
):
    """Hand a booked slot back, up to the cutoff.

    This returns the collaboration to `commercial_agreed` rather than ending
    it: the creator is still on the campaign and still owed a place, they just
    aren't on that one any more. Walking away from the campaign entirely is a
    different decision, and stays with the team.
    """
    collab = await _own_collab_or_404(collab_id, user)
    if collab.get("state") != "slot_booked" or not collab.get("slot_id"):
        raise HTTPException(
            status_code=409,
            detail=f"Your collaboration is {collab.get('state')} — there's no booking to cancel.",
        )

    when = _as_utc(collab.get("scheduled_at"))
    now = datetime.now(timezone.utc)
    if when and when - now < timedelta(hours=SLOT_CANCEL_CUTOFF_HOURS):
        raise HTTPException(
            status_code=409,
            detail=(
                f"It's inside {SLOT_CANCEL_CUTOFF_HOURS} hours of your slot — "
                "message the campaign manager instead."
            ),
        )

    slot_oid = collab["slot_id"]
    # The collaboration moves first. If the seat were released first and this
    # write then lost a race, the place would be on sale while the creator
    # still held it.
    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": "slot_booked", "slot_id": slot_oid},
        {
            "$set": {
                "state": "commercial_agreed",
                "updated_at": now,
                "slot_cancelled_at": now,
                "slot_cancel_reason": (payload.reason or "").strip() or None,
            },
            "$unset": {"slot_id": "", "scheduled_at": "", "preferred_time": ""},
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(
            status_code=409, detail="This just changed — reload and try again."
        )

    await db.campaign_slots.update_one(
        {"_id": slot_oid, "booked_count": {"$gt": 0}},
        {"$inc": {"booked_count": -1}, "$set": {"updated_at": now}},
    )

    await audit(
        user,
        "collaboration.cancel_slot",
        "collaboration",
        collab["_id"],
        before={"state": "slot_booked", "slot_id": str(slot_oid), "scheduled_at": _iso(when)},
        after={"state": "commercial_agreed"},
        note=(payload.reason or "").strip() or None,
    )
    # The manager is the one who has to fill the seat or re-plan the day.
    await _tell_manager_a_seat_freed(collab, "cancelled by the creator")

    return {
        "id": collab_id,
        "state": "commercial_agreed",
        "slot_id": None,
        "scheduled_at": None,
        "next_step": "Pick another slot when you're ready.",
    }



# ---------------------------------------------------------------------------
# Instagram handle parsing
# ---------------------------------------------------------------------------
#
# The Apify Instagram scraper that used to live here has been removed: scraping
# Instagram breaches their terms of service and put the connected Meta Business
# account at risk. Follower counts are self-reported until an officially
# permitted source is wired up.
#
# What survives is handle parsing, which is ours and touches no third party.


def _extract_ig_handle(raw: str) -> Optional[str]:
    """Normalise a pasted handle or profile URL down to the bare handle."""
    if not raw:
        return None
    raw = raw.strip().split("?")[0].rstrip("/")
    if not raw:
        return None
    # A pasted URL or bare handle. Take the last path segment, strip @.
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    raw = raw.lstrip("@").lower()
    if not raw or "." in raw and raw.count(".") > 3:
        return None
    if not re.fullmatch(r"[a-z0-9._]{1,60}", raw):
        return None
    return raw




api_router.include_router(creator_router)


# --- Brand router ----------------------------------------------------------

brand_router = APIRouter(prefix="/brand", tags=["brand"])


def _clean_outlets(rows: list) -> list:
    """Normalise the outlet list, dropping the ones that say nothing.

    A form with an empty row on the end is the normal shape of a repeater, so
    blank rows are discarded rather than stored — otherwise the public page
    grows a run of nameless, addressless entries nobody typed on purpose.
    """
    out = []
    for row in rows or []:
        name = (row.name or "").strip()
        address = (row.address or "").strip()
        area = (row.area or "").strip()
        city = _canonical_city(row.city)
        # Half a coordinate is not a location. Both or neither, so nothing
        # downstream has to ask whether a pin is really a pin.
        has_pin = row.lat is not None and row.lng is not None
        if not (name or address or area or city or has_pin):
            continue
        out.append(
            {
                "name": name or None,
                "address": address or None,
                "area": area or None,
                "city": city,
                "lat": row.lat if has_pin else None,
                "lng": row.lng if has_pin else None,
                "place_id": ((row.place_id or "").strip() or None) if has_pin else None,
            }
        )
    return out


def _serialize_brand_profile(doc: dict) -> dict:
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "business_name": doc.get("business_name"),
        "logo_url": doc.get("logo_url"),
        "category": doc.get("category"),
        "areas": doc.get("areas") or [],
        # What a creator reads on the public page.
        "about": doc.get("about"),
        "city": doc.get("city"),
        "outlets": doc.get("outlets") or [],
        # The business as claimed, which is what documents get checked against.
        "legal_entity_name": doc.get("legal_entity_name"),
        "gst_number": doc.get("gst_number"),
        "business_type": doc.get("business_type"),
        "registered_address": doc.get("registered_address"),
        "website": doc.get("website"),
        "instagram_handle": doc.get("instagram_handle"),
        "facebook_url": doc.get("facebook_url"),
        "linkedin_url": doc.get("linkedin_url"),
        # And the person asking on its behalf.
        "contact_person_name": doc.get("contact_person_name"),
        "contact_person_designation": doc.get("contact_person_designation"),
        "contact_email": doc.get("contact_email"),
        "contact_phone": doc.get("contact_phone"),
        "verified": bool(doc.get("verified", False)),
        "verification_state": _brand_verification_state(doc),
        "submitted_for_verification_at": _iso(doc.get("submitted_for_verification_at")),
        # Set when we refuse a brand, so it can be shown rather than guessed at.
        "verification_reason": doc.get("verification_reason"),
        "created_at": doc["created_at"].isoformat()
        if isinstance(doc.get("created_at"), datetime)
        else doc.get("created_at"),
        "updated_at": doc["updated_at"].isoformat()
        if isinstance(doc.get("updated_at"), datetime)
        else doc.get("updated_at"),
    }


def _serialize_brand_campaign(
    doc: dict, applicant_count: int, filled: int = 0, awaiting: int = 0
) -> dict:
    status = doc.get("status")
    needed = int(doc.get("creators_needed") or 1)
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title"),
        # Never None: the owner's console prints one of two words on every row.
        "visibility": _campaign_visibility(doc),
        "brief": doc.get("brief"),
        "deliverables": doc.get("deliverables"),
        "budget_per_creator": doc.get("budget_per_creator"),
        # Travels with the figure everywhere the figure goes. A number with no
        # word beside it is read as cash, which on a barter brief is a lie.
        "compensation_type": _compensation_type(doc),
        # Case-study material. Ours to decide, not the brand's — see
        # set_campaign_showcase.
        "showcase": bool(doc.get("showcase")),
        "showcase_note": doc.get("showcase_note"),
        "category": doc.get("category"),
        "area": doc.get("area"),
        "city": doc.get("city") or DEFAULT_CAMPAIGN_CITY,
        "creators_needed": needed,
        "campaign_type": doc.get("campaign_type"),
        "cover_image_url": doc.get("cover_image_url"),
        # Who runs it, which decides where applications land. Always sent, and
        # always through the reader — a missing value is "brand", never null,
        # because every surface showing this has to say one of two words.
        "execution_owner": _execution_owner(doc),
        "event_date": _iso(doc.get("event_date")),
        "start_date": _iso(doc.get("start_date")),
        "end_date": _iso(doc.get("end_date")),
        "venue_address": doc.get("venue_address"),
        "venue_instructions": doc.get("venue_instructions"),
        "on_site_contact": doc.get("on_site_contact"),
        # Who runs it day to day. The brand talks to them, so name and phone
        # are theirs to see; assignment itself is the admin's.
        "manager_name": doc.get("manager_name"),
        "manager_phone": doc.get("manager_phone"),
        "status": status,
        "created_at": _iso(doc.get("created_at")),
        "applicant_count": applicant_count,
        "filled_slots": filled,
        "spots_left": max(0, needed - filled),
        # How many applicants are sitting with the brand right now. This is the
        # number that should make somebody act.
        "awaiting_decision": awaiting,
        # Why we sent it back, so the brand can fix the thing we asked about
        # rather than guessing.
        "review_reason": doc.get("review_reason"),
        "submitted_for_review_at": _iso(doc.get("submitted_for_review_at")),
        "reviewed_at": _iso(doc.get("reviewed_at")),
        # Why it is off the feed, when an admin took it off.
        "pause_reason": doc.get("pause_reason"),
        "paused": status == "paused",
        "can_edit": status
        in ("draft", CAMPAIGN_REVIEW_STATUS, "upcoming", "open", "paused"),
        # "Publish" now means "submit for review" — see publish_brand_campaign.
        "can_publish": status == "draft",
        "awaiting_review": status == CAMPAIGN_REVIEW_STATUS,
        "can_close": status
        in ("draft", CAMPAIGN_REVIEW_STATUS, "upcoming", "open", "in_progress", "paused"),
        "can_delete": status == "draft" and applicant_count == 0,
    }


async def _awaiting_brand_counts(campaign_ids: list) -> dict:
    """Applicants the WeAre team has verified and handed to the brand to decide on."""
    if not campaign_ids:
        return {}
    unique = list({cid for cid in campaign_ids})
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": {"$in": unique}, "state": "verified"}},
            {"$group": {"_id": "$campaign_id", "n": {"$sum": 1}}},
        ]
    ).to_list(length=len(unique))
    return {r["_id"]: r["n"] for r in rows}


def _why_brand_is_blocked(profile: Optional[dict]) -> str:
    """Why this brand can't reach creators yet, and what to do about it.

    Three different situations with three different next steps: never
    submitted, waiting on us, or turned down. "Not verified" on its own just
    generates a support email.
    """
    state = _brand_verification_state(profile or {})
    if state == "rejected":
        reason = (profile or {}).get("verification_reason")
        return (
            f"Your brand wasn't verified: {reason} Fix that and submit again."
            if reason
            else "Your brand wasn't verified. Update your details and submit again."
        )
    if state == "pending_verification":
        return (
            "Your business details are with the WeAre team. You can keep drafting — "
            "we'll be in touch as soon as you're verified, usually within 48 hours."
        )
    missing = _brand_missing_fields(profile or {})
    if missing:
        return (
            "Verify your business first — still needed: "
            + ", ".join(row["label"] for row in missing)
            + ", plus a document proving you represent it."
        )
    return (
        "Verify your business first — upload a document proving you represent it, "
        "then submit for verification."
    )


async def _verified_brand_or_403(user: dict) -> dict:
    """Assert the caller's brand has been verified by us.

    Anyone can sign up and claim to be any business, so this is the line
    between a claim and a checked one. Drafting a brief and editing your own
    profile stay open — they cost nobody anything and a rejected brand has to
    be able to fix itself. Everything that *reaches a creator* is behind here:
    publishing, the directory, the applicant list, and every action that
    notifies somebody.
    """
    if user.get("role") == "admin":
        return {}
    profile = await db.brand_profiles.find_one({"user_id": _brand_scope(user)})
    if not profile:
        raise HTTPException(
            status_code=403,
            detail="Finish your brand profile before submitting a campaign.",
        )
    if not profile.get("verified", False):
        raise HTTPException(status_code=403, detail=_why_brand_is_blocked(profile))
    return profile


async def _brand_manager_user(brand_oid) -> Optional[dict]:
    """The one person who runs this brand, or None for a brand that predates
    the role and has not signed in since."""
    if brand_oid is None:
        return None
    return await db.users.find_one(
        {"$or": [{"brand_id": brand_oid}, {"_id": brand_oid}], "role": {"$in": list(BRAND_ROLES)}}
    )


# The same keys `_brand_manager_contact` writes, blanked. Spelling them out
# rather than omitting them keeps the campaign document one shape, so a reader
# never has to tell "no manager" from "field never written".
_NO_CAMPAIGN_MANAGER = {
    "manager_id": None,
    "manager_name": None,
    "manager_phone": None,
    "manager_email": None,
}


async def _brand_manager_contact(brand_oid) -> dict:
    """Name, phone and email for the brand's manager, for stamping onto a
    campaign. The profile is the better source for the first and last — a
    manager may have corrected them there — with the account as the fallback.
    """
    account = await _brand_manager_user(brand_oid) or {}
    profile = await db.brand_profiles.find_one({"user_id": brand_oid}) or {}
    return {
        "manager_id": account.get("_id"),
        "manager_name": (
            profile.get("contact_person_name")
            or account.get("manager_name")
            or account.get("name")
        ),
        "manager_phone": profile.get("contact_phone") or account.get("phone"),
        "manager_email": profile.get("contact_email") or account.get("manager_email"),
    }


def _refuse_dates_foreign_to_type(campaign: dict, update: dict) -> None:
    """An edit must not hand a campaign the other type's date fields.

    Creation validates the combination; without this, a PATCH could quietly give
    a launch a booking window or a personal table an event day.
    """
    ctype = campaign.get("campaign_type")
    if ctype in EVENT_CAMPAIGN_TYPES:
        if update.get("start_date") is not None or update.get("end_date") is not None:
            raise HTTPException(
                status_code=422,
                detail=f"A {ctype.replace('_', ' ')} has an event_date, not a start/end window.",
            )
        if "event_date" in update and update["event_date"] is None:
            raise HTTPException(
                status_code=422,
                detail="An event campaign needs its event_date — set a new one instead.",
            )
    elif ctype == "personal_table":
        if update.get("event_date") is not None:
            raise HTTPException(
                status_code=422,
                detail="A personal table has a booking window, not an event_date.",
            )
        for field in ("start_date", "end_date"):
            if field in update and update[field] is None:
                raise HTTPException(
                    status_code=422,
                    detail="A personal table needs its window — set new dates instead.",
                )


# A brand brief is paid work. Barter — a meal, a stay, a product, and no money —
# is an arrangement WeAre makes, because it is the one most easily used to get a
# day's work out of a creator for nothing, and because whether the thing on
# offer is worth the shoot is a judgement somebody here has to have made.
#
# Both brand write paths funnel through this. There is no admin *create* route
# for campaigns, so in practice barter is reached by an admin editing a brief —
# `admin_update_campaign` is deliberately the only caller that skips this.
BARTER_IS_OURS = (
    "Barter campaigns are arranged by the WeAre team. Post this as paid work — "
    "a fixed fee, or a budget you'll negotiate — and talk to us if barter is "
    "what you had in mind."
)


def _refuse_brand_barter(campaign: Optional[dict], update: dict) -> None:
    """Keep barter out of everything a brand can write.

    Two separate refusals, because they are two different mistakes:
      - asking for barter on a brief of your own, and
      - rewriting the compensation on one we already made barter, which would
        turn a WeAre arrangement back into cash without anyone deciding to.
    `campaign` is None at creation time, where only the first can happen.
    """
    if "compensation_type" not in update:
        return
    if update["compensation_type"] == "barter":
        raise HTTPException(status_code=422, detail=BARTER_IS_OURS)
    if campaign is not None and _is_barter(campaign):
        raise HTTPException(
            status_code=422,
            detail=(
                "We set this campaign up as barter. Ask us to change it to paid "
                "— the rest of the brief is still yours to edit."
            ),
        )


# Statuses in which handing execution over is still just a decision on a form.
# After this the brief has been in front of creators, some of whom applied on
# the understanding of who they would be dealing with.
_EXECUTION_SETTLED_STATUSES = ("draft", CAMPAIGN_REVIEW_STATUS)


def _refuse_late_execution_handover(campaign: Optional[dict], update: dict) -> None:
    """Keep a brand from changing who runs a campaign after it has gone out.

    Changing it silently reroutes every future application away from whoever
    has been working the campaign, and it contradicts what creators were told
    when they applied. While the brief is a draft or in review it is nobody's
    working assumption yet, so it is freely editable there.

    An admin can still move it at any time — that is a conversation that has
    happened, and `PATCH /admin/campaigns/{id}` deliberately does not call this.
    """
    if "execution_owner" not in update or campaign is None:
        return
    if update["execution_owner"] == _execution_owner(campaign):
        return  # not a change; re-sending the same value is not an edit
    if campaign.get("status") not in _EXECUTION_SETTLED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "This campaign is already live, so who runs it can't be changed "
                "here — creators applied knowing who they'd be dealing with. "
                "Ask us and we'll move it."
            ),
        )


async def _execution_manager_fields(campaign: dict, execution_owner: str) -> dict:
    """Keep `manager_*` honest when execution changes hands.

    The two must never disagree: a WeAre-run campaign carrying the brand's
    person as its manager would route applications straight back to the brand
    that asked us to take it on, and would put the campaign in no WeAre queue
    at all.
    """
    if execution_owner == "weare":
        # Ours now, and unstaffed until an admin assigns a real manager.
        return dict(_NO_CAMPAIGN_MANAGER)
    return await _brand_manager_contact(campaign["brand_id"])


async def _own_campaign_or_404(campaign_id: str, user: dict) -> dict:
    """Load a campaign, asserting the caller's brand owns it."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    doc = await db.campaigns.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.get("role") != "admin" and doc.get("brand_id") != _brand_scope(user):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return doc


def _clean_gstin(raw: Optional[str]) -> Optional[str]:
    """A GSTIN is either well-formed or it isn't. Optional, but not sloppy —
    a reviewer matching a number to a certificate needs it in one shape."""
    value = (raw or "").strip().upper().replace(" ", "")
    if not value:
        return None
    if not GSTIN_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail="GSTIN should be 15 characters, like 29ABCDE1234F1Z5.",
        )
    return value


def _clean_web_url(raw: Optional[str], *, label: str) -> Optional[str]:
    """Normalise a URL, or refuse it.

    A reviewer clicks these to check the business exists, so a link that goes
    nowhere is worse than no link — it looks like evidence and isn't.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if not value.lower().startswith(("http://", "https://")):
        value = f"https://{value}"
    if not re.match(r"^https?://[\w.-]+\.[a-z]{2,}(/.*)?$", value, re.IGNORECASE):
        raise HTTPException(
            status_code=422, detail=f"That doesn't look like a {label} URL."
        )
    return value


# What a brand has to tell us before we will look at it. Documents prove the
# business exists; these say which business, and who is asking on its behalf.
_BRAND_REQUIRED_FIELDS = (
    ("business_name", "Business name"),
    ("legal_entity_name", "Legal entity name"),
    ("business_type", "Business type"),
    ("category", "Category"),
    ("registered_address", "Registered address"),
    ("contact_person_name", "Contact person"),
    ("contact_person_designation", "Their designation"),
    ("contact_email", "Work email"),
)

# Domains where an address proves nothing about employment. Not a rejection —
# plenty of real small businesses run on Gmail — but the reviewer should be
# told, because a work email on the company domain is the cheapest signal that
# somebody actually works there.
_FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in",
        "outlook.com", "hotmail.com", "live.com", "rediffmail.com",
        "icloud.com", "proton.me", "protonmail.com", "zoho.com",
    }
)


def _is_free_email(address: Optional[str]) -> bool:
    domain = (address or "").rsplit("@", 1)[-1].lower().strip()
    return bool(domain) and domain in _FREE_EMAIL_DOMAINS


def _brand_missing_fields(profile: dict) -> list:
    return [
        {"field": field, "label": label}
        for field, label in _BRAND_REQUIRED_FIELDS
        if not (profile or {}).get(field)
    ]


def _brand_verification_state(profile: dict) -> str:
    """Where the brand stands, derived so old rows without the field still work."""
    if (profile or {}).get("verified"):
        return "verified"
    stored = (profile or {}).get("verification_state")
    if stored in ("unsubmitted", "pending_verification", "rejected"):
        return stored
    # Pre-dates the field: a refusal left a reason behind, everything else
    # never submitted anything.
    return "rejected" if (profile or {}).get("verification_reason") else "unsubmitted"


async def _brand_documents(brand_oid) -> list:
    docs = (
        await db.brand_documents.find({"brand_id": brand_oid})
        .sort("created_at", -1)
        .to_list(length=100)
    )
    return [_serialize_brand_document(d) for d in docs]


def _serialize_brand_document(doc: dict) -> dict:
    """A document as its uploader sees it: what it is, not where it lives.

    No path and no URL — there is no public one, and a serializer that can't
    produce a link can't leak one into a template by accident.
    """
    return {
        "id": str(doc["_id"]),
        "doc_type": doc.get("doc_type"),
        "doc_label": BRAND_DOCUMENT_LABELS.get(doc.get("doc_type"), doc.get("doc_type")),
        "original_name": doc.get("original_name"),
        "mime": doc.get("mime"),
        "size": doc.get("size"),
        "status": doc.get("status", "submitted"),
        "review_note": doc.get("review_note"),
        "uploaded_at": _iso(doc.get("created_at")),
    }


async def _brand_profile_response(profile: dict) -> dict:
    """The profile plus everything the verification screen needs in one call."""
    out = _serialize_brand_profile(profile)
    missing = _brand_missing_fields(profile)
    # Keyed on user_id, the same id campaigns use for brand_id.
    documents = await _brand_documents(profile["user_id"])
    state = _brand_verification_state(profile)
    out["verification"] = {
        "state": state,
        "missing_fields": missing,
        "documents": documents,
        "document_count": len(documents),
        "can_submit": not missing and bool(documents) and state != "verified",
        "submitted_at": _iso(profile.get("submitted_for_verification_at")),
        "verification_reason": profile.get("verification_reason"),
        "accepted_document_types": [
            {"value": v, "label": BRAND_DOCUMENT_LABELS[v]} for v in BRAND_DOCUMENT_LABELS
        ],
        # What the uploader may send, told rather than guessed. The form
        # pre-checks each file so a 6MB scan fails in the browser instead of
        # after a minute on a hotel wifi — but the check is only honest if it
        # uses the server's number, and a copy of `MAX_UPLOAD_MB` in JavaScript
        # is a copy that drifts the day somebody raises it here.
        "max_document_bytes": max_upload_bytes(),
        "accepted_mime_types": sorted(ACCEPTED_DOCUMENT_MIMES),
        "max_documents": MAX_BRAND_DOCUMENTS,
    }
    # The same telling-rather-than-copying rule for the pictures: the logo on
    # this page and the cover on a brief both land through `_store_upload`, so
    # the browser can refuse an oversized file before a byte moves.
    out["uploads"] = {
        "max_image_bytes": max_upload_bytes(),
        "accepted_image_mime_types": sorted(ACCEPTED_IMAGE_MIMES),
    }
    return out


@brand_router.get("/profile")
async def get_brand_profile(user: dict = Depends(require_roles(*BRAND_ROLES))):
    doc = await db.brand_profiles.find_one({"user_id": _brand_scope(user)})
    if not doc:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return await _brand_profile_response(doc)


@brand_router.put("/profile")
async def update_brand_profile(
    payload: BrandProfileUpdate,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Save the brand profile. Editing stays open whatever the brand's state.

    An unverified brand can always fix its own details — that is the only way
    a rejected brand ever becomes a verified one. What it cannot do is reach a
    creator, which is enforced separately.
    """
    existing = await db.brand_profiles.find_one({"user_id": _brand_scope(user)})
    if not existing:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    sent = payload.model_fields_set
    now = datetime.now(timezone.utc)
    update: dict = {"updated_at": now}

    def text(field, value, *, lower=False):
        if field not in sent:
            return
        cleaned = (value or "").strip()
        update[field] = (cleaned.lower() if lower else cleaned) or None

    text("business_name", payload.business_name)
    text("about", payload.about)
    text("legal_entity_name", payload.legal_entity_name)
    text("registered_address", payload.registered_address)
    text("contact_person_name", payload.contact_person_name)
    text("contact_person_designation", payload.contact_person_designation)
    text("contact_email", payload.contact_email, lower=True)

    if "category" in sent:
        update["category"] = payload.category
    if "business_type" in sent:
        update["business_type"] = payload.business_type
    if "areas" in sent:
        update["areas"] = [a.strip() for a in payload.areas if a and a.strip()]
    if "city" in sent:
        # The same canonicaliser the creator's city and the campaign's go
        # through. Three free-text spellings of Bengaluru is three cities to a
        # filter and one to everybody else.
        update["city"] = _canonical_city(payload.city)
    if "outlets" in sent:
        update["outlets"] = _clean_outlets(payload.outlets)
    if "gst_number" in sent:
        update["gst_number"] = _clean_gstin(payload.gst_number)
    if "website" in sent:
        update["website"] = _clean_web_url(payload.website, label="website")
    if "facebook_url" in sent:
        update["facebook_url"] = _clean_web_url(payload.facebook_url, label="Facebook page")
    if "linkedin_url" in sent:
        update["linkedin_url"] = _clean_web_url(payload.linkedin_url, label="LinkedIn page")
    if "instagram_handle" in sent:
        raw = (payload.instagram_handle or "").strip()
        if raw:
            handle = _extract_ig_handle(raw)
            if not handle:
                raise HTTPException(
                    status_code=422,
                    detail="That doesn't look like an Instagram handle.",
                )
            update["instagram_handle"] = handle
        else:
            update["instagram_handle"] = None
    if "contact_phone" in sent:
        raw = (payload.contact_phone or "").strip()
        update["contact_phone"] = _normalize_phone(raw) if raw else None

    result = await db.brand_profiles.find_one_and_update(
        {"user_id": _brand_scope(user)},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    # Keep the display name on the user doc in sync with business_name.
    business_name = update.get("business_name")
    if business_name and business_name != user.get("name"):
        await db.users.update_one(
            {"_id": _brand_scope(user)}, {"$set": {"name": business_name}}
        )
    return await _brand_profile_response(result)


@brand_router.get("/verification")
async def get_brand_verification(user: dict = Depends(require_roles(*BRAND_ROLES))):
    """Where this brand stands, and what it has already sent us."""
    profile = await db.brand_profiles.find_one({"user_id": _brand_scope(user)})
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return (await _brand_profile_response(profile))["verification"]


@brand_router.post("/verification/documents")
async def upload_brand_document(
    doc_type: BrandDocumentType = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Upload one proof-of-business document.

    Several are allowed and expected: a brand may have a GST certificate and a
    shop licence, and after a rejection it needs to be able to send a clearer
    scan without losing the rest. Nothing is deleted on upload.
    """
    brand_oid = _brand_scope(user)
    profile = await db.brand_profiles.find_one({"user_id": brand_oid})
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    existing = await db.brand_documents.count_documents({"brand_id": brand_oid})
    if existing >= MAX_BRAND_DOCUMENTS:
        raise HTTPException(
            status_code=409,
            detail="That's a lot of documents. Remove one before adding another.",
        )

    stored = await _store_private_upload(file, prefix=f"brand-{brand_oid}")
    now = datetime.now(timezone.utc)
    result = await db.brand_documents.insert_one(
        {
            "brand_id": brand_oid,
            "doc_type": doc_type,
            "stored_name": stored["stored_name"],
            "original_name": stored["original_name"],
            "mime": stored["mime"],
            "size": stored["size"],
            "status": "submitted",
            "review_note": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    doc = await db.brand_documents.find_one({"_id": result.inserted_id})
    await audit(
        user,
        "brand.document_upload",
        "brand_profile",
        profile["_id"],
        after={"doc_type": doc_type, "size": stored["size"]},
        brand_id=brand_oid,
    )
    return _serialize_brand_document(doc)


@brand_router.delete("/verification/documents/{document_id}")
async def delete_brand_document(
    document_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Remove a document — to replace a bad scan, usually.

    Refused once verified: the paperwork we approved against is the record of
    why, and a brand shouldn't be able to empty it after the fact.
    """
    brand_oid = _brand_scope(user)
    profile = await db.brand_profiles.find_one({"user_id": brand_oid})
    if profile and profile.get("verified"):
        raise HTTPException(
            status_code=409,
            detail="Your brand is verified — get in touch if a document needs changing.",
        )
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    # Scoped to the owner in the same query, so another brand's id is a 404.
    doc = await db.brand_documents.find_one_and_delete(
        {"_id": oid, "brand_id": brand_oid}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _delete_private_upload(doc.get("stored_name"))
    return {"deleted": True, "id": document_id}


@brand_router.post("/verification/submit")
async def submit_brand_for_verification(user: dict = Depends(require_roles(*BRAND_ROLES))):
    """Ask us to check the business out.

    Refused until the details are complete and at least one document is on
    file, because a review with nothing to review is a queue item that wastes
    an admin's time and tells the brand nothing.
    """
    brand_oid = _brand_scope(user)
    profile = await db.brand_profiles.find_one({"user_id": brand_oid})
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    if profile.get("verified"):
        raise HTTPException(status_code=409, detail="Your brand is already verified.")

    missing = _brand_missing_fields(profile)
    if missing:
        raise HTTPException(
            status_code=409,
            detail="Still needed: " + ", ".join(row["label"] for row in missing) + ".",
        )
    if not await db.brand_documents.count_documents({"brand_id": brand_oid}):
        raise HTTPException(
            status_code=409,
            detail=(
                "Upload at least one document proving you represent this business — "
                "a GST certificate, business registration, FSSAI licence or shop "
                "establishment licence."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.brand_profiles.find_one_and_update(
        {"user_id": brand_oid},
        {
            "$set": {
                "verification_state": "pending_verification",
                "submitted_for_verification_at": now,
                # A resubmission starts clean; the old refusal is not a verdict
                # on the documents they have just sent.
                "verification_reason": None,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    await audit(
        user,
        "brand.submit_for_verification",
        "brand_profile",
        profile["_id"],
        after={"verification_state": "pending_verification"},
        brand_id=brand_oid,
    )
    await notify(
        brand_oid,
        "brand_verification_submitted",
        title="Verification submitted",
        body="Your business details are with the WeAre team. We usually come back within 48 hours.",
        link="/brand/profile",
    )
    return (await _brand_profile_response(updated))["verification"]


async def _applicant_counts_for(campaign_ids: list) -> dict:
    if not campaign_ids:
        return {}
    unique = list({cid for cid in campaign_ids})
    counts = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": {"$in": unique}}},
            {"$group": {"_id": "$campaign_id", "n": {"$sum": 1}}},
        ]
    ).to_list(length=len(unique))
    return {c["_id"]: c["n"] for c in counts}


@brand_router.get("/campaigns")
async def list_brand_campaigns(
    execution_owner: Optional[str] = None,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    await _expire_stale_campaigns()
    brand_oid = _brand_scope(user)
    query: dict = {"brand_id": brand_oid}
    if execution_owner:
        if execution_owner not in EXECUTION_OWNERS:
            raise HTTPException(
                status_code=422,
                detail=f"execution_owner must be one of: {', '.join(EXECUTION_OWNERS)}.",
            )
        query.update(_execution_owner_query(execution_owner))
    docs = (
        await db.campaigns.find(query)
        .sort("created_at", -1)
        .to_list(length=500)
    )
    ids = [d["_id"] for d in docs]
    count_map = await _applicant_counts_for(ids)
    filled_map = await _filled_counts_for(ids)
    awaiting_map = await _awaiting_brand_counts(ids)
    return [
        _serialize_brand_campaign(
            d,
            count_map.get(d["_id"], 0),
            filled_map.get(d["_id"], 0),
            awaiting_map.get(d["_id"], 0),
        )
        for d in docs
    ]


@brand_router.post("/campaigns")
async def create_brand_campaign(
    payload: PostCampaignPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    # The type/date combinations are enforced by the payload model itself.

    # The status used to come straight off the payload, which let a brand post
    # itself live. Going live is a decision somebody makes about a brief, not a
    # field on the request.
    if payload.status not in BRAND_SETTABLE_CAMPAIGN_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Campaigns go live after a WeAre review. Save it as a draft, or "
                "submit it for review — you can't publish directly."
            ),
        )
    if payload.status == CAMPAIGN_REVIEW_STATUS:
        await _verified_brand_or_403(user)

    # A brand posts paid work. Checked here rather than in the payload model so
    # the refusal explains itself — see _refuse_brand_barter.
    _refuse_brand_barter(None, {"compensation_type": payload.compensation_type})

    now = datetime.now(timezone.utc)
    doc = {
        "brand_id": _brand_scope(user),
        "title": payload.title.strip(),
        "brief": payload.brief.strip(),
        "deliverables": payload.deliverables.strip(),
        "budget_per_creator": float(payload.budget_per_creator),
        "category": payload.category,
        "area": payload.area.strip(),
        # Through the same canonicaliser the creator's city goes through, so a
        # filter can compare them at all.
        "city": _canonical_city(payload.city) or DEFAULT_CAMPAIGN_CITY,
        "creators_needed": int(payload.creators_needed),
        "campaign_type": payload.campaign_type,
        "compensation_type": payload.compensation_type,
        "execution_owner": payload.execution_owner,
        "visibility": payload.visibility,
        "event_date": payload.event_date,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "venue_address": (payload.venue_address or "").strip() or None,
        "venue_instructions": (payload.venue_instructions or "").strip() or None,
        "on_site_contact": (payload.on_site_contact or "").strip() or None,
        # The brand's own manager runs it unless an admin hands it to a WeAre
        # one (see assign_campaign_manager). Defaulting to nobody meant every
        # campaign spent its first days with no named contact on it, which is
        # the state a creator is most likely to have a question in.
        #
        # Unless the brand has handed execution to us: then stamping their
        # person as the campaign manager would route every application back to
        # the brand they just asked us to take it off, and put the campaign in
        # no WeAre queue at all. It waits for an admin to assign a real manager,
        # and says "WeAre" to a creator meanwhile — which is the true answer to
        # "who am I dealing with" either way.
        **(
            _NO_CAMPAIGN_MANAGER
            if payload.execution_owner == "weare"
            else await _brand_manager_contact(_brand_scope(user))
        ),
        "status": payload.status,
        "created_at": now,
        "updated_at": now,
    }
    if payload.status == CAMPAIGN_REVIEW_STATUS:
        doc["submitted_for_review_at"] = now
    result = await db.campaigns.insert_one(doc)
    doc["_id"] = result.inserted_id
    await audit(
        user,
        "campaign.create",
        "campaign",
        result.inserted_id,
        after={"title": doc["title"], "status": doc["status"]},
        **_campaign_audit_context(doc),
    )
    return _serialize_brand_campaign(doc, 0)


@brand_router.put("/campaigns/{campaign_id}")
async def update_brand_campaign(
    campaign_id: str,
    payload: UpdateCampaignPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Correct a brief. Allowed while a campaign is a draft or still live —
    once it's in progress the terms creators applied under are fixed."""
    doc = await _own_campaign_or_404(campaign_id, user)
    # A campaign under review is editable: it isn't in front of anyone yet, and
    # fixing what we asked about is the whole point of a rejection. So is a
    # paused one — fixing it is often why it was paused.
    if doc.get("status") not in (
        "draft", CAMPAIGN_REVIEW_STATUS, "upcoming", "open", "paused",
    ):
        raise HTTPException(
            status_code=409,
            detail="This campaign can no longer be edited — close it and post a new one.",
        )

    fields = payload.model_dump(exclude_unset=True)
    update: dict = {}
    for key, value in fields.items():
        if value is None and key not in ("start_date", "end_date"):
            continue
        if isinstance(value, str):
            value = value.strip()
        update[key] = value

    if not update:
        raise HTTPException(status_code=422, detail="Nothing to update")

    # The same rule as creation, on the path that would otherwise go round it:
    # this loop copies whatever the payload carried, compensation_type included.
    if "city" in update:
        update["city"] = _canonical_city(update["city"]) or DEFAULT_CAMPAIGN_CITY
    _refuse_brand_barter(doc, update)
    _refuse_late_execution_handover(doc, update)
    _refuse_dates_foreign_to_type(doc, update)
    # Handing execution over moves the manager with it, or the two fields
    # disagree and applications go to the wrong inbox.
    if "execution_owner" in update and update["execution_owner"] != _execution_owner(doc):
        update.update(await _execution_manager_fields(doc, update["execution_owner"]))
    start = update.get("start_date", doc.get("start_date"))
    end = update.get("end_date", doc.get("end_date"))
    if start and end and end < start:
        raise HTTPException(
            status_code=422, detail="End date cannot be before start date"
        )

    # Never let an edit shrink the brief below the creators already committed.
    if "creators_needed" in update:
        filled = (await _filled_counts_for([doc["_id"]])).get(doc["_id"], 0)
        if int(update["creators_needed"]) < filled:
            raise HTTPException(
                status_code=409,
                detail=f"{filled} creator(s) are already confirmed on this campaign.",
            )

    update["updated_at"] = datetime.now(timezone.utc)
    updated = await db.campaigns.find_one_and_update(
        {"_id": doc["_id"]}, {"$set": update}, return_document=True
    )
    await audit(
        user,
        "campaign.update",
        "campaign",
        doc["_id"],
        before={k: doc.get(k) for k in update if k != "updated_at"},
        after={k: v for k, v in update.items() if k != "updated_at"},
        **_campaign_audit_context(doc),
    )
    await _sync_campaign_fill(doc["_id"])

    counts = await _applicant_counts_for([doc["_id"]])
    filled_map = await _filled_counts_for([doc["_id"]])
    awaiting = await _awaiting_brand_counts([doc["_id"]])
    return _serialize_brand_campaign(
        updated,
        counts.get(doc["_id"], 0),
        filled_map.get(doc["_id"], 0),
        awaiting.get(doc["_id"], 0),
    )


@brand_router.post("/campaigns/{campaign_id}/publish")
async def publish_brand_campaign(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Submit a draft for review.

    This used to take the draft straight live. It now hands it to us instead —
    the campaign goes in front of creators when an admin approves it, not when
    the brand clicks. The route keeps its name so existing clients keep working;
    what changed is where the campaign lands.
    """
    doc = await _own_campaign_or_404(campaign_id, user)
    if doc.get("status") != "draft":
        raise HTTPException(
            status_code=409,
            detail=(
                "This campaign is already with us for review."
                if doc.get("status") == CAMPAIGN_REVIEW_STATUS
                else "This campaign is already published."
            ),
        )

    # An unverified brand can draft all it likes; it cannot put a brief in the
    # queue that ends with creators being asked to show up somewhere.
    await _verified_brand_or_403(user)

    missing = [
        field
        for field in ("title", "brief", "deliverables", "category", "area")
        if not doc.get(field)
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Finish the brief before submitting — missing: {', '.join(missing)}.",
        )

    now = datetime.now(timezone.utc)
    updated = await db.campaigns.update_one(
        {"_id": doc["_id"], "status": "draft"},
        {
            "$set": {
                "status": CAMPAIGN_REVIEW_STATUS,
                "submitted_for_review_at": now,
                "updated_at": now,
            },
            # A resubmission starts clean rather than carrying the last refusal.
            "$unset": {"review_reason": "", "reviewed_at": ""},
        },
    )
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "campaign.submit_for_review",
        "campaign",
        doc["_id"],
        before={"status": "draft"},
        after={"status": CAMPAIGN_REVIEW_STATUS},
        **_campaign_audit_context(doc),
    )
    return {
        "id": campaign_id,
        "status": CAMPAIGN_REVIEW_STATUS,
        "message": "Submitted for review. We'll publish it once we've read it.",
    }


@brand_router.post("/campaigns/{campaign_id}/close")
async def close_brand_campaign(
    campaign_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Stop a campaign taking new applications. Collaborations already under way
    are untouched — closing a brief is not cancelling the work."""
    doc = await _own_campaign_or_404(campaign_id, user)
    if doc.get("status") in ("closed", "completed"):
        raise HTTPException(status_code=409, detail="This campaign is already closed.")

    now = datetime.now(timezone.utc)
    await db.campaigns.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "closed", "closed_reason": payload.reason, "updated_at": now}},
    )
    await audit(
        user,
        "campaign.close",
        "campaign",
        doc["_id"],
        before={"status": doc.get("status")},
        after={"status": "closed"},
        note=payload.reason,
        **_campaign_audit_context(doc),
    )

    # Anyone still waiting on a decision is owed one.
    stale = await db.collaborations.find(
        {"campaign_id": doc["_id"], "state": {"$in": ["applied", "verified"]}}
    ).to_list(length=500)
    for collab in stale:
        await db.collaborations.update_one(
            {"_id": collab["_id"]},
            {
                "$set": {
                    "state": "declined",
                    "active": False,
                    "exit_reason": "The brand closed this campaign.",
                    "updated_at": now,
                }
            },
        )
        await notify(
            collab["creator_id"],
            "application_declined",
            title="Campaign closed",
            body=f"\"{doc.get('title')}\" was closed before a decision was made.",
        )

    return {"id": campaign_id, "status": "closed", "applications_closed": len(stale)}


@brand_router.delete("/campaigns/{campaign_id}")
async def delete_brand_campaign(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """Delete a draft nobody has seen. Anything published is closed, not erased —
    creators applied to it and that history has to survive."""
    doc = await _own_campaign_or_404(campaign_id, user)
    if doc.get("status") != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only drafts can be deleted. Close a published campaign instead.",
        )
    if await db.collaborations.count_documents({"campaign_id": doc["_id"]}):
        raise HTTPException(
            status_code=409, detail="This campaign already has applicants."
        )
    await db.campaigns.delete_one({"_id": doc["_id"]})
    await audit(
        user,
        "campaign.delete",
        "campaign",
        doc["_id"],
        before={"title": doc.get("title")},
        **_campaign_audit_context(doc),
    )
    return {"success": True, "id": campaign_id}


# --- Applicant board (brand-facing) ----------------------------------------

# What the brand sees, keyed by where the collaboration has got to.
_BRAND_VISIBLE_STATES = [s for s in COLLAB_STATE_ORDER] + ["declined", "cancelled"]


# Everything a brand may know about a creator, and nothing else. Written as an
# allow-list because the alternative — remembering to strip fields — is how a
# phone number ends up in a payload the day somebody adds a `$lookup`.
#
# The line is drawn at "what you need to choose and work with someone" versus
# "how to reach them off-platform". A brand picks a creator on their work, their
# audience and their price; it reaches them through us. That holds after
# acceptance too: this used to reveal an email and a phone number once a
# collaboration was under way, which meant every accepted application handed
# over a contact whether or not the creator would have given it.
_BRAND_VISIBLE_CREATOR_FIELDS = (
    "id",
    "user_id",
    "name",
    "profile_image_url",
    "instagram_handle",
    "instagram_profile_url",
    "youtube_url",
    "youtube_handle",
    "facebook_url",
    # Their own description of themselves. This is what they wrote *for* a
    # brand to read, so it is the one long-form field that belongs here.
    "about",
    "follower_count",
    "follower_count_source",
    "follower_count_verified",
    "follower_count_verified_at",
    "follower_count_self_reported",
    "verified_stats_available",
    "engagement_rate",
    "media_count",
    "city",
    "niches",
    "genres",
    "platforms",
    "base_rate",
    "verification_status",
)

# The fields that must never appear in a brand-scoped response, under any key
# nesting. A unit test walks every brand response shape looking for these; the
# tuple is here rather than in the test so the rule and the code ship together.
BRAND_FORBIDDEN_CREATOR_FIELDS = (
    "phone",
    "whatsapp",
    "whatsapp_number",
    "email",
    "contact_phone",
    "contact_email",
    "full_address",
    "address",
    # A pin on somebody's front door is the address again, to five decimal
    # places. The allow-list already keeps these out; naming them here is what
    # makes the leak test look for them.
    "location_lat",
    "location_lng",
    "location_place_id",
    "payout_upi",
    "payout_account_name",
    "pan",
    "gstin",
)


def _brand_visible_creator(profile: Optional[dict], account: Optional[dict] = None) -> dict:
    """A creator as a brand is allowed to see them.

    One function behind every brand surface — the directory, the applicant
    board, the suggestions panel — so "what a brand can see about a creator" is
    a single answer that can be read, tested and changed in one place.
    """
    profile = profile or {}
    account = account or {}
    row = {
        "id": str(profile["_id"]) if profile.get("_id") else None,
        "user_id": (
            str(profile["user_id"])
            if profile.get("user_id")
            else (str(account["_id"]) if account.get("_id") else None)
        ),
        "name": profile.get("name") or account.get("name"),
        "profile_image_url": profile.get("profile_image_url"),
        "instagram_handle": profile.get("instagram_handle"),
        "instagram_profile_url": profile.get("instagram_profile_url"),
        "youtube_url": profile.get("youtube_url"),
        "facebook_url": profile.get("facebook_url"),
        # What they wrote about themselves, for a brand to read. The only
        # long-form field on this surface, and the only one they chose the
        # words of.
        "about": profile.get("about"),
        "follower_count": profile.get("follower_count"),
        **_follower_provenance(profile),
        "engagement_rate": profile.get("engagement_rate"),
        "city": profile.get("city"),
        "niches": profile.get("niches") or [],
        "genres": profile.get("genres") or [],
        "platforms": profile.get("platforms") or [],
        "base_rate": profile.get("base_rate"),
        "verification_status": profile.get("verification_status"),
    }
    # Belt and braces: the allow-list is the contract, so anything that drifts
    # into the dict above without being declared there does not go out.
    return {k: v for k, v in row.items() if k in _BRAND_VISIBLE_CREATOR_FIELDS}


def _serialize_applicant(
    collab: dict, creator_user: dict, profile: dict, payment: Optional[dict]
) -> dict:
    """An applicant as the brand sees them.

    The creator block comes from `_brand_visible_creator` and carries no way to
    contact anyone. Everything about the *collaboration* — the pitch, the rates,
    the state, the content — is the brand's own business and stays.
    """
    state = collab.get("state", "applied")
    return {
        "id": str(collab["_id"]),
        "state": state,
        "pitch": collab.get("pitch"),
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "agreed_at": _iso(collab.get("agreed_at")),
        "content_urls": collab.get("content_urls")
        or ([collab["content_url"]] if collab.get("content_url") else []),
        "scheduled_at": _iso(collab.get("scheduled_at")),
        "location_note": collab.get("location_note"),
        "exit_reason": collab.get("exit_reason"),
        "revision_note": collab.get("revision_note"),
        "applied_at": _iso(collab.get("created_at")),
        "updated_at": _iso(collab.get("updated_at")),
        # Actions the brand can take on this row, decided server-side so the UI
        # never offers a button the API will refuse.
        "can_accept": state == "verified",
        "can_decline": state in ("applied", "verified", "accepted"),
        "can_review_content": state == "content_submitted",
        "creator": _brand_visible_creator(profile, creator_user),
        "payment": (
            {
                "state": payment.get("state"),
                "brand_invoice_amount": payment.get("brand_invoice_amount"),
                "brand_invoice_state": payment.get("brand_invoice_state"),
            }
            if payment
            else None
        ),
    }


@brand_router.get("/campaigns/{campaign_id}/applicants")
async def list_campaign_applicants(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Who applied, what they pitched, what they want to be paid.

    This is the decision the brand came here to make; before this endpoint the
    brand side of the product could only show a count.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    collabs = (
        await db.collaborations.find({"campaign_id": campaign["_id"]})
        .sort("created_at", -1)
        .to_list(length=500)
    )

    creator_ids = list({c["creator_id"] for c in collabs})
    users_by_id: dict = {}
    profiles_by_uid: dict = {}
    payments_by_collab: dict = {}
    if creator_ids:
        creator_users = await db.users.find(
            {"_id": {"$in": creator_ids}}
        ).to_list(length=len(creator_ids))
        users_by_id = {u["_id"]: u for u in creator_users}
        profiles = await db.creator_profiles.find(
            {"user_id": {"$in": creator_ids}}
        ).to_list(length=len(creator_ids))
        profiles_by_uid = {p["user_id"]: p for p in profiles}
        payments = await db.payments.find(
            {"collaboration_id": {"$in": [c["_id"] for c in collabs]}}
        ).to_list(length=len(collabs))
        payments_by_collab = {p["collaboration_id"]: p for p in payments}

    rows = [
        _serialize_applicant(
            c,
            users_by_id.get(c["creator_id"]),
            profiles_by_uid.get(c["creator_id"]),
            payments_by_collab.get(c["_id"]),
        )
        for c in collabs
    ]

    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([campaign["_id"]])).get(campaign["_id"], 0)
    return {
        "campaign": {
            "id": str(campaign["_id"]),
            "title": campaign.get("title"),
            "status": campaign.get("status"),
            "budget_per_creator": campaign.get("budget_per_creator"),
            "compensation_type": _compensation_type(campaign),
            # Says whether this board is the brand's own work or a copy of
            # what our team is handling for them.
            "execution_owner": _execution_owner(campaign),
            "creators_needed": needed,
            "filled_slots": filled,
            "spots_left": max(0, needed - filled),
            "area": campaign.get("area"),
            "category": campaign.get("category"),
        },
        "applicants": rows,
        "totals": {
            "all": len(rows),
            "awaiting_you": sum(1 for r in rows if r["state"] == "verified"),
            "with_weare": sum(1 for r in rows if r["state"] == "applied"),
            "in_progress": sum(
                1
                for r in rows
                if r["state"] in ("accepted", "commercial_agreed", "slot_booked", "attended")
            ),
            "needs_content_review": sum(
                1 for r in rows if r["state"] == "content_submitted"
            ),
            "closed": sum(
                1 for r in rows if r["state"] in ("closed", "declined", "cancelled")
            ),
        },
    }


async def _brand_collab_or_404(collab_id: str, user: dict) -> tuple[dict, dict]:
    """Load a collaboration together with its campaign, asserting brand ownership."""
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Application not found")
    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Application not found")
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.get("role") != "admin" and campaign.get("brand_id") != _brand_scope(user):
        raise HTTPException(status_code=404, detail="Application not found")
    return collab, campaign


# --- Imagery -----------------------------------------------------------------
#
# Both of these go through `_store_upload`, the same function the creator's
# profile photo uses: the type comes from the magic bytes and never from the
# client's filename, the stored name is ours and random, and the size ceiling is
# enforced while streaming rather than after the whole file is in memory.
#
# They land in UPLOAD_DIR, which is mounted as static files — correct here, and
# the opposite of the brand's verification documents, which carry a registered
# address and go to PRIVATE_UPLOAD_DIR. A cover image and a logo are meant to be
# seen by strangers; that is the point of them.


async def _replace_image(
    collection, query: dict, field: str, file, *, prefix: str, missing: str
) -> str:
    """Store a new image, point the record at it, then delete the old file.

    That order matters: deleting first would leave a record pointing at nothing
    if the write failed, and a broken image is worse than an out-of-date one.
    """
    existing = await collection.find_one(query)
    if not existing:
        raise HTTPException(status_code=404, detail=missing)

    public_url, _path = await _store_upload(file, prefix=prefix)
    previous = existing.get(field)
    await collection.update_one(
        query, {"$set": {field: public_url, "updated_at": datetime.now(timezone.utc)}}
    )
    if previous and previous != public_url:
        _delete_upload(previous)
    return public_url


@brand_router.post("/campaigns/{campaign_id}/cover")
async def upload_campaign_cover(
    campaign_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """The picture on the brief.

    Deliberately its own route rather than a field on the edit payload: the
    value is a path we issued, so it is set by storing a file, never by
    accepting a URL from the client.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    url = await _replace_image(
        db.campaigns,
        {"_id": campaign["_id"]},
        "cover_image_url",
        file,
        prefix=f"campaign-{campaign_id}",
        missing="Campaign not found",
    )
    await audit(
        user, "campaign.cover_upload", "campaign", campaign["_id"],
        **_campaign_audit_context(campaign),
    )
    return {"cover_image_url": url}


@brand_router.delete("/campaigns/{campaign_id}/cover")
async def delete_campaign_cover(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    campaign = await _own_campaign_or_404(campaign_id, user)
    await db.campaigns.update_one(
        {"_id": campaign["_id"]},
        {"$set": {"cover_image_url": None, "updated_at": datetime.now(timezone.utc)}},
    )
    _delete_upload(campaign.get("cover_image_url"))
    await audit(
        user, "campaign.cover_removed", "campaign", campaign["_id"],
        **_campaign_audit_context(campaign),
    )
    return {"cover_image_url": None}


@brand_router.post("/profile/logo")
async def upload_brand_logo(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*BRAND_ROLES)),
):
    """The brand's own mark, shown wherever the brand is named."""
    url = await _replace_image(
        db.brand_profiles,
        {"user_id": _brand_scope(user)},
        "logo_url",
        file,
        prefix=f"brand-{_brand_scope(user)}",
        missing="Brand profile not found",
    )
    return {"logo_url": url}


@brand_router.delete("/profile/logo")
async def delete_brand_logo(user: dict = Depends(require_roles(*BRAND_ROLES))):
    scope = _brand_scope(user)
    profile = await db.brand_profiles.find_one({"user_id": scope})
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    await db.brand_profiles.update_one(
        {"user_id": scope},
        {"$set": {"logo_url": None, "updated_at": datetime.now(timezone.utc)}},
    )
    _delete_upload(profile.get("logo_url"))
    return {"logo_url": None}


@brand_router.post("/collaborations/{collab_id}/accept")
async def brand_accept_applicant(
    collab_id: str,
    payload: BrandAcceptPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """The brand picks a creator. Records who agreed to what, and when."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    if collab.get("state") != "verified":
        raise HTTPException(
            status_code=409,
            detail="This applicant isn't waiting on your decision right now.",
        )

    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([campaign["_id"]])).get(campaign["_id"], 0)
    if filled >= needed:
        raise HTTPException(
            status_code=409,
            detail="This campaign already has all the creators it needs.",
        )

    amount = (
        float(payload.agreed_amount)
        if payload.agreed_amount is not None
        else collab.get("quoted_rate")
    )
    if amount is None:
        raise HTTPException(
            status_code=422, detail="Set the fee you're accepting at."
        )

    now = datetime.now(timezone.utc)
    result = await db.collaborations.update_one(
        {"_id": collab["_id"], "state": "verified"},  # precondition, not a blind write
        {
            "$set": {
                "state": "accepted",
                "agreed_amount": round(float(amount), 2),
                "agreed_at": now,
                "agreed_by": ObjectId(user["_id"]),
                "updated_at": now,
            }
        },
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=409, detail="This applicant just moved — reload and try again."
        )

    await audit(
        user,
        "collaboration.accept",
        "collaboration",
        collab["_id"],
        before={"state": "verified"},
        after={"state": "accepted", "agreed_amount": amount},
        note=payload.note,
        **_campaign_audit_context(campaign),
    )
    await _sync_campaign_fill(campaign["_id"])
    await notify(
        collab["creator_id"],
        "application_accepted",
        title="You're in",
        body=(
            f"{campaign.get('title')} — accepted at ₹{amount:,.0f}. "
            "We'll confirm your slot next."
        ),
        link="/dashboard",
    )
    return {"id": collab_id, "state": "accepted", "agreed_amount": amount}


@brand_router.post("/collaborations/{collab_id}/decline")
async def brand_decline_applicant(
    collab_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Say no, out loud. Every applicant gets an answer instead of silence."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    if collab.get("state") not in ("applied", "verified", "accepted"):
        raise HTTPException(
            status_code=409,
            detail="This collaboration has gone too far to decline — cancel it instead.",
        )

    now = datetime.now(timezone.utc)
    result = await db.collaborations.update_one(
        {"_id": collab["_id"], "state": collab["state"]},
        {
            "$set": {
                "state": "declined",
                "active": False,
                "exit_reason": payload.reason,
                "updated_at": now,
            }
        },
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=409, detail="This applicant just moved — reload and try again."
        )

    await audit(
        user,
        "collaboration.decline",
        "collaboration",
        collab["_id"],
        before={"state": collab["state"]},
        after={"state": "declined"},
        note=payload.reason,
        **_campaign_audit_context(campaign),
    )
    await _sync_campaign_fill(campaign["_id"])
    await notify(
        collab["creator_id"],
        "application_declined",
        title="Not this time",
        body=(
            f"{campaign.get('title')} — the brand went another way."
            + (f" {payload.reason}" if payload.reason else "")
        ),
        link="/campaigns",
    )
    return {"id": collab_id, "state": "declined"}


@brand_router.post("/collaborations/{collab_id}/approve_content")
async def brand_approve_content(
    collab_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Sign off the work. This is the step the landing page promises and the
    thing that should release payment."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    if collab.get("state") != "content_submitted":
        raise HTTPException(
            status_code=409, detail="There's no content waiting for review here."
        )

    now = datetime.now(timezone.utc)
    result = await db.collaborations.update_one(
        {"_id": collab["_id"], "state": "content_submitted"},
        {"$set": {"state": "content_approved", "revision_note": None, "updated_at": now}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.approve_content",
        "collaboration",
        collab["_id"],
        before={"state": "content_submitted"},
        after={"state": "content_approved"},
        **_campaign_audit_context(campaign),
    )
    await notify(
        collab["creator_id"],
        "content_approved",
        title="Content approved",
        body=f"{campaign.get('title')} — your work was approved. Payment is next.",
        link="/dashboard",
    )
    return {"id": collab_id, "state": "content_approved"}


@brand_router.post("/collaborations/{collab_id}/request_changes")
async def brand_request_changes(
    collab_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Send the work back with a note. The creator can resubmit without an admin
    unpicking the state by hand."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    if collab.get("state") != "content_submitted":
        raise HTTPException(
            status_code=409, detail="There's no content waiting for review here."
        )
    if not (payload.reason or "").strip():
        raise HTTPException(
            status_code=422, detail="Tell the creator what needs to change."
        )

    now = datetime.now(timezone.utc)
    result = await db.collaborations.update_one(
        {"_id": collab["_id"], "state": "content_submitted"},
        {
            "$set": {
                "state": "attended",  # back to "shoot done, content owed"
                "revision_note": payload.reason.strip(),
                "updated_at": now,
            }
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.request_changes",
        "collaboration",
        collab["_id"],
        before={"state": "content_submitted"},
        after={"state": "attended"},
        note=payload.reason,
        **_campaign_audit_context(campaign),
    )
    await notify(
        collab["creator_id"],
        "content_changes_requested",
        title="Changes requested",
        body=f"{campaign.get('title')} — {payload.reason.strip()}",
        link="/dashboard",
    )
    return {"id": collab_id, "state": "attended", "revision_note": payload.reason.strip()}


@brand_router.get("/dashboard")
async def get_brand_dashboard(user: dict = Depends(require_roles(*BRAND_ROLES))):
    await _expire_stale_campaigns()
    brand_oid = _brand_scope(user)
    profile = await db.brand_profiles.find_one({"user_id": brand_oid})
    campaigns = (
        await db.campaigns.find({"brand_id": brand_oid})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    ids = [c["_id"] for c in campaigns]
    count_map = await _applicant_counts_for(ids)
    filled_map = await _filled_counts_for(ids)
    awaiting_map = await _awaiting_brand_counts(ids)
    campaign_rows = [
        _serialize_brand_campaign(
            c,
            count_map.get(c["_id"], 0),
            filled_map.get(c["_id"], 0),
            awaiting_map.get(c["_id"], 0),
        )
        for c in campaigns
    ]

    total_applications = sum(count_map.values())
    live = sum(1 for c in campaign_rows if c["status"] in ("open", "upcoming"))
    drafts = sum(1 for c in campaign_rows if c["status"] == "draft")

    # Work sitting with this brand right now, across every campaign.
    content_to_review = await db.collaborations.count_documents(
        {"campaign_id": {"$in": ids}, "state": "content_submitted"}
    ) if ids else 0

    return {
        "profile": _serialize_brand_profile(profile),
        "campaigns": campaign_rows,
        "totals": {
            "total_campaigns": len(campaign_rows),
            "live_campaigns": live,
            "draft_campaigns": drafts,
            "total_applications": total_applications,
            "awaiting_decision": sum(awaiting_map.values()),
            "content_to_review": content_to_review,
        },
    }


# --- Creator directory (brand-facing) --------------------------------------

def _serialize_directory_creator(profile: dict) -> dict:
    """Public projection of a creator profile for the brand-side directory.

    Now the same projection as everywhere else a brand sees a creator. It used
    to be its own hand-written dict that happened to omit the contact fields —
    correct, but by coincidence rather than by construction, and the applicant
    board sitting next to it made the opposite choice.
    """
    return _brand_visible_creator(profile)


@brand_router.get("/creators")
async def brand_directory(
    city: Optional[str] = None,
    niche: Optional[str] = None,
    min_followers: Optional[int] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,  # "newest" | "followers_desc" | "rate_asc"
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Browse verified creators with optional city/niche/keyword filters."""
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    query: dict = {"verification_status": "verified"}
    if city:
        query["city"] = city
    if niche:
        # Case-insensitive membership match in the niches array.
        query["niches"] = {"$regex": f"^{re.escape(niche)}$", "$options": "i"}
    if min_followers is not None:
        query["follower_count"] = {"$gte": min_followers}
    if q:
        # Cap length + escape user input before feeding it to a case-insensitive regex.
        term = re.escape(q.strip()[:120])
        query["$or"] = [
            {"name": {"$regex": term, "$options": "i"}},
            {"instagram_handle": {"$regex": term, "$options": "i"}},
            {"niches": {"$regex": term, "$options": "i"}},
        ]

    sort_spec: list = [("created_at", -1)]
    if sort == "followers_desc":
        sort_spec = [("follower_count", -1), ("created_at", -1)]
    elif sort == "rate_asc":
        sort_spec = [("base_rate", 1), ("created_at", -1)]

    docs = await db.creator_profiles.find(query).sort(sort_spec).to_list(length=300)
    return [_serialize_directory_creator(d) for d in docs]


@brand_router.get("/creators/filters")
async def brand_directory_filters(
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Distinct filter options across verified creators."""
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    base = {"verification_status": "verified"}
    cities_raw = await db.creator_profiles.distinct("city", base)
    niches_flat: list[str] = []
    async for doc in db.creator_profiles.find(base, {"niches": 1}):
        for n in doc.get("niches") or []:
            niches_flat.append(n)
    # Deduplicate case-insensitively, keep original casing of first occurrence.
    seen: set[str] = set()
    niches: list[str] = []
    for n in niches_flat:
        key = n.lower().strip()
        if key and key not in seen:
            seen.add(key)
            niches.append(n)
    return {
        "cities": sorted([c for c in cities_raw if c]),
        "niches": sorted(niches, key=str.lower),
        "total": await db.creator_profiles.count_documents(base),
    }


# --- Suggesting creators for a brief ---------------------------------------
#
# Waiting for applicants means a brief is only ever seen by creators who happen
# to be browsing. This ranks the verified roster against a campaign so a brand
# can go and ask.
#
# The whole score is `score_creator_for_campaign` below: one pure function, no
# hidden state, and every component it adds up is reported alongside the total.
# A brand that cannot see why somebody was suggested has been handed an oracle,
# and an oracle is not something you can argue with or improve.

# What each signal is worth, out of 100. These are the tuning knobs — change
# them here and nothing else moves. They are deliberately not in the database:
# a ranking that silently differs between environments is one nobody can debug.
CREATOR_MATCH_WEIGHTS = {
    # What they cover and what they make, against the brief. The strongest
    # signal by far — a food creator on a food brief is most of the decision.
    "niche": 30,
    "genre": 15,
    # Being in the city. Not decisive on its own (a creator travels) but a
    # campaign with a venue is much easier to fill locally.
    "city": 20,
    # Audience size against what the campaign pays. Both directions are a
    # mismatch: a 500k creator will not turn up for ₹2,000, and a 900-follower
    # account is not what a ₹50,000 brief is buying.
    "reach_fit": 15,
    "engagement": 10,
    # Whether they have actually delivered here before.
    "delivery": 10,
}

# Budget per creator → the follower band that budget is realistically buying.
# Rupees, ascending; the last band has no upper bound.
CREATOR_REACH_TIERS = (
    (3_000, 1_000, 10_000, "nano"),
    (10_000, 10_000, 50_000, "micro"),
    (30_000, 50_000, 200_000, "mid"),
    (float("inf"), 200_000, None, "macro"),
)

# Signals with nothing behind them score here rather than at zero. A creator
# whose engagement we have never measured is an unknown, not a bad bet, and
# scoring unknowns at zero would rank every creator without a connected
# Instagram account below every creator with a poor one.
_UNKNOWN_SIGNAL = 0.5


def _reach_tier(budget: Optional[float]) -> tuple:
    """The follower band a budget is buying: (low, high_or_None, label)."""
    amount = float(budget or 0)
    for ceiling, low, high, label in CREATOR_REACH_TIERS:
        if amount < ceiling:
            return low, high, label
    return CREATOR_REACH_TIERS[-1][1], CREATOR_REACH_TIERS[-1][2], CREATOR_REACH_TIERS[-1][3]


def _reach_fit(followers: Optional[int], budget: Optional[float]) -> Optional[float]:
    """How well an audience size fits the budget, 0..1, or None if unknown.

    Inside the band is a full mark. Outside it decays by how far out they are
    in proportion, not in absolute followers — 5k against a 10k floor is the
    same size of miss as 100k against a 200k one, and treating it in absolutes
    would make every band above micro impossible to miss.
    """
    if not isinstance(followers, int) or followers <= 0:
        return None
    low, high, _ = _reach_tier(budget)
    if followers < low:
        return max(0.0, followers / low)
    if high is not None and followers > high:
        return max(0.0, high / followers)
    return 1.0


def _overlap(values, wanted: set) -> list:
    """The creator's own spelling of each term that matched, order preserved.

    Their casing, not ours: the reason line reads "Matches Brunch" the way they
    wrote it, rather than the lower-cased key we compared on.
    """
    seen, out = set(), []
    for raw in values or []:
        key = str(raw).lower().strip()
        if key and key in wanted and key not in seen:
            seen.add(key)
            out.append(str(raw).strip())
    return out


_CAMPAIGN_TERM_RE = re.compile(r"[a-z][a-z&'-]{2,}")

# Words that appear in every brief and match nothing useful. Without this,
# "creators" in a brief would "match" a creator whose niche is creators.
_CAMPAIGN_STOPWORDS = frozenset(
    """the and for with our your you are who this that from will can new
    looking creators creator content post posts reel reels story stories brand
    brands campaign about into over their they them need needs want wants
    please must should would could have has had been being""".split()
)


# Campaigns pick a category from a fixed enum; creators type their own niches
# and genres. Nobody writes "fnb" about themselves — they write "food" or
# "restaurants" — so without this a food creator scores zero on a food brief.
# Bridging the two vocabularies here keeps both sides free to use their own
# words, and is the sort of thing that has to be visible to be arguable.
CAMPAIGN_CATEGORY_SYNONYMS = {
    "fnb": ("food", "restaurant", "restaurants", "cafe", "cafes", "dining",
            "drinks", "beverage", "foodie"),
    "hospitality": ("hotel", "hotels", "travel", "stays", "resort", "tourism"),
    "retail": ("shopping", "fashion", "style", "beauty", "products"),
    "lifestyle": ("lifestyle", "wellness", "fitness", "culture", "living"),
}


def _campaign_terms(campaign: dict) -> set:
    """The vocabulary of a brief: its category, its area, and the words in it.

    Free text is included because a brief that says "brunch" and "dessert"
    describes what it wants far better than its single category enum does. It
    is only ever used to *find* an overlap with something the creator typed
    about themselves, so a stray word costs a weak match, never a wrong one.
    """
    terms = set()
    for field in ("category", "area"):
        value = (campaign.get(field) or "").lower().strip()
        if value:
            terms.add(value)
    terms.update(CAMPAIGN_CATEGORY_SYNONYMS.get(
        (campaign.get("category") or "").lower().strip(), ()
    ))
    for field in ("title", "brief", "deliverables"):
        for word in _CAMPAIGN_TERM_RE.findall((campaign.get(field) or "").lower()):
            if word not in _CAMPAIGN_STOPWORDS:
                terms.add(word)
    return terms


def _human_followers(n: Optional[int]) -> Optional[str]:
    if not isinstance(n, int) or n <= 0:
        return None
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def _and_list(items: list) -> str:
    """"a", "a and b", "a, b and c" — the reason line is read, not parsed."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def score_creator_for_campaign(
    profile: dict,
    campaign: dict,
    *,
    delivery: Optional[dict] = None,
    weights: Optional[dict] = None,
) -> dict:
    """Rank one creator against one brief, and say why.

    Pure: everything it needs is in its arguments, so it can be read, tested
    and tuned without a database. Returns the score out of 100, a one-line
    reason a brand can read on a card, and the component breakdown behind it.

    `delivery` is this creator's history on WeAre, as
    `{"completed": int, "on_time": int}` — None when they have none, which
    scores as unknown rather than as bad. A creator's first campaign must not
    be unrankable, or the suggestions only ever surface people who are already
    working.
    """
    w = {**CREATOR_MATCH_WEIGHTS, **(weights or {})}
    terms = _campaign_terms(campaign)

    niches = _overlap(profile.get("niches"), terms)
    genres = _overlap(profile.get("genres"), terms)

    campaign_city = (campaign.get("area") or "").lower().strip()
    creator_places = {
        (profile.get("city") or "").lower().strip(),
        (profile.get("address") or "").lower().strip(),
    }
    city_match = bool(campaign_city) and campaign_city in creator_places

    followers = profile.get("follower_count")
    fit = _reach_fit(followers if isinstance(followers, int) else None,
                     campaign.get("budget_per_creator"))

    rate = profile.get("engagement_rate")
    # 3% is a good engagement rate on Instagram; anything at or above it takes
    # the full mark rather than letting one outlier creator define the scale.
    engagement = None if not isinstance(rate, (int, float)) else min(1.0, float(rate) / 3.0)

    completed = int((delivery or {}).get("completed") or 0)
    on_time = int((delivery or {}).get("on_time") or 0)
    reliability = (on_time / completed) if completed else None

    components = {
        "niche": round(w["niche"] * (1.0 if niches else 0.0), 1),
        "genre": round(w["genre"] * (1.0 if genres else 0.0), 1),
        "city": round(w["city"] * (1.0 if city_match else 0.0), 1),
        "reach_fit": round(w["reach_fit"] * (_UNKNOWN_SIGNAL if fit is None else fit), 1),
        "engagement": round(
            w["engagement"] * (_UNKNOWN_SIGNAL if engagement is None else engagement), 1
        ),
        "delivery": round(
            w["delivery"] * (_UNKNOWN_SIGNAL if reliability is None else reliability), 1
        ),
    }

    # The reason names only what actually scored, in the order a person would
    # say it. A card that says "Matches fashion and beauty, based in Mumbai,
    # 24k followers" is a sentence; a list of six components is a debug dump.
    bits = []
    matched = niches + [g for g in genres if g.lower() not in {n.lower() for n in niches}]
    if matched:
        bits.append("Matches " + _and_list(matched[:3]))
    if city_match:
        bits.append(f"based in {campaign.get('area')}")
    reach = _human_followers(followers if isinstance(followers, int) else None)
    if reach:
        bits.append(f"{reach} followers")
    if isinstance(rate, (int, float)) and rate >= 3.0:
        bits.append(f"{rate:g}% engagement")
    if completed:
        bits.append(
            f"{completed} campaign{'s' if completed != 1 else ''} delivered here"
        )
    reason = ", ".join(bits) if bits else "Verified creator on WeAre"

    return {
        "score": round(sum(components.values()), 1),
        "reason": reason[0].upper() + reason[1:],
        "components": components,
        "matched_niches": niches,
        "matched_genres": genres,
        "city_match": city_match,
        # Named so a brand can tell "we have not measured this" apart from
        # "this is poor", which is the whole reason unknowns score at the
        # midpoint instead of at zero.
        "unknown_signals": [
            name
            for name, value in (
                ("reach_fit", fit),
                ("engagement", engagement),
                ("delivery", reliability),
            )
            if value is None
        ],
    }


async def _delivery_history(creator_ids: list) -> dict:
    """How each creator has actually performed here, in one round trip.

    "On time" is deliberately coarse: a collaboration that reached
    `content_approved` or beyond without a no-show being raised was delivered.
    We do not track a content deadline, so anything finer would be invented
    precision dressed up as a statistic.
    """
    if not creator_ids:
        return {}
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"creator_id": {"$in": list(creator_ids)}}},
            {
                "$group": {
                    "_id": "$creator_id",
                    "completed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$state", ["content_approved", "in_payment", "closed"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "on_time": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$in": ["$state", ["content_approved", "in_payment", "closed"]]},
                                        {"$ne": ["$no_show_reported", True]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]
    ).to_list(length=len(creator_ids))
    return {r["_id"]: {"completed": r["completed"], "on_time": r["on_time"]} for r in rows}


async def _suggest_creators_for_campaign(
    campaign: dict,
    *,
    niche: Optional[str] = None,
    city: Optional[str] = None,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """The ranked shortlist for a brief, with the filters applied first.

    Ranked in Python rather than in the aggregation for the same reason the
    creator-side suggestions are: the score has to be explainable per creator,
    and a pipeline that sorts by a computed number cannot say what went into
    it. The candidate set is bounded before it gets here by the filters and by
    `verification_status`, so this is a sort over a roster, not over a firehose.
    """
    query: dict = {"verification_status": "verified"}
    if city:
        query["city"] = {"$regex": f"^{re.escape(city.strip()[:80])}$", "$options": "i"}
    if niche:
        query["niches"] = {"$regex": f"^{re.escape(niche.strip()[:80])}$", "$options": "i"}
    if min_followers is not None or max_followers is not None:
        band: dict = {}
        if min_followers is not None:
            band["$gte"] = int(min_followers)
        if max_followers is not None:
            band["$lte"] = int(max_followers)
        query["follower_count"] = band

    # Anyone already asked, or already applied, is not a suggestion.
    on_campaign = {
        row["creator_id"]
        async for row in db.collaborations.find(
            {"campaign_id": campaign["_id"]}, {"creator_id": 1}
        )
    }
    invited = {
        row["creator_id"]
        async for row in db.campaign_invitations.find(
            {"campaign_id": campaign["_id"]}, {"creator_id": 1}
        )
    }
    excluded = on_campaign | invited
    if excluded:
        query["user_id"] = {"$nin": list(excluded)}

    profiles = await db.creator_profiles.find(query).to_list(length=500)
    history = await _delivery_history([p["user_id"] for p in profiles])

    scored = []
    for profile in profiles:
        result = score_creator_for_campaign(
            profile, campaign, delivery=history.get(profile["user_id"])
        )
        scored.append(
            {
                **_brand_visible_creator(profile),
                "match_score": result["score"],
                "match_reason": result["reason"],
                "match_components": result["components"],
                "matched_niches": result["matched_niches"],
                "matched_genres": result["matched_genres"],
                "unknown_signals": result["unknown_signals"],
                "campaigns_delivered": (history.get(profile["user_id"]) or {}).get("completed", 0),
            }
        )

    # Highest score first; ties broken by the bigger audience, then by name so
    # the order is stable across two identical requests.
    scored.sort(key=lambda r: (-r["match_score"], -(r.get("follower_count") or 0), r.get("name") or ""))

    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    page = scored[offset:offset + limit]
    low, high, tier = _reach_tier(campaign.get("budget_per_creator"))
    return {
        "campaign": {
            "id": str(campaign["_id"]),
            "title": campaign.get("title"),
            "category": campaign.get("category"),
            "area": campaign.get("area"),
            "budget_per_creator": campaign.get("budget_per_creator"),
            "compensation_type": _compensation_type(campaign),
        },
        # Shown in the panel so the ranking explains itself before a brand has
        # to ask why a 500k creator isn't at the top of a ₹4,000 brief.
        "budget_tier": {"label": tier, "min_followers": low, "max_followers": high},
        "weights": CREATOR_MATCH_WEIGHTS,
        "total": len(scored),
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page) < len(scored),
        "suggestions": page,
    }


@brand_router.get("/campaigns/{campaign_id}/suggested-creators")
async def brand_suggested_creators(
    campaign_id: str,
    niche: Optional[str] = None,
    city: Optional[str] = None,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Verified creators ranked for this brief, each with the reason.

    Ownership first, then verification — an unverified brand probing campaign
    ids must not learn which ones exist, and creators are not reachable by a
    brand we have not checked.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    return await _suggest_creators_for_campaign(
        campaign,
        niche=niche,
        city=city,
        min_followers=min_followers,
        max_followers=max_followers,
        limit=limit,
        offset=offset,
    )


# --- Running the campaign (brand manager) ----------------------------------
#
# The brand's own manager runs the day-to-day: stopping and restarting the
# brief, asking creators, settling the fee, and marking who turned up. What
# stays with WeAre is the one thing that can't be self-served — putting a
# campaign in front of creators. Everything here is scoped by
# `_own_campaign_or_404`, so "their own campaigns" is a database filter rather
# than a promise.


@brand_router.post("/campaigns/{campaign_id}/pause")
async def brand_pause_campaign(
    campaign_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Stop taking applications, without ending the campaign.

    A brand that has to email us to pause a brief it is paying for will simply
    let it run. Work already under way is untouched.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    return await _pause_campaign(campaign, payload.reason, user)


@brand_router.post("/campaigns/{campaign_id}/resume")
async def brand_resume_campaign(
    campaign_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Put it back on the feed, in whatever state it was paused from."""
    campaign = await _own_campaign_or_404(campaign_id, user)
    return await _resume_campaign(campaign, (payload.reason if payload else None), user)


@brand_router.post("/campaigns/{campaign_id}/invite")
async def brand_invite_creators(
    campaign_id: str,
    payload: CampaignInvitePayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Ask named creators to take up this brief.

    Ownership first, then verification: an unverified brand asking after
    another brand's campaign must learn nothing from the refusal. The creators'
    numbers are read inside `_invite_creators` and never returned — a brand
    invites through the platform, it does not get a contact list.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    return await _invite_creators(campaign, payload, user)


@brand_router.post("/collaborations/{collab_id}/agreed-amount")
async def brand_record_agreed_amount(
    collab_id: str,
    payload: AgreedAmountPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Record the fee settled offline.

    Negotiation happens on WhatsApp and over the phone — that is the model, not
    a gap in it. What matters is that the number lands somewhere both sides and
    an admin can see, attributed and timestamped, before anybody books a date
    against it. Writing it does not move the collaboration on its own: the fee
    is agreed, the creator still has to book.
    """
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)

    state = collab.get("state")
    if state in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"This application is {state} — there's no fee left to agree.",
        )
    if state not in ("accepted", "commercial_agreed"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Accept the creator first — the fee is agreed with somebody who "
                "is on the campaign."
            ),
        )

    # The same resolver the admin's advance path uses, so the two cannot
    # disagree about what a negotiated brief requires or a barter one refuses.
    # This used to take any float, which meant barter was unreachable here too
    # and a fixed fee could be quietly rewritten per creator.
    amount = _resolve_agreed_amount(campaign, payload.agreed_amount)
    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": state},  # precondition, never a blind write
        {
            "$set": {
                "state": "commercial_agreed",
                "agreed_amount": amount,
                "agreed_at": now,
                "agreed_by": ObjectId(user["_id"]),
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.agreed_amount",
        "collaboration",
        collab["_id"],
        before={"state": state, "agreed_amount": collab.get("agreed_amount")},
        after={"state": "commercial_agreed", "agreed_amount": amount},
        note=payload.note,
        **_campaign_audit_context(campaign),
    )
    # The number and the reasoning belong together. A note supplied here lands
    # in the thread as well, so the record of the negotiation reads in one
    # place rather than half in the audit log.
    if (payload.note or "").strip():
        await db.collaboration_notes.insert_one(
            {
                "collaboration_id": collab["_id"],
                "campaign_id": campaign["_id"],
                "brand_id": campaign.get("brand_id"),
                "author_id": ObjectId(user["_id"]),
                "author_name": user.get("name"),
                "author_role": user.get("role"),
                "body": (
                    f"Agreed ₹{amount:,.0f}. {payload.note.strip()}"
                    if amount is not None
                    else f"Barter agreed. {payload.note.strip()}"
                ),
                "created_at": now,
            }
        )
    await notify(
        collab["creator_id"],
        "commercial_agreed",
        title="Your fee has been agreed",
        # Whose move it is now, said plainly: after this the creator books,
        # and a barter brief has no figure to put in front of them.
        body=(
            (f"₹{amount:,.0f} agreed" if amount is not None else "Barter confirmed")
            + f" for “{campaign.get('title')}”. "
            + _next_action({"state": "commercial_agreed"}, campaign)["detail"]
        ),
        link="/dashboard",
    )
    return {
        "id": str(collab["_id"]),
        "state": "commercial_agreed",
        "agreed_amount": amount,
        "agreed_at": _iso(now),
    }


@brand_router.post("/collaborations/{collab_id}/check-in")
async def brand_check_in_creator(
    collab_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Mark a creator as having turned up.

    The brand is the one standing there when a campaign has no WeAre manager on
    it — which, since campaigns now default to the brand's own manager, is the
    usual case. Same transition and same precondition as the manager's
    check-in; only the door it is reached through differs.
    """
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    # Creators are never reachable by a brand we have not checked.
    await _verified_brand_or_403(user)
    return await _check_in_collaboration(collab, campaign, user)


@brand_router.get("/campaigns/{campaign_id}/roster")
async def brand_campaign_roster(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin")),
):
    """Who is coming and when — without how to reach them.

    The manager's roster carries phone numbers because a WeAre manager is the
    person chasing a creator who is late. A brand gets the same list with the
    numbers withheld: on the day it reaches creators through the platform, not
    out of a spreadsheet. `_roster_rows(..., reveal_contact=False)` is what
    enforces that, not this docstring.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
    await _verified_brand_or_403(user)
    rows = await _roster_rows(campaign, reveal_contact=False)
    return {
        "campaign_id": campaign_id,
        "title": campaign.get("title"),
        "campaign_type": campaign.get("campaign_type"),
        "event_date": _iso(campaign.get("event_date")),
        "venue_address": campaign.get("venue_address"),
        "venue_instructions": campaign.get("venue_instructions"),
        "expected": sum(1 for r in rows if r["attendance"] == "expected"),
        "attended": sum(1 for r in rows if r["attendance"] == "attended"),
        "no_shows": sum(1 for r in rows if r["attendance"] == "no_show"),
        "roster": rows,
    }


api_router.include_router(brand_router)


# --- Admin router ----------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["admin"])

def _next_collab_state(current: str) -> Optional[str]:
    """The next step on the happy path, or None at the end / on an exit state."""
    try:
        idx = COLLAB_STATE_ORDER.index(current)
    except ValueError:
        return None  # declined / cancelled have no "next"
    if idx + 1 >= len(COLLAB_STATE_ORDER):
        return None
    return COLLAB_STATE_ORDER[idx + 1]


def _previous_collab_state(current: str) -> Optional[str]:
    """The step before this one, or None at the start / on an exit state.

    The mirror of `_next_collab_state`. Terminal exits are not on the ladder, so
    they have no previous step either — coming back from one is a different
    decision, not a step backwards.
    """
    try:
        idx = COLLAB_STATE_ORDER.index(current)
    except ValueError:
        return None
    if idx == 0:
        return None
    return COLLAB_STATE_ORDER[idx - 1]


# Steps only the brand may take. The admin console shows them as waiting on the
# brand rather than offering an Advance button that bypasses the buyer.
_BRAND_OWNED_TRANSITIONS = {"accepted", "content_approved"}


# Who has to do something next, and what. One table, read by every surface —
# the admin's application screen, the brand's, and the creator's — so they
# cannot describe the same collaboration differently. The applicant board and
# the console once disagreed about whether an approved application was still
# pending; that was two places deciding the same thing separately.
#
# `owner` is who is being waited on, which is not always who may write the
# next state: at `slot_booked` we are waiting for the shoot to happen, and the
# record is then updated by whoever is at the door.
_NEXT_ACTION = {
    "applied": ("admin", "Approve the profile", "We check the creator before any brand sees them."),
    "verified": ("brand", "Accept or decline", "Approved by us. The brand decides."),
    "accepted": ("admin", "Agree the amount", "Record what was negotiated offline."),
    "commercial_agreed": ("creator", "Book a slot", "The creator picks their place."),
    "slot_booked": ("creator", "Turn up", "Attendance is marked on the day."),
    "attended": ("creator", "Submit the content", "Links to what they published."),
    "content_submitted": ("brand", "Approve or request changes", "The brand reviews the content."),
    "content_approved": ("admin", "Move into payment", "Raise the payout."),
    "in_payment": ("admin", "Record the payout", "Mark it paid to close this out."),
    "closed": (None, "Nothing — this is finished", ""),
    "declined": (None, "Nothing — the brand passed", ""),
    "cancelled": (None, "Nothing — this was cancelled", ""),
}


def _next_action(collab: dict, campaign: Optional[dict] = None) -> dict:
    """What has to happen next on this collaboration, and whose job it is."""
    state = collab.get("state", "applied")
    owner, label, detail = _NEXT_ACTION.get(state, (None, "—", ""))

    # A personal table is a window the creator picks a time inside; a launch
    # has one time everybody shares. Same step, different instruction, and the
    # creator is the one who has to act on the difference.
    if state == "commercial_agreed" and (campaign or {}).get("campaign_type") == "personal_table":
        label = "Pick a time"
        detail = "The creator chooses a time inside the campaign's window."

    return {
        "state": state,
        "owner": owner,
        "label": label,
        "detail": detail,
        "is_final": state in TERMINAL_COLLAB_STATES,
    }


def _lifecycle_for(collab: dict, campaign: Optional[dict] = None) -> dict:
    """The whole ladder plus where this one stands — what a status bar draws.

    Every step ships with the response rather than being rebuilt in the client,
    for the same reason `_next_action` is one table: two implementations of a
    state machine drift, and the drift shows up as a screen confidently telling
    somebody the wrong thing.
    """
    state = collab.get("state", "applied")
    try:
        current_index = COLLAB_STATE_ORDER.index(state)
    except ValueError:
        current_index = -1  # declined / cancelled are not on the ladder

    steps = []
    for i, step in enumerate(COLLAB_STATE_ORDER):
        owner, label, _ = _NEXT_ACTION.get(step, (None, step, ""))
        steps.append(
            {
                "state": step,
                "owner": owner,
                "action": label,
                "done": current_index >= 0 and i < current_index,
                "current": i == current_index,
            }
        )

    return {
        "steps": steps,
        "current": state,
        "current_index": current_index,
        # An exit is not a step on the bar; it is the bar stopping.
        "exited": state in TERMINAL_COLLAB_STATES and state != "closed",
        "next_action": _next_action(collab, campaign),
    }


def _commercial_for(campaign: dict, collab: dict) -> dict:
    """What this collaboration pays, and what the fee step may ask for.

    Three kinds of money need three different forms, and the server decides
    which rather than the client inferring it from a budget that a barter brief
    still carries (it keeps whatever it was posted with, so an admin switching
    it back is not lossy).
    """
    ctype = _compensation_type(campaign)
    budget = campaign.get("budget_per_creator")
    return {
        # The type goes with the figure, always and immediately: a rupee amount
        # with no word beside it reads as cash, and a barter brief keeps the
        # budget it was posted with.
        "budget_per_creator": budget,
        "compensation_type": ctype,
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "agreed_at": _iso(collab.get("agreed_at")),
        # How the fee field behaves: typed, fixed to the brief, or absent.
        "amount_required": ctype == "negotiated",
        "amount_locked": ctype == "fixed",
        "amount_applies": ctype != "barter",
        "locked_amount": budget if ctype == "fixed" else None,
    }


def _resolve_agreed_amount(campaign: dict, supplied) -> Optional[float]:
    """The amount to record when a collaboration reaches `commercial_agreed`.

    Barter used to be unreachable: this step demanded a figure, and a barter
    brief has none, so such a collaboration could never leave `accepted`.
    Fixed made an admin retype a number already on the brief, which is a
    chance to type a different one.

    Raises HTTPException so every caller refuses identically.
    """
    ctype = _compensation_type(campaign)

    if ctype == "barter":
        # A meal or a stay. Recording ₹0 would read as "agreed, nothing" on
        # every surface that shows money; absent is the truth.
        if supplied is not None:
            raise HTTPException(
                status_code=422,
                detail="This is a barter campaign — there is no amount to agree.",
            )
        return None

    if ctype == "fixed":
        budget = campaign.get("budget_per_creator")
        if budget is None:
            raise HTTPException(
                status_code=422,
                detail="This fixed-fee campaign has no budget set, so there is nothing to agree.",
            )
        # The brief's number is the fee. A supplied one is accepted only if it
        # agrees, so a stale form cannot quietly rewrite the commercial.
        if supplied is not None and round(float(supplied), 2) != round(float(budget), 2):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"This is a fixed-fee campaign — the fee is ₹{float(budget):,.0f} "
                    "and is set by the brief, not per creator."
                ),
            )
        return round(float(budget), 2)

    if supplied is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Record the agreed amount before approving this — a negotiated "
                "brief has no fee until somebody agrees one."
            ),
        )
    amount = round(float(supplied), 2)
    if amount <= 0:
        raise HTTPException(
            status_code=422, detail="The agreed amount has to be more than zero."
        )
    return amount

# States a collaboration can be declined from: before the brand has taken the
# creator on. After that it is a cancellation, which is a different admission.
_DECLINABLE_STATES = ("applied", "verified")


class AdvanceCollabPayload(BaseModel):
    """Payload to advance a collaboration one step forward.

    `from_state` is the state the caller believes the collaboration is in. It is
    used as a write precondition, so a double-click or a second admin on the
    same row can't skip a stage.
    """

    from_state: Optional[str] = None
    # Required only when the NEXT state is 'commercial_agreed'.
    agreed_amount: Optional[float] = Field(default=None, ge=0)
    # Optional override when the NEXT state is 'in_payment'; otherwise the fee
    # comes from central config.
    platform_fee: Optional[float] = Field(default=None, ge=0)
    # Required only when the NEXT state is 'slot_booked'.
    scheduled_at: Optional[datetime] = None
    location_note: Optional[str] = Field(default=None, max_length=300)


def _serialize_admin_creator(profile: dict, user: dict) -> dict:
    return {
        "user_id": str(user["_id"]),
        "profile_id": str(profile["_id"]),
        "name": profile.get("name") or user.get("name"),
        "email": profile.get("email") or user.get("email"),
        "phone": user.get("phone"),
        "instagram_handle": profile.get("instagram_handle"),
        "instagram_profile_url": profile.get("instagram_profile_url"),
        "youtube_url": profile.get("youtube_url"),
        "facebook_url": profile.get("facebook_url"),
        # What they say about themselves, which is most of what a reviewer is
        # actually judging — and was the one thing the review screen could not
        # show, because nothing collected it.
        "about": profile.get("about"),
        "profile_image_url": profile.get("profile_image_url"),
        "city": profile.get("city"),
        "address": profile.get("address"),
        "niches": profile.get("niches") or [],
        "genres": profile.get("genres") or [],
        "platforms": profile.get("platforms") or [],
        "full_address": profile.get("full_address"),
        # Staff-side, and the point of collecting it: the label says where to
        # post, the pin says where to actually go.
        "location_lat": profile.get("location_lat"),
        "location_lng": profile.get("location_lng"),
        "location_place_id": profile.get("location_place_id"),
        "base_rate": profile.get("base_rate"),
        "follower_count": profile.get("follower_count"),
        **_follower_provenance(profile),
        "verification_status": profile.get("verification_status", "pending"),
        "created_at": profile["created_at"].isoformat()
        if isinstance(profile.get("created_at"), datetime)
        else profile.get("created_at"),
    }


async def _hydrate_creator_rows(profiles: list) -> list:
    if not profiles:
        return []
    user_ids = [p["user_id"] for p in profiles]
    users = await db.users.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
    users_by_id = {u["_id"]: u for u in users}
    return [
        _serialize_admin_creator(p, users_by_id.get(p["user_id"], {}))
        for p in profiles
    ]


async def _creator_activity_stats(user_ids: list) -> dict:
    """Money and campaign counts per creator, in one round trip.

    Joins payments onto collaborations inside the pipeline rather than looping
    per creator — an admin list of 50 creators would otherwise be 50 queries.
    Returns { creator_oid: {completed, ongoing, applied, earned, committed} }.
    """
    if not user_ids:
        return {}
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"creator_id": {"$in": list(user_ids)}}},
            {
                "$lookup": {
                    "from": "payments",
                    "localField": "_id",
                    "foreignField": "collaboration_id",
                    "as": "payment",
                }
            },
            {"$addFields": {"payment": {"$arrayElemAt": ["$payment", 0]}}},
            {
                "$group": {
                    "_id": "$creator_id",
                    "completed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$state", list(COLLAB_GROUP_COMPLETED)]}, 1, 0
                            ]
                        }
                    },
                    "ongoing": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$state", list(COLLAB_GROUP_ONGOING)]}, 1, 0
                            ]
                        }
                    },
                    "applied": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$state", list(COLLAB_GROUP_APPLIED)]}, 1, 0
                            ]
                        }
                    },
                    # Only money that actually left the bank counts as earned.
                    "earned": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$payment.state", "paid"]},
                                {"$ifNull": ["$payment.creator_payout", 0]},
                                0,
                            ]
                        }
                    },
                    # Agreed but not yet paid — what we owe them if everything
                    # in flight lands.
                    "committed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$state", list(COLLAB_GROUP_ONGOING)]},
                                {"$ifNull": ["$agreed_amount", 0]},
                                0,
                            ]
                        }
                    },
                }
            },
        ]
    ).to_list(length=len(user_ids) + 1)
    return {r["_id"]: r for r in rows}


def _empty_stats() -> dict:
    return {"completed": 0, "ongoing": 0, "applied": 0, "earned": 0.0, "committed": 0.0}


@admin_router.get("/creators")
async def list_all_creators(
    q: Optional[str] = None,
    verification_status: Optional[str] = None,
    niche: Optional[str] = None,
    city: Optional[str] = None,
    area: Optional[str] = None,  # alias for city; creators carry a city, not an area
    onboarded_only: bool = False,
    sort: Optional[str] = None,  # "newest" | "earned_desc" | "name"
    page: int = 1,
    page_size: int = 25,
    user: dict = Depends(require_roles("admin")),
):
    """Every creator, whatever their verification status.

    The other creator endpoints are work queues — this is the roster, for
    looking someone up rather than acting on them.
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 100))
    location = (city or area or "").strip()

    match: dict = {}
    if verification_status:
        if verification_status not in ("pending", "verified", "rejected"):
            raise HTTPException(
                status_code=422,
                detail="verification_status must be pending, verified or rejected.",
            )
        match["verification_status"] = verification_status
    if niche:
        match["niches"] = {"$regex": f"^{re.escape(niche.strip())}$", "$options": "i"}
    if location:
        match["city"] = {"$regex": f"^{re.escape(location)}$", "$options": "i"}
    if onboarded_only:
        match["instagram_handle"] = {"$type": "string", "$ne": ""}
    if q:
        # Phone lives on the user document, so the search has to run after the
        # join below rather than as a plain find().
        term = re.escape(q.strip()[:120])
        match["$or"] = [
            {"name": {"$regex": term, "$options": "i"}},
            {"instagram_handle": {"$regex": term, "$options": "i"}},
            {"user.phone": {"$regex": term, "$options": "i"}},
            {"user.email": {"$regex": term, "$options": "i"}},
        ]

    sort_stage = {"created_at": -1}
    if sort == "name":
        sort_stage = {"name": 1}
    elif sort == "earned_desc":
        # Sorting by money means the stats have to be in the pipeline, so this
        # branch joins them before paginating rather than after.
        sort_stage = {"earned": -1, "created_at": -1}

    pipeline: list = [
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user",
            }
        },
        {"$addFields": {"user": {"$arrayElemAt": ["$user", 0]}}},
    ]

    if sort == "earned_desc":
        pipeline += [
            {
                "$lookup": {
                    "from": "collaborations",
                    "let": {"uid": "$user_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$creator_id", "$$uid"]}}},
                        {
                            "$lookup": {
                                "from": "payments",
                                "localField": "_id",
                                "foreignField": "collaboration_id",
                                "as": "payment",
                            }
                        },
                        {"$addFields": {"payment": {"$arrayElemAt": ["$payment", 0]}}},
                        {"$match": {"payment.state": "paid"}},
                        {
                            "$group": {
                                "_id": None,
                                "earned": {"$sum": {"$ifNull": ["$payment.creator_payout", 0]}},
                            }
                        },
                    ],
                    "as": "_earnings",
                }
            },
            {
                "$addFields": {
                    "earned": {
                        "$ifNull": [{"$arrayElemAt": ["$_earnings.earned", 0]}, 0]
                    }
                }
            },
        ]

    if match:
        pipeline.append({"$match": match})
    pipeline += [
        {"$sort": sort_stage},
        {
            # One round trip for the page and the count.
            "$facet": {
                "rows": [{"$skip": (page - 1) * page_size}, {"$limit": page_size}],
                "total": [{"$count": "n"}],
            }
        },
    ]

    result = await db.creator_profiles.aggregate(pipeline).to_list(length=1)
    facet = result[0] if result else {}
    docs = facet.get("rows") or []
    total_rows = facet.get("total") or []
    total = total_rows[0]["n"] if total_rows else 0

    stats = await _creator_activity_stats([d["user_id"] for d in docs])

    creators = []
    for d in docs:
        s = stats.get(d["user_id"]) or _empty_stats()
        row = _serialize_admin_creator(d, d.get("user") or {"_id": d["user_id"]})
        row.update(
            {
                "status": (d.get("user") or {}).get("status"),
                "pending_review": bool(d.get("pending_review", False)),
                "payout_ready": payout_ready(d),
                "campaigns_completed": s["completed"],
                "collaborations_ongoing": s["ongoing"],
                "applications_open": s["applied"],
                "total_earned": round(float(s["earned"]), 2),
                "committed": round(float(s["committed"]), 2),
            }
        )
        creators.append(row)

    return {
        "creators": creators,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
    }


# Who is actually waiting on a decision. Defined once because it feeds three
# places — the queue itself, the tab badge and the dashboard facet — and the
# last time they disagreed the badge counted people the queue never showed.
_AWAITING_REVIEW_QUERY = {
    "verification_status": "pending",
    "submitted_for_review_at": {"$ne": None, "$exists": True},
}


@admin_router.get("/creators/pending")
async def list_pending_creators(user: dict = Depends(require_roles("admin"))):
    """Creators actually waiting on us.

    A profile stub is created at signup, so filtering on `pending` alone fills
    the queue with people who never finished onboarding. The submission
    timestamp is what separates "waiting on us" from "still building" — it is
    only set by /creator/profile/submit-for-review, which in turn only opens at
    100% completeness, so every row here is a profile that can be decided on.
    """
    profiles = (
        await db.creator_profiles.find(_AWAITING_REVIEW_QUERY)
        .sort("submitted_for_review_at", 1)  # longest wait first
        .to_list(length=500)
    )
    return await _hydrate_creator_rows(profiles)


@admin_router.get("/creators/changed")
async def list_changed_creators(user: dict = Depends(require_roles("admin"))):
    """Verified creators who changed something material since we approved them.

    They stay live and visible to brands while they're in this queue — an edit
    is not a reason to pull someone out of the directory.
    """
    profiles = (
        await db.creator_profiles.find(
            {"verification_status": "verified", "pending_review": True}
        )
        .sort("updated_at", -1)
        .to_list(length=500)
    )
    return await _hydrate_creator_rows(profiles)


@admin_router.get("/creators/incomplete")
async def list_incomplete_creators(user: dict = Depends(require_roles("admin"))):
    """Signed up, never finished onboarding. Not a review queue — a nudge list."""
    profiles = (
        await db.creator_profiles.find(
            {
                "verification_status": "pending",
                "$or": [
                    {"instagram_handle": None},
                    {"instagram_handle": {"$exists": False}},
                    {"instagram_handle": ""},
                ],
            }
        )
        .sort("created_at", -1)
        .to_list(length=500)
    )
    return await _hydrate_creator_rows(profiles)


@admin_router.get("/creators/{user_id}")
async def get_creator_detail(
    user_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """One creator, whole picture.

    Declared after /creators/pending, /changed and /incomplete so those fixed
    paths keep matching first.
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Creator not found")

    account = await db.users.find_one({"_id": oid, "role": "creator"})
    profile = await db.creator_profiles.find_one({"user_id": oid})
    if not account or not profile:
        raise HTTPException(status_code=404, detail="Creator not found")

    # Every collaboration with its campaign, brand and payment attached in one
    # pipeline — the alternative is three queries per row.
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"creator_id": oid}},
            {"$sort": {"created_at": -1}},
            {
                "$lookup": {
                    "from": "campaigns",
                    "localField": "campaign_id",
                    "foreignField": "_id",
                    "as": "campaign",
                }
            },
            {"$addFields": {"campaign": {"$arrayElemAt": ["$campaign", 0]}}},
            {
                "$lookup": {
                    "from": "brand_profiles",
                    "localField": "campaign.brand_id",
                    "foreignField": "user_id",
                    "as": "brand",
                }
            },
            {"$addFields": {"brand": {"$arrayElemAt": ["$brand", 0]}}},
            {
                "$lookup": {
                    "from": "payments",
                    "localField": "_id",
                    "foreignField": "collaboration_id",
                    "as": "payment",
                }
            },
            {"$addFields": {"payment": {"$arrayElemAt": ["$payment", 0]}}},
            {
                "$project": {
                    "state": 1,
                    "quoted_rate": 1,
                    "agreed_amount": 1,
                    "scheduled_at": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "exit_reason": 1,
                    "campaign_id": 1,
                    "campaign_title": "$campaign.title",
                    "campaign_status": "$campaign.status",
                    "campaign_area": "$campaign.area",
                    "brand_name": "$brand.business_name",
                    "payment_state": "$payment.state",
                    "creator_payout": "$payment.creator_payout",
                    "paid_at": "$payment.paid_at",
                }
            },
        ]
    ).to_list(length=1000)

    groups: dict = {"completed": [], "ongoing": [], "applied": [], "ended": []}
    lifetime_earned = 0.0
    committed = 0.0

    for r in rows:
        state = r.get("state")
        row = {
            "id": str(r["_id"]),
            "campaign_id": str(r["campaign_id"]),
            "campaign_title": r.get("campaign_title"),
            "campaign_status": r.get("campaign_status"),
            "area": r.get("campaign_area"),
            "brand_name": r.get("brand_name"),
            "state": state,
            "quoted_rate": r.get("quoted_rate"),
            "agreed_amount": r.get("agreed_amount"),
            "scheduled_at": _iso(r.get("scheduled_at")),
            "exit_reason": r.get("exit_reason"),
            "payment_state": r.get("payment_state"),
            "paid_at": _iso(r.get("paid_at")),
            "created_at": _iso(r.get("created_at")),
            "updated_at": _iso(r.get("updated_at")),
        }

        if r.get("payment_state") == "paid":
            lifetime_earned += float(r.get("creator_payout") or 0)

        if state in COLLAB_GROUP_COMPLETED:
            groups["completed"].append(row)
        elif state in COLLAB_GROUP_ONGOING:
            committed += float(r.get("agreed_amount") or 0)
            groups["ongoing"].append(row)
        elif state in COLLAB_GROUP_APPLIED:
            groups["applied"].append(row)
        else:
            # declined / cancelled — kept rather than dropped, so the record of
            # what happened to this creator is complete.
            groups["ended"].append(row)

    detail = _serialize_admin_creator(profile, account)
    detail.update(
        {
            "status": account.get("status"),
            "pending_review": bool(profile.get("pending_review", False)),
            # Which fields, so a re-check is a two-minute job rather than a
            # diff against a profile nobody kept a copy of.
            "pending_review_fields": profile.get("pending_review_fields") or [],
            "pending_review_since": _iso(profile.get("pending_review_since")),
            "payout_ready": payout_ready(profile),
            "payout_upi": profile.get("payout_upi"),
            "payout_account_name": profile.get("payout_account_name"),
            "pan": profile.get("pan"),
            "gstin": profile.get("gstin"),
            "verified_at": _iso(profile.get("verified_at")),
            "verification_reason": profile.get("verification_reason"),
            "terms_accepted_at": _iso(account.get("terms_accepted_at")),
            "joined_at": _iso(account.get("created_at")),
        }
    )

    # Slots this creator holds, with the campaign they belong to. Separate from
    # the collaboration rows because a booking is a commitment to be somewhere
    # at a time — the question "where is this person on Saturday" is not
    # answerable from a list of states.
    slot_ids = [c["slot_id"] for c in await db.collaborations.find(
        {"creator_id": oid, "slot_id": {"$ne": None}}
    ).to_list(length=500) if c.get("slot_id")]
    bookings = []
    if slot_ids:
        slot_docs = await db.campaign_slots.find(
            {"_id": {"$in": slot_ids}}
        ).sort("starts_at", 1).to_list(length=500)
        slot_campaigns = await db.campaigns.find(
            {"_id": {"$in": [s["campaign_id"] for s in slot_docs]}}
        ).to_list(length=len(slot_docs))
        title_by_campaign = {c["_id"]: c.get("title") for c in slot_campaigns}
        collab_by_slot = {
            c["slot_id"]: c
            for c in await db.collaborations.find(
                {"creator_id": oid, "slot_id": {"$in": slot_ids}}
            ).to_list(length=500)
        }
        for s in slot_docs:
            c = collab_by_slot.get(s["_id"]) or {}
            bookings.append(
                {
                    **_serialize_slot(s),
                    "campaign_title": title_by_campaign.get(s["campaign_id"]),
                    "collaboration_id": str(c["_id"]) if c.get("_id") else None,
                    "state": c.get("state"),
                }
            )

    return {
        "creator": detail,
        # The connection, not the token — _serialize_instagram cannot return
        # one. Absent credentials is a supported state, so this is present and
        # says `configured: false` rather than being missing.
        "instagram": _serialize_instagram(
            await db.instagram_connections.find_one({"user_id": oid})
        ),
        # No API behind YouTube here: the creator gives us a channel URL and
        # that is all we have. Said plainly rather than dressed up as stats.
        "youtube": {
            "url": profile.get("youtube_url"),
            "connected": bool(profile.get("youtube_url")),
        },
        "collaborations": groups,
        "slot_bookings": bookings,
        "totals": {
            "lifetime_earned": round(lifetime_earned, 2),
            # Agreed on work in flight — what we owe if it all lands.
            "committed": round(committed, 2),
            "campaigns_completed": len(groups["completed"]),
            "collaborations_ongoing": len(groups["ongoing"]),
            "applications_open": len(groups["applied"]),
            "collaborations_ended": len(groups["ended"]),
            "slots_booked": len(bookings),
        },
    }


async def _set_creator_verification(
    user_id: str, status: str, actor: dict, reason: Optional[str] = None
) -> dict:
    if status not in ("verified", "rejected"):
        raise HTTPException(status_code=422, detail="Invalid verification status")
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Creator not found")

    before = await db.creator_profiles.find_one({"user_id": oid})
    if not before:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    now = datetime.now(timezone.utc)
    result = await db.creator_profiles.find_one_and_update(
        {"user_id": oid},
        {
            "$set": {
                "verification_status": status,
                # A decision clears the re-review flag either way.
                "pending_review": False,
                # And the labels with it, or the next re-check would tell the
                # creator about a change we already looked at.
                "pending_review_fields": [],
                "verification_reason": reason,
                "verified_at": now,
                "updated_at": now,
            }
        },
        return_document=True,
    )

    # Also flip the user's active status when verified.
    if status == "verified":
        await db.users.update_one({"_id": oid}, {"$set": {"status": "active"}})

    await audit(
        actor,
        f"creator.{status}",
        "creator_profile",
        before["_id"],
        before={"verification_status": before.get("verification_status")},
        after={"verification_status": status},
        note=reason,
    )

    if status == "verified":
        await notify(
            oid,
            "creator_verified",
            title="You're verified",
            body="Your profile is approved — live briefs are open to you now.",
            link="/campaigns",
        )
    else:
        await notify(
            oid,
            "creator_rejected",
            title="Profile not approved yet",
            body=(reason or "Update your profile and we'll take another look."),
            link="/onboarding/creator",
        )

    user = await db.users.find_one({"_id": oid})
    return _serialize_admin_creator(result, user or {})


@admin_router.post("/creators/{user_id}/approve")
async def approve_creator(
    user_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    return await _set_creator_verification(
        user_id, "verified", user, (payload.reason if payload else None)
    )


@admin_router.post("/creators/{user_id}/reject")
async def reject_creator(
    user_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    return await _set_creator_verification(
        user_id, "rejected", user, (payload.reason if payload else None)
    )


@admin_router.post("/creators/{user_id}/suspend")
async def suspend_creator(
    user_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Stop an account without touching what we decided about the profile.

    Suspension and verification are two different judgements, and collapsing
    them loses the one you need later: rejecting a verified creator to get them
    off the platform would erase the record that they were ever approved, and
    re-verifying them afterwards would look like a fresh decision rather than a
    reinstatement. `UserStatus` has always had the state — this is the endpoint
    that sets it.

    Work already under way is deliberately untouched. A suspension is not a
    cancellation: somebody has to decide, per collaboration, whether a shoot
    two days out is still happening.
    """
    oid = _as_oid(user_id)
    if oid is None:
        raise HTTPException(status_code=404, detail="Creator not found")

    account = await db.users.find_one({"_id": oid, "role": "creator"})
    if not account:
        raise HTTPException(status_code=404, detail="Creator not found")
    if account.get("status") == "suspended":
        raise HTTPException(status_code=409, detail="This account is already suspended.")

    reason = payload.reason.strip()
    await db.users.update_one(
        {"_id": oid},
        {"$set": {"status": "suspended", "suspended_at": datetime.now(timezone.utc),
                  "suspension_reason": reason}},
    )
    await audit(
        user,
        "creator.suspend",
        "user",
        oid,
        before={"status": account.get("status")},
        after={"status": "suspended"},
        note=reason,
    )
    await notify(
        oid,
        "creator_suspended",
        title="Your account is on hold",
        body=reason,
        link="/dashboard",
    )
    return {"user_id": user_id, "status": "suspended", "reason": reason}


@admin_router.post("/creators/{user_id}/reinstate")
async def reinstate_creator(
    user_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Undo a suspension.

    Returns the account to `active` and leaves the verification decision
    exactly where it was, which is the whole reason the two are separate.
    """
    oid = _as_oid(user_id)
    if oid is None:
        raise HTTPException(status_code=404, detail="Creator not found")

    account = await db.users.find_one({"_id": oid, "role": "creator"})
    if not account:
        raise HTTPException(status_code=404, detail="Creator not found")
    if account.get("status") != "suspended":
        raise HTTPException(status_code=409, detail="This account is not suspended.")

    reason = payload.reason.strip()
    await db.users.update_one(
        {"_id": oid},
        {"$set": {"status": "active"},
         "$unset": {"suspended_at": "", "suspension_reason": ""}},
    )
    await audit(
        user,
        "creator.reinstate",
        "user",
        oid,
        before={"status": "suspended"},
        after={"status": "active"},
        note=reason,
    )
    await notify(
        oid,
        "creator_reinstated",
        title="Your account is back",
        body="You can apply to briefs again.",
        link="/campaigns",
    )
    return {"user_id": user_id, "status": "active", "reason": reason}


# ---------------------------------------------------------------------------
# Content performance
#
# `content_url` has been collected on every delivery since content submission
# existed and read by nobody. It is the only evidence we have that the work we
# arranged did anything, which makes it the answer to the only question a brand
# asks at renewal.
#
# One record per collaboration, in its own collection. Separate from the
# collaboration because a reading is a thing that happened *at a time* — a post
# keeps accruing reach for days — and because the numbers arrive from two
# different places and one of them is a person typing.
# ---------------------------------------------------------------------------

# What a creator's audience actually did with the post. Reach is the
# denominator for engagement rate; the rest are the numerator or context.
PERFORMANCE_METRICS = ("reach", "impressions", "views", "likes", "comments", "saves")
# The three that count as somebody engaging rather than merely seeing.
ENGAGEMENT_METRICS = ("likes", "comments", "saves")


class PerformancePayload(BaseModel):
    """A reading, typed in by an admin or a campaign manager.

    Every metric is optional and `None` means "not known", never zero — a post
    with no saves and a post whose saves we could not read are different
    things, and averaging the second as a zero is how a report starts lying.

    `engagement_rate` is deliberately absent: it is derived from the metrics
    below so it cannot disagree with them. See `_engagement_rate_from`.
    """

    reach: Optional[int] = Field(default=None, ge=0)
    impressions: Optional[int] = Field(default=None, ge=0)
    views: Optional[int] = Field(default=None, ge=0)
    likes: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    saves: Optional[int] = Field(default=None, ge=0)
    # When the numbers were read off the screen, which is not when they were
    # typed in. Defaults to now.
    captured_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _at_least_one_number(self):
        if all(getattr(self, m) is None for m in PERFORMANCE_METRICS):
            raise ValueError(
                "Give at least one number — an empty reading is not a reading."
            )
        return self


def _engagements(doc: dict) -> Optional[int]:
    """Likes + comments + saves, or None when we know none of them.

    Sums what is present rather than requiring all three: a manual reading off
    a phone screen often has likes and comments and no saves, and refusing that
    would mean recording nothing at all.
    """
    present = [doc.get(m) for m in ENGAGEMENT_METRICS if doc.get(m) is not None]
    return sum(present) if present else None


def _engagement_rate_from(doc: dict) -> Optional[float]:
    """Engagements as a percentage of reach.

    Against **reach**, not followers. Reach is who actually saw it, which is
    the question a brand is asking; a rate against followers flatters a post
    that reached nobody and punishes one that travelled beyond its audience.
    The choice matters enough that it lives in one function rather than being
    inlined at three call sites with two different denominators.

    None when either half is unknown — not zero.
    """
    reach = doc.get("reach")
    eng = _engagements(doc)
    if not reach or eng is None:
        return None
    return round(eng / reach * 100, 2)


def _serialize_performance(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "collaboration_id": str(doc["collaboration_id"]),
        **{m: doc.get(m) for m in PERFORMANCE_METRICS},
        "engagements": _engagements(doc),
        # Recomputed on read rather than trusted from storage, so a record
        # written before the formula existed still reports the current one.
        "engagement_rate": _engagement_rate_from(doc),
        "captured_at": _iso(doc.get("captured_at")),
        # Where the numbers came from. A brand-facing report should be able to
        # say "measured" or not, and an admin looking at an odd figure wants to
        # know whether a person typed it.
        "source": doc.get("source") or "manual",
        "captured_by_name": doc.get("captured_by_name"),
        "content_url": doc.get("content_url"),
        "media_id": doc.get("media_id"),
        "note": doc.get("note"),
        "updated_at": _iso(doc.get("updated_at")),
    }


def _rollup_performance(
    records: list, paid_collab_ids: set, spend: float, barter_collab_ids: set = frozenset()
) -> dict:
    """Totals across a set of readings.

    **Barter is the whole difficulty here.** A barter campaign has reach and
    engagement and no spend, so it belongs in the audience totals and nowhere
    near the cost ones. Excluding only its *spend* would be worse than useless:
    the spend is already zero, so the damage is on the other side of the
    division — its reach would inflate the denominator and quietly report a
    cost per thousand that we never achieved.

    So cost metrics are computed over the paid subset on **both** sides, and
    the paid reach they were computed from is returned alongside them. A number
    you cannot reconstruct is a number nobody can defend in a meeting.

    `paid` and `barter` are asked separately rather than one being the inverse
    of the other, because they are not: a delivery on a *paid* campaign whose
    payment has not gone out yet is neither. Calling that remainder "barter"
    would put a sentence in a client report claiming we got work for free that
    we have simply not paid for yet.
    """
    reach = sum(r["reach"] for r in records if r.get("reach"))
    engagements = sum(e for e in (_engagements(r) for r in records) if e)
    paid = [r for r in records if r["collaboration_id"] in paid_collab_ids]
    paid_reach = sum(r["reach"] for r in paid if r.get("reach"))
    barter = [r for r in records if r["collaboration_id"] in barter_collab_ids]

    return {
        "creators_delivered": len(records),
        "total_reach": reach,
        "total_impressions": sum(r["impressions"] for r in records if r.get("impressions")),
        "total_views": sum(r["views"] for r in records if r.get("views")),
        "total_engagements": engagements,
        # The aggregate rate, which is engagements over reach for the whole set
        # — not the mean of the per-post rates. Those two differ whenever the
        # posts differ in size, and the mean lets one tiny post with a freak
        # rate move the headline number.
        "engagement_rate": round(engagements / reach * 100, 2) if reach else None,
        "total_spend": round(spend, 2),
        # Cost per thousand people reached, over paid work only.
        "cost_per_thousand_reach": (
            round(spend / paid_reach * 1000, 2) if paid_reach and spend else None
        ),
        # Shown so the CPM above can be checked by hand.
        "paid_reach": paid_reach,
        "barter_reach": sum(r["reach"] for r in barter if r.get("reach")),
        "barter_deliveries": len(barter),
        # Delivered, on a paid campaign, and the money has not gone out. Not
        # barter — just not settled — and worth its own number so nobody
        # reports it as either.
        "awaiting_payment_deliveries": len(records) - len(paid) - len(barter),
        # Named so a report can say "3 of 5 posts measured" rather than
        # implying the total covers everybody.
        "with_reach": sum(1 for r in records if r.get("reach")),
    }


async def _paid_collab_ids(campaign_ids: list) -> set:
    """Collaborations that actually cost money, and how much in total.

    A collaboration on a barter campaign never produces a paid payment, so this
    catches barter without having to ask what kind of campaign anything is —
    which also catches a paid campaign whose payment never went out.
    """
    if not campaign_ids:
        return set()
    rows = await db.payments.aggregate(
        [
            {"$match": {"state": "paid"}},
            {
                "$lookup": {
                    "from": "collaborations",
                    "localField": "collaboration_id",
                    "foreignField": "_id",
                    "as": "collab",
                }
            },
            {"$addFields": {"collab": {"$arrayElemAt": ["$collab", 0]}}},
            {"$match": {"collab.campaign_id": {"$in": campaign_ids}}},
            {"$project": {"collaboration_id": 1, "creator_payout": 1}},
        ]
    ).to_list(length=5000)
    return {r["collaboration_id"] for r in rows}


async def _performance_for(campaign_ids: list) -> list:
    if not campaign_ids:
        return []
    return await db.content_performance.find(
        {"campaign_id": {"$in": campaign_ids}}
    ).to_list(length=5000)


async def _barter_collab_ids(campaign_ids: list) -> set:
    """Collaborations on campaigns that pay in kind.

    Read off the campaign's `compensation_type` rather than inferred from a
    missing payment — see the note in `_rollup_performance`.
    """
    if not campaign_ids:
        return set()
    barter = [
        c["_id"]
        for c in await db.campaigns.find(
            {"_id": {"$in": campaign_ids}}, {"compensation_type": 1}
        ).to_list(length=len(campaign_ids))
        if _compensation_type(c) == "barter"
    ]
    if not barter:
        return set()
    return {
        c["_id"]
        for c in await db.collaborations.find(
            {"campaign_id": {"$in": barter}}, {"_id": 1}
        ).to_list(length=5000)
    }


async def _campaign_performance(campaign_ids: list, spend: float) -> dict:
    records = await _performance_for(campaign_ids)
    return _rollup_performance(
        records,
        await _paid_collab_ids(campaign_ids),
        spend,
        await _barter_collab_ids(campaign_ids),
    )


async def _record_performance(
    collab: dict,
    payload: PerformancePayload,
    actor: dict,
    *,
    source: str = "manual",
    media_id: Optional[str] = None,
) -> dict:
    """Write or replace the reading for one collaboration.

    One record per collaboration, upserted: a post keeps accruing reach, so the
    second reading a week later is a correction of the first rather than a
    second data point. `captured_at` says which moment the numbers describe.

    Deliberately does **not** require the collaboration to be in any particular
    state. The obvious rule would be "only once content is approved", and it
    would be wrong the first time a brand asks how a post is doing before they
    have got round to approving it.
    """
    now = datetime.now(timezone.utc)
    given = payload.model_dump(exclude_unset=True)
    doc = {
        **{m: given.get(m) for m in PERFORMANCE_METRICS if m in given},
        "collaboration_id": collab["_id"],
        "campaign_id": collab["campaign_id"],
        "creator_id": collab["creator_id"],
        "captured_at": payload.captured_at or now,
        "source": source,
        "captured_by": ObjectId(actor["_id"]),
        "captured_by_name": actor.get("name"),
        "content_url": (collab.get("content_urls") or [collab.get("content_url")] or [None])[0],
        "updated_at": now,
    }
    if media_id:
        doc["media_id"] = media_id
    if payload.note is not None:
        doc["note"] = payload.note.strip() or None

    saved = await db.content_performance.find_one_and_update(
        {"collaboration_id": collab["_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True,
    )
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    await audit(
        actor,
        "collaboration.performance",
        "collaboration",
        collab["_id"],
        after={
            "source": source,
            **{m: doc.get(m) for m in PERFORMANCE_METRICS if m in doc},
            "engagement_rate": _engagement_rate_from(saved),
        },
        **_campaign_audit_context(campaign or {}),
    )
    return _serialize_performance(saved)


# What Instagram calls each metric, against what we call it. `saved` and
# `total_interactions` are theirs; the rest happen to match.
_IG_MEDIA_METRICS = {
    "reach": "reach",
    "likes": "likes",
    "comments": "comments",
    "saves": "saved",
    "views": "views",
}


def _permalink_key(url: Optional[str]) -> Optional[str]:
    """The shortcode out of an Instagram permalink.

    Matching on the whole URL fails constantly: creators paste links with
    `?igsh=` tracking noise, with and without the trailing slash, and from
    `instagram.com` or `www.instagram.com`. The shortcode is the part that
    identifies the post, so it is the part we compare.
    """
    if not url:
        return None
    m = re.search(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


async def _fetch_instagram_performance(collab: dict) -> tuple[Optional[dict], Optional[str]]:
    """Read one post's insights off the creator's own connected account.

    Returns `(metrics, reason_it_did_not_work)` — never raises. Every branch
    that fails returns a sentence a human can act on, because the alternative
    to this working is somebody typing the numbers in, and they need to know
    that is what they are now doing.

    **It only ever looks at media belonging to the creator's own connected
    account.** The permalink is matched against their media list rather than
    being fetched directly, so there is no path here that reads insights for a
    post we were merely given a link to.
    """
    if not instagram_configured():
        return None, "Instagram isn't connected on this deployment — enter the numbers by hand."

    urls = collab.get("content_urls") or ([collab["content_url"]] if collab.get("content_url") else [])
    wanted = {k for k in (_permalink_key(u) for u in urls) if k}
    if not wanted:
        return None, "No Instagram link on this delivery — enter the numbers by hand."

    conn = await db.instagram_connections.find_one({"user_id": collab["creator_id"]})
    if not conn or conn.get("status") != "connected":
        return None, "This creator hasn't connected Instagram — enter the numbers by hand."
    token = _decrypt_token(conn.get("access_token"))
    if not token:
        return None, "Their Instagram connection needs renewing — enter the numbers by hand."

    try:
        media = await _instagram_get(
            "/me/media",
            {"fields": "id,permalink,media_type,timestamp", "limit": 50, "access_token": token},
        )
    except HTTPException as exc:
        return None, f"Instagram wouldn't answer ({exc.detail}) — enter the numbers by hand."

    match = next(
        (m for m in (media.get("data") or []) if _permalink_key(m.get("permalink")) in wanted),
        None,
    )
    if not match:
        return None, (
            "That post isn't in their recent media — it may be older than the last 50 "
            "posts, or posted from another account. Enter the numbers by hand."
        )

    try:
        insights = await _instagram_get(
            f"/{match['id']}/insights",
            {"metric": ",".join(_IG_MEDIA_METRICS.values()), "access_token": token},
        )
    except HTTPException as exc:
        return None, f"Instagram had no insights for that post ({exc.detail}) — enter the numbers by hand."

    by_name = {row.get("name"): row for row in (insights.get("data") or [])}
    out: dict = {"media_id": match["id"]}
    for ours, theirs in _IG_MEDIA_METRICS.items():
        row = by_name.get(theirs) or {}
        values = row.get("values") or []
        value = values[0].get("value") if values else None
        if isinstance(value, (int, float)):
            out[ours] = int(value)
    if not any(k in out for k in PERFORMANCE_METRICS):
        return None, "Instagram returned no numbers for that post — enter them by hand."
    return out, None


def _phone_tail(raw: Optional[str]) -> Optional[str]:
    """The last ten digits of a number, or None if there aren't ten.

    A number reaches us written five ways — `+91 98765 43210`, `09876543210`,
    `9876543210`, with dashes, with brackets. The tail is the part that is the
    same in all of them, so it is what search matches on. Ten because that is
    an Indian subscriber number; the country code is the part people leave off.
    """
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else None


# Enough to be worth a query. One character would return the whole database
# ranked by nothing.
SEARCH_MIN_CHARS = 2
SEARCH_GROUP_LIMIT = 6


@admin_router.get("/search")
async def admin_global_search(
    q: str = "",
    user: dict = Depends(require_roles("admin")),
):
    """One box over creators, brands, campaigns and phone numbers.

    Built for one moment: somebody messages us mid-campaign and we have thirty
    seconds to find out who they are and what they are on. So a bare phone
    number has to work as well as a name, and the results have to say which
    kind of thing each one is rather than making the reader infer it.

    Declared before /{user_id}-shaped admin paths at this depth — see the route
    ordering test. `search` is a word somebody could plausibly have as an id.
    """
    term = (q or "").strip()[:120]
    if len(term) < SEARCH_MIN_CHARS:
        return {"query": term, "groups": [], "total": 0}

    rx = {"$regex": re.escape(term), "$options": "i"}
    tail = _phone_tail(term)
    # Matching the tail against stored E.164 means a suffix match, which cannot
    # use an index — acceptable at this size, and the alternative is a stored
    # normalised column that every write path has to remember to maintain.
    phone_rx = {"$regex": f"{re.escape(tail)}$"} if tail else None

    creator_or = [{"name": rx}, {"email": rx}]
    if phone_rx:
        creator_or.append({"phone": phone_rx})

    creator_users, profiles, brand_profiles, brand_users, campaigns = await asyncio.gather(
        db.users.find({"role": "creator", "$or": creator_or}).limit(SEARCH_GROUP_LIMIT).to_list(length=SEARCH_GROUP_LIMIT),
        db.creator_profiles.find(
            {"$or": [{"name": rx}, {"instagram_handle": rx}, {"city": rx}]}
        ).limit(SEARCH_GROUP_LIMIT).to_list(length=SEARCH_GROUP_LIMIT),
        db.brand_profiles.find(
            {"$or": [{"business_name": rx}, {"legal_entity_name": rx}, {"contact_person_name": rx}]}
        ).limit(SEARCH_GROUP_LIMIT).to_list(length=SEARCH_GROUP_LIMIT),
        db.users.find(
            {"role": {"$in": list(BRAND_ROLES)}, "$or": creator_or}
        ).limit(SEARCH_GROUP_LIMIT).to_list(length=SEARCH_GROUP_LIMIT),
        db.campaigns.find({"$or": [{"title": rx}, {"area": rx}]})
        .sort("created_at", -1)
        .limit(SEARCH_GROUP_LIMIT)
        .to_list(length=SEARCH_GROUP_LIMIT),
    )

    # A creator can match on their account or on their profile; the two are
    # merged by user id so somebody whose name is on both is one result.
    creator_ids = {u["_id"] for u in creator_users} | {p["user_id"] for p in profiles}
    creator_ids = list(creator_ids)[: SEARCH_GROUP_LIMIT * 2]
    creator_rows = []
    if creator_ids:
        users_by_id = {u["_id"]: u for u in creator_users}
        profile_by_uid = {p["user_id"]: p for p in profiles}
        missing = [i for i in creator_ids if i not in users_by_id]
        if missing:
            for u in await db.users.find({"_id": {"$in": missing}}).to_list(length=len(missing)):
                users_by_id[u["_id"]] = u
        for cid in creator_ids:
            u = users_by_id.get(cid) or {}
            p = profile_by_uid.get(cid) or {}
            if not u and not p:
                continue
            creator_rows.append(
                {
                    "id": str(cid),
                    "label": p.get("name") or u.get("name") or "Unnamed creator",
                    # Staff-side, so the number is here on purpose: it is what
                    # somebody searched to find this person. It never crosses
                    # into a brand response — see _brand_visible_creator.
                    "sublabel": " · ".join(
                        [
                            s
                            for s in (
                                f"@{p['instagram_handle']}" if p.get("instagram_handle") else None,
                                u.get("phone"),
                                p.get("city"),
                            )
                            if s
                        ]
                    ),
                    "badge": p.get("verification_status") or "pending",
                    "href": f"/admin/creators/{cid}",
                }
            )

    brand_ids = {p["user_id"] for p in brand_profiles} | {u["_id"] for u in brand_users}
    brand_rows = []
    if brand_ids:
        profile_by_uid = {p["user_id"]: p for p in brand_profiles}
        accounts = {u["_id"]: u for u in brand_users}
        missing = [i for i in brand_ids if i not in accounts]
        if missing:
            for u in await db.users.find({"_id": {"$in": missing}}).to_list(length=len(missing)):
                accounts[u["_id"]] = u
        missing_p = [i for i in brand_ids if i not in profile_by_uid]
        if missing_p:
            for p in await db.brand_profiles.find(
                {"user_id": {"$in": missing_p}}
            ).to_list(length=len(missing_p)):
                profile_by_uid[p["user_id"]] = p
        for bid in list(brand_ids)[: SEARCH_GROUP_LIMIT * 2]:
            p = profile_by_uid.get(bid) or {}
            u = accounts.get(bid) or {}
            brand_rows.append(
                {
                    "id": str(bid),
                    "label": p.get("business_name") or u.get("name") or "Unnamed brand",
                    "sublabel": " · ".join(
                        [s for s in (p.get("contact_person_name"), u.get("phone"), p.get("category")) if s]
                    ),
                    "badge": "verified" if p.get("verified") else _brand_verification_state(p),
                    "href": f"/admin/brands/{bid}",
                }
            )

    brand_name_map = await _load_brand_map([c["brand_id"] for c in campaigns])
    campaign_rows = [
        {
            "id": str(c["_id"]),
            "label": c.get("title") or "Untitled",
            "sublabel": " · ".join(
                [
                    s
                    for s in (
                        (brand_name_map.get(c["brand_id"]) or {}).get("business_name"),
                        c.get("area"),
                    )
                    if s
                ]
            ),
            "badge": c.get("status"),
            "href": f"/admin/campaigns/{c['_id']}",
        }
        for c in campaigns
    ]

    groups = [
        g
        for g in (
            {"key": "creators", "label": "Creators", "items": creator_rows[:SEARCH_GROUP_LIMIT]},
            {"key": "brands", "label": "Brands", "items": brand_rows[:SEARCH_GROUP_LIMIT]},
            {"key": "campaigns", "label": "Campaigns", "items": campaign_rows},
        )
        if g["items"]
    ]
    return {
        "query": term,
        # Said out loud so the palette can explain an empty result for a number
        # that was typed short rather than one that matched nobody.
        "matched_phone": bool(tail),
        "groups": groups,
        "total": sum(len(g["items"]) for g in groups),
    }


async def _collab_or_404(collab_id: str) -> dict:
    oid = _as_oid(collab_id)
    collab = await db.collaborations.find_one({"_id": oid}) if oid else None
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    return collab


async def _build_campaign_report(campaign: dict) -> dict:
    """What a brand is handed when a campaign closes.

    The rule that shapes it: **it goes to the brand, so it carries what a brand
    may see.** Handles and follower counts are on the allow-list; a phone
    number, an email or an address is not, at any collaboration state. That is
    the same line `_brand_visible_creator` draws on every other brand-facing
    surface, and this file is the one most likely to be forwarded onwards.
    """
    cid = campaign["_id"]
    brand = (await _load_brand_map([campaign["brand_id"]])).get(campaign["brand_id"]) or {}

    # Only the people who actually delivered. A report listing everybody who
    # applied would describe a campaign that did not happen.
    collabs = await db.collaborations.find(
        {"campaign_id": cid, "state": {"$in": list(DELIVERED_COLLAB_STATES)}}
    ).to_list(length=500)
    creator_ids = [c["creator_id"] for c in collabs]
    profiles = {
        p["user_id"]: p
        for p in await db.creator_profiles.find(
            {"user_id": {"$in": creator_ids}}
        ).to_list(length=len(creator_ids) or 1)
    }
    users = {
        u["_id"]: u
        for u in await db.users.find({"_id": {"$in": creator_ids}}).to_list(
            length=len(creator_ids) or 1
        )
    }
    perf = {
        r["collaboration_id"]: r
        for r in await db.content_performance.find({"campaign_id": cid}).to_list(length=500)
    }
    payments = {
        p["collaboration_id"]: p
        for p in await db.payments.find(
            {"collaboration_id": {"$in": [c["_id"] for c in collabs]}}
        ).to_list(length=500)
    }

    spend = sum(
        float(p.get("creator_payout") or 0)
        for p in payments.values()
        if p.get("state") == "paid"
    )
    paid_ids = {
        cid_ for cid_, p in payments.items() if p.get("state") == "paid"
    }

    rows = []
    for c in collabs:
        prof = profiles.get(c["creator_id"]) or {}
        acct = users.get(c["creator_id"]) or {}
        r = perf.get(c["_id"]) or {}
        rows.append(
            {
                "collaboration_id": str(c["_id"]),
                "creator_name": prof.get("name") or acct.get("name"),
                "instagram_handle": prof.get("instagram_handle"),
                "youtube_url": prof.get("youtube_url"),
                "follower_count": prof.get("follower_count"),
                **_follower_provenance(prof),
                # What they were asked for, and the links that prove it.
                "deliverables": campaign.get("deliverables"),
                "content_urls": c.get("content_urls")
                or ([c["content_url"]] if c.get("content_url") else []),
                "delivered_state": c.get("state"),
                **{m: r.get(m) for m in PERFORMANCE_METRICS},
                "engagements": _engagements(r) if r else None,
                "engagement_rate": _engagement_rate_from(r) if r else None,
                "measured": bool(r),
                "measurement_source": r.get("source") if r else None,
                "captured_at": _iso(r.get("captured_at")) if r else None,
            }
        )
    rows.sort(key=lambda r: (r.get("reach") or 0), reverse=True)

    return {
        "campaign": {
            "id": str(cid),
            "title": campaign.get("title"),
            "brand_name": brand.get("business_name") or brand.get("name"),
            "brand_logo_url": brand.get("logo_url"),
            "category": campaign.get("category"),
            "area": campaign.get("area"),
            "status": campaign.get("status"),
            "compensation_type": _compensation_type(campaign),
            "campaign_type": campaign.get("campaign_type"),
            "event_date": _iso(campaign.get("event_date")),
            "start_date": _iso(campaign.get("start_date")),
            "end_date": _iso(campaign.get("end_date")),
            "deliverables": campaign.get("deliverables"),
            "showcase": bool(campaign.get("showcase")),
        },
        "creators": rows,
        "totals": _rollup_performance(
            list(perf.values()),
            paid_ids,
            spend,
            # One campaign, so it is barter or it is not.
            {c["_id"] for c in collabs}
            if _compensation_type(campaign) == "barter"
            else frozenset(),
        ),
        "generated_at": _iso(datetime.now(timezone.utc)),
    }


def _report_csv(report: dict) -> str:
    """The same report as a spreadsheet.

    `csv.writer` rather than joining with commas: a campaign title with a comma
    in it, or a note with a newline, would otherwise silently shift every
    column to its right.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    c = report["campaign"]
    t = report["totals"]

    w.writerow(["Campaign", c["title"]])
    w.writerow(["Brand", c["brand_name"] or ""])
    # Dates, not timestamps. This goes to a client, and "2026-09-01T00:00:00
    # +00:00" in a spreadsheet cell is us showing our working.
    w.writerow([
        "Dates",
        " to ".join([d[:10] for d in (c["start_date"], c["end_date"]) if d])
        or (c["event_date"] or "")[:10],
    ])
    w.writerow(["Deliverables", c["deliverables"] or ""])
    w.writerow([])
    w.writerow(["Creators delivered", t["creators_delivered"]])
    w.writerow(["Total reach", t["total_reach"]])
    w.writerow(["Total engagements", t["total_engagements"]])
    w.writerow(["Engagement rate %", t["engagement_rate"] if t["engagement_rate"] is not None else "—"])
    w.writerow(["Total spend (INR)", t["total_spend"]])
    w.writerow([
        "Cost per 1,000 reach (INR)",
        t["cost_per_thousand_reach"] if t["cost_per_thousand_reach"] is not None else "—",
    ])
    if t["barter_reach"]:
        # Said in the file itself, not just in the UI. A spreadsheet gets
        # forwarded without whatever was on screen beside it.
        n = t["barter_deliveries"]
        w.writerow([
            "Note",
            f"{n} barter {'delivery' if n == 1 else 'deliveries'} contributed "
            f"{t['barter_reach']:,} reach at no cost; cost per 1,000 is over paid work only.",
        ])
    w.writerow([])
    w.writerow([
        "Creator", "Instagram", "Followers", "Reach", "Impressions", "Views",
        "Likes", "Comments", "Saves", "Engagement rate %", "Measured", "Content",
    ])
    for r in report["creators"]:
        w.writerow([
            r["creator_name"] or "",
            f"@{r['instagram_handle']}" if r.get("instagram_handle") else "",
            r.get("follower_count") if r.get("follower_count") is not None else "",
            *[r.get(m) if r.get(m) is not None else "" for m in
              ("reach", "impressions", "views", "likes", "comments", "saves")],
            r["engagement_rate"] if r.get("engagement_rate") is not None else "",
            "yes" if r["measured"] else "no",
            " ".join(r["content_urls"]),
        ])
    return buf.getvalue()


def _report_html(report: dict) -> str:
    """A page to print, or to save as a PDF and send.

    Self-contained and light-on-white on purpose. The app is a dark product,
    but this is the one artefact that leaves it — it gets printed, pasted into
    a deck, and read on somebody else's laptop, and a near-black page prints as
    a solid block of toner.
    """
    c = report["campaign"]
    t = report["totals"]
    esc = html_escape

    def _num(v, suffix=""):
        return f"{v:,}{suffix}" if isinstance(v, (int, float)) else "—"

    dates = " – ".join([d[:10] for d in (c["start_date"], c["end_date"]) if d]) or (
        (c["event_date"] or "")[:10] or "—"
    )

    rows = "".join(
        f"""<tr>
          <td><strong>{esc(r['creator_name'] or 'Creator')}</strong>
            {f"<span class=h>@{esc(r['instagram_handle'])}</span>" if r.get('instagram_handle') else ""}</td>
          <td class=n>{_num(r.get('follower_count'))}</td>
          <td class=n>{_num(r.get('reach'))}</td>
          <td class=n>{_num(r.get('engagements'))}</td>
          <td class=n>{f"{r['engagement_rate']}%" if r.get('engagement_rate') is not None else '—'}</td>
          <td>{"".join(f'<a href="{esc(u)}">{esc(u[:60])}</a><br>' for u in r['content_urls']) or '—'}</td>
        </tr>"""
        for r in report["creators"]
    ) or '<tr><td colspan="6" class=e>Nobody has delivered on this campaign yet.</td></tr>'

    n_barter = t["barter_deliveries"]
    barter_note = (
        f"<p class=note>{n_barter} barter "
        f"{'delivery' if n_barter == 1 else 'deliveries'} contributed "
        f"{_num(t['barter_reach'])} reach at no cost. Cost per 1,000 reach is "
        f"calculated over paid work only.</p>"
        if t["barter_reach"]
        else ""
    )
    unmeasured = t["creators_delivered"] - t["with_reach"]
    measured_note = (
        f"<p class=note>{t['with_reach']} of {t['creators_delivered']} deliveries have "
        f"reach figures; {unmeasured} {'is' if unmeasured == 1 else 'are'} not yet "
        f"measured, so the totals are a floor.</p>"
        if unmeasured > 0
        else ""
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(c['title'] or 'Campaign report')} — WeAre Creators</title>
<style>
  :root {{ --ink:#141210; --mute:#6b6560; --line:#e6e1dc; --ember:#F05D14; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:48px 40px; background:#fff; color:var(--ink);
    font:15px/1.5 "Inter Tight",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  .eyebrow {{ font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--ember); }}
  h1 {{ font-family:Fraunces,Georgia,serif; font-size:38px; line-height:1.05; margin:12px 0 0; font-weight:400; }}
  .meta {{ color:var(--mute); font-size:13px; margin-top:10px; }}
  .stats {{ display:grid; grid-template-columns:repeat(3,1fr); margin:36px 0 8px;
    border:1px solid var(--line); border-right:0; border-bottom:0; }}
  .stat {{ background:#fff; padding:18px 16px;
    border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
  @media (min-width:760px) {{ .stats {{ grid-template-columns:repeat(6,1fr); }} }}
  .stat span {{ display:block; font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:var(--mute); }}
  .stat b {{ display:block; font-family:Fraunces,Georgia,serif; font-size:26px; font-weight:400; margin-top:8px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:32px; font-size:13px; }}
  th {{ text-align:left; font-size:10px; letter-spacing:.15em; text-transform:uppercase;
    color:var(--mute); font-weight:500; padding:0 10px 8px; border-bottom:1px solid var(--line); }}
  td {{ padding:12px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  td.n {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  td.e {{ text-align:center; color:var(--mute); padding:32px; }}
  .h {{ color:var(--mute); margin-left:8px; }}
  a {{ color:var(--ember); word-break:break-all; }}
  .note {{ color:var(--mute); font-size:12px; margin:6px 0 0; }}
  footer {{ margin-top:48px; padding-top:16px; border-top:1px solid var(--line);
    color:var(--mute); font-size:11px; display:flex; justify-content:space-between; gap:20px; }}
  @media print {{ body {{ padding:0; }} a {{ color:var(--ink); }} }}
</style></head>
<body><div class=wrap>
  <p class=eyebrow>Campaign report · {esc(c['brand_name'] or '')}</p>
  <h1>{esc(c['title'] or 'Campaign')}</h1>
  <p class=meta>{esc(dates)}{f" · {esc(c['area'])}" if c.get('area') else ""}
    {f" · {esc(c['category'])}" if c.get('category') else ""}</p>

  <div class=stats>
    <div class=stat><span>Creators delivered</span><b>{_num(t['creators_delivered'])}</b></div>
    <div class=stat><span>Total reach</span><b>{_num(t['total_reach'])}</b></div>
    <div class=stat><span>Engagements</span><b>{_num(t['total_engagements'])}</b></div>
    <div class=stat><span>Engagement rate</span><b>{f"{t['engagement_rate']}%" if t['engagement_rate'] is not None else '—'}</b></div>
    <div class=stat><span>Spend</span><b>{"₹" + format(int(t['total_spend']), ",") if t['total_spend'] else '—'}</b></div>
    <div class=stat><span>Cost / 1,000 reach</span><b>{"₹" + format(round(t['cost_per_thousand_reach']), ",") if t['cost_per_thousand_reach'] is not None else '—'}</b></div>
  </div>
  {barter_note}{measured_note}

  <table>
    <thead><tr><th>Creator</th><th class=n>Followers</th><th class=n>Reach</th>
      <th class=n>Engagements</th><th class=n>Rate</th><th>Content</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <p class=note style="margin-top:28px"><strong>Deliverables:</strong> {esc(c['deliverables'] or '—')}</p>

  <footer><span>WeAre Creators</span><span>Generated {esc((report['generated_at'] or '')[:10])}</span></footer>
</div></body></html>"""


class ShowcasePayload(BaseModel):
    """Mark a campaign as case-study material."""

    showcase: bool
    note: Optional[str] = Field(default=None, max_length=300)


# ---------------------------------------------------------------------------
# Health
#
# The console tells you what is waiting. This tells you what is *going wrong* —
# the difference being that nothing here is in a queue. A campaign quietly
# underfilling four days before the shoot generates no notification, appears in
# no list, and is discovered when the brand rings up.
#
# Every threshold is named here rather than inlined, because every one of them
# is a judgement about how much slack the operation has and will be argued
# about later.
# ---------------------------------------------------------------------------

# A campaign is worth flagging when the shoot is close and the roster is short.
FILL_WARNING_DAYS = 7          # how close "close" is
FILL_WARNING_RATIO = 0.7       # below this share of the brief, it is short
# Somebody accepted onto a campaign who still has no slot, this near the day.
SLOT_WARNING_DAYS = 2
# Attended, and no content since. A creator needs a few days to edit and post.
CONTENT_OVERDUE_DAYS = 7
# Approved work with money still sitting here.
PAYMENT_OVERDUE_DAYS = 7
# A brand that submitted documents and heard nothing.
VERIFICATION_OVERDUE_DAYS = 3
# Signed up, started a profile, and stopped.
PROFILE_STALE_DAYS = 14

# Severity drives the order things are read in, not the colour. `critical`
# means a brand or creator is about to be let down; `warning` means somebody
# will be if nothing happens.
_HEALTH_ORDER = {"critical": 0, "warning": 1}


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def _days_ahead(n: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=n)


@admin_router.get("/health")
async def admin_health(user: dict = Depends(require_roles("admin"))):
    """What is going wrong, before anybody outside finds out.

    Six checks, each returning rows that link straight to the thing that needs
    doing. Deliberately not a count — a number tells you there is a problem and
    then makes you go and find it.

    Declared before `/{campaign_id}`-shaped siblings cannot swallow it: this is
    `/admin/health`, one segment, and there is no bare `/admin/{id}`.
    """
    now = datetime.now(timezone.utc)
    checks: list = []

    # 1. Underfilling with the day approaching.
    soon = _days_ahead(FILL_WARNING_DAYS)
    live = await db.campaigns.find(
        {
            "status": {"$in": list(ACTIVE_CAMPAIGN_STATUSES)},
            "$or": [
                {"event_date": {"$gte": now, "$lte": soon}},
                {"start_date": {"$gte": now, "$lte": soon}},
            ],
        }
    ).to_list(length=500)
    filled = await _filled_counts_for([c["_id"] for c in live])
    rows = []
    for c in live:
        needed = int(c.get("creators_needed") or 1)
        got = filled.get(c["_id"], 0)
        if needed and got / needed < FILL_WARNING_RATIO:
            when = c.get("event_date") or c.get("start_date")
            rows.append(
                {
                    "id": str(c["_id"]),
                    "label": c.get("title") or "Untitled",
                    "detail": f"{got} of {needed} booked · {_humanise_until(when, now)}",
                    "href": f"/admin/campaigns/{c['_id']}",
                    # Nothing booked at all, this close, is a different problem
                    # from being two short.
                    "severity": "critical" if got == 0 else "warning",
                    "at": _iso(when),
                }
            )
    checks.append(
        {
            "key": "underfilling",
            "label": "Campaigns underfilling",
            "blurb": f"Under {int(FILL_WARNING_RATIO * 100)}% booked with under {FILL_WARNING_DAYS} days to go.",
            "items": rows,
        }
    )

    # 2. Accepted, agreed, and still no slot with the day nearly here.
    slot_cutoff = _days_ahead(SLOT_WARNING_DAYS)
    near = await db.campaigns.find(
        {
            "status": {"$in": list(ACTIVE_CAMPAIGN_STATUSES)},
            "$or": [
                {"event_date": {"$gte": now, "$lte": slot_cutoff}},
                {"end_date": {"$gte": now, "$lte": slot_cutoff}},
            ],
        }
    ).to_list(length=500)
    near_by_id = {c["_id"]: c for c in near}
    rows = []
    if near_by_id:
        unbooked = await db.collaborations.find(
            {
                "campaign_id": {"$in": list(near_by_id)},
                "state": {"$in": ["accepted", "commercial_agreed"]},
                "slot_id": None,
            }
        ).to_list(length=1000)
        names = await _creator_names_for([c["creator_id"] for c in unbooked])
        for c in unbooked:
            camp = near_by_id[c["campaign_id"]]
            when = camp.get("event_date") or camp.get("end_date")
            rows.append(
                {
                    "id": str(c["_id"]),
                    "label": names.get(c["creator_id"]) or "Creator",
                    "detail": f"{camp.get('title')} · no slot · {_humanise_until(when, now)}",
                    "href": f"/admin/collaborations/{c['_id']}",
                    "severity": "critical",
                    "at": _iso(when),
                }
            )
    checks.append(
        {
            "key": "no_slot",
            "label": "No slot booked",
            "blurb": f"Accepted creators with nothing booked, within {SLOT_WARNING_DAYS} days of the day.",
            "items": rows,
        }
    )

    # 3. Turned up, never posted.
    overdue = await db.collaborations.find(
        {"state": "attended", "updated_at": {"$lte": _days_ago(CONTENT_OVERDUE_DAYS)}}
    ).to_list(length=500)
    names = await _creator_names_for([c["creator_id"] for c in overdue])
    camp_titles = await _campaign_titles_for([c["campaign_id"] for c in overdue])
    checks.append(
        {
            "key": "content_overdue",
            "label": "Content overdue",
            "blurb": f"Attended more than {CONTENT_OVERDUE_DAYS} days ago with nothing submitted.",
            "items": [
                {
                    "id": str(c["_id"]),
                    "label": names.get(c["creator_id"]) or "Creator",
                    "detail": f"{camp_titles.get(c['campaign_id']) or 'Campaign'} · attended {timeago_days(c.get('updated_at'), now)}",
                    "href": f"/admin/collaborations/{c['_id']}",
                    "severity": "warning",
                    "at": _iso(c.get("updated_at")),
                }
                for c in overdue
            ],
        }
    )

    # 4. Money we are sitting on.
    stale_pay = await db.payments.find(
        {"state": {"$ne": "paid"}, "created_at": {"$lte": _days_ago(PAYMENT_OVERDUE_DAYS)}}
    ).sort("created_at", 1).to_list(length=500)
    pay_collabs = {
        c["_id"]: c
        for c in await db.collaborations.find(
            {"_id": {"$in": [p["collaboration_id"] for p in stale_pay]}}
        ).to_list(length=len(stale_pay) or 1)
    }
    pay_names = await _creator_names_for([c["creator_id"] for c in pay_collabs.values()])
    checks.append(
        {
            "key": "payments_pending",
            "label": "Payments pending",
            "blurb": f"Raised more than {PAYMENT_OVERDUE_DAYS} days ago and still not sent.",
            "items": [
                {
                    "id": str(p["_id"]),
                    "label": pay_names.get(
                        (pay_collabs.get(p["collaboration_id"]) or {}).get("creator_id")
                    )
                    or "Creator",
                    "detail": f"₹{p.get('creator_payout') or 0:,.0f} · raised {timeago_days(p.get('created_at'), now)}",
                    "href": f"/admin/collaborations/{p['collaboration_id']}",
                    # Creators chase us for this, and it is the fastest way to
                    # lose one.
                    "severity": "critical",
                    "at": _iso(p.get("created_at")),
                }
                for p in stale_pay
            ],
        }
    )

    # 5. Brands waiting on a decision from us.
    waiting = await db.brand_profiles.find(
        {
            "verified": False,
            "verification_state": "pending_verification",
            "submitted_for_verification_at": {"$lte": _days_ago(VERIFICATION_OVERDUE_DAYS)},
        }
    ).sort("submitted_for_verification_at", 1).to_list(length=200)
    checks.append(
        {
            "key": "verification_overdue",
            "label": "Brands waiting on us",
            "blurb": f"Documents submitted more than {VERIFICATION_OVERDUE_DAYS} days ago.",
            "items": [
                {
                    "id": str(b["user_id"]),
                    "label": b.get("business_name") or "Unnamed brand",
                    "detail": f"submitted {timeago_days(b.get('submitted_for_verification_at'), now)}",
                    "href": f"/admin/brands/{b['user_id']}",
                    "severity": "warning",
                    "at": _iso(b.get("submitted_for_verification_at")),
                }
                for b in waiting
            ],
        }
    )

    # 6. Creators who started and stopped. Not a failure on their part — it is
    # the signal that onboarding lost somebody, and each one is a person we
    # could still get over the line.
    stalled = await db.creator_profiles.find(
        {
            "verification_status": "pending",
            "submitted_for_review_at": {"$in": [None, False], "$exists": False},
            "updated_at": {"$lte": _days_ago(PROFILE_STALE_DAYS)},
        }
    ).sort("updated_at", 1).to_list(length=200)
    checks.append(
        {
            "key": "profiles_stalled",
            "label": "Profiles stalled",
            "blurb": f"Started a profile, never submitted it, quiet for {PROFILE_STALE_DAYS}+ days.",
            "items": [
                {
                    "id": str(p["user_id"]),
                    "label": p.get("name") or "Unnamed",
                    "detail": (
                        f"{_profile_completeness(p).get('percent', 0)}% complete · "
                        f"last touched {timeago_days(p.get('updated_at'), now)}"
                    ),
                    "href": f"/admin/creators/{p['user_id']}",
                    "severity": "warning",
                    "at": _iso(p.get("updated_at")),
                }
                for p in stalled
            ],
        }
    )

    for c in checks:
        c["items"].sort(key=lambda i: (_HEALTH_ORDER.get(i["severity"], 9), i.get("at") or ""))
        c["count"] = len(c["items"])
        c["critical"] = sum(1 for i in c["items"] if i["severity"] == "critical")

    return {
        "checks": checks,
        "total": sum(c["count"] for c in checks),
        "critical": sum(c["critical"] for c in checks),
        "generated_at": _iso(now),
        # Returned so the UI can say "under 70% with 7 days to go" rather than
        # hard-coding numbers that then drift from the server's.
        "thresholds": {
            "fill_warning_days": FILL_WARNING_DAYS,
            "fill_warning_ratio": FILL_WARNING_RATIO,
            "slot_warning_days": SLOT_WARNING_DAYS,
            "content_overdue_days": CONTENT_OVERDUE_DAYS,
            "payment_overdue_days": PAYMENT_OVERDUE_DAYS,
            "verification_overdue_days": VERIFICATION_OVERDUE_DAYS,
            "profile_stale_days": PROFILE_STALE_DAYS,
        },
    }


# ---------------------------------------------------------------------------
# Exports
#
# **Where the contact-details line falls.** An admin export is an internal
# document: it goes to accounting, or to somebody reconciling a bank statement,
# and a payout row without a phone number to chase is useless. So creator
# contact details are allowed here — and this is the *only* family of responses
# where that is true.
#
# `_ADMIN_ONLY_CONTACT_COLUMNS` names them, in one place, so that "which
# columns are the sensitive ones" is a question with an answer rather than a
# reading exercise. `tests/unit/test_exports.py` walks the real output of every
# brand-facing builder for these same values, so the boundary is checked
# against what is actually emitted rather than against what the code looks
# like it emits.
# ---------------------------------------------------------------------------

_ADMIN_ONLY_CONTACT_COLUMNS = ("Phone", "Email", "Address", "UPI", "PAN", "GSTIN")


def _csv_response(rows: list, headers: list, filename: str) -> Response:
    """Rows to a downloadable file.

    Through `csv.writer` so a note with a comma or a business name with a
    newline cannot shift every column to its right — the failure mode that
    makes a spreadsheet look fine and be wrong.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # These carry phone numbers and payout figures. Not something to
            # leave in a shared browser cache.
            "Cache-Control": "no-store",
        },
    )


def _export_window(date_from: Optional[datetime], date_to: Optional[datetime], field: str) -> dict:
    if not date_from and not date_to:
        return {}
    window: dict = {}
    if date_from:
        window["$gte"] = date_from
    if date_to:
        window["$lte"] = date_to
    return {field: window}


def _stamp(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv"


@admin_router.get("/exports/{kind}")
async def admin_export(
    kind: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    brand_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    q: Optional[str] = None,
    action: Optional[str] = None,
    user: dict = Depends(require_roles("admin")),
):
    """Six exports, one route.

    One route rather than six because they share the whole preamble — the date
    window, the filters, the CSV framing, the audit line — and six copies of
    that is six places for the `no-store` header to be forgotten.

    Every export is audited. A file of creators' phone numbers leaving the
    system is exactly the event the log exists to record.
    """
    if kind not in EXPORT_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown export. One of: {', '.join(EXPORT_KINDS)}.",
        )
    builder = globals()[f"_export_{kind}"]
    rows, headers = await builder(
        date_from=date_from,
        date_to=date_to,
        status=status,
        brand_id=_as_oid(brand_id) if brand_id else None,
        campaign_id=_as_oid(campaign_id) if campaign_id else None,
        q=q,
        action=action,
    )
    await audit(
        user,
        f"export.{kind}",
        "export",
        kind,
        after={
            "rows": len(rows),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            # Named so the log says which slice left, not merely that one did.
            "filters": {
                k: v
                for k, v in (
                    ("status", status), ("brand_id", brand_id),
                    ("campaign_id", campaign_id), ("q", q), ("action", action),
                )
                if v
            },
            "includes_contact_details": kind in EXPORTS_WITH_CONTACT,
        },
    )
    return _csv_response(rows, headers, _stamp(kind))


EXPORT_KINDS = (
    "creators", "brands", "campaigns", "collaborations", "payments", "audit",
)
# Which of them carry a way to reach somebody. Named so the audit line can say
# so, and so a reviewer can see the answer without reading six builders.
EXPORTS_WITH_CONTACT = ("creators", "brands", "collaborations", "payments")


async def _export_creators(*, date_from, date_to, status, q, **_):
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if status:
        query["verification_status"] = status
    if q:
        query["name"] = {"$regex": re.escape(q[:120]), "$options": "i"}
    profiles = await db.creator_profiles.find(query).sort("created_at", -1).to_list(length=10000)
    accounts = {
        u["_id"]: u
        for u in await db.users.find(
            {"_id": {"$in": [p["user_id"] for p in profiles]}}
        ).to_list(length=len(profiles) or 1)
    }
    stats = await _creator_activity_stats([p["user_id"] for p in profiles])
    headers = [
        "Creator ID", "Name", "Phone", "Email", "City", "Address",
        "Instagram", "Followers", "Follower source", "Niches", "Base rate",
        "Verification", "Payout ready", "UPI", "PAN", "Completed", "Ongoing",
        "Lifetime earned", "Joined",
    ]
    rows = []
    for p in profiles:
        u = accounts.get(p["user_id"], {})
        s = stats.get(p["user_id"], {})
        rows.append([
            str(p["user_id"]), p.get("name") or u.get("name") or "",
            u.get("phone") or "", p.get("email") or u.get("email") or "",
            p.get("city") or "", p.get("full_address") or p.get("address") or "",
            f"@{p['instagram_handle']}" if p.get("instagram_handle") else "",
            p.get("follower_count") if p.get("follower_count") is not None else "",
            _follower_provenance(p)["follower_count_source"],
            ", ".join(p.get("niches") or []),
            p.get("base_rate") if p.get("base_rate") is not None else "",
            p.get("verification_status") or "pending",
            "yes" if payout_ready(p) else "no",
            p.get("payout_upi") or "", p.get("pan") or "",
            s.get("completed", 0), s.get("ongoing", 0),
            round(float(s.get("earned", 0) or 0), 2),
            _iso(p.get("created_at")) or "",
        ])
    return rows, headers


async def _export_brands(*, date_from, date_to, status, q, **_):
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if status:
        query["verification_state"] = status
    if q:
        query["business_name"] = {"$regex": re.escape(q[:120]), "$options": "i"}
    profiles = await db.brand_profiles.find(query).sort("created_at", -1).to_list(length=10000)
    ids = [p["user_id"] for p in profiles]
    accounts = {
        u["_id"]: u for u in await db.users.find({"_id": {"$in": ids}}).to_list(length=len(ids) or 1)
    }
    spend = await _brand_spend_map(ids)
    counts: dict = {}
    async for row in db.campaigns.aggregate(
        [{"$match": {"brand_id": {"$in": ids}}}, {"$group": {"_id": "$brand_id", "n": {"$sum": 1}}}]
    ):
        counts[row["_id"]] = row["n"]
    headers = [
        "Brand ID", "Business", "Legal entity", "Type", "GST", "Category",
        "Address", "Manager", "Designation", "Phone", "Email", "Website",
        "Verification", "Campaigns", "Total spend", "Paid collaborations", "Signed up",
    ]
    rows = []
    for p in profiles:
        u = accounts.get(p["user_id"], {})
        s = spend.get(p["user_id"]) or {}
        rows.append([
            str(p["user_id"]), p.get("business_name") or "", p.get("legal_entity_name") or "",
            p.get("business_type") or "", p.get("gst_number") or "", p.get("category") or "",
            p.get("registered_address") or "",
            u.get("manager_name") or u.get("name") or "",
            p.get("contact_person_designation") or "",
            u.get("phone") or "", p.get("contact_email") or u.get("email") or "",
            p.get("website") or "", _brand_verification_state(p),
            counts.get(p["user_id"], 0),
            round(float(s.get("spend", 0) or 0), 2), s.get("paid_collaborations", 0),
            _iso(u.get("created_at")) or "",
        ])
    return rows, headers


async def _export_campaigns(*, date_from, date_to, status, brand_id, q, **_):
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if status:
        query["status"] = status
    if brand_id:
        query["brand_id"] = brand_id
    if q:
        query["title"] = {"$regex": re.escape(q[:120]), "$options": "i"}
    docs = await db.campaigns.find(query).sort("created_at", -1).to_list(length=10000)
    brands = await _load_brand_map([d["brand_id"] for d in docs])
    filled = await _filled_counts_for([d["_id"] for d in docs])
    perf = {
        r["campaign_id"]: r
        for r in await db.content_performance.find(
            {"campaign_id": {"$in": [d["_id"] for d in docs]}}
        ).to_list(length=10000)
    }
    headers = [
        "Campaign ID", "Title", "Brand", "Status", "Compensation", "Budget per creator",
        "Category", "Area", "Type", "Needed", "Filled", "Fill rate %",
        "Manager", "Showcase", "Event date", "Start", "End", "Created",
    ]
    rows = []
    for d in docs:
        needed = int(d.get("creators_needed") or 1)
        got = filled.get(d["_id"], 0)
        rows.append([
            str(d["_id"]), d.get("title") or "",
            (brands.get(d["brand_id"]) or {}).get("business_name") or "",
            d.get("status") or "", _compensation_type(d),
            d.get("budget_per_creator") if d.get("budget_per_creator") is not None else "",
            d.get("category") or "", d.get("area") or "", d.get("campaign_type") or "",
            needed, got, round(got / needed * 100, 1) if needed else "",
            d.get("manager_name") or "", "yes" if d.get("showcase") else "no",
            (_iso(d.get("event_date")) or "")[:10], (_iso(d.get("start_date")) or "")[:10],
            (_iso(d.get("end_date")) or "")[:10], _iso(d.get("created_at")) or "",
        ])
    return rows, headers


async def _export_collaborations(*, date_from, date_to, status, campaign_id, brand_id, **_):
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if status:
        query["state"] = status
    if campaign_id:
        query["campaign_id"] = campaign_id
    if brand_id:
        # Filtering by brand means going through their campaigns first.
        ids = await db.campaigns.distinct("_id", {"brand_id": brand_id})
        query["campaign_id"] = {"$in": ids}
    docs = await db.collaborations.find(query).sort("created_at", -1).to_list(length=20000)
    campaigns = {
        c["_id"]: c
        for c in await db.campaigns.find(
            {"_id": {"$in": [d["campaign_id"] for d in docs]}}
        ).to_list(length=len(docs) or 1)
    }
    brands = await _load_brand_map([c["brand_id"] for c in campaigns.values()])
    creator_ids = [d["creator_id"] for d in docs]
    names = await _creator_names_for(creator_ids)
    accounts = {
        u["_id"]: u
        for u in await db.users.find({"_id": {"$in": list(set(creator_ids))}}).to_list(
            length=len(creator_ids) or 1
        )
    }
    perf = {
        r["collaboration_id"]: r
        for r in await db.content_performance.find(
            {"collaboration_id": {"$in": [d["_id"] for d in docs]}}
        ).to_list(length=len(docs) or 1)
    }
    headers = [
        "Collaboration ID", "Campaign", "Brand", "Creator", "Phone", "State",
        "Quoted", "Agreed", "Scheduled", "Content", "Reach", "Engagements",
        "Engagement rate %", "Created", "Updated",
    ]
    rows = []
    for d in docs:
        camp = campaigns.get(d["campaign_id"]) or {}
        r = perf.get(d["_id"]) or {}
        rows.append([
            str(d["_id"]), camp.get("title") or "",
            (brands.get(camp.get("brand_id")) or {}).get("business_name") or "",
            names.get(d["creator_id"]) or "",
            (accounts.get(d["creator_id"]) or {}).get("phone") or "",
            d.get("state") or "",
            d.get("quoted_rate") if d.get("quoted_rate") is not None else "",
            d.get("agreed_amount") if d.get("agreed_amount") is not None else "",
            _iso(d.get("scheduled_at")) or "",
            " ".join(d.get("content_urls") or ([d["content_url"]] if d.get("content_url") else [])),
            r.get("reach") if r.get("reach") is not None else "",
            _engagements(r) if r else "",
            _engagement_rate_from(r) if r else "",
            _iso(d.get("created_at")) or "", _iso(d.get("updated_at")) or "",
        ])
    return rows, headers


async def _export_payments(*, date_from, date_to, status, brand_id, campaign_id, **_):
    """The accounting export.

    Everything needed to reconcile a bank statement without opening the app:
    who was paid, for which brief, for which brand, what we charged on top,
    what the invoice is doing, and when each of those happened. If somebody has
    to come back and ask "which campaign was this?", the export has failed.
    """
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if status:
        query["state"] = status
    docs = await db.payments.find(query).sort("created_at", -1).to_list(length=20000)
    collabs = {
        c["_id"]: c
        for c in await db.collaborations.find(
            {"_id": {"$in": [d["collaboration_id"] for d in docs]}}
        ).to_list(length=len(docs) or 1)
    }
    campaigns = {
        c["_id"]: c
        for c in await db.campaigns.find(
            {"_id": {"$in": [c["campaign_id"] for c in collabs.values()]}}
        ).to_list(length=len(collabs) or 1)
    }
    if brand_id:
        campaigns = {k: v for k, v in campaigns.items() if v.get("brand_id") == brand_id}
    if campaign_id:
        campaigns = {k: v for k, v in campaigns.items() if k == campaign_id}
    brands = await _load_brand_map([c["brand_id"] for c in campaigns.values()])
    creator_ids = [c["creator_id"] for c in collabs.values()]
    names = await _creator_names_for(creator_ids)
    profiles = {
        p["user_id"]: p
        for p in await db.creator_profiles.find(
            {"user_id": {"$in": list(set(creator_ids))}}
        ).to_list(length=len(creator_ids) or 1)
    }
    accounts = {
        u["_id"]: u
        for u in await db.users.find({"_id": {"$in": list(set(creator_ids))}}).to_list(
            length=len(creator_ids) or 1
        )
    }
    headers = [
        "Payment ID", "State", "Campaign", "Campaign ID", "Brand", "Creator",
        "Phone", "UPI", "PAN", "GSTIN", "Agreed amount", "Platform fee",
        "Creator payout", "Brand invoice amount", "Invoice state", "Reference",
        "Raised", "Paid", "Collaboration ID",
    ]
    rows = []
    for d in docs:
        collab = collabs.get(d["collaboration_id"]) or {}
        camp = campaigns.get(collab.get("campaign_id"))
        if (brand_id or campaign_id) and camp is None:
            continue
        camp = camp or {}
        cid = collab.get("creator_id")
        prof = profiles.get(cid) or {}
        rows.append([
            str(d["_id"]), d.get("state") or "", camp.get("title") or "",
            str(camp.get("_id")) if camp.get("_id") else "",
            (brands.get(camp.get("brand_id")) or {}).get("business_name") or "",
            names.get(cid) or "",
            (accounts.get(cid) or {}).get("phone") or "",
            prof.get("payout_upi") or "", prof.get("pan") or "", prof.get("gstin") or "",
            collab.get("agreed_amount") if collab.get("agreed_amount") is not None else "",
            d.get("platform_fee") if d.get("platform_fee") is not None else "",
            d.get("creator_payout") if d.get("creator_payout") is not None else "",
            d.get("brand_invoice_amount") if d.get("brand_invoice_amount") is not None else "",
            d.get("invoice_state") or "", d.get("reference") or "",
            _iso(d.get("created_at")) or "", _iso(d.get("paid_at")) or "",
            str(d["collaboration_id"]),
        ])
    return rows, headers


async def _export_audit(*, date_from, date_to, brand_id, campaign_id, action, q, **_):
    query: dict = {**_export_window(date_from, date_to, "created_at")}
    if brand_id:
        query["brand_id"] = brand_id
    if campaign_id:
        query["campaign_id"] = campaign_id
    if action:
        term = action.strip()[:80]
        query["action"] = term if "." in term else {"$regex": f"^{re.escape(term)}\\.", "$options": "i"}
    if q:
        query["actor_name"] = {"$regex": re.escape(q[:120]), "$options": "i"}
    docs = await db.audit_log.find(query).sort("created_at", -1).to_list(length=20000)
    headers = [
        "When", "Actor", "Role", "Action", "Subject type", "Subject ID",
        "Brand ID", "Campaign ID", "Note", "Before", "After",
    ]
    rows = [
        [
            _iso(d.get("created_at")) or "", d.get("actor_name") or "",
            d.get("actor_role") or "", d.get("action") or "",
            d.get("subject_type") or "", str(d.get("subject_id") or ""),
            str(d.get("brand_id") or ""), str(d.get("campaign_id") or ""),
            d.get("note") or "",
            json.dumps(_jsonable(d.get("before")), default=str) if d.get("before") else "",
            json.dumps(_jsonable(d.get("after")), default=str) if d.get("after") else "",
        ]
        for d in docs
    ]
    return rows, headers


# How far back the trend charts look, and how long a creator can be quiet
# before we stop calling them active. 60 days because a creator doing one
# campaign a quarter is still a creator.
INTELLIGENCE_WEEKS = 12
DORMANT_AFTER_DAYS = 60


@admin_router.get("/intelligence")
async def admin_intelligence(user: dict = Depends(require_roles("admin"))):
    """Four small shapes, deliberately.

    Not an analytics product: four questions somebody actually asks about the
    business, each answerable from a chart small enough to sit beside the
    others. Anything that needs a legend to read is out of scope here — that is
    what the exports are for.
    """
    now = datetime.now(timezone.utc)
    since = _days_ago(INTELLIGENCE_WEEKS * 7)

    # Weekly buckets, oldest first. Built here rather than in the pipeline so
    # a week with nothing in it is still a point on the line — a chart that
    # silently skips empty weeks draws a lie.
    weeks: list = []
    cursor = since
    while cursor <= now:
        weeks.append(cursor)
        cursor += timedelta(days=7)

    def _bucket(when: Optional[datetime]) -> Optional[int]:
        if not isinstance(when, datetime):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < since:
            return None
        idx = (when - since).days // 7
        return idx if 0 <= idx < len(weeks) else None

    campaigns = await db.campaigns.find(
        {}, {"status": 1, "created_at": 1, "brand_id": 1, "creators_needed": 1}
    ).to_list(length=5000)

    # 1. Campaigns created per week, split by where they ended up. Status is
    # current, not historical — this says "of the briefs posted that week, how
    # many are live now", which is the question worth asking of a young
    # marketplace.
    by_status: dict = {}
    for c in campaigns:
        b = _bucket(c.get("created_at"))
        if b is None:
            continue
        by_status.setdefault(c.get("status") or "draft", [0] * len(weeks))[b] += 1

    # 2. Fill rate of campaigns that reached their day, per week.
    filled = await _filled_counts_for([c["_id"] for c in campaigns])
    fill_num = [0] * len(weeks)
    fill_den = [0] * len(weeks)
    for c in campaigns:
        b = _bucket(c.get("created_at"))
        if b is None:
            continue
        needed = int(c.get("creators_needed") or 0)
        if not needed:
            continue
        fill_num[b] += min(filled.get(c["_id"], 0), needed)
        fill_den[b] += needed
    fill_rate = [
        round(fill_num[i] / fill_den[i] * 100, 1) if fill_den[i] else None
        for i in range(len(weeks))
    ]

    # 3. Repeat brands versus new. A brand is "repeat" from its second campaign
    # onwards, so the split answers "are they coming back", which is the only
    # question that matters about a marketplace's brand side.
    per_brand: dict = {}
    for c in campaigns:
        per_brand.setdefault(c["brand_id"], []).append(c.get("created_at"))
    repeat = sum(1 for v in per_brand.values() if len(v) > 1)
    brand_total = len(per_brand)

    # 4. Creators active versus dormant. Active = applied to something, or was
    # moved along on something, inside the window.
    dormant_cutoff = _days_ago(DORMANT_AFTER_DAYS)
    active_ids = set(
        await db.collaborations.distinct(
            "creator_id", {"updated_at": {"$gte": dormant_cutoff}}
        )
    )
    verified_total = await db.creator_profiles.count_documents(
        {"verification_status": "verified"}
    )
    verified_ids = set(
        await db.creator_profiles.distinct("user_id", {"verification_status": "verified"})
    )
    active_verified = len(active_ids & verified_ids)

    return {
        "weeks": [_iso(w) for w in weeks],
        "campaigns_by_status": [
            {"status": k, "points": v}
            for k, v in sorted(by_status.items(), key=lambda kv: -sum(kv[1]))
        ],
        "fill_rate": fill_rate,
        "brands": {
            "repeat": repeat,
            "new": brand_total - repeat,
            "total": brand_total,
        },
        "creators": {
            "active": active_verified,
            "dormant": max(0, verified_total - active_verified),
            "total": verified_total,
            "window_days": DORMANT_AFTER_DAYS,
        },
        "window_weeks": INTELLIGENCE_WEEKS,
        "generated_at": _iso(now),
    }


async def _creator_names_for(user_ids: list) -> dict:
    ids = [i for i in set(user_ids) if i]
    if not ids:
        return {}
    profiles = await db.creator_profiles.find(
        {"user_id": {"$in": ids}}, {"user_id": 1, "name": 1}
    ).to_list(length=len(ids))
    by_id = {p["user_id"]: p.get("name") for p in profiles if p.get("name")}
    missing = [i for i in ids if i not in by_id]
    if missing:
        for u in await db.users.find({"_id": {"$in": missing}}, {"name": 1}).to_list(
            length=len(missing)
        ):
            by_id[u["_id"]] = u.get("name")
    return by_id


async def _campaign_titles_for(campaign_ids: list) -> dict:
    ids = [i for i in set(campaign_ids) if i]
    if not ids:
        return {}
    return {
        c["_id"]: c.get("title")
        for c in await db.campaigns.find({"_id": {"$in": ids}}, {"title": 1}).to_list(
            length=len(ids)
        )
    }


def _humanise_until(when: Optional[datetime], now: datetime) -> str:
    """"in 3 days", "tomorrow", "today". Read at a glance on a panel that
    exists to be scanned."""
    if not isinstance(when, datetime):
        return "date unknown"
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    days = (when - now).days
    if days < 0:
        return "already started"
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def timeago_days(when: Optional[datetime], now: datetime) -> str:
    if not isinstance(when, datetime):
        return "at some point"
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    days = max(0, (now - when).days)
    return "today" if days == 0 else f"{days}d ago"


@admin_router.get("/campaigns/{campaign_id}/report")
async def campaign_report(
    campaign_id: str,
    format: str = "json",
    user: dict = Depends(require_roles("admin")),
):
    """The close-of-campaign summary, in whichever shape is being asked for.

    Three formats off one builder, so the spreadsheet and the printable page
    cannot come to different totals. `json` feeds the console's own preview.

    Authenticated, deliberately. "Shareable" here means an admin opens it,
    prints it to a PDF and sends that — not a public link. A public one would
    be a new unauthenticated surface carrying creator handles and follower
    counts, and that is a decision to take on purpose rather than as a side
    effect of adding an export.

    **Declared before `/campaigns/{id}` would swallow it** — see the route
    ordering test.
    """
    campaign = await _admin_campaign_or_404(campaign_id)
    report = await _build_campaign_report(campaign)
    slug = re.sub(r"[^a-z0-9]+", "-", (campaign.get("title") or "campaign").lower()).strip("-")[:60]

    if format == "csv":
        return Response(
            content=_report_csv(report),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{slug or "campaign"}-report.csv"',
                "Cache-Control": "no-store",
            },
        )
    if format == "html":
        return Response(
            content=_report_html(report),
            media_type="text/html; charset=utf-8",
            # It names creators and their reach. Not something to leave in a
            # shared browser cache.
            headers={"Cache-Control": "no-store"},
        )
    if format != "json":
        raise HTTPException(status_code=422, detail="format must be json, csv or html.")
    return report


@admin_router.post("/campaigns/{campaign_id}/showcase")
async def set_campaign_showcase(
    campaign_id: str,
    payload: ShowcasePayload,
    user: dict = Depends(require_roles("admin")),
):
    """Flag a campaign as one worth showing people.

    Its own endpoint rather than a field on the campaign edit payload: that one
    is shared with the brand's edit route, and which of our campaigns we put in
    front of a prospect is not a brand's decision to make.
    """
    campaign = await _admin_campaign_or_404(campaign_id)
    now = datetime.now(timezone.utc)
    update = {"showcase": payload.showcase, "updated_at": now}
    if payload.showcase:
        update["showcase_note"] = (payload.note or "").strip() or None
        update["showcase_at"] = now
    updated = await db.campaigns.find_one_and_update(
        {"_id": campaign["_id"]},
        {"$set": update} if payload.showcase else {
            "$set": update,
            "$unset": {"showcase_note": "", "showcase_at": ""},
        },
        return_document=True,
    )
    await audit(
        user,
        "campaign.showcase" if payload.showcase else "campaign.showcase.remove",
        "campaign",
        campaign["_id"],
        before={"showcase": bool(campaign.get("showcase"))},
        after={"showcase": payload.showcase},
        note=payload.note,
        **_campaign_audit_context(campaign),
    )
    return {
        "id": campaign_id,
        "showcase": bool(updated.get("showcase")),
        "showcase_note": updated.get("showcase_note"),
    }


@admin_router.post("/collaborations/{collab_id}/performance")
async def record_collaboration_performance(
    collab_id: str,
    payload: PerformancePayload,
    user: dict = Depends(require_roles("admin")),
):
    """Type in what a post did. Always available — see `_record_performance`."""
    return await _record_performance(await _collab_or_404(collab_id), payload, user)


@admin_router.post("/collaborations/{collab_id}/performance/fetch")
async def fetch_collaboration_performance(
    collab_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """Try Instagram, and say plainly when it can't be done.

    A 200 either way. A failure here is not an error condition — it is the
    ordinary case for every creator who hasn't connected their account, and
    the answer to it is the manual form that is already on screen. Returning a
    4xx would make the UI treat "this creator uses YouTube" as a fault.
    """
    collab = await _collab_or_404(collab_id)
    metrics, reason = await _fetch_instagram_performance(collab)
    if reason:
        return {"fetched": False, "reason": reason, "performance": None}
    media_id = metrics.pop("media_id", None)
    saved = await _record_performance(
        collab,
        PerformancePayload(**metrics),
        user,
        source="instagram",
        media_id=media_id,
    )
    return {"fetched": True, "reason": None, "performance": saved}


@admin_router.post("/impersonate/{user_id}")
async def impersonate_user(
    user_id: str,
    response: Response,
    request: Request,
    user: dict = Depends(require_roles("admin")),
):
    """Start looking at the app as somebody else.

    Read-only — `_reject_impersonated_writes` refuses every unsafe method for
    as long as the cookie is set. This endpoint only mints the token; it is the
    middleware that makes the promise.

    The admin's own cookies are left alone. Stopping is then just deleting one
    cookie, and a failure anywhere in here cannot log the admin out.
    """
    oid = _as_oid(user_id)
    if oid is None:
        raise HTTPException(status_code=404, detail="User not found")

    target = await db.users.find_one({"_id": oid})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    role = target.get("role")
    if role not in IMPERSONATABLE_ROLES:
        # Refusing admin→admin is the point. An admin already sees everything
        # an admin sees, so the only thing this would add is acting as a
        # named colleague — which is precisely what the audit log exists to
        # prevent being possible.
        raise HTTPException(
            status_code=422,
            detail=f"You can't view as {'another admin' if role == 'admin' else f'a {role}'}.",
        )
    if str(target["_id"]) == str(user["_id"]):
        raise HTTPException(status_code=422, detail="You're already yourself.")

    # Refused while already impersonating, so a session cannot be chained from
    # one person to the next without an audited stop in between. (The
    # middleware blocks this POST anyway; this is the readable reason.)
    if _decode_impersonation(request) is not None:
        raise HTTPException(
            status_code=409,
            detail="Stop viewing as the current user first.",
        )

    await audit(
        user,
        "admin.impersonate.start",
        "user",
        oid,
        after={
            "target_user_id": str(target["_id"]),
            "target_name": target.get("name"),
            "target_role": role,
            "expires_in_minutes": IMPERSONATION_MIN,
        },
    )

    response.set_cookie(
        key=IMPERSONATION_COOKIE,
        value=create_impersonation_token(str(target["_id"]), user),
        httponly=True,
        secure=True,
        samesite="none",
        max_age=IMPERSONATION_MIN * 60,
        path="/",
    )
    return {
        "impersonating": {
            "user_id": str(target["_id"]),
            "name": target.get("name"),
            "role": role,
            "expires_in_minutes": IMPERSONATION_MIN,
        }
    }


# --- Brand verification (GAP 5) --------------------------------------------


@admin_router.get("/campaigns")
async def list_all_campaigns(
    brand_id: Optional[str] = None,
    status: Optional[str] = None,
    execution_owner: Optional[str] = None,
    showcase: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    date_field: str = "created_at",  # created_at | start_date | end_date
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    user: dict = Depends(require_roles("admin")),
):
    """Every campaign in every state, closed and draft included.

    The creator feed is deliberately narrow — `list_campaigns` still only shows
    LIVE_CAMPAIGN_STATUSES, and that is unchanged. This is the admin's view of
    the same collection, which has to include what the feed hides.
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 100))

    if date_field not in ("created_at", "start_date", "end_date"):
        raise HTTPException(
            status_code=422,
            detail="date_field must be created_at, start_date or end_date.",
        )

    match: dict = {}
    if status:
        if status not in CampaignStatus.__args__:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of: {', '.join(CampaignStatus.__args__)}.",
            )
        match["status"] = status
    if execution_owner:
        if execution_owner not in EXECUTION_OWNERS:
            raise HTTPException(
                status_code=422,
                detail=f"execution_owner must be one of: {', '.join(EXECUTION_OWNERS)}.",
            )
        match.update(_execution_owner_query(execution_owner))
    if brand_id:
        try:
            match["brand_id"] = ObjectId(brand_id)
        except Exception:
            raise HTTPException(status_code=422, detail="brand_id is not a valid id.")
    if date_from or date_to:
        window: dict = {}
        if date_from:
            window["$gte"] = date_from
        if date_to:
            window["$lte"] = date_to
        match[date_field] = window
    if q:
        term = re.escape(q.strip()[:120])
        match["title"] = {"$regex": term, "$options": "i"}
    if showcase is not None:
        # `False` has to mean "everything not flagged", which includes every
        # campaign written before the field existed — hence $ne rather than an
        # equality that would match nothing.
        match["showcase"] = True if showcase else {"$ne": True}

    pipeline: list = []
    if match:
        pipeline.append({"$match": match})
    pipeline += [
        {"$sort": {"created_at": -1}},
        {
            "$facet": {
                "rows": [{"$skip": (page - 1) * page_size}, {"$limit": page_size}],
                "total": [{"$count": "n"}],
            }
        },
    ]

    result = await db.campaigns.aggregate(pipeline).to_list(length=1)
    facet = result[0] if result else {}
    docs = facet.get("rows") or []
    total_rows = facet.get("total") or []
    total = total_rows[0]["n"] if total_rows else 0

    campaign_ids = [d["_id"] for d in docs]
    brand_map = await _load_brand_map([d["brand_id"] for d in docs])

    # Everyone who is or was on these campaigns, in one grouped pipeline rather
    # than a query per campaign.
    collaborators: dict = {}
    if campaign_ids:
        async for row in db.collaborations.aggregate(
            [
                {"$match": {"campaign_id": {"$in": campaign_ids}}},
                {"$sort": {"created_at": 1}},
                {
                    "$lookup": {
                        "from": "creator_profiles",
                        "localField": "creator_id",
                        "foreignField": "user_id",
                        "as": "profile",
                    }
                },
                {"$addFields": {"profile": {"$arrayElemAt": ["$profile", 0]}}},
                {
                    "$lookup": {
                        "from": "payments",
                        "localField": "_id",
                        "foreignField": "collaboration_id",
                        "as": "payment",
                    }
                },
                {"$addFields": {"payment": {"$arrayElemAt": ["$payment", 0]}}},
                {
                    "$group": {
                        "_id": "$campaign_id",
                        "creators": {
                            "$push": {
                                "collaboration_id": "$_id",
                                "creator_id": "$creator_id",
                                "name": "$profile.name",
                                "instagram_handle": "$profile.instagram_handle",
                                "state": "$state",
                                "quoted_rate": "$quoted_rate",
                                "agreed_amount": "$agreed_amount",
                                "scheduled_at": "$scheduled_at",
                                "payment_state": "$payment.state",
                                # So the console can refund a paid payout from
                                # the row without a second lookup.
                                "payment_id": "$payment._id",
                                "creator_payout": "$payment.creator_payout",
                            }
                        },
                    }
                },
            ]
        ):
            collaborators[row["_id"]] = row["creators"]

    campaigns = []
    for d in docs:
        brand = brand_map.get(d["brand_id"]) or {}
        rows = collaborators.get(d["_id"], [])
        creators = [
            {
                "collaboration_id": str(c["collaboration_id"]),
                "creator_id": str(c["creator_id"]),
                "name": c.get("name"),
                "instagram_handle": c.get("instagram_handle"),
                "state": c.get("state"),
                "quoted_rate": c.get("quoted_rate"),
                "agreed_amount": c.get("agreed_amount"),
                "scheduled_at": _iso(c.get("scheduled_at")),
                "payment_state": c.get("payment_state"),
                "payment_id": str(c["payment_id"]) if c.get("payment_id") else None,
                "creator_payout": c.get("creator_payout"),
            }
            for c in rows
        ]
        needed = int(d.get("creators_needed") or 1)
        filled = sum(1 for c in creators if c["state"] in _FILLED_COLLAB_STATES)
        campaigns.append(
            {
                "id": str(d["_id"]),
                "brand_id": str(d["brand_id"]),
                "brand_name": brand.get("business_name") or brand.get("name"),
                "brand_logo_url": brand.get("logo_url"),
                "title": d.get("title"),
                "visibility": _campaign_visibility(d),
                "brief": d.get("brief"),
                "deliverables": d.get("deliverables"),
                "budget_per_creator": d.get("budget_per_creator"),
                "compensation_type": _compensation_type(d),
                "showcase": bool(d.get("showcase")),
                "category": d.get("category"),
                "area": d.get("area"),
                "campaign_type": d.get("campaign_type"),
                "event_date": _iso(d.get("event_date")),
                "execution_owner": _execution_owner(d),
                "cover_image_url": d.get("cover_image_url"),
                "manager_id": str(d["manager_id"]) if d.get("manager_id") else None,
                "manager_name": d.get("manager_name"),
                "status": d.get("status"),
                "creators_needed": needed,
                "filled_slots": filled,
                "applicant_count": len(creators),
                "start_date": _iso(d.get("start_date")),
                "end_date": _iso(d.get("end_date")),
                "created_at": _iso(d.get("created_at")),
                # Everyone who is or was part of it, declined included.
                "creators": creators,
            }
        )

    return {
        "campaigns": campaigns,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
    }


@admin_router.get("/campaigns/pending")
async def list_campaigns_for_review(user: dict = Depends(require_roles("admin"))):
    """The review queue: briefs a brand has submitted and nobody has read yet.

    Declared before /campaigns/{campaign_id}/... so the fixed path wins. Oldest
    first — a queue people jump is not a queue.
    """
    docs = (
        await db.campaigns.find({"status": CAMPAIGN_REVIEW_STATUS})
        .sort("submitted_for_review_at", 1)
        .to_list(length=500)
    )
    if not docs:
        return []

    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    verified_brand_ids = {
        p["user_id"]
        for p in await db.brand_profiles.find(
            {"user_id": {"$in": [d["brand_id"] for d in docs]}, "verified": True},
            {"user_id": 1},
        ).to_list(length=len(docs))
    }

    return [
        {
            "id": str(d["_id"]),
            "brand_id": str(d["brand_id"]),
            "brand_name": (brand_map.get(d["brand_id"]) or {}).get("business_name")
            or (brand_map.get(d["brand_id"]) or {}).get("name"),
            "brand_logo_url": (brand_map.get(d["brand_id"]) or {}).get("logo_url"),
            "cover_image_url": d.get("cover_image_url"),
            # A brief can be sitting here from a brand we since un-verified.
            "brand_verified": d["brand_id"] in verified_brand_ids,
            "title": d.get("title"),
            "brief": d.get("brief"),
            "deliverables": d.get("deliverables"),
            "budget_per_creator": d.get("budget_per_creator"),
            "compensation_type": _compensation_type(d),
            "category": d.get("category"),
            "area": d.get("area"),
            "creators_needed": d.get("creators_needed"),
            "start_date": _iso(d.get("start_date")),
            "end_date": _iso(d.get("end_date")),
            "submitted_for_review_at": _iso(d.get("submitted_for_review_at")),
            "created_at": _iso(d.get("created_at")),
            # Present when this is a resubmission of something we sent back.
            "previous_review_reason": d.get("review_reason"),
        }
        for d in docs
    ]


@admin_router.get("/campaigns/{campaign_id}")
async def get_admin_campaign_detail(
    campaign_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """One campaign, whole picture.

    The brief itself, who it belongs to, who runs it, what it pays, the slots
    and who is in them, and what has been paid out. The applicants live at
    /campaigns/{id}/applicants and the trail at /audit?campaign_id= — three
    focused calls rather than one that has to be refetched in full every time a
    single row changes.

    **Declared after /campaigns/pending**, or `pending` would be read as a
    campaign id and that route would never match again.
    """
    campaign = await _admin_campaign_or_404(campaign_id)
    cid = campaign["_id"]

    brand_map = await _load_brand_map([campaign["brand_id"]])
    brand = brand_map.get(campaign["brand_id"]) or {}
    brand_account = await db.users.find_one({"_id": campaign["brand_id"]}) or {}

    slots = (
        await db.campaign_slots.find({"campaign_id": cid})
        .sort("starts_at", 1)
        .to_list(length=500)
    )

    # Who is in each slot, so a slot row can name people rather than a count.
    # One query for the campaign, grouped here — a lookup per slot would be a
    # query per row on a page that already makes three.
    booked = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": cid, "slot_id": {"$ne": None}}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "creator_id",
                    "foreignField": "_id",
                    "as": "creator",
                }
            },
            {"$addFields": {"creator": {"$arrayElemAt": ["$creator", 0]}}},
            {
                "$project": {
                    "slot_id": 1,
                    "state": 1,
                    "creator_id": 1,
                    "creator_name": "$creator.name",
                }
            },
        ]
    ).to_list(length=1000)
    by_slot: dict = {}
    for row in booked:
        by_slot.setdefault(row["slot_id"], []).append(
            {
                "collaboration_id": str(row["_id"]),
                "creator_id": str(row["creator_id"]),
                "creator_name": row.get("creator_name"),
                "state": row.get("state"),
            }
        )

    payments = await db.payments.aggregate(
        [
            {
                "$lookup": {
                    "from": "collaborations",
                    "localField": "collaboration_id",
                    "foreignField": "_id",
                    "as": "collab",
                }
            },
            {"$addFields": {"collab": {"$arrayElemAt": ["$collab", 0]}}},
            {"$match": {"collab.campaign_id": cid}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "collab.creator_id",
                    "foreignField": "_id",
                    "as": "creator",
                }
            },
            {"$addFields": {"creator": {"$arrayElemAt": ["$creator", 0]}}},
            {"$sort": {"created_at": -1}},
        ]
    ).to_list(length=1000)

    paid_total = 0.0
    committed_total = 0.0
    payment_rows = []
    for p in payments:
        payout = float(p.get("creator_payout") or 0)
        if p.get("state") == "paid":
            paid_total += payout
        else:
            committed_total += payout
        payment_rows.append(
            {
                "id": str(p["_id"]),
                "collaboration_id": str(p["collaboration_id"]),
                "creator_id": str((p.get("collab") or {}).get("creator_id"))
                if (p.get("collab") or {}).get("creator_id")
                else None,
                "creator_name": (p.get("creator") or {}).get("name"),
                "state": p.get("state"),
                "creator_payout": payout,
                "platform_fee": p.get("platform_fee"),
                "brand_invoice_amount": p.get("brand_invoice_amount"),
                "invoice_state": p.get("invoice_state"),
                "reference": p.get("reference"),
                "paid_at": _iso(p.get("paid_at")),
                "created_at": _iso(p.get("created_at")),
            }
        )

    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([cid])).get(cid, 0)
    performance = await _campaign_performance([cid], paid_total)

    return {
        "performance": performance,
        "campaign": {
            **_serialize_brand_campaign(campaign, 0, filled, 0),
            # The brand's own serializer stops at the manager's name and phone,
            # which is right for the brand. An admin assigns the manager, so
            # the id has to come back or the picker can't show the current one.
            "manager_id": str(campaign["manager_id"])
            if campaign.get("manager_id")
            else None,
            "manager_email": campaign.get("manager_email"),
            "paused_at": _iso(campaign.get("paused_at")),
            "paused_from_status": campaign.get("paused_from_status"),
            "closed_at": _iso(campaign.get("closed_at")),
            "reviewed_at": _iso(campaign.get("reviewed_at")),
        },
        "brand": {
            "user_id": str(campaign["brand_id"]),
            "business_name": brand.get("business_name") or brand_account.get("name"),
            "logo_url": brand.get("logo_url"),
            "category": brand.get("category"),
            "verified": bool(brand.get("verified", False)),
            "verification_state": _brand_verification_state(brand),
            "contact_person_name": brand.get("contact_person_name"),
            "contact_email": brand.get("contact_email"),
            # Staff-side, so the number is the point — this is who to ring when
            # a shoot is going wrong. It never crosses to a brand response.
            "contact_phone": brand.get("contact_phone") or brand_account.get("phone"),
        },
        "slots": [
            {**_serialize_slot(s), "bookings": by_slot.get(s["_id"], [])} for s in slots
        ],
        "payments": payment_rows,
        "totals": {
            "creators_needed": needed,
            "filled_slots": filled,
            "spots_left": max(0, needed - filled),
            "paid_out": round(paid_total, 2),
            # Agreed but not yet released — what this brief still owes.
            "committed": round(committed_total, 2),
            "slot_capacity": sum(int(s.get("capacity") or 0) for s in slots),
            "slot_booked": sum(int(s.get("booked_count") or 0) for s in slots),
        },
    }


@admin_router.post("/campaigns/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    """Publish a reviewed campaign — this is the only route to the creator feed.

    Whether it lands on `upcoming` or `open` is the start date's call, the same
    rule the brand's own publish button used before review existed.
    """
    try:
        cid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = await db.campaigns.find_one({"_id": cid})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    current = campaign.get("status")
    if current != CAMPAIGN_REVIEW_STATUS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This campaign is {current}, not awaiting review. Only a submitted "
                "campaign can be approved."
            ),
        )

    # Approving a brief from a brand we have not verified would walk straight
    # past the gate the review exists to hold.
    brand_profile = await db.brand_profiles.find_one({"user_id": campaign["brand_id"]})
    if not brand_profile or not brand_profile.get("verified", False):
        raise HTTPException(
            status_code=409,
            detail="Verify the brand before publishing its campaigns.",
        )

    now = datetime.now(timezone.utc)
    start = campaign.get("start_date")
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    status = "upcoming" if start and start > now else "open"

    updated = await db.campaigns.find_one_and_update(
        # from_state as a write precondition, as everywhere else — two admins
        # in the queue must not both publish it.
        {"_id": cid, "status": CAMPAIGN_REVIEW_STATUS},
        {
            "$set": {
                "status": status,
                "reviewed_at": now,
                "reviewed_by": ObjectId(user["_id"]) if user.get("_id") else None,
                "updated_at": now,
            },
            "$unset": {"review_reason": ""},
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "campaign.approve",
        "campaign",
        cid,
        before={"status": CAMPAIGN_REVIEW_STATUS},
        after={"status": status},
        note=(payload.reason if payload else None),
    )

    title = updated.get("title") or "Your campaign"
    delivery = await notify_over_utility_template(
        campaign["brand_id"],
        "campaign_approved",
        title="Your campaign is live",
        body=(
            f"“{title}” is {'scheduled' if status == 'upcoming' else 'live'} — "
            "creators can see it now."
            if status == "open"
            else f"“{title}” is approved and goes live on its start date."
        ),
        params=[title, status],
        link=f"/brand/campaigns/{campaign_id}",
    )
    return {"id": campaign_id, "status": status, "notification": delivery}


@admin_router.post("/campaigns/{campaign_id}/reject")
async def reject_campaign(
    campaign_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Send a submitted campaign back to the brand with a reason.

    It returns to `draft` rather than dying: the brand fixes what we asked
    about and submits again. The reason rides on the campaign so they are not
    guessing at what to change.
    """
    try:
        cid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=422,
            detail="Give a reason — the brand is told what to fix.",
        )

    campaign = await db.campaigns.find_one({"_id": cid})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    current = campaign.get("status")
    if current != CAMPAIGN_REVIEW_STATUS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This campaign is {current}, not awaiting review. To pull a live "
                "campaign, close it instead."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.campaigns.find_one_and_update(
        {"_id": cid, "status": CAMPAIGN_REVIEW_STATUS},
        {
            "$set": {
                "status": "draft",
                "review_reason": reason,
                "reviewed_at": now,
                "reviewed_by": ObjectId(user["_id"]) if user.get("_id") else None,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "campaign.reject",
        "campaign",
        cid,
        before={"status": CAMPAIGN_REVIEW_STATUS},
        after={"status": "draft"},
        note=reason,
    )

    title = updated.get("title") or "Your campaign"
    delivery = await notify_over_utility_template(
        campaign["brand_id"],
        "campaign_rejected",
        title="Your campaign needs a change",
        body=f"“{title}”: {reason}",
        params=[title, reason],
        link=f"/brand/campaigns/{campaign_id}",
    )
    return {
        "id": campaign_id,
        "status": "draft",
        "review_reason": reason,
        "notification": delivery,
    }


# A campaign can be paused from any state where it is still running, and comes
# back to whichever of those it was in.
_PAUSABLE_STATUSES = ("upcoming", "open", "in_progress")
_CLOSED_CAMPAIGN_STATUSES = ("completed", "closed")


async def _admin_campaign_or_404(campaign_id: str) -> dict:
    try:
        cid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    doc = await db.campaigns.find_one({"_id": cid})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return doc


async def _pause_campaign(doc: dict, reason: Optional[str], user: dict) -> dict:
    """Take a live campaign off the feed without ending it.

    Collaborations already under way are untouched — pausing stops new
    applications, it does not cancel work somebody is mid-way through. The
    status it was in is remembered so resuming puts it back rather than
    guessing.

    Shared by the admin route and the brand manager's. The two differ only in
    who is allowed to reach the campaign; what pausing *means* must not fork,
    or a brand pause and an admin pause would resume to different places.
    """
    campaign_id = str(doc["_id"])
    current = doc.get("status")
    if current == "paused":
        raise HTTPException(status_code=409, detail="This campaign is already paused.")
    if current not in _PAUSABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"A campaign that is {current} isn't running, so there's nothing to pause.",
        )

    now = datetime.now(timezone.utc)
    updated = await db.campaigns.find_one_and_update(
        {"_id": doc["_id"], "status": current},
        {
            "$set": {
                "status": "paused",
                "paused_at": now,
                "paused_from_status": current,
                "pause_reason": reason,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "campaign.pause",
        "campaign",
        doc["_id"],
        before={"status": current},
        after={"status": "paused"},
        note=reason,
        **_campaign_audit_context(doc),
    )
    await _tell_brand_manager_about_campaign(
        doc,
        actor=user,
        event="brand_campaign_updated",
        title="Your campaign was paused",
        body=(
            f"“{doc.get('title')}” has been paused"
            + (f" — {reason}" if reason else ".")
        ),
    )
    return {"id": campaign_id, "status": "paused", "paused_from_status": current}


@admin_router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Pause any campaign, as WeAre."""
    doc = await _admin_campaign_or_404(campaign_id)
    return await _pause_campaign(doc, payload.reason, user)


async def _resume_campaign(doc: dict, reason: Optional[str], user: dict) -> dict:
    """Put a paused campaign back where it was.

    Pause without this is a one-way door, which is the shape of problem the rest
    of this change is about. The end date is re-checked on the way back, so a
    campaign paused past its window returns as completed rather than quietly
    reopening.
    """
    campaign_id = str(doc["_id"])
    if doc.get("status") != "paused":
        raise HTTPException(
            status_code=409,
            detail=f"This campaign is {doc.get('status')}, not paused.",
        )

    now = datetime.now(timezone.utc)
    back_to = doc.get("paused_from_status") or "open"
    end = doc.get("end_date")
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end and end < now:
        back_to = "completed"

    updated = await db.campaigns.find_one_and_update(
        {"_id": doc["_id"], "status": "paused"},
        {
            "$set": {"status": back_to, "resumed_at": now, "updated_at": now},
            "$unset": {"paused_from_status": "", "pause_reason": ""},
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "campaign.resume",
        "campaign",
        doc["_id"],
        before={"status": "paused"},
        after={"status": back_to},
        note=reason,
        **_campaign_audit_context(doc),
    )
    await _tell_brand_manager_about_campaign(
        doc,
        actor=user,
        event="brand_campaign_updated",
        title="Your campaign is running again",
        body=f"“{doc.get('title')}” is back to {back_to.replace('_', ' ')}.",
    )
    # Re-check the fill: slots may have changed while it was off the feed.
    await _sync_campaign_fill(doc["_id"])
    return {"id": campaign_id, "status": back_to}


@admin_router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    """Resume any campaign, as WeAre."""
    doc = await _admin_campaign_or_404(campaign_id)
    return await _resume_campaign(doc, (payload.reason if payload else None), user)


@admin_router.post("/campaigns/{campaign_id}/close")
async def admin_close_campaign(
    campaign_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Stop a campaign for good, and answer everyone still waiting on it.

    The same shape as the brand's own close, but available to us when the brand
    won't or can't: collaborations under way are left alone, and applications
    nobody ever decided on are declined rather than left hanging forever.
    """
    doc = await _admin_campaign_or_404(campaign_id)
    current = doc.get("status")
    if current in _CLOSED_CAMPAIGN_STATUSES:
        raise HTTPException(
            status_code=409, detail=f"This campaign is already {current}."
        )

    now = datetime.now(timezone.utc)
    updated = await db.campaigns.find_one_and_update(
        {"_id": doc["_id"], "status": current},
        {
            "$set": {
                "status": "closed",
                "closed_reason": payload.reason,
                "closed_at": now,
                "closed_by_admin": True,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    stale = await db.collaborations.find(
        {"campaign_id": doc["_id"], "state": {"$in": list(_DECLINABLE_STATES)}}
    ).to_list(length=500)
    for collab in stale:
        await db.collaborations.update_one(
            {"_id": collab["_id"], "state": collab["state"]},
            {
                "$set": {
                    "state": "declined",
                    "active": False,
                    "exit_reason": f"Campaign closed: {payload.reason}",
                    "declined_at": now,
                    "updated_at": now,
                }
            },
        )
        await notify(
            collab["creator_id"],
            "application_declined",
            title="Campaign closed",
            body=payload.reason,
            link="/campaigns",
        )

    await audit(
        user,
        "campaign.close",
        "campaign",
        doc["_id"],
        before={"status": current},
        after={"status": "closed", "applications_closed": len(stale)},
        note=payload.reason,
    )
    return {
        "id": campaign_id,
        "status": "closed",
        "applications_closed": len(stale),
    }


@admin_router.patch("/campaigns/{campaign_id}")
async def admin_update_campaign(
    campaign_id: str,
    payload: UpdateCampaignPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Correct a campaign, including a live one.

    The brand's own edit stops once a campaign is finished; ours does too, for
    the same reason — the terms creators applied under can't be rewritten after
    the fact. What this adds is the ability to fix a live brief without going
    through the brand, which is what support actually needs.
    """
    doc = await _admin_campaign_or_404(campaign_id)
    current = doc.get("status")
    if current in _CLOSED_CAMPAIGN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"This campaign is {current} and can no longer be edited.",
        )

    fields = payload.model_dump(exclude_unset=True)
    update: dict = {}
    for key, value in fields.items():
        if value is None and key not in ("start_date", "end_date"):
            continue
        if isinstance(value, str):
            value = value.strip()
        update[key] = value
    if not update:
        raise HTTPException(status_code=422, detail="Nothing to update")

    # No _refuse_brand_barter here, and that is the whole point of the feature:
    # this route is the only way a campaign becomes barter. There is no admin
    # campaign-create endpoint, so an admin makes a barter brief by taking one
    # that exists and setting it — which also means somebody read it first.
    _refuse_dates_foreign_to_type(doc, update)
    start = update.get("start_date", doc.get("start_date"))
    end = update.get("end_date", doc.get("end_date"))
    if start and end and end < start:
        raise HTTPException(
            status_code=422, detail="End date cannot be before start date"
        )

    # The same floor the brand's edit has: never shrink a brief below the
    # creators already committed to it.
    if "creators_needed" in update:
        filled = (await _filled_counts_for([doc["_id"]])).get(doc["_id"], 0)
        if int(update["creators_needed"]) < filled:
            raise HTTPException(
                status_code=409,
                detail=f"{filled} creator(s) are already confirmed on this campaign.",
            )

    before = {k: doc.get(k) for k in update}
    update["updated_at"] = datetime.now(timezone.utc)
    updated = await db.campaigns.find_one_and_update(
        {"_id": doc["_id"]}, {"$set": update}, return_document=True
    )

    await audit(
        user,
        "campaign.update",
        "campaign",
        doc["_id"],
        before=before,
        after={k: v for k, v in update.items() if k != "updated_at"},
        **_campaign_audit_context(doc),
    )
    # WeAre editing somebody's brief without telling them means they find out
    # from a creator quoting terms they didn't write. The fields are named so
    # the message says what changed rather than that something did.
    changed = sorted(k.replace("_", " ") for k in update if k != "updated_at")
    if changed:
        await _tell_brand_manager_about_campaign(
            doc,
            actor=user,
            event="brand_campaign_updated",
            title="WeAre updated your campaign",
            body=(
                f"“{doc.get('title')}” was changed by the WeAre team: "
                + ", ".join(changed)
                + "."
            ),
        )
    await _sync_campaign_fill(doc["_id"])

    counts = await _applicant_counts_for([doc["_id"]])
    return _serialize_brand_campaign(updated, counts.get(doc["_id"], 0))


# Campaigns you can still usefully invite someone to. A finished campaign gives
# the creator a brief they can never apply to; a draft or one still in review
# gives them one they cannot even see, which would walk an unapproved brief
# straight past the moderation gate over WhatsApp.
INVITABLE_CAMPAIGN_STATUSES = ("upcoming", "open", "in_progress")


async def _invite_creators(
    campaign: dict, payload: "CampaignInvitePayload", user: dict
) -> dict:
    """Invite hand-picked creators to a campaign over WhatsApp.

    Sourcing is a manual job — someone reads the brief, picks creators who fit
    and asks them. This is that ask, made once per creator so a partial send is
    reportable rather than an all-or-nothing guess.

    Every creator gets an invitation row whether or not the message lands, so a
    failed send can be retried against a record that already exists, and the
    per-creator result says which is which. Duplicate invites are refused by a
    unique index on (campaign_id, creator_id), not just by the pre-check — two
    admins clicking at once must not send the same creator two messages.

    Shared by the admin route and the brand manager's, because an invite is the
    same message whoever sends it — and because the creator's number is read
    here and never returned, which is a property worth having in exactly one
    place.
    """
    cid = campaign["_id"]
    campaign_id = str(cid)
    status = campaign.get("status")
    if status not in INVITABLE_CAMPAIGN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"This campaign is {status} — creators can no longer be invited to it.",
        )

    brand_map = await _load_brand_map([campaign["brand_id"]])
    brand = brand_map.get(campaign["brand_id"]) or {}
    brand_name = brand.get("business_name") or brand.get("name") or "a WeAre brand"
    title = campaign.get("title") or "a campaign"
    budget = float(campaign.get("budget_per_creator") or 0)
    budget_text = f"₹{budget:,.0f}"
    template = os.environ.get("AISENSY_TEMPLATE_CAMPAIGN_INVITE", "").strip()

    # De-duplicate the request itself — a UI multi-select can repeat an id, and
    # that must not turn into two messages. Order is kept so the response reads
    # the way the admin selected.
    requested: list[str] = []
    for raw in payload.creator_ids:
        raw = (raw or "").strip()
        if raw and raw not in requested:
            requested.append(raw)

    # Resolve every id in two queries rather than two per creator.
    wanted_oids = []
    oid_by_raw: dict = {}
    results: dict = {}
    for raw in requested:
        try:
            oid = ObjectId(raw)
        except Exception:
            results[raw] = {"status": "failed", "reason": "That is not a valid creator id."}
            continue
        oid_by_raw[raw] = oid
        wanted_oids.append(oid)

    accounts_by_id: dict = {}
    profiles_by_user: dict = {}
    invited_already: set = set()
    if wanted_oids:
        accounts = await db.users.find(
            {"_id": {"$in": wanted_oids}, "role": "creator"}
        ).to_list(length=len(wanted_oids))
        accounts_by_id = {a["_id"]: a for a in accounts}
        profiles = await db.creator_profiles.find(
            {"user_id": {"$in": wanted_oids}}
        ).to_list(length=len(wanted_oids))
        profiles_by_user = {p["user_id"]: p for p in profiles}
        invited_already = {
            row["creator_id"]
            async for row in db.campaign_invitations.find(
                {"campaign_id": cid, "creator_id": {"$in": wanted_oids}},
                {"creator_id": 1},
            )
        }

    now = datetime.now(timezone.utc)
    sent = 0
    for raw in requested:
        if raw in results:  # already rejected as an unusable id
            continue
        oid = oid_by_raw[raw]
        account = accounts_by_id.get(oid)
        profile = profiles_by_user.get(oid) or {}
        name = profile.get("name") or (account or {}).get("name") or "there"

        if not account:
            results[raw] = {"status": "failed", "reason": "No creator account with that id."}
            continue
        if oid in invited_already:
            # Not a failure — the admin asked for something already true.
            results[raw] = {
                "status": "already_invited",
                "name": name,
                "reason": "This creator has already been invited to this campaign.",
            }
            continue
        if profile.get("verification_status") != "verified":
            # Only verified creators can apply, so an invite to anyone else is
            # a brief they would be blocked from taking up.
            results[raw] = {
                "status": "failed",
                "name": name,
                "reason": "This creator isn't verified yet, so they can't apply.",
            }
            continue
        if _awaiting_recheck(profile):
            # Same reasoning: they are verified but cannot pitch until we have
            # looked at what they changed, so the invite would go nowhere.
            results[raw] = {
                "status": "failed",
                "name": name,
                "reason": "This creator is being re-checked, so they can't apply just now.",
            }
            continue

        phone = account.get("phone")

        try:
            invitation = await db.campaign_invitations.insert_one(
                {
                    "campaign_id": cid,
                    "creator_id": oid,
                    "brand_id": campaign["brand_id"],
                    "invited_by": ObjectId(user["_id"]) if user.get("_id") else None,
                    "note": payload.note,
                    "state": "sent",
                    "delivered_on_whatsapp": False,
                    "whatsapp_mode": None,
                    "error": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except DuplicateKeyError:
            # Another admin got there between the pre-check and the write.
            results[raw] = {
                "status": "already_invited",
                "name": name,
                "reason": "This creator has already been invited to this campaign.",
            }
            continue

        invitation_id = invitation.inserted_id

        delivered = False
        mode = None
        reason = None
        if not phone:
            reason = "No WhatsApp number on file for this creator."
        else:
            try:
                mode = await _send_aisensy_utility(
                    phone, name, template, [title, brand_name, budget_text]
                )
                delivered = mode == "aisensy"
            except HTTPException as exc:
                reason = exc.detail

        await db.campaign_invitations.update_one(
            {"_id": invitation_id},
            {
                "$set": {
                    "state": "sent" if (delivered or mode) else "send_failed",
                    "delivered_on_whatsapp": delivered,
                    "whatsapp_mode": mode,
                    "error": reason,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        # The in-app record goes in either way — the invite is real even when
        # WhatsApp is not reachable, and this is where the creator finds it.
        await record_notification(
            oid,
            "campaign_invite",
            title="You've been invited to a campaign",
            body=f"{brand_name} would like you on “{title}” — {budget_text} per creator.",
            link=f"/campaigns/{campaign_id}",
            delivered=delivered,
        )

        if reason:
            results[raw] = {
                "status": "failed",
                "name": name,
                "invitation_id": str(invitation_id),
                "reason": reason,
            }
        else:
            sent += 1
            results[raw] = {
                "status": "invited",
                "name": name,
                "invitation_id": str(invitation_id),
                "delivered_on_whatsapp": delivered,
                "whatsapp_mode": mode,
            }

    rows = [{"creator_id": raw, **results[raw]} for raw in requested]
    failed = sum(1 for r in rows if r["status"] == "failed")
    skipped = sum(1 for r in rows if r["status"] == "already_invited")

    await audit(
        user,
        "campaign.invite",
        "campaign",
        cid,
        after={"invited": sent, "failed": failed, "already_invited": skipped},
        note=payload.note,
        **_campaign_audit_context(campaign),
    )

    # 200 even when nothing sent: the per-creator rows are the answer, and the
    # UI reports a partial send from them.
    return {
        "campaign_id": campaign_id,
        "campaign_title": title,
        "brand_name": brand_name,
        "invited": sent,
        "failed": failed,
        "already_invited": skipped,
        "results": rows,
    }


@admin_router.post("/campaigns/{campaign_id}/invite")
async def invite_creators_to_campaign(
    campaign_id: str,
    payload: CampaignInvitePayload,
    user: dict = Depends(require_roles("admin")),
):
    """Invite creators to any campaign, as WeAre."""
    campaign = await _admin_campaign_or_404(campaign_id)
    return await _invite_creators(campaign, payload, user)


async def _brand_spend_map(brand_ids: list) -> dict:
    """What each brand has actually paid, in one round trip.

    Walks payments → collaborations → campaigns inside the pipeline. Older
    payment rows predate `brand_invoice_amount`, so it falls back to the payout
    plus our fee, which is the same number by construction.
    """
    if not brand_ids:
        return {}
    rows = await db.payments.aggregate(
        [
            {"$match": {"state": "paid"}},
            {
                "$lookup": {
                    "from": "collaborations",
                    "localField": "collaboration_id",
                    "foreignField": "_id",
                    "as": "collab",
                }
            },
            {"$addFields": {"collab": {"$arrayElemAt": ["$collab", 0]}}},
            {
                "$lookup": {
                    "from": "campaigns",
                    "localField": "collab.campaign_id",
                    "foreignField": "_id",
                    "as": "campaign",
                }
            },
            {"$addFields": {"campaign": {"$arrayElemAt": ["$campaign", 0]}}},
            {"$match": {"campaign.brand_id": {"$in": list(brand_ids)}}},
            {
                "$group": {
                    "_id": "$campaign.brand_id",
                    "spend": {
                        "$sum": {
                            "$ifNull": [
                                "$brand_invoice_amount",
                                {
                                    "$add": [
                                        {"$ifNull": ["$creator_payout", 0]},
                                        {"$ifNull": ["$platform_fee", 0]},
                                    ]
                                },
                            ]
                        }
                    },
                    "paid_collaborations": {"$sum": 1},
                }
            },
        ]
    ).to_list(length=len(brand_ids) + 1)
    return {r["_id"]: r for r in rows}


@admin_router.get("/brands")
async def list_brands_for_review(
    unverified_only: bool = False,
    q: Optional[str] = None,
    user: dict = Depends(require_roles("admin")),
):
    """Every brand, with what they've run and what they've spent.

    `unverified_only=true` narrows this to the verification queue — which is how
    the admin console's "Brands to verify" section calls it.
    """
    query: dict = {"verified": False} if unverified_only else {}
    if q:
        term = re.escape(q.strip()[:120])
        query["business_name"] = {"$regex": term, "$options": "i"}

    profiles = (
        await db.brand_profiles.find(query)
        .sort("created_at", -1)
        .to_list(length=500)
    )
    if not profiles:
        return []

    user_ids = [p["user_id"] for p in profiles]
    users = await db.users.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
    users_by_id = {u["_id"]: u for u in users}

    # Total and active campaign counts in a single grouped pass.
    counts: dict = {}
    async for row in db.campaigns.aggregate(
        [
            {"$match": {"brand_id": {"$in": user_ids}}},
            {
                "$group": {
                    "_id": "$brand_id",
                    "total": {"$sum": 1},
                    "active": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", list(ACTIVE_CAMPAIGN_STATUSES)]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]
    ):
        counts[row["_id"]] = row

    spend = await _brand_spend_map(user_ids)

    out = []
    for p in profiles:
        u = users_by_id.get(p["user_id"], {})
        c = counts.get(p["user_id"]) or {}
        s = spend.get(p["user_id"]) or {}
        out.append(
            {
                "user_id": str(p["user_id"]),
                "business_name": p.get("business_name"),
                "category": p.get("category"),
                "areas": p.get("areas") or [],
                "verified": bool(p.get("verified", False)),
                "email": u.get("email"),
                "phone": u.get("phone"),
                "status": u.get("status"),
                "campaign_count": c.get("total", 0),
                # Still taking applications or mid-delivery.
                "active_campaign_count": c.get("active", 0),
                "total_spend": round(float(s.get("spend", 0) or 0), 2),
                "paid_collaborations": s.get("paid_collaborations", 0),
                "created_at": _iso(p.get("created_at")),
            }
        )
    return out


def _admin_brand_fields(p: dict, u: dict) -> dict:
    """A brand as staff read it: the claim, the evidence for it, and who is
    making it. Shared by the verification queue and the brand detail page so
    the two can't describe the same business differently."""
    return {
        "user_id": str(p["user_id"]),
        "profile_id": str(p["_id"]),
        "business_name": p.get("business_name"),
        "logo_url": p.get("logo_url"),
        "category": p.get("category"),
        "areas": p.get("areas") or [],
        "verified": bool(p.get("verified", False)),
        # The same vocabulary the brand's own profile reports, so one field
        # name doesn't mean two different things on two screens.
        "verification_state": _brand_verification_state(p),
        "verification_reason": p.get("verification_reason"),
        "verified_at": _iso(p.get("verified_at")),
        "rejected_at": _iso(p.get("rejected_at")),
        "submitted_at": _iso(p.get("submitted_for_verification_at")),
        # The business, as claimed — this is what the documents are checked
        # against.
        "legal_entity_name": p.get("legal_entity_name"),
        "business_type": p.get("business_type"),
        "gst_number": p.get("gst_number"),
        "registered_address": p.get("registered_address"),
        "website": p.get("website"),
        "instagram_handle": p.get("instagram_handle"),
        "facebook_url": p.get("facebook_url"),
        "linkedin_url": p.get("linkedin_url"),
        # And the person asking on its behalf.
        "contact_person_name": p.get("contact_person_name"),
        "contact_person_designation": p.get("contact_person_designation"),
        "contact_email": p.get("contact_email"),
        "contact_phone": p.get("contact_phone"),
        # Flagged, not refused: a café on Gmail is normal, but an address on
        # the company's own domain is the cheapest evidence that somebody
        # actually works there.
        "contact_email_is_free_domain": _is_free_email(p.get("contact_email")),
        "name": u.get("name"),
        "email": u.get("email"),
        "phone": u.get("phone"),
        "status": u.get("status"),
        "terms_accepted_at": _iso(u.get("terms_accepted_at")),
        "signed_up_at": _iso(u.get("created_at")),
        "created_at": _iso(p.get("created_at")),
    }


@admin_router.get("/brands/pending")
async def list_pending_brands(user: dict = Depends(require_roles("admin"))):
    """Brands waiting on us, with what they told us at signup.

    Declared before any /brands/{user_id} route so the fixed path keeps
    matching first. Rejected brands are included — a refusal is a decision the
    admin may want to revisit, and hiding it makes the queue look emptier than
    it is; `verification_state` says which is which.
    """
    profiles = (
        await db.brand_profiles.find(
            {"verified": False, "verification_state": {"$in": ["pending_verification", "rejected"]}}
        )
        .sort("submitted_for_verification_at", 1)  # longest wait first
        .to_list(length=500)
    )
    if not profiles:
        return []

    user_ids = [p["user_id"] for p in profiles]
    users = await db.users.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
    users_by_id = {u["_id"]: u for u in users}

    # Every queued brand's documents in one query, so a page of twenty doesn't
    # become twenty round trips.
    docs_by_brand: dict = {}
    for doc in await db.brand_documents.find(
        {"brand_id": {"$in": user_ids}}
    ).sort("created_at", -1).to_list(length=1000):
        docs_by_brand.setdefault(doc["brand_id"], []).append(
            _serialize_brand_document(doc)
        )

    # How much they have already drafted — a brand with briefs waiting is a
    # more urgent review than one that signed up and stopped.
    drafts: dict = {}
    async for row in db.campaigns.aggregate(
        [
            {"$match": {"brand_id": {"$in": user_ids}}},
            {
                "$group": {
                    "_id": "$brand_id",
                    "total": {"$sum": 1},
                    "awaiting_review": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", CAMPAIGN_REVIEW_STATUS]}, 1, 0]
                        }
                    },
                }
            },
        ]
    ):
        drafts[row["_id"]] = row

    out = []
    for p in profiles:
        u = users_by_id.get(p["user_id"], {})
        d = drafts.get(p["user_id"]) or {}
        out.append(
            {
                **_admin_brand_fields(p, u),
                # In this queue it is always pending_verification or rejected.
                "documents": docs_by_brand.get(p["user_id"], []),
                "campaign_count": d.get("total", 0),
                "campaigns_awaiting_review": d.get("awaiting_review", 0),
            }
        )
    return out


@admin_router.get("/brands/{user_id}")
async def get_admin_brand_detail(
    user_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """One brand, whole picture: the claim, the documents behind it, the named
    person who signed up, and every campaign they have run with what it filled
    and what it cost.

    **Declared after /brands/pending**, or `pending` becomes a user id.
    """
    oid = _as_oid(user_id)
    if oid is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    profile = await db.brand_profiles.find_one({"user_id": oid})
    account = await db.users.find_one({"_id": oid})
    if not profile or not account:
        raise HTTPException(status_code=404, detail="Brand not found")

    documents = [
        _serialize_brand_document(d)
        for d in await db.brand_documents.find({"brand_id": oid})
        .sort("created_at", -1)
        .to_list(length=200)
    ]

    campaigns = (
        await db.campaigns.find({"brand_id": oid})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    campaign_ids = [c["_id"] for c in campaigns]
    filled_map = await _filled_counts_for(campaign_ids)

    # Spend per campaign, so a row can say what it actually cost rather than
    # what it budgeted. One pass over payments for the whole brand.
    spend_by_campaign: dict = {}
    if campaign_ids:
        async for row in db.payments.aggregate(
            [
                {
                    "$lookup": {
                        "from": "collaborations",
                        "localField": "collaboration_id",
                        "foreignField": "_id",
                        "as": "collab",
                    }
                },
                {"$addFields": {"collab": {"$arrayElemAt": ["$collab", 0]}}},
                {"$match": {"collab.campaign_id": {"$in": campaign_ids}, "state": "paid"}},
                {
                    "$group": {
                        "_id": "$collab.campaign_id",
                        "spend": {"$sum": {"$ifNull": ["$creator_payout", 0]}},
                        "paid_collaborations": {"$sum": 1},
                    }
                },
            ]
        ):
            spend_by_campaign[row["_id"]] = row

    campaign_rows = []
    for c in campaigns:
        needed = int(c.get("creators_needed") or 1)
        filled = filled_map.get(c["_id"], 0)
        s = spend_by_campaign.get(c["_id"]) or {}
        campaign_rows.append(
            {
                "id": str(c["_id"]),
                "title": c.get("title"),
                "status": c.get("status"),
                "category": c.get("category"),
                "area": c.get("area"),
                "budget_per_creator": c.get("budget_per_creator"),
                "compensation_type": _compensation_type(c),
                "creators_needed": needed,
                "filled_slots": filled,
                # The number an admin is actually scanning for: a brief at 1/8
                # a week before the shoot is the one to ring somebody about.
                "fill_rate": round(filled / needed, 3) if needed else 0.0,
                "spend": round(float(s.get("spend", 0) or 0), 2),
                "paid_collaborations": s.get("paid_collaborations", 0),
                "execution_owner": _execution_owner(c),
                "manager_name": c.get("manager_name"),
                "event_date": _iso(c.get("event_date")),
                "start_date": _iso(c.get("start_date")),
                "end_date": _iso(c.get("end_date")),
                "created_at": _iso(c.get("created_at")),
            }
        )

    total_spend = await _brand_spend_map([oid])
    s = total_spend.get(oid) or {}
    performance = await _campaign_performance(
        campaign_ids, float(s.get("spend", 0) or 0)
    )

    return {
        "performance": performance,
        "brand": {
            **_admin_brand_fields(profile, account),
            # The one login this brand has, and the person it belongs to.
            "manager_name": account.get("manager_name") or account.get("name"),
            "manager_designation": profile.get("contact_person_designation"),
            "manager_phone": account.get("phone"),
            "manager_email": profile.get("contact_email") or account.get("email"),
            "manager_role": account.get("role"),
        },
        "documents": documents,
        "campaigns": campaign_rows,
        "totals": {
            "campaign_count": len(campaign_rows),
            "active_campaign_count": sum(
                1 for c in campaigns if c.get("status") in ACTIVE_CAMPAIGN_STATUSES
            ),
            "total_spend": round(float(s.get("spend", 0) or 0), 2),
            "paid_collaborations": s.get("paid_collaborations", 0),
            "creators_booked": sum(r["filled_slots"] for r in campaign_rows),
        },
    }


@admin_router.get("/brands/{user_id}/documents/{document_id}")
async def download_brand_document(
    user_id: str,
    document_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """Stream one verification document to a reviewing admin.

    The only way these bytes leave the server. They are written outside the
    static upload directory precisely so there is no second path — a GST
    certificate carries a registered address and a director's name, and it must
    never be one guessed URL away from the public internet.
    """
    try:
        brand_oid = ObjectId(user_id)
        doc_oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    # Both ids in the filter, so a document id can't be pulled out from under a
    # different brand.
    doc = await db.brand_documents.find_one({"_id": doc_oid, "brand_id": brand_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = _private_upload_path(doc.get("stored_name"))
    if not path:
        logger.error("brand document %s is recorded but missing on disk", document_id)
        raise HTTPException(status_code=410, detail="That file is no longer on disk.")

    await audit(
        user,
        "brand.document_view",
        "brand_profile",
        brand_oid,
        after={"document_id": document_id, "doc_type": doc.get("doc_type")},
    )
    return FileResponse(
        path,
        media_type=doc.get("mime") or "application/octet-stream",
        # inline so a reviewer can read it in the browser; the filename is the
        # one they uploaded, which is only ever a label.
        headers={
            "Content-Disposition": f'inline; filename="{doc.get("original_name") or "document"}"',
            "Cache-Control": "no-store",
        },
    )


@admin_router.post("/brands/{user_id}/documents/{document_id}/review")
async def review_brand_document(
    user_id: str,
    document_id: str,
    payload: DocumentReviewPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Mark one document accepted or rejected, with a note.

    Per-document rather than only per-brand, so "your FSSAI licence is
    illegible" doesn't have to be written as a whole-brand rejection.
    """
    decision = (payload.reason or "").strip()
    status = payload.status
    if status == "rejected" and not decision:
        raise HTTPException(
            status_code=422,
            detail="Say what's wrong with it — the brand is told what to re-upload.",
        )
    try:
        brand_oid = ObjectId(user_id)
        doc_oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")

    updated = await db.brand_documents.find_one_and_update(
        {"_id": doc_oid, "brand_id": brand_oid},
        {
            "$set": {
                "status": status,
                "review_note": decision or None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    await audit(
        user,
        f"brand.document_{status}",
        "brand_profile",
        brand_oid,
        after={"document_id": document_id, "doc_type": updated.get("doc_type")},
        note=decision or None,
    )
    return _serialize_brand_document(updated)


@admin_router.post("/brands/{user_id}/verify")
async def verify_brand(
    user_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Brand not found")
    now = datetime.now(timezone.utc)
    result = await db.brand_profiles.find_one_and_update(
        {"user_id": oid},
        {
            "$set": {
                "verified": True,
                "verification_state": "verified",
                "verified_at": now,
                "updated_at": now,
            },
            # Approving clears an earlier refusal; leaving it would keep telling
            # the brand it was rejected.
            "$unset": {"verification_reason": "", "rejected_at": ""},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    await db.users.update_one({"_id": oid}, {"$set": {"status": "active"}})
    await audit(
        user,
        "brand.verify",
        "brand_profile",
        result["_id"],
        after={"verified": True},
        note=(payload.reason if payload else None),
    )
    name = result.get("business_name") or "your brand"
    delivery = await notify_over_utility_template(
        oid,
        "brand_verified",
        title="Your brand is verified",
        body=f"{name} is verified. You can submit campaigns for review now.",
        params=[name],
        link="/brand/campaigns",
    )
    out = _serialize_brand_profile(result)
    out["notification"] = delivery
    return out


@admin_router.post("/brands/{user_id}/reject")
async def reject_brand(
    user_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Refuse a brand, with the reason on the record.

    Distinct from `unverify`, which takes an already-approved brand back out
    without explaining itself. A rejection is a decision we have to be able to
    tell the brand about, so the reason is required.
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Brand not found")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=422,
            detail="Give a reason — the brand is told what to fix.",
        )

    now = datetime.now(timezone.utc)
    result = await db.brand_profiles.find_one_and_update(
        {"user_id": oid},
        {
            "$set": {
                "verified": False,
                "verification_state": "rejected",
                "verification_reason": reason,
                "rejected_at": now,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    # Their campaigns must not stay in the review queue behind a refused brand.
    pulled = await db.campaigns.update_many(
        {"brand_id": oid, "status": CAMPAIGN_REVIEW_STATUS},
        {
            "$set": {
                "status": "draft",
                "review_reason": f"Brand not verified: {reason}",
                "updated_at": now,
            }
        },
    )

    await audit(
        user,
        "brand.reject",
        "brand_profile",
        result["_id"],
        after={"verified": False, "campaigns_returned": pulled.modified_count},
        note=reason,
    )
    name = result.get("business_name") or "your brand"
    delivery = await notify_over_utility_template(
        oid,
        "brand_rejected",
        title="We couldn't verify your brand yet",
        body=f"{name}: {reason}",
        params=[name, reason],
        link="/brand/profile",
    )
    out = _serialize_brand_profile(result)
    out["verification_reason"] = reason
    out["campaigns_returned_to_draft"] = pulled.modified_count
    out["notification"] = delivery
    return out


@admin_router.post("/brands/{user_id}/unverify")
async def unverify_brand(
    user_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Brand not found")
    now = datetime.now(timezone.utc)
    result = await db.brand_profiles.find_one_and_update(
        {"user_id": oid},
        {"$set": {"verified": False,
                "verification_state": "pending_verification", "updated_at": now}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    await audit(
        user,
        "brand.unverify",
        "brand_profile",
        result["_id"],
        after={"verified": False},
        note=(payload.reason if payload else None),
    )
    return _serialize_brand_profile(result)


def _serialize_admin_collab(
    collab: dict,
    campaign: Optional[dict],
    brand_name: Optional[str],
    creator_user: Optional[dict],
    creator_profile: Optional[dict],
    payment: Optional[dict],
) -> dict:
    return {
        "id": str(collab["_id"]),
        "state": collab.get("state"),
        "pitch": collab.get("pitch"),
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "content_url": collab.get("content_url"),
        "content_urls": collab.get("content_urls")
        or ([collab["content_url"]] if collab.get("content_url") else []),
        "scheduled_at": _iso(collab.get("scheduled_at")),
        "location_note": collab.get("location_note"),
        "exit_reason": collab.get("exit_reason"),
        "revision_note": collab.get("revision_note"),
        "agreed_at": _iso(collab.get("agreed_at")),
        "created_at": _iso(collab.get("created_at")),
        "updated_at": _iso(collab.get("updated_at")),
        "campaign": {
            "id": str((campaign or {}).get("_id")) if campaign else None,
            "title": (campaign or {}).get("title"),
            "area": (campaign or {}).get("area"),
            "category": (campaign or {}).get("category"),
            "budget_per_creator": (campaign or {}).get("budget_per_creator"),
            "compensation_type": _compensation_type(campaign),
            "status": (campaign or {}).get("status"),
        },
        "brand_name": brand_name,
        "creator": {
            "id": str((creator_user or {}).get("_id")) if creator_user else None,
            "name": (creator_profile or {}).get("name")
            or (creator_user or {}).get("name"),
            "email": (creator_user or {}).get("email"),
            "instagram_handle": (creator_profile or {}).get("instagram_handle"),
            "instagram_profile_url": (creator_profile or {}).get("instagram_profile_url"),
            "verification_status": (creator_profile or {}).get("verification_status"),
            "follower_count": (creator_profile or {}).get("follower_count"),
            "phone": (creator_user or {}).get("phone"),
            # Surfaced so an admin can see *before* clicking through to payment
            # that the payout details are missing.
            "payout_ready": payout_ready(creator_profile or {}),
        },
        "payment": (
            {
                "id": str(payment["_id"]),
                "agreed_amount": payment.get("agreed_amount"),
                "platform_fee": payment.get("platform_fee"),
                "creator_payout": payment.get("creator_payout"),
                "brand_invoice_amount": payment.get("brand_invoice_amount"),
                "brand_invoice_state": payment.get("brand_invoice_state"),
                "payment_reference": payment.get("payment_reference"),
                "state": payment.get("state"),
                "paid_at": _iso(payment.get("paid_at")),
            }
            if payment
            else None
        ),
    }


@admin_router.get("/collaborations")
async def list_all_collaborations(
    user: dict = Depends(require_roles("admin")),
):
    collabs = (
        await db.collaborations.find({}).sort("created_at", -1).to_list(length=2000)
    )
    if not collabs:
        return {"by_state": {s: [] for s in COLLAB_STATE_ORDER}, "total": 0}

    campaign_ids = list({c["campaign_id"] for c in collabs})
    campaigns = await db.campaigns.find(
        {"_id": {"$in": campaign_ids}}
    ).to_list(length=len(campaign_ids))
    campaign_by_id = {c["_id"]: c for c in campaigns}
    brand_map = await _load_brand_map([c["brand_id"] for c in campaigns])

    creator_ids = list({c["creator_id"] for c in collabs})
    creator_users = await db.users.find(
        {"_id": {"$in": creator_ids}}
    ).to_list(length=len(creator_ids))
    creator_user_by_id = {u["_id"]: u for u in creator_users}
    creator_profiles = await db.creator_profiles.find(
        {"user_id": {"$in": creator_ids}}
    ).to_list(length=len(creator_ids))
    creator_profile_by_uid = {p["user_id"]: p for p in creator_profiles}

    payments = await db.payments.find(
        {"collaboration_id": {"$in": [c["_id"] for c in collabs]}}
    ).to_list(length=len(collabs))
    payment_by_collab = {p["collaboration_id"]: p for p in payments}

    by_state: dict = {s: [] for s in COLLAB_STATE_ORDER + ["declined", "cancelled"]}
    for c in collabs:
        camp = campaign_by_id.get(c["campaign_id"])
        brand = brand_map.get(camp["brand_id"]) if camp else None
        brand_name = (brand or {}).get("business_name") or (brand or {}).get("name")
        creator_user = creator_user_by_id.get(c["creator_id"])
        creator_profile = creator_profile_by_uid.get(c["creator_id"])
        payment = payment_by_collab.get(c["_id"])
        row = _serialize_admin_collab(
            c, camp, brand_name, creator_user, creator_profile, payment
        )
        next_state = _next_collab_state(row["state"])
        row["next_state"] = next_state
        # Tell the console which button, if any, belongs to it — the brand owns
        # accepting and approving, and the API will refuse if we bypass them.
        row["next_owner"] = (
            "brand" if next_state in _BRAND_OWNED_TRANSITIONS else "admin"
        )
        row["can_advance"] = bool(next_state) and next_state not in _BRAND_OWNED_TRANSITIONS
        row["can_cancel"] = row["state"] not in TERMINAL_COLLAB_STATES
        by_state.setdefault(row["state"], []).append(row)
    return {"by_state": by_state, "total": len(collabs)}


@admin_router.get("/collaborations/{collab_id}")
async def get_admin_collaboration_detail(
    collab_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """One application, end to end.

    The lifecycle timeline is read out of the audit log rather than kept as a
    second history on the collaboration: the log is already written on every
    transition and is append-only, so a timeline built from it cannot disagree
    with the record. A separate `state_history` array would be a second truth
    to keep in step, and the one that drifts is always the one being read.

    **Declared after GET /collaborations**, which takes no path parameter, so
    ordering only matters against future fixed paths under this prefix.
    """
    oid = _as_oid(collab_id)
    if oid is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    brand = None
    if campaign:
        brand = (await _load_brand_map([campaign["brand_id"]])).get(
            campaign["brand_id"]
        )
    creator_user = await db.users.find_one({"_id": collab["creator_id"]})
    creator_profile = await db.creator_profiles.find_one(
        {"user_id": collab["creator_id"]}
    )
    payment = await db.payments.find_one({"collaboration_id": oid})

    row = _serialize_admin_collab(
        collab,
        campaign,
        (brand or {}).get("business_name") or (brand or {}).get("name"),
        creator_user,
        creator_profile,
        payment,
    )
    next_state = _next_collab_state(row["state"])
    row["next_state"] = next_state
    row["next_owner"] = "brand" if next_state in _BRAND_OWNED_TRANSITIONS else "admin"
    row["can_advance"] = bool(next_state) and next_state not in _BRAND_OWNED_TRANSITIONS
    row["can_cancel"] = row["state"] not in TERMINAL_COLLAB_STATES

    slot = None
    if collab.get("slot_id"):
        slot_doc = await db.campaign_slots.find_one({"_id": collab["slot_id"]})
        if slot_doc:
            slot = _serialize_slot(slot_doc)

    # Oldest first: a timeline is read forwards, unlike the audit log's own
    # most-recent-first listing.
    events = (
        await db.audit_log.find(
            {"subject_type": "collaboration", "subject_id": oid}
        )
        .sort("created_at", 1)
        .to_list(length=500)
    )

    return {
        "collaboration": row,
        "slot": slot,
        "payment": {
            "id": str(payment["_id"]),
            "state": payment.get("state"),
            "creator_payout": payment.get("creator_payout"),
            "platform_fee": payment.get("platform_fee"),
            "brand_invoice_amount": payment.get("brand_invoice_amount"),
            "invoice_state": payment.get("invoice_state"),
            "reference": payment.get("reference"),
            "paid_at": _iso(payment.get("paid_at")),
            "created_at": _iso(payment.get("created_at")),
        }
        if payment
        else None,
        "timeline": [
            {
                "id": str(e["_id"]),
                "action": e.get("action"),
                "actor_id": str(e["actor_id"]) if e.get("actor_id") else None,
                "actor_name": e.get("actor_name"),
                "actor_role": e.get("actor_role"),
                "before": _jsonable(e.get("before")),
                "after": _jsonable(e.get("after")),
                "note": e.get("note"),
                "created_at": _iso(e.get("created_at")),
            }
            for e in events
        ],
        # The order the states actually run in, so the page can draw the ones
        # still ahead rather than only the ones already behind.
        "state_order": list(COLLAB_STATE_ORDER),
        "terminal_states": list(TERMINAL_COLLAB_STATES),
        # Whether there is anything to measure yet, decided here rather than by
        # the UI keeping its own copy of the delivered set.
        "delivered_states": list(DELIVERED_COLLAB_STATES),
        "performance": _serialize_performance(
            await db.content_performance.find_one({"collaboration_id": oid})
        ),
    }


@admin_router.post("/collaborations/{collab_id}/advance")
async def advance_collaboration(
    collab_id: str,
    payload: AdvanceCollabPayload,
    user: dict = Depends(require_roles("admin")),
):
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    current = collab.get("state", "applied")

    # `from_state` is the state the caller was looking at. Requiring it to match
    # is what stops a double-click advancing twice and skipping a stage.
    if payload.from_state and payload.from_state != current:
        raise HTTPException(
            status_code=409,
            detail=f"This collaboration has already moved to {current}. Reload and try again.",
        )

    if current in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"This collaboration is {current} and can't be moved.",
        )
    if current == "in_payment":
        raise HTTPException(
            status_code=400,
            detail="This collaboration is awaiting payment — use Mark as paid to close it.",
        )

    to_state = _next_collab_state(current)
    if not to_state:
        raise HTTPException(
            status_code=400, detail="Collaboration is already at the final state"
        )
    if to_state in _BRAND_OWNED_TRANSITIONS:
        raise HTTPException(
            status_code=409,
            detail=(
                "This step is the brand's to take — they accept applicants and "
                "approve content from their dashboard."
            ),
        )

    now = datetime.now(timezone.utc)
    update: dict = {"state": to_state, "updated_at": now}

    if to_state == "commercial_agreed":
        # What the amount must be depends on how the brief pays. This used to
        # demand a figure whatever the campaign was, which left every barter
        # collaboration stuck at `accepted` for good.
        agreed_campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
        if not agreed_campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        resolved = _resolve_agreed_amount(agreed_campaign, payload.agreed_amount)
        if resolved is not None:
            update["agreed_amount"] = resolved
        update["agreed_at"] = now
        update["agreed_by"] = ObjectId(user["_id"])

    if to_state == "slot_booked":
        if payload.scheduled_at is None:
            raise HTTPException(
                status_code=422,
                detail="A date and time is required to book the slot.",
            )
        scheduled = payload.scheduled_at
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        update["scheduled_at"] = scheduled
        update["location_note"] = (payload.location_note or "").strip() or None

    if to_state == "in_payment":
        agreed = collab.get("agreed_amount")
        if agreed is None:
            raise HTTPException(
                status_code=422,
                detail="Collaboration has no agreed amount yet",
            )

        # We must know where the money is going before we say it's on the way.
        profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
        if not payout_ready(profile or {}):
            raise HTTPException(
                status_code=422,
                detail=(
                    "This creator hasn't added payout details yet (UPI ID and PAN). "
                    "Ask them to complete their profile before moving to payment."
                ),
            )

        fee = compute_fee(float(agreed), payload.platform_fee)
        # Create the payment record (idempotent by unique index on collaboration_id).
        existing_payment = await db.payments.find_one({"collaboration_id": oid})
        if existing_payment is None:
            await db.payments.insert_one(
                {
                    "collaboration_id": oid,
                    "agreed_amount": float(agreed),
                    "platform_fee": fee,
                    "fee_percent": platform_fee_percent(),
                    "creator_payout": float(agreed),
                    "brand_invoice_amount": round(float(agreed) + fee, 2),
                    "brand_invoice_state": "pending",
                    "payout_snapshot": {
                        "upi": (profile or {}).get("payout_upi"),
                        "account_name": (profile or {}).get("payout_account_name"),
                        "pan": (profile or {}).get("pan"),
                        "gstin": (profile or {}).get("gstin"),
                    },
                    "state": "pending",
                    "paid_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    updated = await db.collaborations.find_one_and_update(
        {"_id": oid, "state": current},  # precondition — never a blind write
        {"$set": update},
        return_document=True,
    )
    if not updated:
        raise HTTPException(
            status_code=409,
            detail="This collaboration just moved. Reload and try again.",
        )

    await audit(
        user,
        "collaboration.advance",
        "collaboration",
        oid,
        before={"state": current},
        after={k: v for k, v in update.items() if k != "updated_at"},
    )

    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    campaign_title = (campaign or {}).get("title") or "your collaboration"
    if to_state == "commercial_agreed":
        # The next move is the creator's, so say so — this is the message that
        # turns "agreed" into somebody booking a slot. A barter brief has no
        # amount to quote, and inventing ₹0 here would read as an insult.
        agreed_value = update.get("agreed_amount")
        booking = _next_action({"state": "commercial_agreed"}, campaign)["label"].lower()
        terms = (
            f"agreed at ₹{agreed_value:,.0f}"
            if agreed_value is not None
            else "confirmed — this one's a barter brief"
        )
        await notify(
            collab["creator_id"],
            "commercial_agreed",
            title="Fee agreed",
            body=f"{campaign_title} — {terms}. Over to you: {booking}.",
            link="/dashboard",
        )
    elif to_state == "slot_booked":
        when = update["scheduled_at"].strftime("%d %b, %I:%M %p")
        await notify(
            collab["creator_id"],
            "slot_booked",
            title="Slot confirmed",
            body=f"{campaign_title} — {when}."
            + (f" {update['location_note']}" if update.get("location_note") else ""),
            link="/dashboard",
        )

    return {
        "id": collab_id,
        "state": updated["state"],
        "agreed_amount": updated.get("agreed_amount"),
        "scheduled_at": _iso(updated.get("scheduled_at")),
        "next_state": _next_collab_state(updated["state"]),
    }


@admin_router.post("/collaborations/{collab_id}/revert")
async def revert_collaboration(
    collab_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Move a collaboration back one step.

    The ladder used to only go up, so a fee agreed at the wrong number or a slot
    booked on the wrong day had no fix short of cancelling the whole thing. This
    is the step back; re-advancing then writes the corrected values over the old
    ones.

    Not a way out of a finished collaboration: `closed` means the creator has
    been paid, and the exits are decisions rather than steps, so neither can be
    walked back from here.
    """
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    current = collab.get("state", "applied")
    if current == "closed":
        raise HTTPException(
            status_code=409,
            detail="This collaboration is closed and paid. It can't be reverted.",
        )
    if current in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This collaboration is {current}, which is an exit rather than a "
                "step. Reverting only walks back the pipeline."
            ),
        )

    to_state = _previous_collab_state(current)
    if not to_state:
        raise HTTPException(
            status_code=409,
            detail="This collaboration is at the first step — there's nothing behind it.",
        )

    # A paid-out payout is money that left the bank. Undoing the state that
    # produced it would strand the payment; refund is the route for that.
    payment = await db.payments.find_one({"collaboration_id": oid})
    if payment and payment.get("state") == "paid":
        raise HTTPException(
            status_code=409,
            detail="This payout has already been paid. Refund it instead of reverting.",
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid, "state": current},  # precondition — never a blind write
        {
            "$set": {
                "state": to_state,
                "reverted_at": now,
                "reverted_from": current,
                "revert_reason": payload.reason,
                "updated_at": now,
            },
            # Stepping back out of slot_booked gives the seat up; the slot link
            # goes with it so a re-book claims fresh.
            "$unset": {"slot_id": ""},
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    # The seat itself: only when leaving slot_booked backwards, and floored at
    # zero so a manual booking (no slot row) can't drive the count negative.
    if current == "slot_booked" and collab.get("slot_id"):
        await db.campaign_slots.update_one(
            {"_id": collab["slot_id"], "booked_count": {"$gt": 0}},
            {"$inc": {"booked_count": -1}, "$set": {"updated_at": now}},
        )
        await _tell_manager_a_seat_freed(collab, "reverted")

    # Stepping back out of `in_payment` must take the payable with it. The row
    # is deleted rather than cancelled because `collaboration_id` is unique, so
    # a cancelled one left behind would stop the payment being recreated when
    # the collaboration advances again. The audit entry below is the record.
    payment_removed = None
    if payment and current == "in_payment":
        await db.payments.delete_one({"_id": payment["_id"], "state": "pending"})
        payment_removed = {
            "payment_id": str(payment["_id"]),
            "creator_payout": payment.get("creator_payout"),
        }

    await audit(
        user,
        "collaboration.revert",
        "collaboration",
        oid,
        before={
            "state": current,
            # What the forward step had written, so the old numbers survive the
            # overwrite that a re-advance performs.
            "agreed_amount": collab.get("agreed_amount"),
            "scheduled_at": collab.get("scheduled_at"),
            "payment": payment_removed,
        },
        after={"state": to_state},
        note=payload.reason,
    )

    # Coming back below `accepted` frees the slot on the campaign again.
    await _sync_campaign_fill(collab["campaign_id"])

    return {
        "id": collab_id,
        "state": to_state,
        "reverted_from": current,
        "payment_voided": payment_removed is not None,
        "next_state": _next_collab_state(to_state),
    }


@admin_router.post("/collaborations/{collab_id}/decline")
async def decline_applicant(
    collab_id: str,
    payload: ReasonPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Turn down an applicant before anyone took them on.

    Separate from `cancel`: nothing was agreed and nothing was owed, so this is
    a "no thanks" rather than an admission that something fell through. Past
    `verified` the brand has accepted them, and ending it there is a
    cancellation.
    """
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    current = collab.get("state", "applied")
    if current in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409, detail=f"This application is already {current}."
        )
    if current not in _DECLINABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This creator is already {current} on the campaign. Cancel the "
                "collaboration instead of declining the application."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid, "state": current},
        {
            "$set": {
                "state": "declined",
                "active": False,
                "exit_reason": payload.reason,
                "declined_at": now,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.decline",
        "collaboration",
        oid,
        before={"state": current},
        after={"state": "declined"},
        note=payload.reason,
    )
    await _sync_campaign_fill(collab["campaign_id"])
    await notify(
        collab["creator_id"],
        "application_declined",
        title="Your application wasn't taken forward",
        body=payload.reason,
        link="/campaigns",
    )
    return {"id": collab_id, "state": "declined"}


@admin_router.post("/collaborations/{collab_id}/cancel")
async def cancel_collaboration(
    collab_id: str,
    payload: CancelCollabPayload,
    user: dict = Depends(require_roles("admin")),
):
    """End a collaboration that is already under way — a no-show, a pull-out, a
    brand cancelling the shoot. Without this the only exit was to leave the row
    sitting mid-pipeline forever.

    The awkward case is a cancellation after the fee was agreed: no payment row
    exists yet (one is only created at `in_payment`), so there is nothing to
    refund, but there was a number both sides had accepted. That number is
    recorded on the way out, and a cancellation after the creator has already
    turned up is flagged for a settlement decision rather than silently dropped.
    """
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    current = collab.get("state", "applied")
    if current in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409, detail=f"This collaboration is already {current}."
        )

    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})

    payment = await db.payments.find_one({"collaboration_id": oid})
    if payment and payment.get("state") == "paid":
        raise HTTPException(
            status_code=409,
            detail=(
                "This collaboration has already been paid out. Refund the payment "
                "instead — that cancels the collaboration with it."
            ),
        )

    # Was there a live commitment when it fell over, and had the creator already
    # done the work? Both are facts, not policy — what to pay is a human call,
    # so this flags it rather than deciding it.
    order = COLLAB_STATE_ORDER
    agreed_amount = collab.get("agreed_amount")
    had_agreement = current in order and order.index(current) >= order.index(
        "commercial_agreed"
    )
    creator_attended = current in order and order.index(current) >= order.index(
        "attended"
    )
    settlement_review_needed = bool(
        agreed_amount and creator_attended and payload.cancellation_type != "creator_no_show"
    )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid, "state": current},
        {
            "$set": {
                "state": "cancelled",
                "active": False,
                "exit_reason": payload.reason,
                "cancellation_type": payload.cancellation_type,
                "cancelled_at": now,
                "cancelled_from_state": current,
                # Kept so a dropped commitment is still readable after the
                # collaboration leaves the "ongoing" group it was counted in.
                "agreed_amount_at_cancellation": agreed_amount if had_agreement else None,
                "creator_attended": creator_attended,
                "settlement_review_needed": settlement_review_needed,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    # A cancelled collaboration must not leave a payable row behind.
    if payment:
        await db.payments.update_one(
            {"_id": payment["_id"]},
            {"$set": {"state": "cancelled", "updated_at": now}},
        )

    # And a seat it was holding goes back on sale — but only before the event:
    # a no-show's seat was still consumed on the day.
    if collab.get("slot_id") and current == "slot_booked":
        await db.campaign_slots.update_one(
            {"_id": collab["slot_id"], "booked_count": {"$gt": 0}},
            {"$inc": {"booked_count": -1}, "$set": {"updated_at": now}},
        )
        await _tell_manager_a_seat_freed(collab, "cancelled")

    await audit(
        user,
        "collaboration.cancel",
        "collaboration",
        oid,
        before={"state": current, "agreed_amount": agreed_amount},
        after={
            "state": "cancelled",
            "cancellation_type": payload.cancellation_type,
            "settlement_review_needed": settlement_review_needed,
        },
        note=payload.reason,
        **_campaign_audit_context(campaign),
    )
    await _sync_campaign_fill(collab["campaign_id"])
    await notify(
        collab["creator_id"],
        "application_declined",
        title="Collaboration cancelled",
        body=payload.reason,
        link="/dashboard",
    )
    # The brand loses a creator it had counted on — and if anything was agreed,
    # a place to fill. It hears that from us, not from the empty table.
    cancelled_profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    await _tell_brand_manager_about_campaign(
        campaign,
        actor=user,
        event="brand_creator_cancelled",
        title="A creator dropped off your campaign",
        body=(
            f"{(cancelled_profile or {}).get('name') or 'A creator'} is off "
            f"“{(campaign or {}).get('title')}” — {payload.reason}"
        ),
    )
    return {
        "id": collab_id,
        "state": "cancelled",
        "cancellation_type": payload.cancellation_type,
        "cancelled_from_state": current,
        "agreed_amount_at_cancellation": agreed_amount if had_agreement else None,
        # True when the creator had already turned up for work that was agreed:
        # somebody has to decide what they are owed.
        "settlement_review_needed": settlement_review_needed,
    }


@admin_router.post("/payments/{payment_id}/mark_paid")
async def mark_payment_paid(
    payment_id: str,
    payload: MarkPaidPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Record a payout that happened in the bank.

    This does not move money — it asserts that money moved — so it demands a
    reference you can reconcile against, and refuses to fire twice.
    """
    try:
        pid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Payment not found")

    existing = await db.payments.find_one({"_id": pid})
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found")
    if existing.get("state") == "paid":
        raise HTTPException(
            status_code=409,
            detail=f"Already marked paid on {_iso(existing.get('paid_at'))}.",
        )
    if existing.get("state") == "cancelled":
        raise HTTPException(
            status_code=409, detail="This payment belongs to a cancelled collaboration."
        )

    now = datetime.now(timezone.utc)
    payment = await db.payments.find_one_and_update(
        {"_id": pid, "state": "pending"},  # precondition, so a double-click is a no-op
        {
            "$set": {
                "state": "paid",
                "paid_at": now,
                "payment_reference": payload.payment_reference.strip(),
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not payment:
        raise HTTPException(
            status_code=409, detail="This payment just changed — reload and try again."
        )

    # Move the linked collaboration to 'closed'.
    await db.collaborations.update_one(
        {"_id": payment["collaboration_id"]},
        {"$set": {"state": "closed", "updated_at": now}},
    )

    collab = await db.collaborations.find_one({"_id": payment["collaboration_id"]})
    await audit(
        user,
        "payment.mark_paid",
        "payment",
        pid,
        before={"state": "pending"},
        after={
            "state": "paid",
            "creator_payout": payment.get("creator_payout"),
            "payment_reference": payload.payment_reference.strip(),
        },
    )
    if collab:
        await notify(
            collab["creator_id"],
            "payment_sent",
            title="Payment sent",
            body=(
                f"₹{(payment.get('creator_payout') or 0):,.0f} has been sent. "
                f"Reference: {payload.payment_reference.strip()}."
            ),
            link="/dashboard",
        )

    return {
        "id": payment_id,
        "state": payment["state"],
        "paid_at": _iso(payment["paid_at"]),
        "payment_reference": payment.get("payment_reference"),
        "collaboration_id": str(payment["collaboration_id"]),
    }


@admin_router.post("/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    payload: RefundPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Claw back a payout that already went out, and end the collaboration.

    Like `mark_paid`, this records something that happened in the bank rather
    than moving money itself. `refunded` is deliberately a separate state from
    `cancelled`: cancelled is a payout that never happened, refunded is one that
    happened and came back, and every revenue figure has to be able to tell them
    apart.

    If we had already collected from the brand, the refund leaves us holding
    their money — that is flagged rather than resolved, because paying a brand
    back is a decision with an invoice attached.
    """
    try:
        pid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Payment not found")

    existing = await db.payments.find_one({"_id": pid})
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found")

    state = existing.get("state")
    if state == "refunded":
        raise HTTPException(
            status_code=409,
            detail=f"This payout was already refunded on {_iso(existing.get('refunded_at'))}.",
        )
    if state != "paid":
        raise HTTPException(
            status_code=409,
            detail=(
                f"This payout is {state}, so there is nothing to refund. Cancel the "
                "collaboration instead."
            ),
        )

    now = datetime.now(timezone.utc)
    invoice_state = existing.get("brand_invoice_state")
    brand_refund_due = invoice_state == "settled"

    payment = await db.payments.find_one_and_update(
        {"_id": pid, "state": "paid"},  # precondition, so a double-click is a no-op
        {
            "$set": {
                "state": "refunded",
                "refunded_at": now,
                "refund_reason": payload.reason,
                "refund_reference": (payload.refund_reference or "").strip() or None,
                # Nothing is owed to us on a refunded collaboration. An invoice
                # already settled is money we now hold for the brand, so that
                # one is left alone and flagged instead of quietly voided.
                "brand_invoice_state": invoice_state if brand_refund_due else "void",
                "brand_refund_due": brand_refund_due,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not payment:
        raise HTTPException(
            status_code=409, detail="This payment just changed — reload and try again."
        )

    # The collaboration goes with it: work that was paid for and then unwound is
    # not a closed collaboration.
    collab_id = payment["collaboration_id"]
    collab = await db.collaborations.find_one({"_id": collab_id})
    previous_state = (collab or {}).get("state")
    await db.collaborations.update_one(
        {"_id": collab_id},
        {
            "$set": {
                "state": "cancelled",
                "active": False,
                "cancellation_type": "admin_cancelled",
                "exit_reason": payload.reason,
                "cancelled_at": now,
                "cancelled_from_state": previous_state,
                "refunded": True,
                "updated_at": now,
            }
        },
    )

    await audit(
        user,
        "payment.refund",
        "payment",
        pid,
        before={"state": "paid", "creator_payout": payment.get("creator_payout")},
        after={
            "state": "refunded",
            "refund_reference": payment.get("refund_reference"),
            "collaboration_state": "cancelled",
            "brand_refund_due": brand_refund_due,
        },
        note=payload.reason,
    )

    if collab:
        await _sync_campaign_fill(collab["campaign_id"])
        await notify(
            collab["creator_id"],
            "application_declined",
            title="Collaboration reversed",
            body=payload.reason,
            link="/dashboard",
        )

    return {
        "id": payment_id,
        "state": "refunded",
        "refunded_at": _iso(now),
        "refund_reference": payment.get("refund_reference"),
        "collaboration_id": str(collab_id),
        "collaboration_state": "cancelled",
        # True when the brand had already settled: we are holding their money.
        "brand_refund_due": brand_refund_due,
    }


@admin_router.post("/payments/{payment_id}/invoice_state")
async def set_brand_invoice_state(
    payment_id: str,
    state: Literal["pending", "sent", "settled"],
    user: dict = Depends(require_roles("admin")),
):
    """Track what the brand owes us, separately from what we owe the creator."""
    try:
        pid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Payment not found")
    now = datetime.now(timezone.utc)
    payment = await db.payments.find_one_and_update(
        {"_id": pid},
        {"$set": {"brand_invoice_state": state, "updated_at": now}},
        return_document=True,
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    await audit(user, "payment.invoice_state", "payment", pid, after={"brand_invoice_state": state})
    return {"id": payment_id, "brand_invoice_state": state}


@admin_router.get("/metrics")
async def admin_metrics(user: dict = Depends(require_roles("admin"))):
    await _expire_stale_campaigns()
    open_campaigns = await db.campaigns.count_documents({"status": "open"})
    verified_creators = await db.creator_profiles.count_documents(
        {"verification_status": "verified"}
    )
    agg = await db.payments.aggregate(
        [
            {"$match": {"state": "paid"}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$creator_payout"},
                    "fees": {"$sum": "$platform_fee"},
                    "n": {"$sum": 1},
                }
            },
        ]
    ).to_list(length=1)
    total_paid = float(agg[0]["total"]) if agg else 0.0
    # What the business actually earned. Previously invisible in our own console.
    platform_revenue = float(agg[0]["fees"]) if agg else 0.0

    pending_agg = await db.payments.aggregate(
        [
            {"$match": {"state": "pending"}},
            {"$group": {"_id": None, "total": {"$sum": "$creator_payout"}, "n": {"$sum": 1}}},
        ]
    ).to_list(length=1)

    receivable_agg = await db.payments.aggregate(
        [
            {"$match": {"brand_invoice_state": {"$in": ["pending", "sent"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$brand_invoice_amount"}}},
        ]
    ).to_list(length=1)

    # Campaign counts by status, in one pass, zero-filled so a caller never has
    # to guard for a missing key.
    campaigns_by_status = {s: 0 for s in CampaignStatus.__args__}
    async for row in db.campaigns.aggregate(
        [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    ):
        if row["_id"]:
            campaigns_by_status[row["_id"]] = row["n"]

    # What is actually sitting on our desk. Counted per queue and summed, so the
    # headline number can always be explained.
    collab_action_counts = {s: 0 for s in ADMIN_ACTION_STATES}
    async for row in db.collaborations.aggregate(
        [
            {"$match": {"state": {"$in": list(ADMIN_ACTION_STATES)}}},
            {"$group": {"_id": "$state", "n": {"$sum": 1}}},
        ]
    ):
        collab_action_counts[row["_id"]] = row["n"]

    creators_pending_review = await db.creator_profiles.count_documents(
        _AWAITING_REVIEW_QUERY
    )
    creators_changed = await db.creator_profiles.count_documents(
        {"verification_status": "verified", "pending_review": True}
    )
    brands_unverified = await db.brand_profiles.count_documents({"verified": False})
    campaigns_to_review = await db.campaigns.count_documents(
        {"status": CAMPAIGN_REVIEW_STATUS}
    )
    payouts_pending_count = int(pending_agg[0]["n"]) if pending_agg else 0

    awaiting = {
        "creators_to_review": creators_pending_review,
        "creator_edits_to_review": creators_changed,
        "brands_to_verify": brands_unverified,
        "campaigns_to_review": campaigns_to_review,
        "applicants_to_verify": collab_action_counts["applied"],
        "fees_to_agree": collab_action_counts["accepted"],
        "slots_to_book": collab_action_counts["commercial_agreed"],
        "attendance_to_confirm": collab_action_counts["slot_booked"],
        "payments_to_start": collab_action_counts["content_approved"],
        "payouts_to_record": payouts_pending_count,
    }

    return {
        "open_campaigns": open_campaigns,
        "verified_creators": verified_creators,
        "total_paid_out": total_paid,
        "platform_revenue": platform_revenue,
        "platform_fee_percent": platform_fee_percent(),
        # Gross value transacted: what brands paid in total, which is the
        # creators' fees plus our margin on settled collaborations.
        "gmv": round(total_paid + platform_revenue, 2),
        "collaborations_paid": int(agg[0]["n"]) if agg else 0,
        "payouts_pending": float(pending_agg[0]["total"]) if pending_agg else 0.0,
        "payouts_pending_count": payouts_pending_count,
        "brand_receivable": float(receivable_agg[0]["total"]) if receivable_agg else 0.0,
        "campaigns_by_status": campaigns_by_status,
        "campaigns_total": sum(campaigns_by_status.values()),
        "campaigns_pending_review": campaigns_to_review,
        "awaiting_admin_action": sum(awaiting.values()),
        "awaiting_breakdown": awaiting,
        # Kept for existing callers; the same numbers now appear in the
        # breakdown above.
        "creators_pending_review": creators_pending_review,
        "brands_unverified": brands_unverified,
        "applicants_awaiting_verification": collab_action_counts["applied"],
    }


# The three buckets an applicant can be in, from the console's point of view.
#
# `verified` is the admin's own approval of the application — it is the state
# the console's Approve button *produces*, so it has to read as approved here
# or the admin approves somebody and watches them stay in the pending column.
# That was the bug: this bucketed on COLLAB_GROUP_APPLIED, which is
# ("applied", "verified").
#
# COLLAB_GROUP_APPLIED is deliberately left alone. It answers a different
# question — "did this application go anywhere yet", on a creator's history,
# where an approved-but-not-yet-accepted application genuinely has not — and
# reusing it here conflated the two.
_APPLICANT_PENDING_STATES = ("applied",)
_APPLICANT_APPROVED_STATES = (
    ("verified",) + tuple(COLLAB_GROUP_ONGOING) + tuple(COLLAB_GROUP_COMPLETED)
)

# Work actually in flight: the brand has taken this creator on. Deliberately
# *not* the approved set above, which now includes `verified` — an application
# we have approved but no brand has accepted is not work, and counting it as
# such would inflate "active creators" with people who are still waiting.
_ENGAGED_COLLAB_STATES = tuple(COLLAB_GROUP_ONGOING) + tuple(COLLAB_GROUP_COMPLETED)
_APPLICANT_BUCKETS = (
    ("applied", _APPLICANT_PENDING_STATES),
    ("approved", _APPLICANT_APPROVED_STATES),
    ("rejected", COLLAB_GROUP_ENDED),
)

# Every state belongs to exactly one bucket, or an applicant silently vanishes
# from a board that is supposed to account for all of them.
assert set(COLLAB_STATE_ORDER) | set(COLLAB_GROUP_ENDED) == set(
    _APPLICANT_PENDING_STATES + _APPLICANT_APPROVED_STATES + COLLAB_GROUP_ENDED
), "an applicant state belongs to no bucket"


def _bucket_counts_expr() -> dict:
    """$sum/$cond accumulators counting each applicant bucket in one pass."""
    out = {
        name: {"$sum": {"$cond": [{"$in": ["$state", list(states)]}, 1, 0]}}
        for name, states in _APPLICANT_BUCKETS
    }
    # Completed is a subset of approved, reported separately because "how many
    # actually finished" is a different question from "how many were taken on".
    out["completed"] = {
        "$sum": {"$cond": [{"$in": ["$state", list(COLLAB_GROUP_COMPLETED)]}, 1, 0]}
    }
    return out


@admin_router.get("/dashboard")
async def admin_dashboard(
    campaign_id: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_roles("admin")),
):
    """Everything the console's landing view needs, in one call.

    Five separate requests used to fill this screen, which meant five spinners
    and five chances for one slow query to make the page look broken. Each
    block below is a single aggregation — `$facet` where one collection answers
    several questions, `$group` where it answers one — so this is a fixed
    number of round trips whatever the data looks like.

    `campaign_id` scopes every number to one campaign, for the same screen
    zoomed in on a single brief.
    """
    await _expire_stale_campaigns()

    limit = max(1, min(int(limit or 50), 200))
    scoped_oid = None
    if campaign_id:
        try:
            scoped_oid = ObjectId(campaign_id)
        except Exception:
            raise HTTPException(status_code=422, detail="campaign_id is not a valid id.")
        if not await db.campaigns.find_one({"_id": scoped_oid}):
            raise HTTPException(status_code=404, detail="Campaign not found")

    campaign_match = {"_id": scoped_oid} if scoped_oid else {}
    collab_match = {"campaign_id": scoped_oid} if scoped_oid else {}

    # --- campaigns: statuses, the summary rows, and the active-brand count ---
    campaign_facet = await db.campaigns.aggregate(
        ([{"$match": campaign_match}] if campaign_match else [])
        + [
            {
                "$facet": {
                    "by_status": [{"$group": {"_id": "$status", "n": {"$sum": 1}}}],
                    "active_brands": [
                        {"$match": {"status": {"$in": list(ACTIVE_CAMPAIGN_STATUSES)}}},
                        {"$group": {"_id": "$brand_id"}},
                        {"$count": "n"},
                    ],
                    "rows": [
                        {"$sort": {"created_at": -1}},
                        {"$limit": limit},
                        {
                            "$lookup": {
                                "from": "brand_profiles",
                                "localField": "brand_id",
                                "foreignField": "user_id",
                                "as": "brand",
                            }
                        },
                        {"$addFields": {"brand": {"$arrayElemAt": ["$brand", 0]}}},
                    ],
                }
            }
        ]
    ).to_list(length=1)
    facet = campaign_facet[0] if campaign_facet else {}

    campaigns_by_status = {s: 0 for s in CampaignStatus.__args__}
    for row in facet.get("by_status") or []:
        if row["_id"]:
            campaigns_by_status[row["_id"]] = row["n"]

    active_brands_rows = facet.get("active_brands") or []
    active_brands = active_brands_rows[0]["n"] if active_brands_rows else 0

    docs = facet.get("rows") or []

    # --- collaborations: per-campaign buckets and the queue counts, one pass ---
    collab_facet = await db.collaborations.aggregate(
        ([{"$match": collab_match}] if collab_match else [])
        + [
            {
                "$facet": {
                    "per_campaign": [
                        {"$group": {"_id": "$campaign_id", **_bucket_counts_expr()}}
                    ],
                    "by_state": [{"$group": {"_id": "$state", "n": {"$sum": 1}}}],
                    # Distinct creators with work in flight or finished — the
                    # honest reading of "active", rather than "signed up once".
                    "active_creators": [
                        {"$match": {"state": {"$in": list(_ENGAGED_COLLAB_STATES)}}},
                        {"$group": {"_id": "$creator_id"}},
                        {"$count": "n"},
                    ],
                }
            }
        ]
    ).to_list(length=1)
    cfacet = collab_facet[0] if collab_facet else {}

    per_campaign = {r["_id"]: r for r in (cfacet.get("per_campaign") or [])}
    collab_by_state = {r["_id"]: r["n"] for r in (cfacet.get("by_state") or [])}
    active_creator_rows = cfacet.get("active_creators") or []
    active_creators = active_creator_rows[0]["n"] if active_creator_rows else 0

    # --- money: settled and outstanding, one pass -------------------------
    payment_match: dict = {}
    if scoped_oid:
        # Payments hang off collaborations, so scoping to a campaign means
        # naming that campaign's collaborations first.
        ids = await db.collaborations.find(
            {"campaign_id": scoped_oid}, {"_id": 1}
        ).to_list(length=1000)
        payment_match = {"collaboration_id": {"$in": [d["_id"] for d in ids]}}

    money = await db.payments.aggregate(
        ([{"$match": payment_match}] if payment_match else [])
        + [
            {
                "$facet": {
                    "paid": [
                        {"$match": {"state": "paid"}},
                        {
                            "$group": {
                                "_id": None,
                                "payout": {"$sum": "$creator_payout"},
                                "fees": {"$sum": "$platform_fee"},
                                "n": {"$sum": 1},
                            }
                        },
                    ],
                    "pending": [
                        {"$match": {"state": "pending"}},
                        {
                            "$group": {
                                "_id": None,
                                "total": {"$sum": "$creator_payout"},
                                "n": {"$sum": 1},
                            }
                        },
                    ],
                }
            }
        ]
    ).to_list(length=1)
    mfacet = money[0] if money else {}
    paid_rows = mfacet.get("paid") or []
    pending_rows = mfacet.get("pending") or []
    total_paid = float(paid_rows[0]["payout"]) if paid_rows else 0.0
    platform_revenue = float(paid_rows[0]["fees"]) if paid_rows else 0.0
    payouts_pending_count = int(pending_rows[0]["n"]) if pending_rows else 0
    payouts_pending = float(pending_rows[0]["total"]) if pending_rows else 0.0

    # --- the review queues -------------------------------------------------
    # Creator and brand vetting are platform-wide: they are not about any one
    # campaign, so they read zero when the view is scoped to one.
    if scoped_oid:
        creators_to_review = 0
        creator_edits = 0
        brands_to_verify = 0
        verified_creators = 0
    else:
        creator_facet = await db.creator_profiles.aggregate(
            [
                {
                    "$facet": {
                        "pending": [
                            {"$match": _AWAITING_REVIEW_QUERY},
                            {"$count": "n"},
                        ],
                        "changed": [
                            {
                                "$match": {
                                    "verification_status": "verified",
                                    "pending_review": True,
                                }
                            },
                            {"$count": "n"},
                        ],
                        "verified": [
                            {"$match": {"verification_status": "verified"}},
                            {"$count": "n"},
                        ],
                    }
                }
            ]
        ).to_list(length=1)
        cf = creator_facet[0] if creator_facet else {}
        first = lambda rows: rows[0]["n"] if rows else 0  # noqa: E731
        creators_to_review = first(cf.get("pending") or [])
        creator_edits = first(cf.get("changed") or [])
        verified_creators = first(cf.get("verified") or [])
        brands_to_verify = await db.brand_profiles.count_documents({"verified": False})

    awaiting = {
        "creators_to_review": creators_to_review,
        "creator_edits_to_review": creator_edits,
        "brands_to_verify": brands_to_verify,
        "campaigns_to_review": campaigns_by_status.get(CAMPAIGN_REVIEW_STATUS, 0),
        "collaborations_to_move": sum(
            collab_by_state.get(s, 0) for s in ADMIN_ACTION_STATES
        ),
        "payouts_to_record": payouts_pending_count,
    }

    # --- the per-campaign summary -----------------------------------------
    summary = []
    for d in docs:
        counts = per_campaign.get(d["_id"]) or {}
        brand = d.get("brand") or {}
        summary.append(
            {
                "id": str(d["_id"]),
                "title": d.get("title"),
                "brand_id": str(d["brand_id"]),
                "brand_name": brand.get("business_name"),
                "campaign_type": d.get("campaign_type"),
                "status": d.get("status"),
                # One date or two, depending on what the type actually carries.
                "event_date": _iso(d.get("event_date")),
                "start_date": _iso(d.get("start_date")),
                "end_date": _iso(d.get("end_date")),
                "creators_needed": d.get("creators_needed"),
                # Keyed off the bucket definitions rather than spelled out, so
                # the summary can never drift from what was counted.
                **{key: counts.get(key, 0) for key in _bucket_counts_expr()},
            }
        )

    return {
        "scoped_to_campaign": campaign_id,
        "campaigns": {
            **campaigns_by_status,
            # The feed's word for it, so the console and the creator app agree.
            "live": campaigns_by_status.get("open", 0),
            "total": sum(campaigns_by_status.values()),
        },
        "awaiting": awaiting,
        "awaiting_total": sum(awaiting.values()),
        "totals": {
            "gmv": round(total_paid + platform_revenue, 2),
            "total_paid_out": round(total_paid, 2),
            "platform_revenue": round(platform_revenue, 2),
            "payouts_pending": round(payouts_pending, 2),
            "collaborations_paid": int(paid_rows[0]["n"]) if paid_rows else 0,
            # Creators with work in flight or behind them, not everyone who
            # ever signed up.
            "active_creators": active_creators,
            "verified_creators": verified_creators,
            "active_brands": active_brands,
        },
        "campaign_summary": summary,
        "summary_truncated": len(docs) >= limit,
    }


@admin_router.get("/campaigns/{campaign_id}/applicants")
async def admin_campaign_applicants(
    campaign_id: str,
    user: dict = Depends(require_roles("admin")),
):
    """Everyone who ever applied to one campaign, in three groups.

    The brand's own applicant board shows the same people but answers a
    different question — it is a decision screen, and it stops at the brand's
    own campaigns. This is the admin's read of any campaign, including the ones
    that ended.

    One pipeline with the three joins; the bucketing is done here because
    splitting a list already in memory is cheaper than three more passes.
    """
    campaign = await _admin_campaign_or_404(campaign_id)

    rows = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": campaign["_id"]}},
            {"$sort": {"created_at": -1}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "creator_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$addFields": {"user": {"$arrayElemAt": ["$user", 0]}}},
            {
                "$lookup": {
                    "from": "creator_profiles",
                    "localField": "creator_id",
                    "foreignField": "user_id",
                    "as": "profile",
                }
            },
            {"$addFields": {"profile": {"$arrayElemAt": ["$profile", 0]}}},
            {
                "$lookup": {
                    "from": "payments",
                    "localField": "_id",
                    "foreignField": "collaboration_id",
                    "as": "payment",
                }
            },
            {"$addFields": {"payment": {"$arrayElemAt": ["$payment", 0]}}},
        ]
    ).to_list(length=1000)

    groups = {name: [] for name, _ in _APPLICANT_BUCKETS}
    for r in rows:
        profile = r.get("profile") or {}
        account = r.get("user") or {}
        payment = r.get("payment") or {}
        state = r.get("state")
        entry = {
            "collaboration_id": str(r["_id"]),
            "creator_id": str(r["creator_id"]),
            "name": profile.get("name") or account.get("name"),
            "profile_image_url": profile.get("profile_image_url"),
            "instagram_handle": profile.get("instagram_handle"),
            "instagram_profile_url": profile.get("instagram_profile_url"),
            "follower_count": profile.get("follower_count"),
            "verification_status": profile.get("verification_status"),
            "quoted_rate": r.get("quoted_rate"),
            "agreed_amount": r.get("agreed_amount"),
            "state": state,
            "pitch": r.get("pitch"),
            "scheduled_at": _iso(r.get("scheduled_at")),
            "exit_reason": r.get("exit_reason"),
            "payment_state": payment.get("state"),
            "created_at": _iso(r.get("created_at")),
            "updated_at": _iso(r.get("updated_at")),
        }
        for name, states in _APPLICANT_BUCKETS:
            if state in states:
                groups[name].append(entry)
                break

    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([campaign["_id"]])).get(campaign["_id"], 0)
    brand_map = await _load_brand_map([campaign["brand_id"]])
    brand = brand_map.get(campaign["brand_id"]) or {}

    return {
        "campaign": {
            "id": campaign_id,
            "title": campaign.get("title"),
            "brand_id": str(campaign["brand_id"]),
            "brand_name": brand.get("business_name") or brand.get("name"),
            "brand_logo_url": brand.get("logo_url"),
            "campaign_type": campaign.get("campaign_type"),
            "execution_owner": _execution_owner(campaign),
            "status": campaign.get("status"),
            "budget_per_creator": campaign.get("budget_per_creator"),
            "compensation_type": _compensation_type(campaign),
            "event_date": _iso(campaign.get("event_date")),
            "start_date": _iso(campaign.get("start_date")),
            "end_date": _iso(campaign.get("end_date")),
            "creators_needed": needed,
            "filled_slots": filled,
            "spots_left": max(0, needed - filled),
        },
        "counts": {name: len(rows_) for name, rows_ in groups.items()},
        "total": len(rows),
        **groups,
    }


@admin_router.get("/audit")
async def list_audit_log(
    limit: int = 100,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    user: dict = Depends(require_roles("admin")),
):
    """Who did what, most recent first.

    `action` matches a whole action ("payment.refund") or a prefix ("payment"),
    because "everything that happened to money" is the question people actually
    arrive with. `brand_id` and `campaign_id` are the other two: a brand
    manager's work lands on collaborations and slots as often as on the
    campaign, so filtering by subject alone never assembled the story.
    """
    query: dict = {}
    for field, raw in (("brand_id", brand_id), ("campaign_id", campaign_id)):
        if raw:
            oid = _as_oid(raw)
            if oid is None:
                raise HTTPException(
                    status_code=422, detail=f"{field} is not a valid id."
                )
            query[field] = oid
    if subject_type:
        query["subject_type"] = subject_type
    if subject_id:
        # Subject ids are stored as ObjectId where we have one and as a string
        # otherwise, so both shapes have to be matched.
        candidates: list = [subject_id]
        try:
            candidates.append(ObjectId(subject_id))
        except Exception:
            pass
        query["subject_id"] = {"$in": candidates}
    if actor_id:
        try:
            query["actor_id"] = ObjectId(actor_id)
        except Exception:
            raise HTTPException(status_code=422, detail="actor_id is not a valid id.")
    if action:
        term = action.strip()[:80]
        if "." in term:
            query["action"] = term
        else:
            query["action"] = {"$regex": f"^{re.escape(term)}\\.", "$options": "i"}
    if date_from or date_to:
        window: dict = {}
        if date_from:
            window["$gte"] = date_from
        if date_to:
            window["$lte"] = date_to
        query["created_at"] = window

    limit = max(1, min(int(limit or 100), 500))
    docs = (
        await db.audit_log.find(query)
        .sort("created_at", -1)
        .to_list(length=limit)
    )
    return [
        {
            "id": str(d["_id"]),
            # The id, not just the name: names change, and "which admin" is the
            # question an audit log exists to answer.
            "actor_id": str(d["actor_id"]) if d.get("actor_id") else None,
            "actor_name": d.get("actor_name"),
            "actor_role": d.get("actor_role"),
            "action": d.get("action"),
            "subject_type": d.get("subject_type"),
            "subject_id": str(d.get("subject_id")),
            "brand_id": str(d["brand_id"]) if d.get("brand_id") else None,
            "campaign_id": str(d["campaign_id"]) if d.get("campaign_id") else None,
            "before": _jsonable(d.get("before")),
            "after": _jsonable(d.get("after")),
            "note": d.get("note"),
            "created_at": _iso(d.get("created_at")),
        }
        for d in docs
    ]


# --- Campaign managers -------------------------------------------------------


@admin_router.post("/managers")
async def create_manager_account(
    payload: CreateManagerPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Create a campaign-manager account.

    Managers are staff: an admin makes the account, and they sign in with email
    and password like an admin does. There is deliberately no self-signup route
    into this role — it can read creators' phone numbers.
    """
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="That email already has an account.")

    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "name": payload.name.strip(),
        "role": "campaign_manager",
        "phone": (payload.phone or "").strip() or None,
        "status": "active",
        "password_hash": hash_password(payload.password),
        "created_at": now,
    }
    result = await db.users.insert_one(doc)
    await audit(
        user,
        "manager.create",
        "user",
        result.inserted_id,
        after={"email": email, "role": "campaign_manager"},
    )
    return {
        "id": str(result.inserted_id),
        "name": doc["name"],
        "email": email,
        "phone": doc["phone"],
        "role": "campaign_manager",
    }


@admin_router.get("/managers")
async def list_managers(user: dict = Depends(require_roles("admin"))):
    """Every manager, with how many campaigns each is currently carrying —
    the number you look at before assigning them another one."""
    managers = (
        await db.users.find({"role": "campaign_manager"})
        .sort("name", 1)
        .to_list(length=200)
    )
    if not managers:
        return []

    load: dict = {}
    async for row in db.campaigns.aggregate(
        [
            {
                "$match": {
                    "manager_id": {"$in": [m["_id"] for m in managers]},
                    "status": {"$in": list(ACTIVE_CAMPAIGN_STATUSES) + ["paused"]},
                }
            },
            {"$group": {"_id": "$manager_id", "n": {"$sum": 1}}},
        ]
    ):
        load[row["_id"]] = row["n"]

    return [
        {
            "id": str(m["_id"]),
            "name": m.get("name"),
            "email": m.get("email"),
            "phone": m.get("phone"),
            "active_campaigns": load.get(m["_id"], 0),
        }
        for m in managers
    ]


@admin_router.post("/campaigns/{campaign_id}/assign-manager")
async def assign_campaign_manager(
    campaign_id: str,
    payload: AssignManagerPayload,
    user: dict = Depends(require_roles("admin")),
):
    """Assign (or reassign) the manager who runs a campaign.

    Name, phone and email are snapshotted onto the campaign: that is what the
    brand and the accepted creators see, and it must not silently change if the
    manager later edits their account mid-campaign.
    """
    campaign = await _admin_campaign_or_404(campaign_id)

    try:
        manager_oid = ObjectId(payload.manager_user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Manager not found")
    manager = await db.users.find_one({"_id": manager_oid, "role": "campaign_manager"})
    if not manager:
        raise HTTPException(
            status_code=404,
            detail="No campaign manager with that id. Create the account first.",
        )

    previous = campaign.get("manager_name")
    now = datetime.now(timezone.utc)
    await db.campaigns.update_one(
        {"_id": campaign["_id"]},
        {
            "$set": {
                "manager_id": manager_oid,
                "manager_name": manager.get("name"),
                "manager_phone": manager.get("phone"),
                "manager_email": manager.get("email"),
                "manager_assigned_at": now,
                # Putting one of our managers on a campaign *is* taking over
                # its execution — there is no such thing as a WeAre manager
                # running a campaign the brand is still said to run, and the
                # two fields disagreeing would send applications to the wrong
                # inbox while the console said otherwise.
                "execution_owner": "weare",
                "updated_at": now,
            }
        },
    )

    await audit(
        user,
        "campaign.assign_manager",
        "campaign",
        campaign["_id"],
        before={"manager_name": previous},
        after={"manager_name": manager.get("name")},
    )
    await notify(
        manager_oid,
        "manager_assigned",
        title="You've been assigned a campaign",
        body=f"“{campaign.get('title')}” is yours to run.",
        link="/manager",
    )
    return {
        "id": campaign_id,
        "manager_id": str(manager_oid),
        "manager_name": manager.get("name"),
        "manager_phone": manager.get("phone"),
        "manager_email": manager.get("email"),
        "reassigned_from": previous,
    }


# ---------------------------------------------------------------------------
# Scheduled job: chase half-finished creator profiles
# ---------------------------------------------------------------------------


def _nudge_after_days() -> int:
    """How long to leave somebody alone before chasing them."""
    try:
        return max(1, int(os.environ.get("PROFILE_NUDGE_AFTER_DAYS", "3")))
    except ValueError:
        logger.warning("PROFILE_NUDGE_AFTER_DAYS is not a number — using 3")
        return 3


def _nudge_interval_seconds() -> int:
    """How often the loop wakes. Zero disables it entirely."""
    try:
        return max(0, int(os.environ.get("PROFILE_NUDGE_INTERVAL_SECONDS", "3600")))
    except ValueError:
        return 3600


async def nudge_stale_creator_profiles(limit: int = 200) -> dict:
    """WhatsApp the creators who signed up, started a profile and stopped.

    Exactly once each, ever. The claim is the write: the profile is stamped
    with `onboarding_nudge_sent_at` under a filter that only matches while it
    is absent, so two workers racing produce one message, and a send that
    fails afterwards still counts as used up. Chasing somebody twice about the
    same unfinished form is how a marketplace teaches people to mute it.

    Idempotent and safe to call by hand — it is wired to a loop below and to
    POST /admin/jobs/creator-nudges, because this deployment has no external
    scheduler to hang it off.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_nudge_after_days())
    template = os.environ.get("AISENSY_TEMPLATE_PROFILE_NUDGE", "").strip()

    # Old enough to have gone quiet, not yet chased, not yet decided on.
    candidates = (
        await db.creator_profiles.find(
            {
                "created_at": {"$lte": cutoff},
                "onboarding_nudge_sent_at": {"$exists": False},
                "verification_status": "pending",
                "submitted_for_review_at": {"$in": [None, False]},
            }
        )
        .sort("created_at", 1)
        .to_list(length=limit)
    )

    report = {"considered": len(candidates), "sent": 0, "skipped": 0, "failed": 0}
    for profile in candidates:
        completeness = _profile_completeness(profile)
        if completeness["complete"]:
            # Finished but not submitted. That is a different message and a
            # different problem, so leave them for it rather than spending the
            # one nudge here.
            report["skipped"] += 1
            continue

        claimed = await db.creator_profiles.find_one_and_update(
            {"_id": profile["_id"], "onboarding_nudge_sent_at": {"$exists": False}},
            {"$set": {"onboarding_nudge_sent_at": now}},
        )
        if not claimed:
            report["skipped"] += 1
            continue

        account = await db.users.find_one({"_id": profile["user_id"]})
        name = profile.get("name") or (account or {}).get("name") or "there"
        outstanding = ", ".join(row["label"] for row in completeness["missing"][:3])
        body = (
            f"Your WeAre profile is {completeness['percent']}% done. "
            f"Still needed: {outstanding}. Finish it and brands can start booking you."
        )
        delivered = False
        mode = None
        phone = (account or {}).get("phone")
        if phone:
            try:
                mode = await _send_aisensy_utility(
                    phone, name, template, [name, str(completeness["percent"]), outstanding]
                )
                delivered = mode == "aisensy"
            except HTTPException as exc:
                logger.warning("profile nudge to %s failed: %s", phone, exc.detail)
            except Exception as exc:  # a bad send must not stop the batch
                logger.error("profile nudge to %s failed: %s", phone, exc)

        await record_notification(
            profile["user_id"],
            "profile_nudge",
            title="Finish your profile",
            body=body,
            link="/onboarding/creator",
            delivered=delivered,
        )
        report["sent" if delivered or mode == "simulation" else "failed"] += 1

    if report["sent"]:
        logger.info("profile nudge: %s", report)
    return report


async def _nudge_loop() -> None:
    """Drive the nudge on a timer, since there is no external scheduler here."""
    interval = _nudge_interval_seconds()
    while True:
        try:
            await asyncio.sleep(interval)
            await nudge_stale_creator_profiles()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A failed pass must never take the loop — or the app — down.
            logger.error("profile nudge pass failed: %s", exc)


# ---------------------------------------------------------------------------
# Scheduled jobs: keep Instagram tokens alive and the stats current
# ---------------------------------------------------------------------------


async def refresh_instagram_tokens(limit: int = 200) -> dict:
    """Renew long-lived tokens before they lapse.

    A long-lived token is good for 60 days and can be exchanged for a fresh 60
    from 24 hours old. We renew a week out, so the job can be down for days
    without anybody quietly falling off — and when Instagram refuses, the
    connection goes stale and the creator is asked to reconnect rather than
    the number silently freezing at whatever it last was.
    """
    if not instagram_configured():
        return {"considered": 0, "refreshed": 0, "stale": 0, "skipped": "not configured"}

    now = datetime.now(timezone.utc)
    due = now + timedelta(days=INSTAGRAM_REFRESH_WINDOW_DAYS)
    docs = (
        await db.instagram_connections.find(
            {"status": "connected", "token_expires_at": {"$lte": due}}
        )
        .sort("token_expires_at", 1)
        .to_list(length=limit)
    )

    report = {"considered": len(docs), "refreshed": 0, "stale": 0}
    for doc in docs:
        token = _decrypt_token(doc.get("access_token"))
        if not token:
            await _mark_connection_stale(doc, "We lost access to your Instagram connection.")
            report["stale"] += 1
            continue
        try:
            body = await _instagram_get(
                "/refresh_access_token",
                {"grant_type": "ig_refresh_token", "access_token": token},
            )
        except HTTPException as exc:
            detail = str(exc.detail)
            if _is_revoked(detail):
                await _mark_connection_stale(doc, "Instagram access was withdrawn or expired.")
                report["stale"] += 1
            else:
                # A transient Graph error is not a revocation. Leave it
                # connected and try again next pass rather than sending
                # somebody a reconnect prompt over a blip.
                logger.warning("Instagram token refresh deferred for %s: %s", doc.get("username"), detail)
            continue

        fresh = body.get("access_token")
        expires_in = int(body.get("expires_in") or INSTAGRAM_TOKEN_TTL_DAYS * 86400)
        if not fresh:
            logger.warning("Instagram refresh returned no token for %s", doc.get("username"))
            continue
        await db.instagram_connections.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "access_token": _encrypt_token(fresh),
                    "token_expires_at": now + timedelta(seconds=expires_in),
                    "last_refreshed_at": now,
                    "status": "connected",
                    "stale_reason": None,
                    "updated_at": now,
                }
            },
        )
        report["refreshed"] += 1

    if report["refreshed"] or report["stale"]:
        logger.info("Instagram token refresh: %s", report)
    return report


async def refresh_instagram_stats(limit: int = 200) -> dict:
    """Pull follower count, media count, reach and engagement on a schedule.

    Never on a dashboard load. The ceiling is 200 calls per user per hour and
    a reading costs three, so a creator who opens the app twenty times a day
    would spend that budget on numbers that barely move. Cached for
    INSTAGRAM_STATS_TTL_HOURS (12) and read from the cache everywhere else.
    """
    if not instagram_configured():
        return {"considered": 0, "updated": 0, "stale": 0, "skipped": "not configured"}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=_instagram_stats_ttl_hours())
    docs = (
        await db.instagram_connections.find(
            {
                "status": "connected",
                "$or": [
                    {"stats_fetched_at": {"$lte": cutoff}},
                    {"stats_fetched_at": {"$exists": False}},
                ],
            }
        )
        .sort("stats_fetched_at", 1)
        .to_list(length=limit)
    )

    report = {"considered": len(docs), "updated": 0, "stale": 0, "failed": 0}
    for doc in docs:
        token = _decrypt_token(doc.get("access_token"))
        if not token:
            await _mark_connection_stale(doc, "We lost access to your Instagram connection.")
            report["stale"] += 1
            continue
        try:
            stats = await _fetch_instagram_stats(doc["ig_user_id"], token)
        except HTTPException as exc:
            if _is_revoked(str(exc.detail)):
                await _mark_connection_stale(doc, "Instagram access was withdrawn or expired.")
                report["stale"] += 1
            else:
                logger.warning("Instagram stats deferred for %s: %s", doc.get("username"), exc.detail)
                report["failed"] += 1
            continue
        except Exception as exc:  # one bad account must not stop the batch
            logger.error("Instagram stats failed for %s: %s", doc.get("username"), exc)
            report["failed"] += 1
            continue
        await _store_instagram_stats(doc, stats)
        report["updated"] += 1

    if report["updated"] or report["stale"]:
        logger.info("Instagram stats refresh: %s", report)
    return report


async def _instagram_loop() -> None:
    """Drive both Instagram jobs on a timer, since there is no scheduler here."""
    interval = _instagram_job_interval_seconds()
    while True:
        try:
            await asyncio.sleep(interval)
            await refresh_instagram_tokens()
            await refresh_instagram_stats()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A failed pass must never take the loop — or the app — down.
            logger.error("Instagram job pass failed: %s", exc)


@admin_router.post("/jobs/instagram")
async def run_instagram_jobs(user: dict = Depends(require_roles("admin"))):
    """Run both Instagram passes now. Same functions the timer calls, same
    cache window, so a manual run can't blow the rate limit."""
    tokens = await refresh_instagram_tokens()
    stats = await refresh_instagram_stats()
    report = {"tokens": tokens, "stats": stats}
    await audit(user, "job.instagram_refresh", "job", "instagram", after=report)
    return report


@admin_router.post("/jobs/creator-nudges")
async def run_creator_nudges(user: dict = Depends(require_roles("admin"))):
    """Run the nudge pass now. Same function the timer calls, same once-only
    guarantee, so a manual run can't double-message anybody."""
    report = await nudge_stale_creator_profiles()
    # A manual run puts messages on real phones, so it belongs in the log next
    # to every other admin action that reaches somebody.
    await audit(user, "job.creator_nudges", "job", "creator_nudges", after=report)
    return report


api_router.include_router(admin_router)


# ---------------------------------------------------------------------------
# Campaign manager router — scoped to assigned campaigns
# ---------------------------------------------------------------------------

manager_router = APIRouter(prefix="/manager", tags=["manager"])


async def _managed_campaign_or_404(campaign_id: str, user: dict) -> dict:
    """Load a campaign the caller is allowed to run.

    A manager sees only what they are assigned to — 404 rather than 403, the
    same shape as brand ownership, so the existence of other campaigns leaks
    nothing. Admins pass on everything.
    """
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    doc = await db.campaigns.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.get("role") != "admin" and doc.get("manager_id") != ObjectId(user["_id"]):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return doc


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Mongo hands back naive datetimes; comparisons need them aware."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _validate_slot_times(campaign: dict, starts_at: datetime, ends_at: Optional[datetime]):
    """Check a slot's times against the campaign it belongs to.

    Shared by create and edit, because a slot moved onto the wrong day is
    exactly as wrong as one created there.
    """
    ctype = campaign.get("campaign_type")
    if not ctype:
        raise HTTPException(
            status_code=409,
            detail="This campaign predates campaign types and can't take slots.",
        )

    starts = _as_utc(starts_at)
    ends = _as_utc(ends_at)
    if ends is not None and ends <= starts:
        raise HTTPException(status_code=422, detail="A slot has to end after it starts.")

    if ctype in EVENT_CAMPAIGN_TYPES:
        event = _as_utc(campaign.get("event_date"))
        if event and starts.date() != event.date():
            raise HTTPException(
                status_code=422,
                detail=f"This {ctype.replace('_', ' ')} happens on "
                f"{event.date().isoformat()} — slots have to be on that day.",
            )
    else:  # personal_table
        if ends is None:
            raise HTTPException(
                status_code=422,
                detail="A personal-table window needs an end time.",
            )
        win_start = _as_utc(campaign.get("start_date"))
        win_end = _as_utc(campaign.get("end_date"))
        if (win_start and starts < win_start) or (win_end and ends > win_end):
            raise HTTPException(
                status_code=422,
                detail="The window has to sit inside the campaign's dates.",
            )
    return starts, ends


async def _slot_or_404(slot_id: str, user: dict):
    """Load a slot, asserting the caller runs the campaign it belongs to."""
    try:
        oid = ObjectId(slot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Slot not found")
    slot = await db.campaign_slots.find_one({"_id": oid})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    campaign = await _managed_campaign_or_404(str(slot["campaign_id"]), user)
    return slot, campaign


async def _managed_collab_or_404(collab_id: str, user: dict):
    """Load a collaboration on a campaign the caller runs.

    Scope rides on the campaign: a manager touches a creator because they are
    running the day that creator is booked onto, not because of anything about
    the creator.
    """
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    campaign = await _managed_campaign_or_404(str(collab["campaign_id"]), user)
    return collab, campaign


def _serialize_slot(doc: dict) -> dict:
    capacity = int(doc.get("capacity") or 0)
    booked = int(doc.get("booked_count") or 0)
    return {
        "id": str(doc["_id"]),
        "campaign_id": str(doc["campaign_id"]),
        "starts_at": _iso(doc.get("starts_at")),
        "ends_at": _iso(doc.get("ends_at")),
        "capacity": capacity,
        "booked_count": booked,
        "spots_left": max(0, capacity - booked),
        "created_at": _iso(doc.get("created_at")),
    }


@manager_router.get("/campaigns")
async def list_managed_campaigns(
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """The campaigns this manager runs. An admin calling it sees everything
    assigned to anyone — the workload view."""
    query: dict = (
        {"manager_id": ObjectId(user["_id"])}
        if user.get("role") == "campaign_manager"
        else {"manager_id": {"$ne": None}}
    )
    docs = (
        await db.campaigns.find(query).sort("created_at", -1).to_list(length=500)
    )
    if not docs:
        return []

    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    filled = await _filled_counts_for([d["_id"] for d in docs])

    # Slot totals per campaign, one pass.
    slot_totals: dict = {}
    async for row in db.campaign_slots.aggregate(
        [
            {"$match": {"campaign_id": {"$in": [d["_id"] for d in docs]}}},
            {
                "$group": {
                    "_id": "$campaign_id",
                    "slots": {"$sum": 1},
                    "capacity": {"$sum": "$capacity"},
                    "booked": {"$sum": "$booked_count"},
                }
            },
        ]
    ):
        slot_totals[row["_id"]] = row

    out = []
    for d in docs:
        brand = brand_map.get(d["brand_id"]) or {}
        s = slot_totals.get(d["_id"]) or {}
        out.append(
            {
                "id": str(d["_id"]),
                "title": d.get("title"),
                "brand_name": brand.get("business_name") or brand.get("name"),
                "brand_logo_url": brand.get("logo_url"),
                "campaign_type": d.get("campaign_type"),
                "status": d.get("status"),
                "area": d.get("area"),
                "event_date": _iso(d.get("event_date")),
                "start_date": _iso(d.get("start_date")),
                "end_date": _iso(d.get("end_date")),
                "venue_address": d.get("venue_address"),
                "venue_instructions": d.get("venue_instructions"),
                "on_site_contact": d.get("on_site_contact"),
                "creators_needed": d.get("creators_needed"),
                "filled_slots": filled.get(d["_id"], 0),
                "manager_name": d.get("manager_name"),
                "slot_count": s.get("slots", 0),
                "slot_capacity": s.get("capacity", 0),
                "slot_booked": s.get("booked", 0),
            }
        )
    return out


@manager_router.get("/campaigns/{campaign_id}/slots")
async def list_campaign_slots(
    campaign_id: str,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    campaign = await _managed_campaign_or_404(campaign_id, user)
    docs = (
        await db.campaign_slots.find({"campaign_id": campaign["_id"]})
        .sort("starts_at", 1)
        .to_list(length=500)
    )
    return {
        "campaign_id": campaign_id,
        "campaign_type": campaign.get("campaign_type"),
        "slots": [_serialize_slot(d) for d in docs],
    }


@manager_router.post("/campaigns/{campaign_id}/slots")
async def create_campaign_slot(
    campaign_id: str,
    payload: SlotPayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Add a bookable slot.

    For launch/group_event the slot has to sit on the event day — a slot on
    another date is a typo with real people showing up to it. For
    personal_table it is an availability window inside the campaign's dates,
    so ends_at is required there.
    """
    campaign = await _managed_campaign_or_404(campaign_id, user)
    starts, ends = _validate_slot_times(campaign, payload.starts_at, payload.ends_at)

    now = datetime.now(timezone.utc)
    doc = {
        "campaign_id": campaign["_id"],
        "starts_at": starts,
        "ends_at": ends,
        "capacity": int(payload.capacity),
        "booked_count": 0,
        "created_by": ObjectId(user["_id"]),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.campaign_slots.insert_one(doc)
    doc["_id"] = result.inserted_id
    await audit(
        user,
        "slot.create",
        "campaign_slot",
        result.inserted_id,
        after={"campaign_id": str(campaign["_id"]), "starts_at": _iso(starts),
               "capacity": payload.capacity},
    )
    return _serialize_slot(doc)


@manager_router.delete("/slots/{slot_id}")
async def delete_campaign_slot(
    slot_id: str,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Remove an empty slot. One with bookings holds real people's plans —
    those bookings have to be moved (revert and rebook) before it can go."""
    try:
        oid = ObjectId(slot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Slot not found")
    slot = await db.campaign_slots.find_one({"_id": oid})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    # Scope check rides on the campaign.
    await _managed_campaign_or_404(str(slot["campaign_id"]), user)

    # Precondition on emptiness, so a booking that lands mid-delete wins.
    result = await db.campaign_slots.delete_one({"_id": oid, "booked_count": 0})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Creators are booked on this slot — move them before deleting it.",
        )
    await audit(
        user,
        "slot.delete",
        "campaign_slot",
        oid,
        before={"starts_at": _iso(slot.get("starts_at")), "capacity": slot.get("capacity")},
    )
    return {"id": slot_id, "deleted": True}


@manager_router.post("/slots")
async def create_slot(
    payload: CreateSlotPayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Create a slot, naming the campaign in the body.

    The same operation as POST /manager/campaigns/{id}/slots, which stays for
    callers already using it; both land here.
    """
    return await create_campaign_slot(
        payload.campaign_id,
        SlotPayload(
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            capacity=payload.capacity,
        ),
        user,
    )


@manager_router.patch("/slots/{slot_id}")
async def update_slot(
    slot_id: str,
    payload: UpdateSlotPayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Move a slot or resize it.

    Capacity can go up freely and down only to what is already booked —
    shrinking below that would leave creators holding places the slot says do
    not exist. Moving the time takes the people booked on it with it, so their
    collaborations are re-stamped rather than left pointing at the old hour.
    """
    slot, campaign = await _slot_or_404(slot_id, user)

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Nothing to update")

    booked = int(slot.get("booked_count") or 0)
    new_capacity = fields.get("capacity", slot.get("capacity"))
    if new_capacity is not None and int(new_capacity) < booked:
        raise HTTPException(
            status_code=409,
            detail=f"{booked} creator(s) are booked on this slot — capacity can't go below that.",
        )

    starts = fields.get("starts_at", slot.get("starts_at"))
    # An explicit null clears the end time; anything else keeps or replaces it.
    ends = fields["ends_at"] if "ends_at" in fields else slot.get("ends_at")
    starts, ends = _validate_slot_times(campaign, starts, ends)

    now = datetime.now(timezone.utc)
    update = {"starts_at": starts, "ends_at": ends, "updated_at": now}
    if "capacity" in fields:
        update["capacity"] = int(fields["capacity"])

    updated = await db.campaign_slots.find_one_and_update(
        {"_id": slot["_id"]}, {"$set": update}, return_document=True
    )

    # Anyone booked on it is booked on the new time, not the old one.
    moved = 0
    if starts != _as_utc(slot.get("starts_at")):
        result = await db.collaborations.update_many(
            {"slot_id": slot["_id"], "state": "slot_booked"},
            {"$set": {"scheduled_at": starts, "updated_at": now}},
        )
        moved = result.modified_count

    await audit(
        user,
        "slot.update",
        "campaign_slot",
        slot["_id"],
        before={
            "starts_at": _iso(slot.get("starts_at")),
            "capacity": slot.get("capacity"),
        },
        after={
            "starts_at": _iso(starts),
            "capacity": updated.get("capacity"),
            "collaborations_moved": moved,
        },
    )
    out = _serialize_slot(updated)
    out["collaborations_moved"] = moved
    return out


# ---------------------------------------------------------------------------
# On the day
# ---------------------------------------------------------------------------

# Who is actually coming. An applicant the brand hasn't taken isn't on the
# roster, and someone who has been through it already isn't either.
_ROSTER_STATES = (
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "content_approved",
    "in_payment",
    "closed",
)


async def _roster_rows(campaign: dict, *, reveal_contact: bool = True) -> list:
    """Everyone confirmed on a campaign, with what the manager needs on the day.

    One pipeline rather than a query per creator: a roster of forty would
    otherwise be eighty round trips on a phone at a venue.

    `reveal_contact` is what separates the WeAre manager's copy from the
    brand's. It defaults to True because the manager's is the original use and
    the brand's route passes False explicitly — a caller that forgets is a
    caller inside WeAre.
    """
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": campaign["_id"], "state": {"$in": list(_ROSTER_STATES)}}},
            {"$sort": {"scheduled_at": 1, "created_at": 1}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "creator_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$addFields": {"user": {"$arrayElemAt": ["$user", 0]}}},
            {
                "$lookup": {
                    "from": "creator_profiles",
                    "localField": "creator_id",
                    "foreignField": "user_id",
                    "as": "profile",
                }
            },
            {"$addFields": {"profile": {"$arrayElemAt": ["$profile", 0]}}},
            {
                "$lookup": {
                    "from": "campaign_slots",
                    "localField": "slot_id",
                    "foreignField": "_id",
                    "as": "slot",
                }
            },
            {"$addFields": {"slot": {"$arrayElemAt": ["$slot", 0]}}},
        ]
    ).to_list(length=1000)

    out = []
    for r in rows:
        state = r.get("state")
        profile = r.get("profile") or {}
        account = r.get("user") or {}
        slot = r.get("slot") or {}
        row = {
            "collaboration_id": str(r["_id"]),
            "creator_id": str(r["creator_id"]),
            "name": profile.get("name") or account.get("name"),
            "instagram_handle": profile.get("instagram_handle"),
        }
        if reveal_contact:
            # A WeAre manager rings these on the day — that is the whole job.
            # A brand doesn't get them: the key is absent rather than null, so
            # a brand response has no creator-contact shape at all.
            row["phone"] = account.get("phone")
        out.append(
            {
                **row,
                "state": state,
                "slot_id": str(r["slot_id"]) if r.get("slot_id") else None,
                "slot_time": _iso(slot.get("starts_at") or r.get("scheduled_at")),
                "slot_ends_at": _iso(slot.get("ends_at")),
                # Three plain words rather than nine pipeline states: on the day
                # the only question is whether they turned up.
                "attendance": (
                    "no_show"
                    if state in ("declined", "cancelled")
                    else "attended"
                    if state in ("attended", "content_submitted", "content_approved",
                                 "in_payment", "closed")
                    else "expected"
                ),
                "booked": state != "accepted" and bool(r.get("slot_id")),
                "agreed_amount": r.get("agreed_amount"),
            }
        )
    return out


@manager_router.get("/campaigns/{campaign_id}/roster")
async def campaign_roster(
    campaign_id: str,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Who is coming, when, and how to reach them."""
    campaign = await _managed_campaign_or_404(campaign_id, user)
    rows = await _roster_rows(campaign)
    return {
        "campaign_id": campaign_id,
        "title": campaign.get("title"),
        "campaign_type": campaign.get("campaign_type"),
        "event_date": _iso(campaign.get("event_date")),
        "venue_address": campaign.get("venue_address"),
        "venue_instructions": campaign.get("venue_instructions"),
        "on_site_contact": campaign.get("on_site_contact"),
        "expected": sum(1 for r in rows if r["attendance"] == "expected"),
        "attended": sum(1 for r in rows if r["attendance"] == "attended"),
        "no_shows": sum(1 for r in rows if r["attendance"] == "no_show"),
        "roster": rows,
    }


@manager_router.get("/campaigns/{campaign_id}/daysheet")
async def campaign_daysheet(
    campaign_id: str,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """The roster as a CSV, for the clipboard at the door.

    Written with the csv module rather than joined by hand: a creator called
    "Priya, Rao" would otherwise silently become two columns.
    """
    campaign = await _managed_campaign_or_404(campaign_id, user)
    rows = await _roster_rows(campaign)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Slot time", "Name", "Instagram", "Phone", "Attendance", "State"])
    for r in rows:
        writer.writerow(
            [
                r["slot_time"] or "",
                r["name"] or "",
                f"@{r['instagram_handle']}" if r.get("instagram_handle") else "",
                r["phone"] or "",
                r["attendance"],
                r["state"],
            ]
        )

    slug = re.sub(r"[^a-z0-9]+", "-", (campaign.get("title") or "campaign").lower()).strip("-")
    filename = f"daysheet-{slug or 'campaign'}-{datetime.now(timezone.utc).date()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _check_in_collaboration(collab: dict, campaign: dict, user: dict) -> dict:
    """Mark a creator as turned up.

    The same transition the admin's advance makes, done by the person actually
    standing there. Only from slot_booked — checking in somebody who never got
    a slot would skip the booking the venue is counting on.

    Shared by the WeAre manager's route and the brand manager's: who is holding
    the clipboard depends on whether the campaign was reassigned, and the
    attendance record must not depend on that.
    """
    collab_id = str(collab["_id"])
    current = collab.get("state")
    if current == "attended":
        raise HTTPException(status_code=409, detail="They're already checked in.")
    if current != "slot_booked":
        raise HTTPException(
            status_code=409,
            detail=(
                f"This collaboration is {current} — only a booked creator can be "
                "checked in."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": "slot_booked"},
        {
            "$set": {
                "state": "attended",
                "checked_in_at": now,
                "checked_in_by": ObjectId(user["_id"]),
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.check_in",
        "collaboration",
        collab["_id"],
        before={"state": "slot_booked"},
        after={"state": "attended"},
        **_campaign_audit_context(campaign),
    )
    return {"id": collab_id, "state": "attended", "checked_in_at": _iso(now)}


@manager_router.post("/collaborations/{collab_id}/performance")
async def manager_record_performance(
    collab_id: str,
    payload: PerformancePayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """The same thing, for the manager who was actually at the shoot.

    Scoped to their assigned campaigns by `_managed_campaign_or_404`, which is
    what keeps a manager out of a campaign they were never given.
    """
    collab = await _collab_or_404(collab_id)
    await _managed_campaign_or_404(str(collab["campaign_id"]), user)
    return await _record_performance(collab, payload, user)


@manager_router.post("/collaborations/{collab_id}/check-in")
async def check_in_creator(
    collab_id: str,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Mark a creator as turned up, as the assigned WeAre manager."""
    collab, campaign = await _managed_collab_or_404(collab_id, user)
    return await _check_in_collaboration(collab, campaign, user)


@manager_router.post("/collaborations/{collab_id}/no-show")
async def mark_no_show(
    collab_id: str,
    payload: NoShowPayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Record that a booked creator didn't turn up.

    This deliberately does not cancel anything. A manager at a venue knows who
    was in the room; whether the collaboration ends, and whether anything is
    owed, is the admin's call with the money in front of them. So the flag is
    raised here and the collaboration is left where it is, showing up on the
    admin's desk with `no_show_reported` set and the note attached — which is
    what the cancel endpoint reads when it is used (cancellation_type
    creator_no_show suppresses the settlement flag).
    """
    collab, campaign = await _managed_collab_or_404(collab_id, user)
    current = collab.get("state")
    if current in TERMINAL_COLLAB_STATES:
        raise HTTPException(
            status_code=409, detail=f"This collaboration is already {current}."
        )
    if current != "slot_booked":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only a booked creator can be a no-show — "
                f"this one is {current}."
            ),
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": "slot_booked"},
        {
            "$set": {
                "no_show_reported": True,
                "no_show_note": payload.note.strip(),
                "no_show_reported_at": now,
                "no_show_reported_by": ObjectId(user["_id"]),
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="This just moved — reload and try again.")

    await audit(
        user,
        "collaboration.no_show",
        "collaboration",
        collab["_id"],
        before={"state": current},
        after={"no_show_reported": True},
        note=payload.note.strip(),
        **_campaign_audit_context(campaign),
    )
    creator_profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    await _tell_brand_manager_unless_managed(
        campaign,
        "brand_creator_no_show",
        title="A creator didn't turn up",
        body=(
            f"{(creator_profile or {}).get('name') or 'A creator'} was marked a "
            f"no-show on “{campaign.get('title')}”. The WeAre team will settle it."
        ),
    )
    return {
        "id": collab_id,
        "state": current,
        "no_show_reported": True,
        "note": payload.note.strip(),
        # What happens next is the admin's, and the UI should say so.
        "next_step": (
            "Flagged for the WeAre team. They'll cancel it as a no-show, and "
            "refund the brand if anything was already paid."
        ),
    }


@manager_router.post("/collaborations/{collab_id}/reschedule")
async def reschedule_creator(
    collab_id: str,
    payload: ReschedulePayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Move a booked creator to a different slot on the same campaign.

    The new seat is claimed before the old one is released, under the same
    conditional increment booking uses — otherwise a reschedule into a full
    slot would free the creator's original place and leave them with neither.
    """
    collab, campaign = await _managed_collab_or_404(collab_id, user)
    if collab.get("state") != "slot_booked":
        raise HTTPException(
            status_code=409,
            detail=f"This collaboration is {collab.get('state')} — there's no booking to move.",
        )

    try:
        target_oid = ObjectId(payload.slot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Slot not found")
    if collab.get("slot_id") == target_oid:
        raise HTTPException(status_code=409, detail="They're already on that slot.")

    target = await db.campaign_slots.find_one({"_id": target_oid})
    if not target or target["campaign_id"] != campaign["_id"]:
        # Another campaign's slot is not a slot as far as this campaign goes.
        raise HTTPException(status_code=404, detail="Slot not found")

    now = datetime.now(timezone.utc)
    claimed = await db.campaign_slots.find_one_and_update(
        {"_id": target_oid, "$expr": {"$lt": ["$booked_count", "$capacity"]}},
        {"$inc": {"booked_count": 1}, "$set": {"updated_at": now}},
        return_document=True,
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="That slot is full. Pick another.")

    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": "slot_booked", "slot_id": collab.get("slot_id")},
        {
            "$set": {
                "slot_id": target_oid,
                "scheduled_at": target["starts_at"],
                "rescheduled_at": now,
                "reschedule_reason": (payload.reason or "").strip() or None,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    if not updated:
        # Give the new seat back rather than holding one they never got.
        await db.campaign_slots.update_one(
            {"_id": target_oid, "booked_count": {"$gt": 0}},
            {"$inc": {"booked_count": -1}},
        )
        raise HTTPException(
            status_code=409, detail="This just moved — reload and try again."
        )

    # Only once the move is written does the old seat go back on sale.
    if collab.get("slot_id"):
        await db.campaign_slots.update_one(
            {"_id": collab["slot_id"], "booked_count": {"$gt": 0}},
            {"$inc": {"booked_count": -1}, "$set": {"updated_at": now}},
        )

    await audit(
        user,
        "collaboration.reschedule",
        "collaboration",
        collab["_id"],
        before={"slot_id": str(collab.get("slot_id")) if collab.get("slot_id") else None},
        after={"slot_id": str(target_oid), "scheduled_at": _iso(target["starts_at"])},
        note=(payload.reason or "").strip() or None,
        **_campaign_audit_context(campaign),
    )
    await notify(
        collab["creator_id"],
        "slot_booked",
        title="Your slot moved",
        body=(
            f"{campaign.get('title')} — you're now at "
            f"{target['starts_at'].strftime('%d %b, %I:%M %p')}."
        ),
        link=f"/campaigns/{str(campaign['_id'])}",
    )
    moved_profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    await _tell_brand_manager_unless_managed(
        campaign,
        "brand_slot_rescheduled",
        title="A creator's slot moved",
        body=(
            f"{(moved_profile or {}).get('name') or 'A creator'} is now at "
            f"{target['starts_at'].strftime('%d %b, %I:%M %p')} on "
            f"“{campaign.get('title')}”."
        ),
    )
    return {
        "id": collab_id,
        "state": "slot_booked",
        "slot": _serialize_slot(claimed),
        "scheduled_at": _iso(target["starts_at"]),
    }


@manager_router.post("/campaigns/{campaign_id}/broadcast")
async def broadcast_to_campaign(
    campaign_id: str,
    payload: BroadcastPayload,
    user: dict = Depends(require_roles("campaign_manager", "admin")),
):
    """Message everyone confirmed on the campaign.

    Sent one at a time through the utility sender — the same helper, with the
    same simulation fallback — so one unreachable number doesn't swallow the
    rest, and the result says who actually got it. Everyone gets the in-app
    copy either way.
    """
    campaign = await _managed_campaign_or_404(campaign_id, user)
    rows = await _roster_rows(campaign)
    # Somebody who has already been through it doesn't need today's briefing.
    audience = [r for r in rows if r["attendance"] == "expected"]
    if not audience:
        raise HTTPException(
            status_code=409,
            detail="Nobody is confirmed on this campaign yet.",
        )

    message = payload.message.strip()
    title = campaign.get("title") or "your campaign"
    results = []
    delivered = 0
    for row in audience:
        outcome = await notify_over_utility_template(
            row["creator_id"],
            "campaign_broadcast",
            title=f"Message about {title}",
            body=message,
            params=[title, message],
            link=f"/campaigns/{campaign_id}",
        )
        if outcome["delivered"]:
            delivered += 1
        results.append(
            {
                "creator_id": row["creator_id"],
                "name": row["name"],
                "delivered": outcome["delivered"],
                "mode": outcome["mode"],
                "error": outcome["error"],
            }
        )

    await audit(
        user,
        "campaign.broadcast",
        "campaign",
        campaign["_id"],
        after={"recipients": len(results), "delivered": delivered},
        note=message,
    )
    return {
        "campaign_id": campaign_id,
        "recipients": len(results),
        "delivered": delivered,
        "failed": len(results) - delivered,
        "results": results,
    }


api_router.include_router(manager_router)




# --- Campaigns router ------------------------------------------------------

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_LIVE_STATUSES = LIVE_CAMPAIGN_STATUSES


def _serialize_campaign(doc: dict, brand: Optional[dict] = None) -> dict:
    return {
        "id": str(doc["_id"]),
        "brand_id": str(doc["brand_id"]),
        "brand_name": (brand or {}).get("business_name") or (brand or {}).get("name"),
        "title": doc.get("title"),
        "brief": doc.get("brief"),
        "deliverables": doc.get("deliverables"),
        "budget_per_creator": doc.get("budget_per_creator"),
        "compensation_type": _compensation_type(doc),
        # Safe on a creator-facing row: anyone receiving a private campaign's
        # serialisation has already passed the invited-or-applied gate, and
        # telling them it is invite-only is telling them something flattering.
        "visibility": _campaign_visibility(doc),
        "category": doc.get("category"),
        "area": doc.get("area"),
        # Never null: a filter chip has to print a word, and every campaign
        # ran somewhere even if it predates the field.
        "city": doc.get("city") or DEFAULT_CAMPAIGN_CITY,
        "creators_needed": doc.get("creators_needed"),
        "campaign_type": doc.get("campaign_type"),
        "cover_image_url": doc.get("cover_image_url"),
        # The brand's mark travels with the brand's name, so a card can show
        # both without a second request.
        "brand_logo_url": (brand or {}).get("logo_url"),
        # A creator deciding whether to give up a day wants to know whose
        # WhatsApp they will be on. Carries no contact detail — just which of
        # us they will be dealing with.
        "execution_owner": _execution_owner(doc),
        "event_date": doc["event_date"].isoformat() if isinstance(doc.get("event_date"), datetime) else doc.get("event_date"),
        "start_date": doc["start_date"].isoformat() if isinstance(doc.get("start_date"), datetime) else doc.get("start_date"),
        "end_date": doc["end_date"].isoformat() if isinstance(doc.get("end_date"), datetime) else doc.get("end_date"),
        "status": doc.get("status"),
        "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
    }


async def _expire_stale_campaigns() -> None:
    """Move campaigns past their end date out of the live feed.

    Called from the listing endpoints rather than a scheduler: this deployment
    has no job runner, and a brief whose window closed last month must not keep
    collecting applications while we wait for one.
    """
    now = datetime.now(timezone.utc)
    try:
        result = await db.campaigns.update_many(
            {
                "status": {"$in": list(LIVE_CAMPAIGN_STATUSES)},
                # A window that closed, or an event day that passed — either
                # way the brief must stop collecting applications.
                "$or": [
                    {"end_date": {"$ne": None, "$lt": now}},
                    {"event_date": {"$ne": None, "$lt": now}},
                ],
            },
            {"$set": {"status": "completed", "updated_at": now}},
        )
        if result.modified_count:
            logger.info("Expired %d campaign(s) past end_date", result.modified_count)
    except Exception as exc:
        logger.error("campaign expiry sweep failed: %s", exc)


# States that occupy one of a campaign's slots.
_FILLED_COLLAB_STATES = [
    s for s in COLLAB_STATE_ORDER if s not in ("applied", "verified")
]


async def _filled_counts_for(campaign_ids: list) -> dict:
    """How many slots on each campaign are actually taken — accepted onwards,
    excluding anyone declined or cancelled."""
    if not campaign_ids:
        return {}
    unique = list({cid for cid in campaign_ids})
    rows = await db.collaborations.aggregate(
        [
            {
                "$match": {
                    "campaign_id": {"$in": unique},
                    "state": {"$in": _FILLED_COLLAB_STATES},
                }
            },
            {"$group": {"_id": "$campaign_id", "n": {"$sum": 1}}},
        ]
    ).to_list(length=len(unique))
    return {r["_id"]: r["n"] for r in rows}


async def _sync_campaign_fill(campaign_id: ObjectId) -> None:
    """Close a campaign to new applications once it has the creators it asked
    for, and reopen it if a slot frees up again."""
    campaign = await db.campaigns.find_one({"_id": campaign_id})
    if not campaign:
        return
    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([campaign_id])).get(campaign_id, 0)
    now = datetime.now(timezone.utc)

    if filled >= needed and campaign.get("status") in LIVE_CAMPAIGN_STATUSES:
        await db.campaigns.update_one(
            {"_id": campaign_id},
            {"$set": {"status": "in_progress", "updated_at": now}},
        )
        logger.info("Campaign %s filled (%d/%d)", campaign_id, filled, needed)
    elif filled < needed and campaign.get("status") == "in_progress":
        # A decline freed a slot — put the brief back on the feed.
        await db.campaigns.update_one(
            {"_id": campaign_id},
            {"$set": {"status": "open", "updated_at": now}},
        )


async def _load_brand_map(brand_ids: list) -> dict:
    """Return { brand_id (ObjectId): { business_name, name, logo_url } }."""
    if not brand_ids:
        return {}
    unique_ids = list({b for b in brand_ids})
    profiles = await db.brand_profiles.find(
        {"user_id": {"$in": unique_ids}}
    ).to_list(length=len(unique_ids))
    profile_by_user = {p["user_id"]: p for p in profiles}

    # Fill in the name fallback from users for anyone missing a profile.
    missing_ids = [uid for uid in unique_ids if uid not in profile_by_user]
    users_by_id = {}
    if missing_ids:
        users = await db.users.find({"_id": {"$in": missing_ids}}).to_list(length=len(missing_ids))
        users_by_id = {u["_id"]: u for u in users}

    out = {}
    for uid in unique_ids:
        p = profile_by_user.get(uid)
        u = users_by_id.get(uid)
        out[uid] = {
            "business_name": (p or {}).get("business_name"),
            "name": (u or {}).get("name"),
            # Carried here so every caller that already loads the brand for its
            # name gets the mark too, rather than each one fetching again.
            "logo_url": (p or {}).get("logo_url"),
        }
    return out


# The mirror of `score_creator_for_campaign`, pointed the other way: not "who
# fits this brief" but "which briefs look like this creator's work". Same
# vocabulary (`_campaign_terms`, `_overlap`), so the two ends of the market are
# matched on one definition of fit rather than two that drift.
CREATOR_FEED_WEIGHTS = {"work_match": 50, "city": 30, "neighbourhood": 20}


def score_campaign_for_creator(campaign: dict, profile: Optional[dict]) -> float:
    """How much this brief looks like this creator's work. Pure, no DB.

    An empty or missing profile scores everything 0, which makes the sort fall
    through to recency — the feed's old order, and the right one for somebody
    we know nothing about. Deliberately **no budget or compensation term**: a
    barter brief must rank on fit exactly like a paid one, or "most relevant
    first" quietly becomes "paid first" and barter drops to the bottom of every
    feed — the invisible version of the bug where it was missing outright.
    """
    if not profile:
        return 0.0
    score = 0.0

    words = {
        str(w).lower().strip()
        for w in (profile.get("niches") or []) + (profile.get("genres") or [])
        if str(w).strip()
    }
    if words:
        terms = _campaign_terms(campaign)
        matched = sum(1 for w in words if w in terms)
        if matched:
            # Two matched terms are a stronger signal than one, but five are
            # not five times stronger — saturate at three so a creator with a
            # long tag list doesn't pin every brief to the top.
            score += CREATOR_FEED_WEIGHTS["work_match"] * min(matched, 3) / 3

    campaign_city = ((campaign.get("city") or DEFAULT_CAMPAIGN_CITY)).lower().strip()
    if campaign_city and campaign_city == (profile.get("city") or "").lower().strip():
        score += CREATOR_FEED_WEIGHTS["city"]

    # The brief's neighbourhood against where the creator says they are —
    # most of this work is in-person, and Indiranagar to Indiranagar is a
    # different proposition from Indiranagar to Whitefield.
    campaign_area = (campaign.get("area") or "").lower().strip()
    creator_places = {
        (profile.get("city") or "").lower().strip(),
        (profile.get("address") or "").lower().strip(),
    }
    if campaign_area and campaign_area in creator_places:
        score += CREATOR_FEED_WEIGHTS["neighbourhood"]

    return score


# "Most relevant first" ranks in Python, because the score needs the creator's
# profile and Mongo doesn't have it. The scan is capped: ranking the newest N
# rather than everything is the honest trade, and N is far above what the feed
# holds today.
_RELEVANCE_SCAN_CAP = 500


@campaigns_router.get("")
async def list_campaigns(
    city: Optional[str] = None,
    area: Optional[str] = None,
    category: Optional[str] = None,
    campaign_type: Optional[str] = None,
    compensation_type: Optional[str] = None,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,  # "relevant" (default) | "newest" | "budget_desc" | "budget_asc"
    limit: int = 200,
    offset: int = 0,
    user: dict = Depends(require_roles("creator", "admin")),
):
    """Every live brief this caller may see, most relevant first.

    No filter is applied by default — a creator sees everything that is open
    or upcoming and narrows from there, rather than being shown a slice
    somebody else chose. Private briefs are the one cut that is not a filter:
    they appear only to creators who were invited or already applied, and to
    admins. Ordering defaults to relevance against the creator's own profile,
    falling back to recency for anyone we know nothing about.
    """
    await _expire_stale_campaigns()
    limit = max(1, min(int(limit or 200), 200))
    offset = max(0, int(offset or 0))
    query: dict = {"status": {"$in": list(_LIVE_STATUSES)}}
    if city:
        # Campaigns predate this field, and the backfill fills them in — but a
        # filter that only works after a migration has run returns nothing on a
        # box that has not restarted. Same shape as execution_owner.
        canonical = _canonical_city(city)
        if canonical == DEFAULT_CAMPAIGN_CITY:
            # Appended, never assigned: the visibility clause below owns a slot
            # in $and too, and an assignment here would silently drop it.
            query.setdefault("$and", []).append(
                {"$or": [{"city": canonical}, {"city": {"$exists": False}}, {"city": None}]}
            )
        else:
            query["city"] = canonical
    if area:
        query["area"] = area
    if category:
        query["category"] = category
    if campaign_type:
        if campaign_type not in CampaignType.__args__:
            raise HTTPException(
                status_code=422,
                detail=f"campaign_type must be one of: {', '.join(CampaignType.__args__)}.",
            )
        query["campaign_type"] = campaign_type
    if compensation_type:
        if compensation_type not in CompensationType.__args__:
            raise HTTPException(
                status_code=422,
                detail=f"compensation_type must be one of: {', '.join(CompensationType.__args__)}.",
            )
        if compensation_type == DEFAULT_COMPENSATION_TYPE:
            # Same reasoning: a campaign with no compensation_type is fixed.
            query["$or"] = [
                {"compensation_type": compensation_type},
                {"compensation_type": {"$exists": False}},
                {"compensation_type": None},
            ]
        else:
            query["compensation_type"] = compensation_type
    if budget_min is not None or budget_max is not None:
        budget_q: dict = {}
        if budget_min is not None:
            budget_q["$gte"] = budget_min
        if budget_max is not None:
            budget_q["$lte"] = budget_max
        query["budget_per_creator"] = budget_q
        # A barter brief keeps whatever budget it was posted with, so without
        # this a money filter would include or exclude barter by a number that
        # means nothing — "₹5k–15k" surfaced a barter stay whose vestigial
        # budget happened to be 5000. Combined with an explicit
        # compensation_type=barter above, the two clauses AND to an empty set,
        # which is the honest answer to "barter briefs priced ₹5k–15k".
        query.setdefault("$and", []).append({"compensation_type": {"$ne": "barter"}})
    if q:
        # Case-insensitive keyword match against title / brief / deliverables.
        # Pushed into $and rather than assigned to $or, because the
        # compensation filter above may already own that key — two $or
        # assignments would silently drop the first.
        term = re.escape(q.strip())
        query.setdefault("$and", []).append(
            {
                "$or": [
                    {"title": {"$regex": term, "$options": "i"}},
                    {"brief": {"$regex": term, "$options": "i"}},
                    {"deliverables": {"$regex": term, "$options": "i"}},
                ]
            }
        )

    # The visibility cut. Not a filter a creator can remove: private briefs are
    # in this list only through one of the two doors — an invitation, or an
    # application they already hold. Admins see everything; brands don't browse
    # this list at all (their own campaigns live on their dashboard).
    profile = None
    if user["role"] == "creator":
        creator_oid = ObjectId(user["_id"])
        allowed = await _visible_campaign_ids_for_creator(creator_oid)
        query.setdefault("$and", []).append(
            {"$or": [PUBLIC_CAMPAIGN_QUERY, {"_id": {"$in": allowed}}]}
        )
        profile = await db.creator_profiles.find_one({"user_id": creator_oid})

    total = await db.campaigns.count_documents(query)

    if sort in ("budget_desc", "budget_asc", "newest"):
        sort_key: list = [("created_at", -1)]
        if sort == "budget_desc":
            sort_key = [("budget_per_creator", -1), ("created_at", -1)]
        elif sort == "budget_asc":
            sort_key = [("budget_per_creator", 1), ("created_at", -1)]
        docs = (
            await db.campaigns.find(query)
            .sort(sort_key)
            .skip(offset)
            .limit(limit)
            .to_list(length=limit)
        )
    else:
        # "relevant", the default. Scored in Python against the caller's own
        # profile — Mongo doesn't have it — over the newest _RELEVANCE_SCAN_CAP
        # matches, then sliced, so pagination and X-Total-Count still hold.
        # `-created` in the key keeps the tiebreak (and the whole order, for a
        # profile that matches nothing) newest-first, which is the old
        # behaviour and the right one for a creator we know nothing about.
        pool = (
            await db.campaigns.find(query)
            .sort([("created_at", -1)])
            .limit(_RELEVANCE_SCAN_CAP)
            .to_list(length=_RELEVANCE_SCAN_CAP)
        )
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        def _created(d):
            value = d.get("created_at")
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return epoch
        pool.sort(
            key=lambda d: (-score_campaign_for_creator(d, profile), -_created(d).timestamp())
        )
        docs = pool[offset : offset + limit]

    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    rows = [_serialize_campaign(d, brand_map.get(d["brand_id"])) for d in docs]
    # The list used to be a bare array capped at 200 with no way to know
    # whether anything was cut off. Still an array for anything already reading
    # it that way — the count rides in a header, which is additive.
    return JSONResponse(
        content=jsonable_encoder(rows),
        headers={"X-Total-Count": str(total), "X-Returned-Count": str(len(rows))},
    )


@campaigns_router.get("/filters")
async def campaign_filters(
    user: dict = Depends(require_roles("creator", "admin")),
):
    """What is actually worth filtering by, across listable campaigns.

    Distinct values rather than the full enums: offering a category with no
    live brief in it is a filter whose only outcome is an empty list.
    """
    await _expire_stale_campaigns()
    # Public only. A private brief's neighbourhood showing up as a filter
    # option would announce its existence to everyone the privacy is for —
    # and an invited creator losing one dropdown entry costs nothing.
    base = {"status": {"$in": list(_LIVE_STATUSES)}, **PUBLIC_CAMPAIGN_QUERY}
    areas = await db.campaigns.distinct("area", base)
    categories = await db.campaigns.distinct("category", base)
    cities = await db.campaigns.distinct("city", base)
    campaign_types = await db.campaigns.distinct("campaign_type", base)
    compensation_types = await db.campaigns.distinct("compensation_type", base)
    # A campaign with no city or compensation predates the field and reads as
    # the default, so the option has to be offered even when no document
    # literally stores it.
    has_unset_city = await db.campaigns.count_documents(
        {**base, "$or": [{"city": {"$exists": False}}, {"city": None}]}
    )
    if has_unset_city:
        cities.append(DEFAULT_CAMPAIGN_CITY)
    has_unset_comp = await db.campaigns.count_documents(
        {**base, "$or": [{"compensation_type": {"$exists": False}}, {"compensation_type": None}]}
    )
    if has_unset_comp:
        compensation_types.append(DEFAULT_COMPENSATION_TYPE)

    # Budget bounds — used by the UI to build a sensible range slider/bucket.
    budget_bounds = {"min": None, "max": None}
    pipeline = [
        {"$match": {**base, "budget_per_creator": {"$type": "number"}}},
        {
            "$group": {
                "_id": None,
                "min": {"$min": "$budget_per_creator"},
                "max": {"$max": "$budget_per_creator"},
            }
        },
    ]
    async for row in db.campaigns.aggregate(pipeline):
        budget_bounds = {"min": row.get("min"), "max": row.get("max")}
        break

    return {
        # Cities in canonical order rather than alphabetical — Bengaluru leads
        # because that is where the work is.
        "cities": [c for c in INDIAN_CITIES if c in set(cities)],
        "areas": sorted([a for a in areas if a]),
        "categories": sorted([c for c in categories if c]),
        "campaign_types": [t for t in CampaignType.__args__ if t in set(campaign_types)],
        "compensation_types": [
            t for t in CompensationType.__args__ if t in set(compensation_types)
        ],
        "budget_bounds": budget_bounds,
    }


@campaigns_router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    user: dict = Depends(require_roles("creator", *BRAND_ROLES, "admin")),
):
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")

    doc = await db.campaigns.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # A brand may read its own brief in any state, and nobody else's — a live
    # campaign carries a competitor's budget and deliverables.
    if is_brand_side(user):
        if doc.get("brand_id") != _brand_scope(user):
            raise HTTPException(status_code=404, detail="Campaign not found")
    elif user["role"] != "admin":
        # Creators can only view live/upcoming campaigns. Admins see anything.
        if doc.get("status") not in _LIVE_STATUSES:
            raise HTTPException(status_code=404, detail="Campaign not found")
        # A private brief answers 404, not 403 — whether it exists is itself
        # what the privacy protects. Same reasoning as _own_campaign_or_404.
        if not await _creator_may_see(doc, ObjectId(user["_id"])):
            raise HTTPException(status_code=404, detail="Campaign not found")

    brand_map = await _load_brand_map([doc["brand_id"]])
    payload = _serialize_campaign(doc, brand_map.get(doc["brand_id"]))

    # Whether the current creator has already applied.
    payload["has_applied"] = False
    payload["application"] = None
    payload["can_apply"] = False
    payload["apply_blocked_reason"] = None
    if user["role"] == "creator":
        # Decide eligibility server-side so the button and the API agree.
        profile = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
        verification = (profile or {}).get("verification_status", "pending")
        needed = int(doc.get("creators_needed") or 1)
        filled = (await _filled_counts_for([oid])).get(oid, 0)

        if verification == "pending":
            payload["apply_blocked_reason"] = (
                "Your profile is still with the WeAre team. You can pitch on briefs "
                "as soon as it's approved."
            )
        elif verification == "rejected":
            payload["apply_blocked_reason"] = (
                "Your profile wasn't approved. Update it and we'll take another look."
            )
        elif _awaiting_recheck(profile):
            payload["apply_blocked_reason"] = _recheck_message(profile)
        elif filled >= needed:
            payload["apply_blocked_reason"] = (
                "This campaign has all the creators it needs."
            )
        else:
            payload["can_apply"] = True

        existing = await db.collaborations.find_one(
            {"campaign_id": oid, "creator_id": ObjectId(user["_id"]), "active": True}
        )
        if existing:
            payload["has_applied"] = True
            payload["application"] = {
                "id": str(existing["_id"]),
                "state": existing.get("state", "applied"),
                "pitch": existing.get("pitch"),
                "quoted_rate": existing.get("quoted_rate"),
                "agreed_amount": existing.get("agreed_amount"),
                "created_at": existing["created_at"].isoformat()
                if isinstance(existing.get("created_at"), datetime)
                else existing.get("created_at"),
            }

        # The venue and the person running the campaign, for creators the brand
        # has actually taken on. An applicant doesn't get a staff phone number.
        payload["coordination"] = None
        if existing and existing.get("state") in _ONBOARD_COLLAB_STATES:
            payload["coordination"] = {
                "manager_name": doc.get("manager_name"),
                "manager_phone": doc.get("manager_phone"),
                "venue_address": doc.get("venue_address"),
                "venue_instructions": doc.get("venue_instructions"),
                "on_site_contact": doc.get("on_site_contact"),
                "event_date": _iso(doc.get("event_date")),
            }
    return payload


def _why_you_cannot_apply(profile: Optional[dict]) -> str:
    """Why this creator can't pitch yet, and what to do about it.

    "Not verified" on its own sends people to support. Whether they are still
    building, waiting on us, or were turned down are three different problems
    with three different next steps, so the message says which one it is and
    names the fields when the answer is "finish your profile".
    """
    status = (profile or {}).get("verification_status", "pending")
    if status == "rejected":
        reason = (profile or {}).get("verification_reason")
        return (
            f"Your profile wasn't approved: {reason} Update it and submit it again."
            if reason
            else "Your profile wasn't approved. Update it and submit it again to be reviewed."
        )
    if (profile or {}).get("submitted_for_review_at"):
        return (
            "Your profile is with the WeAre team — you can pitch on briefs as soon "
            "as it's approved. Reviews usually finish within 48 hours."
        )
    completeness = _profile_completeness(profile or {})
    outstanding = ", ".join(row["label"] for row in completeness["missing"])
    return (
        f"Finish your profile before pitching — it's {completeness['percent']}% done. "
        f"Still needed: {outstanding}. Submit it for review and we'll get back to you "
        "within 48 hours."
    )


@campaigns_router.post("/{campaign_id}/apply")
async def apply_to_campaign(
    campaign_id: str,
    payload: ApplyPayload,
    user: dict = Depends(require_roles("creator")),
):
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = await db.campaigns.find_one({"_id": oid})
    if not campaign or campaign.get("status") not in _LIVE_STATUSES:
        raise HTTPException(status_code=404, detail="Campaign not found")

    creator_oid = ObjectId(user["_id"])

    # Invite-only means invite-only at the API, not in the UI: a private brief
    # takes pitches solely from creators holding an invitation (or an existing
    # application, which the duplicate check below turns into its own 409).
    if not await _creator_may_see(campaign, creator_oid):
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Verification has to gate something, or the 48-hour review is decoration.
    # Browsing stays open to everyone — a creator deciding whether this is worth
    # finishing a profile for needs to see what is on offer — but pitching does
    # not, and the check lives here rather than in the UI so it holds whatever
    # the request came from.
    profile = await db.creator_profiles.find_one({"user_id": creator_oid})
    if (profile or {}).get("verification_status") != "verified":
        raise HTTPException(status_code=403, detail=_why_you_cannot_apply(profile))
    # Verified, but they have changed something we verified. New pitches wait;
    # anything already accepted is untouched, because this gate is only on the
    # act of applying.
    if _awaiting_recheck(profile):
        raise HTTPException(status_code=403, detail=_recheck_message(profile))

    # Don't take a pitch for a slot that's already gone.
    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([oid])).get(oid, 0)
    if filled >= needed:
        raise HTTPException(
            status_code=409,
            detail="This campaign has all the creators it needs.",
        )

    now = datetime.now(timezone.utc)
    try:
        result = await db.collaborations.insert_one(
            {
                "campaign_id": oid,
                "creator_id": creator_oid,
                "pitch": payload.pitch.strip(),
                "quoted_rate": float(payload.quoted_rate),
                "agreed_amount": None,
                "content_url": None,
                "content_urls": [],
                "scheduled_at": None,
                "state": "applied",
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409, detail="You've already applied to this campaign"
        )

    # Where the application goes is the whole point of execution_owner. This
    # used to tell the brand's manager unconditionally, so a brand that had
    # handed a campaign to us still got paged for every applicant and our own
    # manager got nothing.
    applicant_line = (
        f"{user.get('name') or 'A creator'} applied to “{campaign.get('title')}”."
    )
    if _weare_runs(campaign):
        # Ours to action. `notify_campaign_manager` is silent when nobody is
        # assigned yet — a campaign we own but have not staffed is a gap for
        # the admin queue to show, not a booking to fail over.
        await notify_weare_team(
            campaign,
            "new_applicant",
            title="New applicant",
            body=applicant_line,
        )
        # The brand still hears about their own campaign; they just are not the
        # ones being asked to act. Skipped automatically when the assigned
        # manager *is* their person, so nobody is told twice.
        await _tell_brand_manager_unless_managed(
            campaign,
            "brand_new_application",
            title="New applicant",
            body=applicant_line,
        )
    else:
        await notify_brand_manager(
            campaign["brand_id"],
            "brand_new_application",
            title="New applicant",
            body=applicant_line,
            link=f"/brand/campaigns/{campaign_id}/applicants",
        )

    return {
        "id": str(result.inserted_id),
        "campaign_id": campaign_id,
        "state": "applied",
        "pitch": payload.pitch.strip(),
        "quoted_rate": float(payload.quoted_rate),
        "created_at": now.isoformat(),
    }


# States from which a creator is actually on the campaign — what unlocks the
# venue details and the manager's number. Applying is not being on it.
_ONBOARD_COLLAB_STATES = tuple(COLLAB_GROUP_ONGOING) + tuple(COLLAB_GROUP_COMPLETED)


async def _claim_slot(
    user: dict,
    collab: dict,
    campaign: dict,
    slot: dict,
    preferred_time: Optional[datetime] = None,
) -> dict:
    """Take a place on a slot and move the collaboration onto it.

    One implementation behind both booking routes, because a second copy of an
    atomic claim is a second chance to get it subtly wrong.

    The seat is claimed with a conditional increment — the filter only matches
    while booked_count is under capacity, so two creators after the last place
    resolve inside the database and exactly one wins. If the collaboration then
    moves under us, the seat is handed straight back rather than held for
    somebody who no longer has it.
    """
    soid = slot["_id"]
    now = datetime.now(timezone.utc)

    claimed = await db.campaign_slots.find_one_and_update(
        {"_id": soid, "$expr": {"$lt": ["$booked_count", "$capacity"]}},
        {"$inc": {"booked_count": 1}, "$set": {"updated_at": now}},
        return_document=True,
    )
    if not claimed:
        raise HTTPException(
            status_code=409, detail="That slot just filled up. Pick another."
        )

    update = {
        "state": "slot_booked",
        "scheduled_at": slot["starts_at"],
        "slot_id": soid,
        "updated_at": now,
    }
    # A personal-table window is an availability range, so the creator can name
    # the time inside it they actually want. The seat is still the window's —
    # that is what carries the capacity.
    if preferred_time is not None:
        update["scheduled_at"] = preferred_time
        update["preferred_time"] = preferred_time

    updated = await db.collaborations.find_one_and_update(
        {"_id": collab["_id"], "state": "commercial_agreed"},
        {"$set": update},
        return_document=True,
    )
    if not updated:
        await db.campaign_slots.update_one(
            {"_id": soid, "booked_count": {"$gt": 0}},
            {"$inc": {"booked_count": -1}},
        )
        raise HTTPException(
            status_code=409, detail="Your collaboration just changed — reload and try again."
        )

    when = update["scheduled_at"]
    await audit(
        user,
        "collaboration.book_slot",
        "collaboration",
        collab["_id"],
        before={"state": "commercial_agreed"},
        after={"state": "slot_booked", "slot_id": str(soid), "scheduled_at": _iso(when)},
    )
    await notify(
        collab["creator_id"],
        "slot_confirmed",
        title="Slot booked",
        body=f"{campaign.get('title')} — "
        f"{when.strftime('%d %b, %I:%M %p')}. See the campaign for the venue.",
        link=f"/campaigns/{str(campaign['_id'])}",
    )
    # The manager is the one who has to plan around it.
    creator_profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    creator_name = (creator_profile or {}).get("name") or "A creator"
    await notify_campaign_manager(
        campaign,
        "manager_slot_booked",
        title="A creator booked a slot",
        body=f"{creator_name} booked "
        f"{when.strftime('%d %b, %I:%M %p')} on {campaign.get('title')}.",
    )
    # And the brand, which has a table to hold whoever is running the day.
    # `notify_brand_manager` no-ops when the campaign manager *is* the brand
    # manager and has just been told, so nobody gets the same thing twice.
    await _tell_brand_manager_unless_managed(
        campaign,
        "brand_slot_booked",
        title="A creator booked a slot",
        body=f"{creator_name} booked {when.strftime('%d %b, %I:%M %p')} on "
        f"“{campaign.get('title')}”.",
    )
    return {
        "collaboration_id": str(collab["_id"]),
        "state": "slot_booked",
        "slot": _serialize_slot(claimed),
        "scheduled_at": _iso(when),
    }


@campaigns_router.get("/{campaign_id}/slots")
async def list_slots_for_creator(
    campaign_id: str,
    user: dict = Depends(require_roles("creator", "admin")),
):
    """The bookable slots, as the creator sees them.

    Only a creator who has been accepted onto the campaign sees the schedule —
    a slot list names dates, a venue's rhythm and capacity, none of which
    belongs to an applicant the brand hasn't taken."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = await db.campaigns.find_one({"_id": oid})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    collab = None
    if user["role"] == "creator":
        collab = await db.collaborations.find_one(
            {"campaign_id": oid, "creator_id": ObjectId(user["_id"]), "active": True}
        )
        if not collab or collab.get("state") not in _ONBOARD_COLLAB_STATES:
            raise HTTPException(status_code=404, detail="Campaign not found")

    docs = (
        await db.campaign_slots.find({"campaign_id": oid})
        .sort("starts_at", 1)
        .to_list(length=500)
    )
    return {
        "campaign_id": campaign_id,
        "campaign_type": campaign.get("campaign_type"),
        # Booking is the step out of commercial_agreed; the flag saves the UI
        # from re-deriving the state machine.
        "can_book": bool(collab) and collab.get("state") == "commercial_agreed",
        "booked_slot_id": str(collab["slot_id"]) if collab and collab.get("slot_id") else None,
        "slots": [_serialize_slot(d) for d in docs],
    }


@campaigns_router.post("/slots/{slot_id}/book")
async def book_slot(
    slot_id: str,
    user: dict = Depends(require_roles("creator")),
):
    """A creator taking a place on a slot.

    The seat is claimed with a conditional increment — the filter only matches
    while booked_count is under capacity, so two creators after the last place
    resolve inside the database, and exactly one of them gets it. The other
    sees a 409, not a double-booked table.
    """
    try:
        soid = ObjectId(slot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Slot not found")
    slot = await db.campaign_slots.find_one({"_id": soid})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    campaign = await db.campaigns.find_one({"_id": slot["campaign_id"]})
    if not campaign or campaign.get("status") not in (
        tuple(ACTIVE_CAMPAIGN_STATUSES)
    ):
        raise HTTPException(
            status_code=409, detail="This campaign isn't taking bookings right now."
        )

    collab = await db.collaborations.find_one(
        {
            "campaign_id": slot["campaign_id"],
            "creator_id": ObjectId(user["_id"]),
            "active": True,
        }
    )
    if not collab:
        raise HTTPException(status_code=404, detail="Slot not found")
    state = collab.get("state")
    if state == "slot_booked":
        raise HTTPException(status_code=409, detail="You already have a slot booked.")
    if state != "commercial_agreed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Booking opens once your fee is agreed."
                if state in ("applied", "verified", "accepted")
                else f"Your collaboration is {state} — there's nothing to book."
            ),
        )

    return await _claim_slot(user, collab, campaign, slot)


api_router.include_router(campaigns_router)


# --- Public (unauthenticated) preview ---------------------------------------

public_router = APIRouter(prefix="/public", tags=["public"])


@public_router.get("/campaigns")
async def public_campaign_preview(limit: int = 6):
    """A shop window. The landing page promises "discover briefs", so a visitor
    should see real ones before being asked for a phone number.

    Deliberately thin: enough to judge whether it's worth signing up, not enough
    to work the brief without an account. No brand contact details, no full text.
    """
    await _expire_stale_campaigns()
    limit = max(1, min(int(limit or 6), 24))

    # Only verified brands get the shop window. An unverified brand can still
    # post and be seen by verified creators in-app; it just isn't promoted to the
    # public internet under our name.
    verified = await db.brand_profiles.find(
        {"verified": True}, {"user_id": 1}
    ).to_list(length=1000)
    verified_ids = [b["user_id"] for b in verified]
    if not verified_ids:
        return {"campaigns": [], "total_open": 0}

    docs = (
        await db.campaigns.find(
            # Public only — this is the open internet, which is the audience
            # a private brief is private *from*.
            {"status": "open", "brand_id": {"$in": verified_ids}, **PUBLIC_CAMPAIGN_QUERY}
        )
        .sort("created_at", -1)
        .to_list(length=limit)
    )
    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    filled = await _filled_counts_for([d["_id"] for d in docs])

    out = []
    for d in docs:
        brand = brand_map.get(d["brand_id"]) or {}
        needed = int(d.get("creators_needed") or 1)
        brief = (d.get("brief") or "").strip()
        out.append(
            {
                "id": str(d["_id"]),
                "title": d.get("title"),
                "brand_name": brand.get("business_name") or brand.get("name"),
                "brand_logo_url": brand.get("logo_url"),
                "cover_image_url": d.get("cover_image_url"),
                "category": d.get("category"),
                "area": d.get("area"),
                "budget_per_creator": d.get("budget_per_creator"),
                "compensation_type": _compensation_type(d),
                "teaser": brief[:180] + ("…" if len(brief) > 180 else ""),
                "spots_left": max(0, needed - filled.get(d["_id"], 0)),
            }
        )
    return {
        "campaigns": out,
        "total_open": await db.campaigns.count_documents(
            {"status": "open", "brand_id": {"$in": verified_ids}, **PUBLIC_CAMPAIGN_QUERY}
        ),
    }


@public_router.get("/stats")
async def public_stats():
    """Headline numbers for the landing page — no PII, no auth."""
    return {
        "verified_creators": await db.creator_profiles.count_documents(
            {"verification_status": "verified"}
        ),
        "open_campaigns": await db.campaigns.count_documents({"status": "open"}),
        "cities": len(
            [
                c
                for c in await db.creator_profiles.distinct(
                    "city", {"verification_status": "verified"}
                )
                if c
            ]
        ),
    }


api_router.include_router(public_router)


# --- Notifications ----------------------------------------------------------

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.get("")
async def list_notifications(
    unread_only: bool = False,
    user: dict = Depends(get_current_user),
):
    query: dict = {"user_id": ObjectId(user["_id"])}
    if unread_only:
        query["read"] = False
    docs = (
        await db.notifications.find(query)
        .sort("created_at", -1)
        .to_list(length=100)
    )
    return {
        "notifications": [
            {
                "id": str(d["_id"]),
                "event": d.get("event"),
                "title": d.get("title"),
                "body": d.get("body"),
                "link": d.get("link"),
                "read": bool(d.get("read", False)),
                "created_at": _iso(d.get("created_at")),
            }
            for d in docs
        ],
        "unread": await db.notifications.count_documents(
            {"user_id": ObjectId(user["_id"]), "read": False}
        ),
    }


@notifications_router.post("/read")
async def mark_notifications_read(user: dict = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": ObjectId(user["_id"]), "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return {"success": True, "marked": result.modified_count}


api_router.include_router(notifications_router)


# --- Work notes on a collaboration -----------------------------------------
#
# Negotiation happens offline — on WhatsApp, on the phone, at the venue. That is
# the model, not a gap in it, and it means the reasoning behind a number lives
# in somebody's head until they leave. This is where it goes instead: who said
# what, when, against the application it was about.
#
# Deliberately not visible to the creator. A brand writing "asked for 12k, worth
# 8" needs somewhere to write it; a thread the creator can read is a thread
# nobody uses, and the creator-facing record is the collaboration itself — the
# agreed amount, the state, the notifications — which is honest about the terms
# without being a transcript of the deliberation.

notes_router = APIRouter(prefix="/collaborations", tags=["notes"])


class NotePayload(BaseModel):
    """One entry in the thread."""

    body: str = Field(min_length=1, max_length=4000)


async def _note_readable_collab_or_404(collab_id: str, user: dict) -> tuple[dict, dict]:
    """Load a collaboration whose notes this caller may read.

    Three doors, and a 404 rather than a 403 behind all of them: an admin, the
    brand that owns the campaign, or the WeAre manager assigned to it. A
    creator gets the 404 too — not because their own collaboration is a secret
    from them, but because whether a private thread exists on it is.
    """
    role = (user or {}).get("role")
    try:
        oid = ObjectId(collab_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Application not found")
    collab = await db.collaborations.find_one({"_id": oid})
    if not collab:
        raise HTTPException(status_code=404, detail="Application not found")
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Application not found")

    if role == "admin":
        return collab, campaign
    if is_brand_side(user) and campaign.get("brand_id") == _brand_scope(user):
        return collab, campaign
    if role == "campaign_manager" and campaign.get("manager_id") == ObjectId(user["_id"]):
        return collab, campaign
    raise HTTPException(status_code=404, detail="Application not found")


def _serialize_note(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "collaboration_id": str(doc["collaboration_id"]),
        "author_id": str(doc["author_id"]) if doc.get("author_id") else None,
        "author_name": doc.get("author_name"),
        # The role at the time of writing, stored rather than joined: "the
        # brand said" and "WeAre said" is most of what a thread is for, and a
        # manager who later becomes an admin must not rewrite what they were.
        "author_role": doc.get("author_role"),
        "body": doc.get("body"),
        "created_at": _iso(doc.get("created_at")),
    }


@notes_router.get("/{collab_id}/notes")
async def list_collaboration_notes(
    collab_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    """The thread, oldest first, with the agreed amount above it.

    The number travels with the conversation because the conversation is how it
    was arrived at — reading one without the other is what made a fee look
    arbitrary a month later.
    """
    collab, campaign = await _note_readable_collab_or_404(collab_id, user)
    docs = (
        await db.collaboration_notes.find({"collaboration_id": collab["_id"]})
        .sort("created_at", 1)
        .to_list(length=500)
    )
    profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    return {
        "collaboration_id": collab_id,
        "campaign": {"id": str(campaign["_id"]), "title": campaign.get("title")},
        "creator": _brand_visible_creator(profile),
        "state": collab.get("state"),
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "agreed_at": _iso(collab.get("agreed_at")),
        "notes": [_serialize_note(d) for d in docs],
    }


@notes_router.post("/{collab_id}/notes")
async def add_collaboration_note(
    collab_id: str,
    payload: NotePayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    """Add to the thread. Append-only — there is no edit and no delete.

    A record of a negotiation that can be quietly rewritten afterwards is not a
    record. If something was written in error, the correction is another note.
    """
    collab, campaign = await _note_readable_collab_or_404(collab_id, user)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="A note needs something in it.")

    now = datetime.now(timezone.utc)
    doc = {
        "collaboration_id": collab["_id"],
        "campaign_id": campaign["_id"],
        "brand_id": campaign.get("brand_id"),
        "author_id": ObjectId(user["_id"]),
        "author_name": user.get("name"),
        "author_role": user.get("role"),
        "body": body,
        "created_at": now,
    }
    result = await db.collaboration_notes.insert_one(doc)
    doc["_id"] = result.inserted_id

    await audit(
        user,
        "collaboration.note",
        "collaboration",
        collab["_id"],
        after={"note_id": str(result.inserted_id)},
        # The note itself, so the audit log carries the paper trail rather than
        # a pointer to it — the two are read in different places.
        note=body[:500],
        **_campaign_audit_context(campaign),
    )
    return _serialize_note(doc)


api_router.include_router(notes_router)


# --- Creator questions on a campaign ----------------------------------------
#
# A creator reading a brief had no way to ask anything — "is parking possible",
# "can I bring a videographer" — short of applying and hoping. This is that
# channel: one thread per (campaign, creator), asked from the campaign page,
# answered by whoever runs the campaign.
#
# **It is not the work notes.** `collaboration_notes` is the internal paper
# trail — brand, admin and the assigned manager, never the creator, and this
# file keeps that so. Questions are the opposite shape: the creator is a party
# to the thread, other creators never see it, and who answers follows
# `execution_owner` — the brand's manager on a brand-run campaign, only the
# WeAre side on a weare-run one, where the brand does not see the thread at
# all. Both collections are append-only for the same reason: a record that can
# be quietly rewritten is not a record.

questions_router = APIRouter(prefix="/questions", tags=["questions"])


class QuestionPayload(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _question_staff_may_see(campaign: dict, user: dict) -> bool:
    """Which side of the house may read and answer this campaign's threads.

    Admins always; the assigned WeAre manager on their own campaigns; the
    owning brand **only when the campaign is brand-run** — handing a campaign
    to WeAre hands the creator conversations with it, and a creator asking
    "our team" a question has not agreed to the brand reading it.
    """
    role = (user or {}).get("role")
    if role == "admin":
        return True
    if role == "campaign_manager":
        return campaign.get("manager_id") == ObjectId(user["_id"])
    if is_brand_side(user):
        return campaign.get("brand_id") == _brand_scope(user) and not _weare_runs(campaign)
    return False


async def _question_campaign_or_404(campaign_id: str) -> dict:
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = await db.campaigns.find_one({"_id": oid})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


async def _creator_can_discuss(campaign: dict, creator_oid: ObjectId) -> bool:
    """May this creator hold a thread here? The same doors as reading the
    campaign, plus one: a creator already on the campaign can keep asking
    after it leaves the live statuses — mid-shoot is when the questions come.
    """
    if not await _creator_may_see(campaign, creator_oid):
        return False
    if campaign.get("status") in LIVE_CAMPAIGN_STATUSES:
        return True
    return bool(
        await db.collaborations.find_one(
            {"campaign_id": campaign["_id"], "creator_id": creator_oid, "active": True},
            {"_id": 1},
        )
    )


def _serialize_question(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "campaign_id": str(doc["campaign_id"]),
        "author_name": doc.get("author_name"),
        # Stored, not joined, for the reason the notes store it — and reduced
        # to two words before it leaves: a creator does not need to know
        # whether "the team" today was an admin or the assigned manager, and a
        # staff role name is one more thing a rename would break.
        "from_creator": bool(doc.get("from_creator")),
        "author_side": "creator" if doc.get("from_creator") else doc.get("author_side"),
        "body": doc.get("body"),
        "created_at": _iso(doc.get("created_at")),
    }


def _question_author_side(campaign: dict, user: dict) -> str:
    """The word the creator sees beside an answer: who they are dealing with.
    The same two words `execution_owner` prints everywhere else."""
    if is_brand_side(user):
        return "brand"
    return "weare"


async def _thread_docs(campaign_id, creator_id) -> list:
    return (
        await db.campaign_questions.find(
            {"campaign_id": campaign_id, "creator_id": creator_id}
        )
        # _id as the tiebreak: a question and its answer can land in the same
        # clock tick, and "which came last" decides whether a thread reads as
        # answered. ObjectIds are monotonic; timestamps alone are not.
        .sort([("created_at", 1), ("_id", 1)])
        .to_list(length=500)
    )


def _thread_unanswered(docs: list) -> bool:
    """A thread is waiting on us when its last word is the creator's."""
    return bool(docs) and bool(docs[-1].get("from_creator"))


@questions_router.get("/campaign/{campaign_id}")
async def my_campaign_questions(
    campaign_id: str,
    user: dict = Depends(require_roles("creator")),
):
    """The caller's own thread on this campaign. Nobody else's is reachable
    from this route at all — the creator_id is the session, never a parameter.
    """
    campaign = await _question_campaign_or_404(campaign_id)
    creator_oid = ObjectId(user["_id"])
    if not await _creator_may_see(campaign, creator_oid):
        raise HTTPException(status_code=404, detail="Campaign not found")
    docs = await _thread_docs(campaign["_id"], creator_oid)
    return {
        "campaign_id": campaign_id,
        "can_ask": await _creator_can_discuss(campaign, creator_oid),
        # Who will answer, so the ask box can say so instead of "someone".
        "answered_by": "weare" if _weare_runs(campaign) else "brand",
        "questions": [_serialize_question(d) for d in docs],
    }


@questions_router.post("/campaign/{campaign_id}")
async def ask_campaign_question(
    campaign_id: str,
    payload: QuestionPayload,
    user: dict = Depends(require_roles("creator")),
):
    campaign = await _question_campaign_or_404(campaign_id)
    creator_oid = ObjectId(user["_id"])
    # The same 404 as the campaign read: a private brief's existence is not
    # answered by its question box either.
    if not await _creator_may_see(campaign, creator_oid):
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not await _creator_can_discuss(campaign, creator_oid):
        raise HTTPException(
            status_code=409,
            detail="This campaign has wrapped up, so questions on it are closed.",
        )

    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="A question needs something in it.")

    now = datetime.now(timezone.utc)
    doc = {
        "campaign_id": campaign["_id"],
        "creator_id": creator_oid,
        "brand_id": campaign.get("brand_id"),
        "author_id": creator_oid,
        "author_name": user.get("name"),
        "from_creator": True,
        "author_side": None,
        "body": body,
        "created_at": now,
    }
    result = await db.campaign_questions.insert_one(doc)
    doc["_id"] = result.inserted_id

    await audit(
        user, "campaign.question", "campaign", campaign["_id"],
        after={"question_id": str(result.inserted_id)},
        note=body[:500],
        **_campaign_audit_context(campaign),
    )

    # Routed exactly like a new application, because it is the same question:
    # who runs this campaign? `notify_weare_team` falls back to every admin
    # when nobody is assigned, so a question on an unstaffed weare-run
    # campaign still reaches someone.
    line = f"{user.get('name') or 'A creator'} asked on “{campaign.get('title')}”: {body[:140]}"
    if _weare_runs(campaign):
        await notify_weare_team(
            campaign, "campaign_question", title="A creator asked a question", body=line
        )
    else:
        await notify_brand_manager(
            campaign.get("brand_id"),
            "campaign_question",
            title="A creator asked a question",
            body=line,
            link=f"/brand/campaigns/{campaign_id}/applicants",
        )
    return _serialize_question(doc)


@questions_router.get("/campaign/{campaign_id}/threads")
async def campaign_question_threads(
    campaign_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    """Every thread on one campaign, for whoever answers them.

    The creator block goes through `_brand_visible_creator` — the reader may
    be the brand, and a question is not an offer of a phone number.
    """
    campaign = await _question_campaign_or_404(campaign_id)
    if not _question_staff_may_see(campaign, user):
        raise HTTPException(status_code=404, detail="Campaign not found")

    docs = (
        await db.campaign_questions.find({"campaign_id": campaign["_id"]})
        .sort([("created_at", 1), ("_id", 1)])
        .to_list(length=2000)
    )
    by_creator: dict = {}
    for d in docs:
        by_creator.setdefault(d["creator_id"], []).append(d)

    profiles = {
        p["user_id"]: p
        for p in await db.creator_profiles.find(
            {"user_id": {"$in": list(by_creator)}}
        ).to_list(length=len(by_creator) or 1)
    }
    threads = [
        {
            "creator": _brand_visible_creator(profiles.get(creator_id)),
            "creator_id": str(creator_id),
            "unanswered": _thread_unanswered(thread),
            "questions": [_serialize_question(d) for d in thread],
        }
        for creator_id, thread in by_creator.items()
    ]
    # Waiting threads first, then by most recent word.
    threads.sort(
        key=lambda t: (not t["unanswered"], t["questions"][-1]["created_at"] or ""),
    )
    return {"campaign_id": campaign_id, "threads": threads}


@questions_router.get("/campaign/{campaign_id}/thread/{creator_id}")
async def campaign_question_thread(
    campaign_id: str,
    creator_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    """One creator's thread, for the application page."""
    campaign = await _question_campaign_or_404(campaign_id)
    if not _question_staff_may_see(campaign, user):
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        creator_oid = ObjectId(creator_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Thread not found")
    docs = await _thread_docs(campaign["_id"], creator_oid)
    return {
        "campaign_id": campaign_id,
        "creator_id": creator_id,
        "unanswered": _thread_unanswered(docs),
        "questions": [_serialize_question(d) for d in docs],
    }


@questions_router.post("/campaign/{campaign_id}/thread/{creator_id}/reply")
async def answer_campaign_question(
    campaign_id: str,
    creator_id: str,
    payload: QuestionPayload,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    campaign = await _question_campaign_or_404(campaign_id)
    if not _question_staff_may_see(campaign, user):
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        creator_oid = ObjectId(creator_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Thread not found")
    # An answer needs a question. Replying into a void would start a thread the
    # creator never opened, which is outreach, and outreach is the invite flow.
    if not await db.campaign_questions.find_one(
        {"campaign_id": campaign["_id"], "creator_id": creator_oid}, {"_id": 1}
    ):
        raise HTTPException(status_code=404, detail="Thread not found")

    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="An answer needs something in it.")

    now = datetime.now(timezone.utc)
    doc = {
        "campaign_id": campaign["_id"],
        "creator_id": creator_oid,
        "brand_id": campaign.get("brand_id"),
        "author_id": ObjectId(user["_id"]),
        "author_name": user.get("name"),
        "from_creator": False,
        "author_side": _question_author_side(campaign, user),
        "body": body,
        "created_at": now,
    }
    result = await db.campaign_questions.insert_one(doc)
    doc["_id"] = result.inserted_id

    await audit(
        user, "campaign.question_answered", "campaign", campaign["_id"],
        after={"question_id": str(result.inserted_id), "creator_id": creator_id},
        note=body[:500],
        **_campaign_audit_context(campaign),
    )
    await notify(
        creator_oid,
        "question_answered",
        title="Your question was answered",
        body=f"On “{campaign.get('title')}”: {body[:140]}",
        link=f"/campaigns/{campaign_id}",
    )
    return _serialize_question(doc)


@questions_router.get("/unanswered")
async def unanswered_questions(user: dict = Depends(require_roles("admin"))):
    """Threads whose last word is a creator's, for the action queue.

    A question nobody answered generates no state change and sits in no other
    list — it is discovered when the creator stops applying, unless something
    looks for it. Newest first, joined to the campaign and the creator's name
    so a queue row reads as a sentence.
    """
    docs = (
        await db.campaign_questions.find({})
        # Same tiebreak as _thread_docs, reversed, and for the same reason.
        .sort([("created_at", -1), ("_id", -1)])
        .to_list(length=2000)
    )
    latest: dict = {}
    for d in docs:  # newest first, so the first hit per thread is its last word
        latest.setdefault((d["campaign_id"], d["creator_id"]), d)
    waiting = [d for d in latest.values() if d.get("from_creator")]
    waiting.sort(key=lambda d: _iso(d.get("created_at")) or "", reverse=True)
    waiting = waiting[:100]

    campaign_ids = list({d["campaign_id"] for d in waiting})
    campaigns = {
        c["_id"]: c
        for c in await db.campaigns.find({"_id": {"$in": campaign_ids}}).to_list(
            length=len(campaign_ids) or 1
        )
    }
    brand_map = await _load_brand_map(
        [c["brand_id"] for c in campaigns.values()]
    )
    rows = []
    for d in waiting:
        c = campaigns.get(d["campaign_id"]) or {}
        rows.append(
            {
                "campaign_id": str(d["campaign_id"]),
                "campaign_title": c.get("title"),
                "brand_name": (brand_map.get(c.get("brand_id")) or {}).get("business_name"),
                "creator_id": str(d["creator_id"]),
                "creator_name": d.get("author_name"),
                "body": d.get("body"),
                "asked_at": _iso(d.get("created_at")),
                "execution_owner": _execution_owner(c),
            }
        )
    return rows


api_router.include_router(questions_router)


# --- One application, on its own ------------------------------------------
#
# Everything a single application needs, in one call, for one screen that the
# admin and the brand both open. The two used to read the same collaboration
# through different endpoints and describe it differently — an approved
# application showing as pending in one and approved in the other — so the
# lifecycle, the next action and the commercial terms are computed here, once,
# and both consoles render what they are given.
#
# Access is `_note_readable_collab_or_404`: the same three doors as the work
# notes this screen embeds, and a 404 behind all of them.

application_router = APIRouter(prefix="/applications", tags=["applications"])


@application_router.get("/{collab_id}")
async def get_application(
    collab_id: str,
    user: dict = Depends(require_roles(*BRAND_ROLES, "admin", "campaign_manager")),
):
    """One application: where it stands, who it is, what it pays, what's next."""
    collab, campaign = await _note_readable_collab_or_404(collab_id, user)

    creator_user = await db.users.find_one({"_id": collab["creator_id"]})
    profile = await db.creator_profiles.find_one({"user_id": collab["creator_id"]})
    payment = await db.payments.find_one({"collaboration_id": collab["_id"]})
    brand_map = await _load_brand_map([campaign["brand_id"]])
    brand = brand_map.get(campaign["brand_id"]) or {}

    state = collab.get("state", "applied")
    is_admin = (user or {}).get("role") == "admin"

    return {
        "id": str(collab["_id"]),
        "state": state,
        "pitch": collab.get("pitch"),
        "applied_at": _iso(collab.get("created_at")),
        "updated_at": _iso(collab.get("updated_at")),
        "scheduled_at": _iso(collab.get("scheduled_at")),
        "location_note": collab.get("location_note"),
        "exit_reason": collab.get("exit_reason"),
        "revision_note": collab.get("revision_note"),
        "content_urls": collab.get("content_urls")
        or ([collab["content_url"]] if collab.get("content_url") else []),
        # The status bar, and whose move it is.
        "lifecycle": _lifecycle_for(collab, campaign),
        "commercial": _commercial_for(campaign, collab),
        # The same allow-listed projection every brand-facing surface uses. An
        # admin screen could show more, but this screen is one component and a
        # phone number that only appears for one role is a phone number waiting
        # to be rendered for the other.
        "creator": _brand_visible_creator(profile, creator_user),
        # Whether this caller may open the creator's question thread — false
        # for a brand on a weare-run campaign, where the conversation is
        # between the creator and our team. Decided here so the shared screen
        # never asks what role is looking.
        "questions_enabled": _question_staff_may_see(campaign, user),
        "campaign": {
            "id": str(campaign["_id"]),
            "title": campaign.get("title"),
            "status": campaign.get("status"),
            "campaign_type": campaign.get("campaign_type"),
            # Who runs this brief, which is who the creator will be dealing
            # with and where this application was routed.
            "execution_owner": _execution_owner(campaign),
            "category": campaign.get("category"),
            "area": campaign.get("area"),
            "brand_id": str(campaign["brand_id"]),
            "brand_name": brand.get("business_name") or brand.get("name"),
            "brand_logo_url": brand.get("logo_url"),
            "creators_needed": int(campaign.get("creators_needed") or 1),
            "event_date": _iso(campaign.get("event_date")),
            "start_date": _iso(campaign.get("start_date")),
            "end_date": _iso(campaign.get("end_date")),
        },
        "payment": (
            {
                "state": payment.get("state"),
                "brand_invoice_amount": payment.get("brand_invoice_amount"),
                "brand_invoice_state": payment.get("brand_invoice_state"),
            }
            if payment
            else None
        ),
        # Decided server-side so neither console offers a button the API will
        # refuse — the brand owns exactly two transitions and no more.
        "actions": {
            "can_approve_profile": is_admin and state == "applied",
            "can_accept": state == "verified" and (is_admin or is_brand_side(user)),
            "can_decline": state in ("applied", "verified", "accepted")
            and (is_admin or is_brand_side(user)),
            # The brand records the fee too — they are the ones who negotiated
            # it. Mirrors POST /brand/collaborations/{id}/agreed-amount, which
            # takes BRAND_ROLES and admin and accepts both `accepted` (agree
            # it) and `commercial_agreed` (correct it).
            "can_agree_commercial": (is_admin or is_brand_side(user))
            and state in ("accepted", "commercial_agreed"),
            "can_review_content": state == "content_submitted"
            and (is_admin or is_brand_side(user)),
            "can_advance": is_admin
            and state not in TERMINAL_COLLAB_STATES
            and _next_collab_state(state) not in _BRAND_OWNED_TRANSITIONS
            and _next_collab_state(state) is not None,
        },
    }


api_router.include_router(application_router)


# --- Admin sample route ----------------------------------------------------


@api_router.get("/admin/ping")
async def admin_ping(user: dict = Depends(require_roles("admin"))):
    return {"pong": True, "admin_email": user["email"]}



# --- The shareable brief -----------------------------------------------------
#
# A campaign that cannot be sent to somebody is a campaign that only reaches
# people already inside the product. This is the page a link opens.
#
# **Server-rendered, deliberately.** The app is a static SPA, and the crawlers
# that build a link preview — WhatsApp, Instagram, X, Slack — do not run
# JavaScript. Open Graph tags injected by React are tags no crawler ever sees,
# so the preview has to come from HTML that already contains them at fetch
# time. That means the backend serves this one, not the bundle.
#
# It is also the page a human lands on, rather than a crawler-only shim that
# redirects: one page, so what was promised in the preview is what opens.

SHARE_PATH = "/c"


def _share_base() -> str:
    """The origin share links are built from.

    Defaults to the frontend's own origin so links look like the product. Set
    PUBLIC_SHARE_BASE_URL when the backend is on a different host and you have
    proxied /c/* to it — see PREVIEW.md.
    """
    return (
        os.environ.get("PUBLIC_SHARE_BASE_URL", "").strip().rstrip("/")
        or os.environ.get("CORS_ORIGINS", "").split(",")[0].strip().rstrip("/")
    )


def _share_url(campaign_id: str) -> str:
    return f"{_share_base()}{SHARE_PATH}/{campaign_id}"


# The brand's own public page lives at the same origin and is built the same
# way, so both are here rather than in two places that would drift.
BRAND_PATH = "/brands"


def _brand_page_url(brand_id: str) -> str:
    return f"{_share_base()}{BRAND_PATH}/{brand_id}"


def _absolute_media_url(url: Optional[str], base: str) -> str:
    """An uploaded file's path, made absolute against the host serving it.

    A preview crawler is handed the tag and no page to resolve it against, so a
    relative `/uploads/…` is a broken image in every WhatsApp card. The base is
    the origin *this* request arrived on, which is the backend — the host that
    actually mounts UPLOAD_URL_PREFIX. `_share_base()` would be wrong here: it
    is the frontend, where only `/c/*` is proxied.
    """
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"{(base or '').rstrip('/')}{url}"


def _cover_hue(seed: str) -> int:
    """The hue of the generated fallback cover, derived from the campaign id.

    A brief with no picture still has to look like itself rather than like every
    other brief, so the tint is a function of the id — stable across renders,
    different between neighbours in a list. `frontend/src/lib/cover.js` computes
    the same number the same way, so the card in the app and the server-rendered
    share page of the same brief are the same colour.

    FNV-1a rather than a sum of character codes, which was the first version and
    was measured to be useless: ids that differ in their last byte — which is
    what consecutive ObjectIds are — came out two degrees apart, so a row of
    coverless briefs was a row of the same rectangle.
    """
    h = 2166136261
    for ch in (seed or "?"):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % 360


def _share_summary(campaign: dict, brand: dict) -> str:
    """The one line that appears under the title in a WhatsApp preview.

    Money first, because that is what decides whether somebody taps.
    """
    bits = []
    if _is_barter(campaign):
        bits.append("Barter")
    elif campaign.get("budget_per_creator") is not None:
        rupees = f"₹{float(campaign['budget_per_creator']):,.0f}"
        kind = _compensation_type(campaign)
        bits.append(f"{rupees} per creator{' (negotiable)' if kind == 'negotiated' else ''}")
    where = ", ".join(x for x in (campaign.get("area"), campaign.get("city")) if x)
    if where:
        bits.append(where)
    if brand.get("business_name"):
        bits.append(f"with {brand['business_name']}")
    return " · ".join(bits) or "A paid brief on WeAre Creators."


def _share_page_html(
    campaign: dict, brand: dict, spots_left: int, media_base: str = ""
) -> str:
    """One page, no framework, everything escaped.

    Light-on-dark to match the product, inline CSS because a stylesheet is a
    second request a preview crawler will not make and a person on a bus does
    not need.
    """
    e = html_escape
    cid = str(campaign["_id"])
    title = e(campaign.get("title") or "A brief on WeAre Creators")
    brand_name = e(brand.get("business_name") or "A verified brand")
    # The brand's own page, which is where a creator goes to find out who is
    # actually asking. It is also the only link between two public pages, so it
    # is what gives a crawler a path from a shared brief into the rest.
    brand_link = (
        f'<a href="{e(_brand_page_url(str(brand["user_id"])))}">{brand_name} &rarr;</a>'
        if brand.get("user_id")
        else brand_name
    )
    summary = e(_share_summary(campaign, brand))
    url = e(_share_url(cid))
    app_base = e((os.environ.get("CORS_ORIGINS", "").split(",")[0] or "").strip().rstrip("/"))
    money = (
        "Barter"
        if _is_barter(campaign)
        else (
            f"₹{float(campaign['budget_per_creator']):,.0f} per creator"
            if campaign.get("budget_per_creator") is not None
            else "—"
        )
    )
    if _compensation_type(campaign) == "negotiated" and not _is_barter(campaign):
        money += " · negotiable"

    when = _iso(campaign.get("event_date")) or _iso(campaign.get("start_date"))
    when_label = e((when or "")[:10] or "To be confirmed")
    where = e(", ".join(x for x in (campaign.get("area"), campaign.get("city")) if x) or "—")

    # The brief's own picture is the preview card, and the site card is only the
    # fallback — a shared link that looks like every other shared link is a link
    # nobody taps.
    cover = _absolute_media_url(campaign.get("cover_image_url"), media_base)
    og_image = e(cover or f"{app_base}/og-image.png")
    # The dimensions are only declared for the site card, whose size we know. A
    # cover is whatever the brand uploaded, and a wrong og:image:width is worse
    # than none — some crawlers lay the card out from it without checking.
    og_image_size = (
        ""
        if cover
        else '\n<meta property="og:image:width" content="1200">'
        '\n<meta property="og:image:height" content="630">'
    )
    hue = _cover_hue(cid)
    initial = e((brand.get("business_name") or campaign.get("title") or "?").strip()[:1].upper())
    cover_html = (
        f'<div class="cover"><img src="{e(cover)}" alt="" loading="eager"></div>'
        if cover
        else (
            f'<div class="cover fallback" style="--h:{hue}" aria-hidden="true">'
            f"<span>{initial}</span></div>"
        )
    )

    rows = "".join(
        f'<div class="row"><dt>{e(label)}</dt><dd>{value}</dd></div>'
        for label, value in (
            ("What it pays", e(money)),
            ("Deliverables", e(campaign.get("deliverables") or "—")),
            ("Where", where),
            ("When", when_label),
            ("Creators wanted", e(str(campaign.get("creators_needed") or 1))),
            ("Spots left", e(str(max(0, spots_left)))),
            ("Run by", "WeAre" if _weare_runs(campaign) else brand_name),
        )
    )

    return f"""<!doctype html>
<html lang="en-IN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {brand_name} | WeAre Creators</title>
<meta name="description" content="{summary}">
<meta name="theme-color" content="#0B0A09">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="WeAre Creators">
<meta property="og:locale" content="en_IN">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{title} — {brand_name}">
<meta property="og:description" content="{summary}">
<meta property="og:image" content="{og_image}">{og_image_size}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title} — {brand_name}">
<meta name="twitter:description" content="{summary}">
<meta name="twitter:image" content="{og_image}">
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0B0A09;color:#F5F1EC;font:16px/1.6 'Inter Tight',system-ui,-apple-system,sans-serif}}
.wrap{{max-width:44rem;margin:0 auto;padding:2.5rem 1.5rem 4rem}}
.eyebrow{{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:#9C938B}}
/* The box is reserved before the image arrives, so the headline below it does
   not jump when it does. */
.cover{{aspect-ratio:16/9;margin-bottom:2rem;border:1px solid rgba(255,255,255,.1);border-radius:.5rem;overflow:hidden;background:rgba(255,255,255,.03)}}
.cover img{{width:100%;height:100%;object-fit:cover;display:block}}
/* The same two layers as coverGradient() in frontend/src/lib/cover.js. */
.fallback{{display:grid;place-items:center;background:
  radial-gradient(120% 120% at 20% 0%,hsl(var(--h) 42% 32%) 0%,transparent 62%),
  linear-gradient(140deg,hsl(var(--h) 30% 20%),hsl(var(--h) 22% 11%))}}
.fallback span{{font-family:Fraunces,Georgia,serif;font-size:clamp(3rem,12vw,5.5rem);color:rgba(245,241,236,.55);line-height:1}}
h1{{font-family:Fraunces,Georgia,serif;font-size:clamp(2rem,6vw,3rem);line-height:1.05;margin:.75rem 0 0;letter-spacing:-.02em}}
.brand{{margin-top:.75rem;color:#F05D14;font-size:.9rem}}
.card{{margin-top:2rem;border:1px solid rgba(255,255,255,.1);border-radius:.5rem;background:rgba(255,255,255,.02);padding:1.5rem}}
.row{{display:flex;gap:1rem;padding:.7rem 0;border-bottom:1px solid rgba(255,255,255,.07)}}
.row:last-child{{border-bottom:0}}
dt{{flex:0 0 9.5rem;font-size:.68rem;letter-spacing:.18em;text-transform:uppercase;color:#9C938B}}
dd{{margin:0;flex:1;min-width:0}}
.brief{{margin-top:2rem;white-space:pre-line;color:rgba(245,241,236,.9)}}
.cta{{margin-top:2.5rem;display:flex;flex-wrap:wrap;gap:.75rem}}
.btn{{display:inline-flex;align-items:center;min-height:2.9rem;padding:0 1.4rem;border-radius:999px;text-decoration:none;font-size:.85rem}}
.primary{{background:#F05D14;color:#0B0A09}}
.ghost{{border:1px solid rgba(255,255,255,.18);color:#F5F1EC}}
footer{{margin-top:3rem;color:#7d766f;font-size:.78rem}}
a{{color:inherit}}
</style></head><body><div class="wrap">
{cover_html}
<p class="eyebrow">Paid brief · Open to verified creators</p>
<h1>{title}</h1>
<p class="brand">{brand_link}</p>
<div class="card"><dl style="margin:0">{rows}</dl></div>
<div class="brief">{e(campaign.get("brief") or "")}</div>
<div class="cta">
  <a class="btn primary" href="{app_base}/signup?role=creator">Sign up to apply</a>
  <a class="btn ghost" href="{app_base}/login">Log in</a>
</div>
<footer>
  You need a verified WeAre Creators account to pitch on this brief.
  <a href="{app_base}/campaigns">See every open brief</a>.
</footer>
</div></body></html>"""


@app.get(SHARE_PATH + "/{campaign_id}", include_in_schema=False)
async def public_campaign_page(campaign_id: str, request: Request):
    """One brief, readable by anyone with the link. No account, no API prefix.

    Only live briefs from verified brands, the same rule the shop window uses:
    an unverified brand can post and be seen by verified creators in-app, but
    it is not promoted to the open internet under our name.
    """
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="That brief isn't available.")
    campaign = await db.campaigns.find_one({"_id": oid})
    if not campaign or campaign.get("status") not in LIVE_CAMPAIGN_STATUSES:
        raise HTTPException(status_code=404, detail="That brief isn't available.")
    # A private brief has no public page at all — not a login wall, a 404, so
    # the link says nothing about whether the campaign exists.
    if _is_private(campaign):
        raise HTTPException(status_code=404, detail="That brief isn't available.")

    brand_profile = await db.brand_profiles.find_one({"user_id": campaign["brand_id"]}) or {}
    if not brand_profile.get("verified"):
        raise HTTPException(status_code=404, detail="That brief isn't available.")

    needed = int(campaign.get("creators_needed") or 1)
    filled = (await _filled_counts_for([oid])).get(oid, 0)
    return Response(
        content=_share_page_html(
            campaign,
            brand_profile,
            needed - filled,
            # This request's own origin, because the backend is what mounts
            # /uploads. Not _share_base(), which is the frontend.
            media_base=str(request.base_url),
        ),
        media_type="text/html; charset=utf-8",
        # Public and safe to cache briefly — a crawler and a person often fetch
        # it seconds apart, and the spots-left figure is the only thing that
        # moves. Short enough that a closed brief stops being shared quickly.
        headers={"Cache-Control": "public, max-age=300"},
    )


# --- The brand behind the brief ----------------------------------------------
#
# A creator could see a campaign and learn nothing whatever about who was
# posting it — a name, and that was all. This is the page that answers "who are
# these people", and it is built the same way and for the same reason as the
# brief's: server-rendered, so it is shareable and something a search engine can
# actually read.
#
# **It is a public page about a business, and nothing else.** The account behind
# a brand belongs to a named person whose phone number is their WhatsApp and
# whose email is their work address, and `registered_address` is frequently a
# director's home. None of that is on here. `_public_brand` is an allow-list for
# the same reason `_brand_visible_creator` is: a deny-list is a list somebody
# forgets to add to.

CATEGORY_LABELS = {
    "fnb": "Food & drink",
    "hospitality": "Hospitality",
    "retail": "Retail",
    "real_estate": "Real estate",
    "fashion": "Fashion",
    "travel": "Travel",
    "wellness": "Wellness",
    "lifestyle": "Lifestyle",
}

# What a stranger may read about a business. Everything not named here is
# absent by construction rather than by having been remembered.
_PUBLIC_BRAND_FIELDS = (
    "business_name",
    "logo_url",
    "category",
    "about",
    "city",
    "outlets",
    "website",
    "instagram_handle",
    "verified",
)

# Named so the leak test can look for them by name as well as by value. The
# first three are the manager as a person; the rest are the business's
# paperwork, which is the reviewer's business and nobody else's.
PUBLIC_BRAND_FORBIDDEN_FIELDS = (
    "contact_phone",
    "contact_email",
    "contact_person_name",
    "contact_person_designation",
    "registered_address",
    "gst_number",
    "verification_reason",
    "manager_phone",
    "manager_email",
    "phone",
    "email",
)


def _public_brand(profile: dict) -> dict:
    """The only projection of a brand on any unauthenticated surface."""
    out = {k: profile.get(k) for k in _PUBLIC_BRAND_FIELDS}
    out["id"] = str(profile["user_id"])
    out["outlets"] = [
        {k: o.get(k) for k in ("name", "address", "area", "city", "lat", "lng", "place_id")}
        for o in (profile.get("outlets") or [])
    ]
    out["verified"] = bool(profile.get("verified"))
    return out


def _maps_link(outlet: dict) -> str:
    """Where "Open in Maps" goes.

    Built from the coordinate rather than the text, because that is the thing
    the brand actually dropped a pin on — an autocomplete address routinely
    resolves to the street. No API key: this is a plain Google Maps URL, which
    matters on a page anyone can load, since embedding a static map would mean
    publishing a key on an unauthenticated page for decoration.
    """
    if outlet.get("lat") is not None and outlet.get("lng") is not None:
        query = f"{outlet['lat']},{outlet['lng']}"
        place = outlet.get("place_id")
        suffix = f"&query_place_id={quote(place)}" if place else ""
        return f"https://www.google.com/maps/search/?api=1&query={quote(query)}{suffix}"
    where = ", ".join(
        x for x in (outlet.get("address"), outlet.get("area"), outlet.get("city")) if x
    )
    return f"https://www.google.com/maps/search/?api=1&query={quote(where)}" if where else ""


def _brand_summary(brand: dict, live: int) -> str:
    """The line under the name in a preview card."""
    bits = []
    label = CATEGORY_LABELS.get(brand.get("category"))
    if label:
        bits.append(label)
    if brand.get("city"):
        bits.append(brand["city"])
    if live:
        bits.append(f"{live} open {'brief' if live == 1 else 'briefs'}")
    about = (brand.get("about") or "").strip()
    if about:
        first = about.split("\n")[0].strip()
        return first[:180] + ("…" if len(first) > 180 else "")
    return " · ".join(bits) or "A verified brand on WeAre Creators."


def _brand_page_html(
    brand: dict, campaigns: list, media_base: str = "", request_base: str = ""
) -> str:
    """One brand, no framework, everything escaped.

    Takes the already-projected `_public_brand` dict, not the raw profile — so
    a field that is not on the allow-list cannot be reached from in here even
    by accident.
    """
    e = html_escape
    bid = e(brand["id"])
    name = e(brand.get("business_name") or "A verified brand")
    url = e(_brand_page_url(brand["id"]))
    app_base = e((os.environ.get("CORS_ORIGINS", "").split(",")[0] or "").strip().rstrip("/"))
    summary = e(_brand_summary(brand, len(campaigns)))
    category = e(CATEGORY_LABELS.get(brand.get("category"), ""))
    logo = _absolute_media_url(brand.get("logo_url"), media_base)
    og_image = e(logo or f"{app_base}/og-image.png")
    og_image_size = (
        ""
        if logo
        else '\n<meta property="og:image:width" content="1200">'
        '\n<meta property="og:image:height" content="630">'
    )

    monogram = e((brand.get("business_name") or "?").strip()[:1].upper())
    mark = (
        f'<img class="logo" src="{e(logo)}" alt="">'
        if logo
        else f'<span class="logo mono" style="--h:{_cover_hue(brand["id"])}">{monogram}</span>'
    )

    chips = "".join(
        f'<span class="chip">{c}</span>'
        for c in (
            category,
            e(brand.get("city") or ""),
            '<span class="tick">✓</span> Verified by WeAre' if brand.get("verified") else "",
        )
        if c
    )

    about_html = (
        f'<div class="about">{e(brand.get("about"))}</div>' if brand.get("about") else ""
    )

    links = "".join(
        f'<a class="out" href="{e(href)}" rel="nofollow noopener" target="_blank">{label}</a>'
        for href, label in (
            (brand.get("website") or "", "Website"),
            (
                f"https://instagram.com/{brand['instagram_handle']}"
                if brand.get("instagram_handle")
                else "",
                f"@{e(brand.get('instagram_handle') or '')}",
            ),
        )
        if href
    )

    outlets = ""
    if brand.get("outlets"):
        rows = []
        for o in brand["outlets"]:
            where = e(
                ", ".join(x for x in (o.get("address"), o.get("area"), o.get("city")) if x)
                or "—"
            )
            link = _maps_link(o)
            # An outlet with a dropped pin links to the coordinate; one typed
            # in without a pin falls back to a Maps *search* for its address,
            # which is honest — we are not inventing a coordinate we do not
            # have. An outlet with neither gets no link and still lists.
            pin = (
                f'<a class="pin" href="{e(link)}" rel="nofollow noopener" target="_blank">'
                f'<span class="tick">◎</span> Open in Maps</a>'
                if link
                else ""
            )
            rows.append(
                f'<li><p class="oname">{e(o.get("name") or name)}</p>'
                f'<p class="oaddr">{where}</p>{pin}</li>'
            )
        outlets = (
            '<section><h2>Where they are</h2><ul class="outlets">'
            + "".join(rows)
            + "</ul></section>"
        )

    briefs = ""
    if campaigns:
        cards = []
        for c in campaigns:
            cid = str(c["_id"])
            cover = _absolute_media_url(c.get("cover_image_url"), media_base)
            art = (
                f'<span class="cover"><img src="{e(cover)}" alt=""></span>'
                if cover
                else f'<span class="cover fallback" style="--h:{_cover_hue(cid)}"></span>'
            )
            money = (
                "Barter"
                if _is_barter(c)
                else (
                    f"₹{float(c['budget_per_creator']):,.0f}"
                    if c.get("budget_per_creator") is not None
                    else "—"
                )
            )
            place = e(", ".join(x for x in (c.get("area"), c.get("city")) if x) or "")
            cards.append(
                f'<a class="brief" href="{e(_share_url(cid))}">{art}'
                f'<span class="btitle">{e(c.get("title") or "A brief")}</span>'
                f'<span class="bmeta">{e(money)}{" · " + place if place else ""}</span></a>'
            )
        briefs = (
            f'<section><h2>Open briefs</h2><div class="briefs">{"".join(cards)}</div></section>'
        )
    else:
        briefs = (
            '<section><h2>Open briefs</h2><p class="none">Nothing open right now. '
            'New briefs from verified brands go up every week.</p></section>'
        )

    # Structured data, so a search result can show this as a business rather
    # than as an untitled page. Built from the same allow-listed dict.
    ld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand.get("business_name") or "",
        "url": _brand_page_url(brand["id"]),
        **({"logo": logo} if logo else {}),
        **({"description": brand["about"]} if brand.get("about") else {}),
        **({"sameAs": [brand["website"]]} if brand.get("website") else {}),
        **(
            {"address": {"@type": "PostalAddress", "addressLocality": brand["city"],
                         "addressCountry": "IN"}}
            if brand.get("city")
            else {}
        ),
    }
    ld_json = json.dumps(ld).replace("<", "\\u003c")

    return f"""<!doctype html>
<html lang="en-IN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — briefs on WeAre Creators</title>
<meta name="description" content="{summary}">
<meta name="theme-color" content="#0B0A09">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="WeAre Creators">
<meta property="og:locale" content="en_IN">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{name} on WeAre Creators">
<meta property="og:description" content="{summary}">
<meta property="og:image" content="{og_image}">{og_image_size}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{name} on WeAre Creators">
<meta name="twitter:description" content="{summary}">
<meta name="twitter:image" content="{og_image}">
<script type="application/ld+json">{ld_json}</script>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0B0A09;color:#F5F1EC;font:16px/1.6 'Inter Tight',system-ui,-apple-system,sans-serif}}
.wrap{{max-width:44rem;margin:0 auto;padding:2.5rem 1.5rem 4rem}}
.head{{display:flex;gap:1.25rem;align-items:center}}
.logo{{width:5rem;height:5rem;flex:none;border-radius:.5rem;border:1px solid rgba(255,255,255,.1);object-fit:contain;background:rgba(255,255,255,.04)}}
.mono{{display:grid;place-items:center;font-family:Fraunces,Georgia,serif;font-size:2.25rem;color:rgba(245,241,236,.6);
  background:linear-gradient(140deg,hsl(var(--h) 30% 20%),hsl(var(--h) 22% 11%))}}
.eyebrow{{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:#9C938B}}
h1{{font-family:Fraunces,Georgia,serif;font-size:clamp(1.9rem,5.5vw,2.75rem);line-height:1.05;margin:.4rem 0 0;letter-spacing:-.02em}}
h2{{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:#9C938B;font-weight:500;margin:0 0 1rem}}
section{{margin-top:2.5rem}}
.chips{{margin-top:1.25rem;display:flex;flex-wrap:wrap;gap:.5rem}}
.chip{{border:1px solid rgba(255,255,255,.12);border-radius:999px;padding:.3rem .8rem;font-size:.72rem;letter-spacing:.06em;color:#C9C1B8}}
.tick{{color:#F05D14}}
.about{{white-space:pre-line;color:rgba(245,241,236,.9)}}
.links{{margin-top:1.25rem;display:flex;flex-wrap:wrap;gap:.75rem}}
.out{{display:inline-flex;align-items:center;min-height:2.5rem;padding:0 1rem;border:1px solid rgba(255,255,255,.15);border-radius:999px;font-size:.8rem;text-decoration:none;color:#F5F1EC}}
.outlets{{list-style:none;margin:0;padding:0;display:grid;gap:.75rem}}
.outlets li{{border:1px solid rgba(255,255,255,.1);border-radius:.5rem;background:rgba(255,255,255,.02);padding:1rem 1.15rem}}
.oname{{margin:0;font-family:Fraunces,Georgia,serif;font-size:1.05rem}}
.oaddr{{margin:.35rem 0 0;color:#9C938B;font-size:.88rem}}
.pin{{display:inline-block;margin-top:.6rem;font-size:.78rem;color:#F5F1EC;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.2)}}
.briefs{{display:grid;gap:.75rem}}
.brief{{display:block;border:1px solid rgba(255,255,255,.1);border-radius:.5rem;overflow:hidden;text-decoration:none;color:inherit;background:rgba(255,255,255,.02)}}
.cover{{display:block;aspect-ratio:16/9;background:rgba(255,255,255,.03)}}
.cover img{{width:100%;height:100%;object-fit:cover;display:block}}
.fallback{{background:
  radial-gradient(120% 120% at 20% 0%,hsl(var(--h) 42% 32%) 0%,transparent 62%),
  linear-gradient(140deg,hsl(var(--h) 30% 20%),hsl(var(--h) 22% 11%))}}
.btitle{{display:block;padding:1rem 1.15rem .2rem;font-family:Fraunces,Georgia,serif;font-size:1.2rem;line-height:1.2}}
.bmeta{{display:block;padding:0 1.15rem 1.1rem;color:#9C938B;font-size:.82rem}}
.none{{color:#9C938B;margin:0}}
.cta{{margin-top:2.5rem;display:flex;flex-wrap:wrap;gap:.75rem}}
.btn{{display:inline-flex;align-items:center;min-height:2.9rem;padding:0 1.4rem;border-radius:999px;text-decoration:none;font-size:.85rem}}
.primary{{background:#F05D14;color:#0B0A09}}
.ghost{{border:1px solid rgba(255,255,255,.18);color:#F5F1EC}}
footer{{margin-top:3rem;color:#7d766f;font-size:.78rem}}
a{{color:inherit}}
@media(min-width:40rem){{.briefs{{grid-template-columns:1fr 1fr}}}}
</style></head><body><div class="wrap">
<div class="head">{mark}<div>
  <p class="eyebrow">Brand on WeAre Creators</p>
  <h1>{name}</h1>
</div></div>
<div class="chips">{chips}</div>
{f'<section>{about_html}</section>' if about_html else ''}
{f'<div class="links">{links}</div>' if links else ''}
{outlets}
{briefs}
<div class="cta">
  <a class="btn primary" href="{app_base}/signup?role=creator">Sign up to pitch</a>
  <a class="btn ghost" href="{app_base}/campaigns">See every open brief</a>
</div>
<footer>
  WeAre Creators connects verified creators with brands running paid campaigns
  in Bengaluru. Brands are checked by our team before their briefs go public.
</footer>
</div></body></html>"""


@app.get(BRAND_PATH + "/{brand_id}", include_in_schema=False)
async def public_brand_page(brand_id: str, request: Request):
    """One brand, readable by anyone. No account, no API prefix.

    Only verified brands, the same rule the brief's page uses: a business we
    have not checked is not published under our name.
    """
    try:
        oid = ObjectId(brand_id)
    except Exception:
        raise HTTPException(status_code=404, detail="That brand isn't available.")
    profile = await db.brand_profiles.find_one({"user_id": oid})
    if not profile or not profile.get("verified"):
        raise HTTPException(status_code=404, detail="That brand isn't available.")

    campaigns = (
        await db.campaigns.find(
            # The page is public, so its brief shelf is too. A brand's private
            # briefs are its own business — literally the feature.
            {"brand_id": oid, "status": {"$in": list(LIVE_CAMPAIGN_STATUSES)},
             **PUBLIC_CAMPAIGN_QUERY}
        )
        .sort("created_at", -1)
        .to_list(length=24)
    )
    return Response(
        content=_brand_page_html(
            _public_brand(profile),
            campaigns,
            media_base=str(request.base_url),
        ),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def public_sitemap():
    """Every public page, so "indexable" means something.

    Nothing on the open internet links to a brand page except our own brief
    pages, and nothing links to those except this. Without a sitemap the whole
    public surface is reachable only by being sent the link.
    """
    brand_ids = [
        p["user_id"]
        for p in await db.brand_profiles.find({"verified": True}, {"user_id": 1}).to_list(
            length=2000
        )
    ]
    campaigns = (
        await db.campaigns.find(
            {"brand_id": {"$in": brand_ids}, "status": {"$in": list(LIVE_CAMPAIGN_STATUSES)},
             # "Not indexable" starts with not being listed for indexing.
             **PUBLIC_CAMPAIGN_QUERY},
            {"_id": 1, "updated_at": 1},
        ).to_list(length=5000)
        if brand_ids
        else []
    )

    urls = [(_brand_page_url(str(b)), None) for b in brand_ids]
    urls += [(_share_url(str(c["_id"])), _iso(c.get("updated_at"))) for c in campaigns]

    body = "".join(
        f"<url><loc>{html_escape(loc)}</loc>"
        + (f"<lastmod>{html_escape(mod[:10])}</lastmod>" if mod else "")
        + "</url>"
        for loc, mod in urls
    )
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{body}</urlset>"
        ),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


app.include_router(api_router)

# Uploaded images are served straight off disk. Mounted outside /api because
# these are plain files, not API responses — the frontend joins the backend
# origin with the stored path.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    UPLOAD_URL_PREFIX,
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_cors_origins = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup: indexes + admin seed
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _startup():
    # First, before any of the slow work: whether this process will hand out a
    # fixed login code. It belongs at the top of the deploy log, not buried
    # under index maintenance.
    warn_about_fixed_test_otp()

    # users
    # NOTE: partial-unique indexes on email + phone because creators/brands now
    # sign up with phone only (email may be null), and admins have email but
    # no phone. A partial filter is required because `sparse` still indexes
    # explicit null values, which would collide.
    async def _ensure_partial_unique(collection, field: str) -> None:
        target_name = f"{field}_partial_unique"
        # First, drop any legacy single-field index on this field that isn't the
        # target — old non-partial `unique` or `sparse+unique` variants collide
        # on multiple null values and must go.
        existing = await collection.index_information()
        for name, info in existing.items():
            if name in ("_id_", target_name):
                continue
            keys = info.get("key", [])
            if len(keys) == 1 and keys[0][0] == field:
                await collection.drop_index(name)
        await collection.create_index(
            field,
            unique=True,
            partialFilterExpression={field: {"$type": "string"}},
            name=target_name,
        )

    await _ensure_partial_unique(db.users, "email")
    await _ensure_partial_unique(db.users, "phone")
    await db.users.create_index("role")
    await db.users.create_index("status")

    # otp_codes (TTL cleans up expired docs automatically)
    await db.otp_codes.create_index("expires_at", expireAfterSeconds=0)
    await db.otp_codes.create_index([("phone", 1), ("created_at", -1)])

    # creator_profiles (1:1 with users)
    await db.creator_profiles.create_index("user_id", unique=True)
    await db.creator_profiles.create_index("verification_status")
    # The vetting queue reads these together; the nudge job reads the second.
    await db.creator_profiles.create_index(
        [("verification_status", 1), ("submitted_for_review_at", 1)]
    )
    await db.creator_profiles.create_index(
        [("onboarding_nudge_sent_at", 1), ("created_at", 1)]
    )

    # Brand verification documents — read per brand, newest first.
    await db.brand_documents.create_index([("brand_id", 1), ("created_at", -1)])
    await db.brand_profiles.create_index(
        [("verified", 1), ("verification_state", 1), ("submitted_for_verification_at", 1)]
    )

    # Work notes — always read as one thread, oldest first.
    await db.collaboration_notes.create_index(
        [("collaboration_id", 1), ("created_at", 1)]
    )
    await db.collaboration_notes.create_index([("campaign_id", 1), ("created_at", 1)])
    # One thread per (campaign, creator), read oldest-first; the queue scans
    # newest-first across all of them.
    await db.campaign_questions.create_index(
        [("campaign_id", 1), ("creator_id", 1), ("created_at", 1)]
    )
    await db.campaign_questions.create_index([("created_at", -1)])

    # One login per brand, enforced by the database rather than by everybody
    # remembering. Partial, so it constrains brand managers and nothing else.
    await db.users.create_index(
        "brand_id",
        unique=True,
        partialFilterExpression={"role": "brand_manager"},
        name="one_manager_per_brand",
    )

    # Instagram connections — one per creator, read by the two refresh jobs in
    # expiry and staleness order.
    await db.instagram_connections.create_index("user_id", unique=True)

    # content_performance: one reading per collaboration, so the upsert in
    # _record_performance has something to be unique against; campaign_id
    # carries every rollup.
    await db.content_performance.create_index("collaboration_id", unique=True)
    await db.content_performance.create_index("campaign_id")
    # Showcase is a filter on the campaigns list. Sparse: almost nothing
    # carries it, and an index over mostly-absent values should not be paying
    # for the rows that do not.
    await db.campaigns.create_index("showcase", sparse=True)
    await db.instagram_connections.create_index([("status", 1), ("token_expires_at", 1)])
    await db.instagram_connections.create_index([("status", 1), ("stats_fetched_at", 1)])
    # OAuth states are single-use and short-lived; Mongo expires the leftovers
    # from journeys nobody finished.
    await db.instagram_oauth_states.create_index("state", unique=True)
    await db.instagram_oauth_states.create_index("expires_at", expireAfterSeconds=0)
    await db.creator_profiles.create_index("niches")

    # brand_profiles (1:1 with users)
    await db.brand_profiles.create_index("user_id", unique=True)
    await db.brand_profiles.create_index("verified")
    await db.brand_profiles.create_index("category")

    # campaigns
    await db.campaigns.create_index("brand_id")
    await db.campaigns.create_index("status")
    await db.campaigns.create_index([("status", 1), ("created_at", -1)])
    await db.campaigns.create_index([("area", 1), ("category", 1)])

    # collaborations
    await db.collaborations.create_index("campaign_id")
    await db.collaborations.create_index("creator_id")
    await db.collaborations.create_index("state")

    # A creator can only hold one *live* application per campaign. The index is
    # partial on `active` so that declining someone frees them to apply again if
    # the brief reopens — a plain unique index made every decline permanent.
    await db.collaborations.update_many(
        {"active": {"$exists": False}},
        {"$set": {"active": True}},
    )
    await db.collaborations.update_many(
        {"state": {"$in": ["declined", "cancelled"]}, "active": True},
        {"$set": {"active": False}},
    )
    existing_collab_indexes = await db.collaborations.index_information()
    for name, info in existing_collab_indexes.items():
        if name == "_id_":
            continue
        keys = [k for k, _ in info.get("key", [])]
        if keys == ["campaign_id", "creator_id"] and name != "one_live_application":
            await db.collaborations.drop_index(name)
    await db.collaborations.create_index(
        [("campaign_id", 1), ("creator_id", 1)],
        unique=True,
        partialFilterExpression={"active": True},
        name="one_live_application",
    )

    # slots — read per campaign in time order; manager scoping reads by manager.
    await db.campaign_slots.create_index([("campaign_id", 1), ("starts_at", 1)])
    await db.campaigns.create_index("manager_id")

    # campaign invitations — one per creator per campaign, enforced in the
    # database so two admins inviting at once can't double-message anyone.
    await db.campaign_invitations.create_index(
        [("campaign_id", 1), ("creator_id", 1)],
        unique=True,
        name="one_invite_per_creator",
    )
    await db.campaign_invitations.create_index([("creator_id", 1), ("created_at", -1)])

    # payments (one per collaboration)
    await db.payments.create_index("collaboration_id", unique=True)
    await db.payments.create_index("state")
    await db.payments.create_index("brand_invoice_state")

    # audit log + notifications
    await db.audit_log.create_index([("created_at", -1)])
    await db.audit_log.create_index([("subject_type", 1), ("subject_id", 1)])
    # "what did this admin do", and "everything that happened to money", both
    # newest-first — the two ways the log is actually read.
    await db.audit_log.create_index([("actor_id", 1), ("created_at", -1)])
    await db.audit_log.create_index([("action", 1), ("created_at", -1)])
    # "everything this brand did" and "everything that happened on this brief" —
    # sparse, because only the actions that have the context carry the keys.
    await db.audit_log.create_index(
        [("brand_id", 1), ("created_at", -1)], sparse=True
    )
    await db.audit_log.create_index(
        [("campaign_id", 1), ("created_at", -1)], sparse=True
    )
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1)])

    # --- Data migrations ---------------------------------------------------
    # The creator approval concept has been called three things. Normalise all
    # of them, in order, so a database from any previous version lands correct.
    # Every step is filtered so re-running is a no-op.

    # 1. Field rename: vetting_status -> verification_status. Guarded on the new
    #    field being absent so a partly-migrated document is never clobbered.
    for old_field, new_field in (
        ("vetting_status", "verification_status"),
        ("vetted_at", "verified_at"),
        ("vetting_reason", "verification_reason"),
    ):
        renamed = await db.creator_profiles.update_many(
            {old_field: {"$exists": True}, new_field: {"$exists": False}},
            {"$rename": {old_field: new_field}},
        )
        if renamed.modified_count:
            logger.info(
                "Migrated %d creator profile(s): %s -> %s",
                renamed.modified_count,
                old_field,
                new_field,
            )
    # Anything left holding both fields keeps the new one; drop the stale copy.
    await db.creator_profiles.update_many(
        {"vetting_status": {"$exists": True}},
        {"$unset": {"vetting_status": "", "vetted_at": "", "vetting_reason": ""}},
    )

    # 2. Value rename. `approved` was written by an old demo seed while
    #    approvals wrote `vetted`, which is what once hid every approved creator
    #    from the brand directory.
    for legacy in ("approved", "vetted"):
        migrated = await db.creator_profiles.update_many(
            {"verification_status": legacy},
            {"$set": {"verification_status": "verified"}},
        )
        if migrated.modified_count:
            logger.info(
                "Migrated %d creator profile(s) from verification_status '%s' to 'verified'",
                migrated.modified_count,
                legacy,
            )

    # 3. The collaboration state carried the same word.
    collabs_migrated = await db.collaborations.update_many(
        {"state": "vetted"}, {"$set": {"state": "verified"}}
    )
    if collabs_migrated.modified_count:
        logger.info(
            "Migrated %d collaboration(s) from state 'vetted' to 'verified'",
            collabs_migrated.modified_count,
        )

    # 4. Drop the index on the old field name so it stops being maintained.
    for name in list((await db.creator_profiles.index_information()).keys()):
        if name.startswith("vetting_status"):
            await db.creator_profiles.drop_index(name)
            logger.info("Dropped stale index %s on creator_profiles", name)

    await db.creator_profiles.update_many(
        {"pending_review": {"$exists": False}}, {"$set": {"pending_review": False}}
    )

    # 5. The vetting queue used to be "pending, and has an Instagram handle",
    #    which was a guess at who had finished onboarding. It is now an
    #    explicit submission timestamp. Backfill it from the old heuristic so
    #    nobody who was already waiting on us silently drops out of the queue
    #    on deploy; `updated_at` is the closest thing we have to when they
    #    finished.
    backfilled = 0
    async for doc in db.creator_profiles.find(
        {
            "verification_status": "pending",
            "submitted_for_review_at": {"$exists": False},
            "instagram_handle": {"$type": "string", "$ne": ""},
        }
    ):
        await db.creator_profiles.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "submitted_for_review_at": doc.get("updated_at")
                    or doc.get("created_at")
                    or datetime.now(timezone.utc)
                }
            },
        )
        backfilled += 1
    if backfilled:
        logger.info(
            "Backfilled submitted_for_review_at on %d creator profile(s) already "
            "waiting in the vetting queue",
            backfilled,
        )

    # 6. Brands predate `verification_state`, and the review queue now filters
    #    on it. Anyone already waiting on us is moved to pending_verification
    #    rather than dropped — they will show in the queue with no documents
    #    attached, which is the truth about them and something an admin can act
    #    on, where vanishing silently would not be.
    for query, state in (
        ({"verified": True}, "verified"),
        ({"verified": False, "verification_reason": {"$nin": [None, ""]}}, "rejected"),
        ({"verified": False}, "pending_verification"),
    ):
        moved = await db.brand_profiles.update_many(
            {**query, "verification_state": {"$exists": False}},
            {"$set": {"verification_state": state}},
        )
        if moved.modified_count:
            logger.info(
                "Backfilled verification_state=%s on %d brand profile(s)",
                state,
                moved.modified_count,
            )

    # 7. `brand` accounts predate the `brand_manager` role. Every one of them is
    #    already a single login belonging to a single person — that is what the
    #    role names, so they are moved rather than left on a second spelling
    #    that every guard would have to keep remembering. Demo brands seeded for
    #    the feed are skipped: they have no password and no phone, nobody signs
    #    into them, and calling them managers would put a fiction in the role.
    promoted = await db.users.update_many(
        {"role": "brand", "phone": {"$nin": [None, ""]}},
        [{"$set": {"role": "brand_manager", "brand_id": "$_id"}}],
    )
    if promoted.modified_count:
        logger.info(
            "Moved %d brand account(s) onto the brand_manager role",
            promoted.modified_count,
        )
    # Any brand login still missing the link — including one promoted before
    # this ran — gets it, since `_brand_scope` reads it on every request.
    await db.users.update_many(
        {"role": "brand_manager", "brand_id": {"$exists": False}},
        [{"$set": {"brand_id": "$_id"}}],
    )
    # And the name: a manager with no name makes for a campaign whose contact
    # is blank. The account name is who signed up, which is the best we have
    # until they fill the profile in.
    await db.users.update_many(
        {"role": "brand_manager", "manager_name": {"$in": [None, ""]}},
        [{"$set": {"manager_name": "$name"}}],
    )

    # 8. Campaigns predate `compensation_type`. Every one of them was posted by
    #    a brand against a cash budget, so `fixed` is what they are rather than
    #    a default standing in for the unknown. `_compensation_type` reads the
    #    same answer without this, but the field being present means an admin
    #    filtering for barter gets a query that can use an index, and means the
    #    stored document says what it is instead of relying on a reader.
    priced = await db.campaigns.update_many(
        {"compensation_type": {"$exists": False}},
        {"$set": {"compensation_type": DEFAULT_COMPENSATION_TYPE}},
    )
    if priced.modified_count:
        logger.info(
            "Backfilled compensation_type=%s on %d campaign(s)",
            DEFAULT_COMPENSATION_TYPE,
            priced.modified_count,
        )

    # 9. Campaigns predate `execution_owner`. Who ran one was implicit in who
    #    its manager was: a WeAre campaign_manager on it meant we were running
    #    it, anything else meant the brand. That is derived once, here, rather
    #    than by every reader joining users on every campaign row forever.
    weare_manager_ids = await db.users.distinct("_id", {"role": "campaign_manager"})
    if weare_manager_ids:
        ours = await db.campaigns.update_many(
            {
                "execution_owner": {"$exists": False},
                "manager_id": {"$in": weare_manager_ids},
            },
            {"$set": {"execution_owner": "weare"}},
        )
        if ours.modified_count:
            logger.info(
                "Backfilled execution_owner=weare on %d campaign(s) with a WeAre manager",
                ours.modified_count,
            )
    # Everything still unmarked was the brand's own. Done second and
    # unconditionally, so the pass is idempotent and order-independent.
    theirs = await db.campaigns.update_many(
        {"execution_owner": {"$exists": False}},
        {"$set": {"execution_owner": DEFAULT_EXECUTION_OWNER}},
    )
    if theirs.modified_count:
        logger.info(
            "Backfilled execution_owner=%s on %d campaign(s)",
            DEFAULT_EXECUTION_OWNER,
            theirs.modified_count,
        )

    # 10. Campaigns predate `city`. They all ran in Bengaluru — that is where
    #     the operation is and was — so this is what they are rather than a
    #     default standing in for the unknown.
    placed = await db.campaigns.update_many(
        {"$or": [{"city": {"$exists": False}}, {"city": None}]},
        {"$set": {"city": DEFAULT_CAMPAIGN_CITY}},
    )
    if placed.modified_count:
        logger.info(
            "Backfilled city=%s on %d campaign(s)", DEFAULT_CAMPAIGN_CITY, placed.modified_count
        )

    # The nudge loop. Off entirely when the interval is zero, so a deployment
    # that has its own scheduler can drive POST /admin/jobs/creator-nudges
    # instead without two things chasing the same people.
    if _nudge_interval_seconds() > 0:
        app.state.nudge_task = asyncio.create_task(_nudge_loop())
        logger.info(
            "Creator profile nudges on: every %ds, %d day(s) after signup",
            _nudge_interval_seconds(),
            _nudge_after_days(),
        )

    # Instagram token renewal and stats caching. Off when the Meta app isn't
    # configured yet, which is the normal state during app review — the rest
    # of the product carries on with self-reported numbers.
    if instagram_configured() and _instagram_job_interval_seconds() > 0:
        app.state.instagram_task = asyncio.create_task(_instagram_loop())
        logger.info(
            "Instagram refresh on: every %ds, stats cached for %dh",
            _instagram_job_interval_seconds(),
            _instagram_stats_ttl_hours(),
        )
    elif not instagram_configured():
        logger.info(
            "Instagram stats are off — set INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, "
            "INSTAGRAM_REDIRECT_URI and INSTAGRAM_TOKEN_KEY to switch them on."
        )

    # The Apify scraper is gone, so nothing writes or reads this cache any more.
    # It holds scraped Instagram data, which is exactly what we no longer want
    # to be storing — but dropping a collection is not something startup should
    # decide on its own, so this only says so.
    try:
        if "instagram_stats_cache" in await db.list_collection_names():
            stale = await db.instagram_stats_cache.estimated_document_count()
            logger.warning(
                "instagram_stats_cache still holds ~%d scraped profile(s). Nothing "
                "reads it now the Apify integration is removed — drop it with: "
                "db.instagram_stats_cache.drop()",
                stale,
            )
    except Exception as exc:  # a diagnostic must never block startup
        logger.debug("could not inspect instagram_stats_cache: %s", exc)

    admin_email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    admin_name = os.environ.get("ADMIN_NAME", "Admin")
    if not admin_email or not admin_password:
        logger.warning("ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping admin seed")
        return

    now = datetime.now(timezone.utc)
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one(
            {
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": admin_name,
                "role": "admin",
                "phone": None,
                "status": "active",
                "terms_accepted_at": now,
                "terms_version": TERMS_VERSION,
                "created_at": now,
            }
        )
        logger.info("Seeded admin user %s", admin_email)
    else:
        # Create-only. Rewriting the password hash on every boot meant a rotated
        # password silently reverted to whatever was in the environment, and an
        # environment leak was a permanent backdoor rather than a one-off.
        update = {"role": "admin", "status": existing.get("status") or "active"}
        await db.users.update_one({"email": admin_email}, {"$set": update})
        if not verify_password(admin_password, existing.get("password_hash") or ""):
            logger.warning(
                "ADMIN_PASSWORD does not match the stored hash for %s. The stored "
                "password is authoritative; set ADMIN_PASSWORD_RESET=true for one "
                "boot to overwrite it.",
                admin_email,
            )
            if os.environ.get("ADMIN_PASSWORD_RESET", "").strip().lower() in (
                "1",
                "true",
                "yes",
            ):
                await db.users.update_one(
                    {"email": admin_email},
                    {"$set": {"password_hash": hash_password(admin_password)}},
                )
                logger.warning("Admin password reset from environment for %s", admin_email)

    # Backfill status field on any legacy users that were created before the
    # schema was extended so downstream code can rely on the field existing.
    await db.users.update_many(
        {"status": {"$exists": False}}, {"$set": {"status": "pending"}}
    )

    # Seed a handful of demo brand accounts + campaigns so the Campaigns page
    # is not empty on a fresh install. Fully idempotent — keyed by email/title.
    await _seed_demo_campaigns()
    await _seed_demo_creators()


# ---------------------------------------------------------------------------
# Demo data seeding
# ---------------------------------------------------------------------------

_DEMO_BRANDS = [
    {
        "email": "hello+demo@bluetokai.in",
        "name": "Blue Tokai Coffee",
        "business_name": "Blue Tokai Coffee Roasters",
        "category": "fnb",
        "areas": ["Koramangala", "Indiranagar"],
    },
    {
        "email": "hello+demo@toit.in",
        "name": "Toit Brewpub",
        "business_name": "Toit Brewpub",
        "category": "fnb",
        "areas": ["Indiranagar"],
    },
    {
        "email": "hello+demo@thepermitroom.in",
        "name": "The Permit Room",
        "business_name": "The Permit Room",
        "category": "hospitality",
        "areas": ["MG Road"],
    },
    {
        "email": "hello+demo@farmlore.in",
        "name": "Farmlore",
        "business_name": "Farmlore Kitchen",
        "category": "fnb",
        "areas": ["Whitefield"],
    },
]


def _future(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _demo_campaign_specs() -> list[dict]:
    return [
        {
            "brand_email": "hello+demo@bluetokai.in",
            "title": "Weekend brunch reel — new menu launch",
            "brief": (
                "We're launching our new weekend brunch menu at the Koramangala roastery. "
                "Looking for a food-first creator to shoot a single high-quality Instagram reel "
                "capturing 3 signature dishes and the roastery ambience. Free brunch for two, "
                "plus paid fee. Deliver within 10 days of the shoot."
            ),
            "deliverables": "1 Instagram reel (30-45s) + 3 stories, tag @bluetokaicoffee",
            "budget_per_creator": 8000,
            "category": "fnb",
            "area": "Koramangala",
            "creators_needed": 2,
            "start_date": _future(2),
            "end_date": _future(30),
            "status": "open",
        },
        {
            "brand_email": "hello+demo@toit.in",
            "title": "Signature cocktail launch — 5 creators",
            "brief": (
                "Toit is launching a limited-run signature cocktail series this month. "
                "We want creators known for craft F&B storytelling to visit the pub, sample the "
                "flight of 4 cocktails and shoot content around it. Slot is fixed (weekday evening)."
            ),
            "deliverables": "1 reel + 3 stories + 1 static feed post",
            "budget_per_creator": 12000,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": 5,
            "start_date": _future(5),
            "end_date": _future(20),
            "status": "open",
        },
        {
            "brand_email": "hello+demo@thepermitroom.in",
            "title": "Grand opening night — MG Road",
            "brief": (
                "The Permit Room is opening its first MG Road outpost. We're inviting a curated "
                "cohort of Bengaluru lifestyle & F&B creators for the opening night to shoot cover-"
                "worthy content of the space, the menu and the vibe. Black-tie dress code."
            ),
            "deliverables": "1 reel + 5 stories that night; 1 recap post within 5 days",
            "budget_per_creator": 15000,
            "category": "hospitality",
            "area": "MG Road",
            "creators_needed": 8,
            "start_date": _future(7),
            "end_date": _future(21),
            "status": "upcoming",
        },
        {
            "brand_email": "hello+demo@farmlore.in",
            "title": "Chef's tasting menu — solo feature",
            "brief": (
                "Farmlore's 8-course seasonal tasting menu is now live. We're looking for a single "
                "creator with a fine-dining audience for a full editorial-style coverage — writeup, "
                "reel, and stills. Complimentary tasting for two included."
            ),
            "deliverables": "1 long-form reel (60-90s) + carousel post (5 stills) + writeup",
            "budget_per_creator": 25000,
            "category": "fnb",
            "area": "Whitefield",
            "creators_needed": 1,
            "start_date": _future(1),
            "end_date": _future(45),
            "status": "open",
        },
        {
            "brand_email": "hello+demo@bluetokai.in",
            "title": "Home baking workshop coverage",
            "brief": (
                "Blue Tokai is hosting a Saturday home-baking workshop at the Indiranagar café. "
                "Looking for a creator who can attend, shoot behind-the-scenes and produce a "
                "warm, personal recap for their audience."
            ),
            "deliverables": "1 reel + 4 stories same-day, 1 carousel post within 3 days",
            "budget_per_creator": 6000,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": 2,
            "start_date": _future(10),
            "end_date": _future(25),
            "status": "upcoming",
        },
        # A draft campaign — intentionally NOT visible on the creator feed.
        {
            "brand_email": "hello+demo@toit.in",
            "title": "[Internal draft — should not appear]",
            "brief": "Internal draft used to verify status filtering.",
            "deliverables": "n/a",
            "budget_per_creator": 5000,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": 1,
            "start_date": None,
            "end_date": None,
            "status": "draft",
        },
        # A closed campaign — also filtered out.
        {
            "brand_email": "hello+demo@farmlore.in",
            "title": "[Closed — should not appear]",
            "brief": "Closed campaign used to verify status filtering.",
            "deliverables": "n/a",
            "budget_per_creator": 5000,
            "category": "fnb",
            "area": "Whitefield",
            "creators_needed": 1,
            "start_date": _future(-30),
            "end_date": _future(-5),
            "status": "closed",
        },
    ]


async def _seed_demo_campaigns() -> None:
    now = datetime.now(timezone.utc)
    # 1. Ensure demo brand users + brand_profiles exist (idempotent by email).
    #    These exist to populate the feed, not to be signed into — they carry no
    #    password, so a shared demo credential can't leak into a real deployment.
    brand_id_by_email: dict[str, ObjectId] = {}
    for b in _DEMO_BRANDS:
        existing = await db.users.find_one({"email": b["email"]})
        if existing is None:
            result = await db.users.insert_one(
                {
                    "email": b["email"],
                    "password_hash": None,
                    "name": b["name"],
                    "role": "brand",
                    "phone": None,
                    "status": "active",
                    "created_at": now,
                }
            )
            uid = result.inserted_id
        else:
            uid = existing["_id"]
        brand_id_by_email[b["email"]] = uid

        # Upsert brand profile so business_name/category/areas stay fresh.
        await db.brand_profiles.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "business_name": b["business_name"],
                    "category": b["category"],
                    "areas": b["areas"],
                    "verified": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"user_id": uid, "created_at": now},
            },
            upsert=True,
        )

    # 2. Insert campaigns (idempotent by (brand_id, title)).
    for spec in _demo_campaign_specs():
        brand_id = brand_id_by_email.get(spec["brand_email"])
        if brand_id is None:
            continue
        exists = await db.campaigns.find_one({"brand_id": brand_id, "title": spec["title"]})
        if exists:
            continue
        await db.campaigns.insert_one(
            {
                "brand_id": brand_id,
                "title": spec["title"],
                "brief": spec["brief"],
                "deliverables": spec["deliverables"],
                "budget_per_creator": spec["budget_per_creator"],
                # The demo feed is all paid work, which is also the only kind a
                # brand can post — a seeded barter brief would show creators an
                # arrangement the product does not offer self-serve.
                "compensation_type": spec.get(
                    "compensation_type", DEFAULT_COMPENSATION_TYPE
                ),
                "category": spec["category"],
                "area": spec["area"],
                "creators_needed": spec["creators_needed"],
                "start_date": spec["start_date"],
                "end_date": spec["end_date"],
                "status": spec["status"],
                "created_at": now,
                "updated_at": now,
            }
        )
    logger.info("Demo campaigns ensured (%d specs)", len(_demo_campaign_specs()))


@app.on_event("shutdown")
async def _shutdown():
    for name in ("nudge_task", "instagram_task"):
        task = getattr(app.state, name, None)
        if task:
            task.cancel()
    client.close()


# ---------------------------------------------------------------------------
# Demo creators — populate the brand-side directory on a fresh install
# ---------------------------------------------------------------------------

_DEMO_CREATORS = [
    {
        "email": "priya.rao+demo@wearemonk.in",
        "phone": "+919000000101",
        "name": "Priya Rao",
        "instagram_handle": "priyaeats",
        "instagram_profile_url": "https://instagram.com/priyaeats",
        "city": "Bengaluru",
        "niches": ["cafe", "brunch", "coffee"],
        "follower_count": 84500,
        "base_rate": 12000,
        "pan": "AAAPR1001A",
    },
    {
        "email": "arjun.mehta+demo@wearemonk.in",
        "phone": "+919000000102",
        "name": "Arjun Mehta",
        "instagram_handle": "arjuneats",
        "instagram_profile_url": "https://instagram.com/arjuneats",
        "city": "Mumbai",
        "niches": ["fine dining", "cocktails", "lifestyle"],
        "follower_count": 132000,
        "base_rate": 24000,
        "pan": "AAAPM1002B",
    },
    {
        "email": "ananya.gupta+demo@wearemonk.in",
        "phone": "+919000000103",
        "name": "Ananya Gupta",
        "instagram_handle": "styledbyananya",
        "instagram_profile_url": "https://instagram.com/styledbyananya",
        "city": "Delhi NCR",
        "niches": ["fashion", "beauty", "lifestyle"],
        "follower_count": 210000,
        "base_rate": 38000,
        "pan": "AAAPG1003C",
    },
    {
        "email": "rohan.kapoor+demo@wearemonk.in",
        "phone": "+919000000104",
        "name": "Rohan Kapoor",
        "instagram_handle": "roamswithrohan",
        "instagram_profile_url": "https://instagram.com/roamswithrohan",
        "city": "Goa",
        "niches": ["travel", "hotels", "staycations"],
        "follower_count": 96500,
        "base_rate": 18000,
        "pan": "AAAPK1004D",
    },
    {
        "email": "meera.iyer+demo@wearemonk.in",
        "phone": "+919000000105",
        "name": "Meera Iyer",
        "instagram_handle": "meerainmadras",
        "instagram_profile_url": "https://instagram.com/meerainmadras",
        "city": "Chennai",
        "niches": ["home decor", "retail", "lifestyle"],
        "follower_count": 47000,
        "base_rate": 8500,
        "pan": "AAAPI1005E",
    },
    {
        "email": "kabir.singh+demo@wearemonk.in",
        "phone": "+919000000106",
        "name": "Kabir Singh",
        "instagram_handle": "kabirbuilds",
        "instagram_profile_url": "https://instagram.com/kabirbuilds",
        "city": "Hyderabad",
        "niches": ["real estate", "lifestyle"],
        "follower_count": 61000,
        "base_rate": 15000,
        "pan": "AAAPS1006F",
    },
    {
        "email": "sana.khan+demo@wearemonk.in",
        "phone": "+919000000107",
        "name": "Sana Khan",
        "instagram_handle": "sanaskitchen",
        "instagram_profile_url": "https://instagram.com/sanaskitchen",
        "city": "Pune",
        "niches": ["home chef", "bakery", "brunch"],
        "follower_count": 38000,
        "base_rate": 6500,
        "pan": "AAAPK1007G",
    },
    {
        "email": "vivek.rao+demo@wearemonk.in",
        "phone": "+919000000108",
        "name": "Vivek Rao",
        "instagram_handle": "vivekfits",
        "instagram_profile_url": "https://instagram.com/vivekfits",
        "city": "Bengaluru",
        "niches": ["fitness", "wellness"],
        "follower_count": 72000,
        "base_rate": 11000,
        "pan": "AAAPV1008H",
    },
]


async def _seed_demo_creators() -> None:
    """Idempotently seed a small directory of verified demo creators."""
    now = datetime.now(timezone.utc)
    for c in _DEMO_CREATORS:
        existing = await db.users.find_one({"email": c["email"]})
        if existing is None:
            result = await db.users.insert_one(
                {
                    "email": c["email"],
                    "password_hash": None,
                    "name": c["name"],
                    "role": "creator",
                    "phone": c["phone"],
                    "status": "active",
                    "created_at": now,
                }
            )
            uid = result.inserted_id
        else:
            uid = existing["_id"]

        await db.creator_profiles.update_one(
            {"user_id": uid},
            {
                "$set": {
                    "name": c["name"],
                    "instagram_handle": c["instagram_handle"],
                    "instagram_profile_url": c["instagram_profile_url"],
                    "email": c["email"],
                    "city": c["city"],
                    "niches": c["niches"],
                    "follower_count": c["follower_count"],
                    "base_rate": c["base_rate"],
                    "verification_status": "verified",
                    "pending_review": False,
                    # Demo creators carry payout details so the full pipeline —
                    # including the payment step's payout check — is walkable
                    # on a fresh install.
                    "payout_upi": f"{c['instagram_handle']}@okhdfcbank",
                    "payout_account_name": c["name"],
                    "pan": c["pan"],
                    "updated_at": now,
                },
                "$setOnInsert": {"user_id": uid, "created_at": now},
            },
            upsert=True,
        )
    logger.info("Demo creators ensured (%d specs)", len(_DEMO_CREATORS))
