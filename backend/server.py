from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, Annotated

import bcrypt
import httpx
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, EmailStr, Field, BeforeValidator, ConfigDict

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("wearecreators")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MIN = 60 * 24  # 1 day
REFRESH_TOKEN_DAYS = 7

Role = Literal["creator", "brand", "admin"]


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
    return os.environ["JWT_SECRET"]


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


class OtpRequestInput(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    purpose: OtpPurpose = "login"
    # required for signup only
    name: Optional[str] = Field(default=None, max_length=80)
    role: Optional[Literal["creator", "brand"]] = None
    accept_terms: bool = False


class OtpVerifyInput(BaseModel):
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


class CreatorProfileUpdate(BaseModel):
    """Payload for creator onboarding / profile edits."""

    name: str = Field(min_length=1, max_length=120)
    instagram_handle: str = Field(min_length=1, max_length=60)
    instagram_profile_url: str = Field(min_length=1, max_length=300)
    email: EmailStr
    city: Optional[str] = Field(default=None, max_length=80)
    address: str = Field(min_length=1, max_length=500)
    niches: list[str] = Field(default_factory=list, max_length=25)
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


class BrandProfileUpdate(BaseModel):
    """Payload for brand onboarding / profile edits."""

    business_name: str = Field(min_length=1, max_length=140)
    category: CATEGORY_LITERAL
    areas: list[str] = Field(default_factory=list, max_length=30)


class PostCampaignPayload(BaseModel):
    """Payload for a brand posting a new campaign."""

    title: str = Field(min_length=1, max_length=140)
    brief: str = Field(min_length=1, max_length=5000)
    deliverables: str = Field(min_length=1, max_length=1000)
    budget_per_creator: float = Field(ge=0)
    category: CATEGORY_LITERAL
    area: str = Field(min_length=1, max_length=80)
    creators_needed: int = Field(ge=1, le=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Literal["draft", "open"] = "open"


class UpdateCampaignPayload(BaseModel):
    """Payload for editing an existing campaign. Every field is optional so a
    brand can correct one thing without resubmitting the whole brief."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=140)
    brief: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    deliverables: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    budget_per_creator: Optional[float] = Field(default=None, ge=0)
    category: Optional[CATEGORY_LITERAL] = None
    area: Optional[str] = Field(default=None, min_length=1, max_length=80)
    creators_needed: Optional[int] = Field(default=None, ge=1, le=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class DecisionPayload(BaseModel):
    """Payload for a decision that ends or redirects a collaboration."""

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


class MarkPaidPayload(BaseModel):
    """Payload recording an actual payout that happened outside the platform."""

    payment_reference: str = Field(min_length=1, max_length=140)


# --- Domain models (schema-only; used for validation & docs) ---------------

UserStatus = Literal["pending", "active", "suspended"]
VettingStatus = Literal["pending", "vetted", "rejected"]
CampaignStatus = Literal[
    "draft", "upcoming", "open", "in_progress", "completed", "closed"
]
CollabState = Literal[
    "applied",
    "vetted",
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
PaymentState = Literal["pending", "paid"]
BrandInvoiceState = Literal["pending", "sent", "settled"]

# The happy path, in order. `declined` / `cancelled` are exits, not steps, so
# they deliberately do not appear here.
COLLAB_STATE_ORDER = [
    "applied",
    "vetted",
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

# A campaign in one of these states is visible on the creator feed.
LIVE_CAMPAIGN_STATUSES = ("open", "upcoming")


class CreatorProfile(BaseModel):
    """Collection: creator_profiles (1:1 with users where role='creator')."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    name: str
    instagram_handle: Optional[str] = None
    instagram_profile_url: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    address: Optional[str] = None
    niches: list[str] = Field(default_factory=list)
    base_rate: Optional[float] = None
    follower_count: Optional[int] = None
    vetting_status: VettingStatus = "pending"
    # True when an already-vetted creator edits something material. They stay
    # vetted (and visible to brands) but surface in a separate admin queue.
    pending_review: bool = False
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
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
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


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


async def audit(
    actor: dict,
    action: str,
    subject_type: str,
    subject_id,
    *,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    note: Optional[str] = None,
) -> None:
    """Record who changed what. Every state-changing admin or brand action goes
    through here — without it a payout is a click with no author."""
    try:
        await db.audit_log.insert_one(
            {
                "actor_id": ObjectId(actor["_id"]) if actor.get("_id") else None,
                "actor_role": actor.get("role"),
                "actor_name": actor.get("name"),
                "action": action,
                "subject_type": subject_type,
                "subject_id": subject_id if isinstance(subject_id, ObjectId) else str(subject_id),
                "before": before,
                "after": after,
                "note": note,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:  # never let logging break the operation
        logger.error("audit write failed for %s/%s: %s", action, subject_id, exc)


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
    "creator_vetted": "You're vetted — briefs are open to you",
    "creator_rejected": "We couldn't approve your profile yet",
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

    now = datetime.now(timezone.utc)
    delivered = False
    try:
        user = await db.users.find_one({"_id": oid})
        template = os.environ.get(f"AISENSY_TEMPLATE_{event.upper()}", "").strip()
        if user and user.get("phone") and template:
            delivered = await _send_aisensy_template(
                user["phone"], user.get("name") or "there", template, params or [body]
            )
        await db.notifications.insert_one(
            {
                "user_id": oid,
                "event": event,
                "title": title,
                "body": body,
                "link": link,
                "read": False,
                "delivered_on_whatsapp": delivered,
                "created_at": now,
            }
        )
    except Exception as exc:
        logger.error("notify failed for %s/%s: %s", event, user_id, exc)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


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
                "vetting_status": "pending",
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

    if user.get("role") != "admin":
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
    return {
        "id": user["_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "phone": user.get("phone"),
        "status": user.get("status"),
        "created_at": user["created_at"].isoformat() if isinstance(user.get("created_at"), datetime) else user.get("created_at"),
    }


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
            raise HTTPException(
                status_code=503,
                detail="WhatsApp sign-in is unavailable right now. Please try again shortly.",
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
        raise HTTPException(
            status_code=503,
            detail="Could not send WhatsApp code right now. Please try again.",
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
        raise HTTPException(
            status_code=503,
            detail="WhatsApp delivery is temporarily unavailable. Please resend.",
        )
    raise HTTPException(
        status_code=502,
        detail="WhatsApp delivery failed. Please resend or try a different number.",
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
            raise HTTPException(
                status_code=404,
                detail="No account found for this number. Please sign up first.",
            )
        if existing_user.get("role") == "admin":
            raise HTTPException(
                status_code=403,
                detail="Admins must sign in with email and password.",
            )
    else:  # signup
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="This number is already registered. Please log in.",
            )
        if not payload.name or not payload.role:
            raise HTTPException(
                status_code=400,
                detail="Name and role are required to sign up.",
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
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {retry_after}s before requesting another code.",
            )

    hour_ago = now - timedelta(hours=1)
    count_recent = await db.otp_codes.count_documents(
        {"phone": phone, "created_at": {"$gte": hour_ago}}
    )
    if count_recent >= hourly_limit:
        raise HTTPException(
            status_code=429,
            detail="Too many code requests for this number. Try again later.",
        )

    # Generate + send -----------------------------------------------------
    code = f"{_secrets.randbelow(1_000_000):06d}"
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
        raise HTTPException(status_code=400, detail="No active code. Please request a new one.")

    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Code expired. Please resend.")

    max_attempts = _otp_max_attempts()
    if record["attempts"] >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail="Too many wrong attempts. Please request a new code.",
        )

    if not _verify_otp_code(phone, payload.code, record["code_hash"]):
        await db.otp_codes.update_one({"_id": record["_id"]}, {"$inc": {"attempts": 1}})
        remaining = max_attempts - (record["attempts"] + 1)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Too many wrong attempts. Please request a new code.",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect code. {remaining} attempt(s) remaining.",
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
            raise HTTPException(status_code=404, detail="Account not found. Please sign up.")
        if user.get("role") == "admin":
            raise HTTPException(
                status_code=403,
                detail="Admins must sign in with email and password.",
            )
    else:  # signup
        existing_user = await db.users.find_one({"phone": phone})
        if existing_user:
            raise HTTPException(status_code=409, detail="This number is already registered.")

        signup_name = (record.get("name") or payload.name or "").strip()
        signup_role = record.get("role") or payload.role
        if not signup_name or signup_role not in ("creator", "brand"):
            raise HTTPException(status_code=400, detail="Missing signup details.")
        if not (payload.accept_terms or record.get("accept_terms")):
            raise HTTPException(
                status_code=400,
                detail="Please accept the terms and privacy policy to create an account.",
            )

        user_doc = {
            "email": None,
            "password_hash": None,
            "name": signup_name,
            "role": signup_role,
            "phone": phone,
            "status": "pending",
            "terms_accepted_at": now,
            "terms_version": TERMS_VERSION,
            "created_at": now,
        }
        result = await db.users.insert_one(user_doc)
        user_id = result.inserted_id

        if signup_role == "creator":
            await db.creator_profiles.insert_one(
                {
                    "user_id": user_id,
                    "name": signup_name,
                    "instagram_handle": None,
                    "instagram_profile_url": None,
                    "email": None,
                    "address": None,
                    "niches": [],
                    "base_rate": None,
                    "follower_count": None,
                    "vetting_status": "pending",
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
        "email": doc.get("email"),
        "city": doc.get("city"),
        "address": doc.get("address"),
        "niches": doc.get("niches") or [],
        "base_rate": doc.get("base_rate"),
        "follower_count": doc.get("follower_count"),
        "vetting_status": doc.get("vetting_status", "pending"),
        "pending_review": bool(doc.get("pending_review", False)),
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


def _clean_payout_fields(payload) -> dict:
    """Normalise and validate the payout identity fields. Each is optional, but
    anything supplied has to be well-formed — a typo'd UPI ID is a lost payout."""
    out: dict = {}

    upi = (payload.payout_upi or "").strip()
    if upi:
        if not UPI_RE.match(upi):
            raise HTTPException(
                status_code=422,
                detail="UPI ID should look like yourname@bank.",
            )
        out["payout_upi"] = upi
    else:
        out["payout_upi"] = None

    out["payout_account_name"] = (payload.payout_account_name or "").strip() or None

    pan = (payload.pan or "").strip().upper()
    if pan:
        if not PAN_RE.match(pan):
            raise HTTPException(
                status_code=422,
                detail="PAN should be 10 characters, like ABCDE1234F.",
            )
        out["pan"] = pan
    else:
        out["pan"] = None

    gstin = (payload.gstin or "").strip().upper()
    if gstin:
        if not GSTIN_RE.match(gstin):
            raise HTTPException(
                status_code=422,
                detail="GSTIN should be 15 characters, like 29ABCDE1234F1Z5.",
            )
        out["gstin"] = gstin
    else:
        out["gstin"] = None

    return out


@creator_router.get("/profile")
async def get_creator_profile(user: dict = Depends(require_roles("creator"))):
    doc = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not doc:
        # Shouldn't happen (stub created at signup), but handle gracefully.
        raise HTTPException(status_code=404, detail="Creator profile not found")
    return _serialize_creator_profile(doc)


@creator_router.put("/profile")
async def update_creator_profile(
    payload: CreatorProfileUpdate,
    user: dict = Depends(require_roles("creator")),
):
    # Normalise Instagram handle (strip leading @, lowercase, no whitespace).
    handle = payload.instagram_handle.strip().lstrip("@").lower()
    if not handle:
        raise HTTPException(status_code=422, detail="Instagram handle is required")

    existing = await db.creator_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not existing:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    now = datetime.now(timezone.utc)
    update = {
        "name": payload.name.strip(),
        "instagram_handle": handle,
        "instagram_profile_url": payload.instagram_profile_url.strip(),
        "email": payload.email.lower().strip(),
        "city": (payload.city or "").strip() or None,
        "address": payload.address.strip(),
        "niches": [n.strip().lower() for n in payload.niches if n and n.strip()],
        "base_rate": payload.base_rate,
        "follower_count": payload.follower_count,
        "updated_at": now,
        **_clean_payout_fields(payload),
    }

    # A vetted creator who fixes a typo should not fall out of the directory.
    # Only a material change (who they are, or where their audience is) needs a
    # second look, and even then they stay live while we look.
    material_fields = ("name", "instagram_handle", "city")
    changed_material = any(
        (existing.get(f) or None) != (update.get(f) or None) for f in material_fields
    )
    if existing.get("vetting_status") == "vetted":
        update["pending_review"] = changed_material or bool(
            existing.get("pending_review")
        )
    else:
        # Still pending, or previously rejected — this is a (re)submission.
        update["vetting_status"] = "pending"
        update["pending_review"] = False

    result = await db.creator_profiles.find_one_and_update(
        {"user_id": ObjectId(user["_id"])},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    # Also mirror the display name onto the user document so it stays in sync.
    if update["name"] != user.get("name"):
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
) -> dict:
    state = collab.get("state", "applied")
    return {
        "id": str(collab["_id"]),
        "campaign_id": str(collab["campaign_id"]),
        "campaign_title": (campaign or {}).get("title"),
        "brand_name": brand_name,
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
        "vetting_status": (profile or {}).get("vetting_status", "pending"),
        "pending_review": bool((profile or {}).get("pending_review", False)),
        "niches": (profile or {}).get("niches") or [],
        "follower_count": (profile or {}).get("follower_count"),
        "base_rate": (profile or {}).get("base_rate"),
        "payout_ready": payout_ready(profile or {}),
    }

    # Attach cached Instagram stats if we have any for this handle.
    ig_handle = _extract_ig_handle((profile or {}).get("instagram_handle") or "")
    profile_summary["instagram_stats"] = (
        await _load_cached_ig_stats(ig_handle) if ig_handle else None
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
        return _serialize_collab_row(collab, camp, brand_name)

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

    return {
        "profile": profile_summary,
        "applications": applications,
        "upcoming": upcoming,
        "payments": payments,
        "in_payment_collaborations": in_payment_collabs,
        "totals": {
            "applications": len(applications),
            "upcoming": len(upcoming),
            "payments": len(payments) + len(in_payment_collabs),
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

    # Tell the brand there's something to look at.
    campaign = await db.campaigns.find_one({"_id": collab["campaign_id"]})
    if campaign:
        await notify(
            campaign["brand_id"],
            "content_submitted",
            title="Content submitted for review",
            body=(
                f"{user.get('name') or 'A creator'} submitted content for "
                f"\"{campaign.get('title')}\"."
            ),
            link=f"/brand/campaigns/{campaign['_id']}/applicants",
        )

    return {
        "id": collab_id,
        "state": updated["state"],
        "content_url": updated.get("content_url"),
        "content_urls": updated.get("content_urls") or [],
    }





# ---------------------------------------------------------------------------
# Instagram stats via Apify (server-only)
# ---------------------------------------------------------------------------

APIFY_ACTOR = "apify~instagram-profile-scraper"
INSTAGRAM_STATS_TTL_SECONDS = 6 * 3600
_HANDLE_URL_RE = re.compile(
    r"(?:instagram\.com/)?@?([A-Za-z0-9._]{1,60})/?", re.IGNORECASE
)


def _extract_ig_handle(raw: str) -> Optional[str]:
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


def _apify_token() -> Optional[str]:
    tok = os.environ.get("APIFY_API_TOKEN", "").strip()
    return tok or None


async def _fetch_instagram_from_apify(handle: str) -> dict:
    """Call the Apify Instagram Profile Scraper actor synchronously."""
    token = _apify_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Instagram stats aren't configured on this server yet.",
        )
    url = (
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR}"
        f"/run-sync-get-dataset-items?token={token}&timeout=60"
    )
    payload = {"usernames": [handle]}
    try:
        async with httpx.AsyncClient(timeout=75.0) as client:
            resp = await client.post(url, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Instagram fetch timed out. Please try again in a moment.",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502, detail=f"Could not reach Instagram provider: {e}"
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=500, detail="Invalid Instagram provider token."
        )
    if resp.status_code == 402:
        raise HTTPException(
            status_code=402,
            detail="Instagram stats provider is out of credits. Please recharge.",
        )
    if resp.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="Instagram stats provider rate limit hit. Try again shortly.",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Instagram provider error ({resp.status_code}).",
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid response from Instagram provider.")

    if not isinstance(data, list) or not data:
        raise HTTPException(
            status_code=404,
            detail="No public Instagram profile found for that handle.",
        )

    item = data[0]
    # Apify sometimes returns an error item — flag it.
    if isinstance(item, dict) and item.get("error"):
        raise HTTPException(status_code=404, detail="Instagram profile not found or is private.")

    return {
        "handle": (item.get("username") or handle).lower(),
        "full_name": item.get("fullName") or None,
        "biography": item.get("biography") or None,
        "profile_pic_url": item.get("profilePicUrlHD") or item.get("profilePicUrl"),
        "followers_count": item.get("followersCount"),
        "following_count": item.get("followsCount"),
        "posts_count": item.get("postsCount"),
        "verified": bool(item.get("verified", False)),
        "is_private": bool(item.get("private", False)),
        "business_category": item.get("businessCategoryName"),
        "external_url": item.get("externalUrl"),
    }


async def _load_cached_ig_stats(handle: str) -> Optional[dict]:
    doc = await db.instagram_stats_cache.find_one({"handle": handle})
    if not doc:
        return None
    updated = doc.get("updated_at")
    age = None
    if isinstance(updated, datetime):
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated).total_seconds()
        doc["updated_at"] = updated.isoformat()
    doc["_age_seconds"] = age
    doc.pop("_id", None)
    return doc


async def _save_ig_stats(handle: str, stats: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {**stats, "handle": handle, "updated_at": now}
    await db.instagram_stats_cache.update_one(
        {"handle": handle}, {"$set": doc}, upsert=True
    )
    doc["updated_at"] = now.isoformat()
    doc["_age_seconds"] = 0
    return doc


async def _get_or_refresh_ig(handle: str, force: bool = False) -> dict:
    if not force:
        cached = await _load_cached_ig_stats(handle)
        if cached and (cached.get("_age_seconds") or 0) < INSTAGRAM_STATS_TTL_SECONDS:
            cached["from_cache"] = True
            return cached
    stats = await _fetch_instagram_from_apify(handle)
    saved = await _save_ig_stats(handle, stats)
    saved["from_cache"] = False
    return saved


@creator_router.get("/instagram-stats")
async def get_instagram_stats(
    refresh: bool = False,
    user: dict = Depends(require_roles("creator")),
):
    profile = await db.creator_profiles.find_one(
        {"user_id": ObjectId(user["_id"])}
    )
    raw = (profile or {}).get("instagram_handle") or (profile or {}).get(
        "instagram_profile_url"
    )
    handle = _extract_ig_handle(raw or "")
    if not handle:
        raise HTTPException(
            status_code=400,
            detail="Add your Instagram handle on your profile first.",
        )
    return await _get_or_refresh_ig(handle, force=refresh)




api_router.include_router(creator_router)


# --- Brand router ----------------------------------------------------------

brand_router = APIRouter(prefix="/brand", tags=["brand"])


def _serialize_brand_profile(doc: dict) -> dict:
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "business_name": doc.get("business_name"),
        "category": doc.get("category"),
        "areas": doc.get("areas") or [],
        "verified": bool(doc.get("verified", False)),
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
        "brief": doc.get("brief"),
        "deliverables": doc.get("deliverables"),
        "budget_per_creator": doc.get("budget_per_creator"),
        "category": doc.get("category"),
        "area": doc.get("area"),
        "creators_needed": needed,
        "start_date": _iso(doc.get("start_date")),
        "end_date": _iso(doc.get("end_date")),
        "status": status,
        "created_at": _iso(doc.get("created_at")),
        "applicant_count": applicant_count,
        "filled_slots": filled,
        "spots_left": max(0, needed - filled),
        # How many applicants are sitting with the brand right now. This is the
        # number that should make somebody act.
        "awaiting_decision": awaiting,
        "can_edit": status in ("draft", "upcoming", "open"),
        "can_publish": status == "draft",
        "can_close": status in ("draft", "upcoming", "open", "in_progress"),
        "can_delete": status == "draft" and applicant_count == 0,
    }


async def _awaiting_brand_counts(campaign_ids: list) -> dict:
    """Applicants the WeAre team has vetted and handed to the brand to decide on."""
    if not campaign_ids:
        return {}
    unique = list({cid for cid in campaign_ids})
    rows = await db.collaborations.aggregate(
        [
            {"$match": {"campaign_id": {"$in": unique}, "state": "vetted"}},
            {"$group": {"_id": "$campaign_id", "n": {"$sum": 1}}},
        ]
    ).to_list(length=len(unique))
    return {r["_id"]: r["n"] for r in rows}


async def _own_campaign_or_404(campaign_id: str, user: dict) -> dict:
    """Load a campaign, asserting the caller's brand owns it."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found")
    doc = await db.campaigns.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if user.get("role") != "admin" and doc.get("brand_id") != ObjectId(user["_id"]):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return doc


@brand_router.get("/profile")
async def get_brand_profile(user: dict = Depends(require_roles("brand"))):
    doc = await db.brand_profiles.find_one({"user_id": ObjectId(user["_id"])})
    if not doc:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return _serialize_brand_profile(doc)


@brand_router.put("/profile")
async def update_brand_profile(
    payload: BrandProfileUpdate,
    user: dict = Depends(require_roles("brand")),
):
    now = datetime.now(timezone.utc)
    business_name = payload.business_name.strip()
    update = {
        "business_name": business_name,
        "category": payload.category,
        "areas": [a.strip() for a in payload.areas if a and a.strip()],
        "updated_at": now,
    }
    result = await db.brand_profiles.find_one_and_update(
        {"user_id": ObjectId(user["_id"])},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    # Keep the display name on the user doc in sync with business_name.
    if business_name and business_name != user.get("name"):
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])}, {"$set": {"name": business_name}}
        )
    return _serialize_brand_profile(result)


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
async def list_brand_campaigns(user: dict = Depends(require_roles("brand"))):
    await _expire_stale_campaigns()
    brand_oid = ObjectId(user["_id"])
    docs = (
        await db.campaigns.find({"brand_id": brand_oid})
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
    user: dict = Depends(require_roles("brand")),
):
    if (
        payload.start_date
        and payload.end_date
        and payload.end_date < payload.start_date
    ):
        raise HTTPException(
            status_code=422, detail="End date cannot be before start date"
        )

    now = datetime.now(timezone.utc)
    doc = {
        "brand_id": ObjectId(user["_id"]),
        "title": payload.title.strip(),
        "brief": payload.brief.strip(),
        "deliverables": payload.deliverables.strip(),
        "budget_per_creator": float(payload.budget_per_creator),
        "category": payload.category,
        "area": payload.area.strip(),
        "creators_needed": int(payload.creators_needed),
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "status": payload.status,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.campaigns.insert_one(doc)
    doc["_id"] = result.inserted_id
    await audit(user, "campaign.create", "campaign", result.inserted_id, after={"title": doc["title"], "status": doc["status"]})
    return _serialize_brand_campaign(doc, 0)


@brand_router.put("/campaigns/{campaign_id}")
async def update_brand_campaign(
    campaign_id: str,
    payload: UpdateCampaignPayload,
    user: dict = Depends(require_roles("brand")),
):
    """Correct a brief. Allowed while a campaign is a draft or still live —
    once it's in progress the terms creators applied under are fixed."""
    doc = await _own_campaign_or_404(campaign_id, user)
    if doc.get("status") not in ("draft", "upcoming", "open"):
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
    user: dict = Depends(require_roles("brand")),
):
    """Take a draft live. Without this a saved draft is a trap door."""
    doc = await _own_campaign_or_404(campaign_id, user)
    if doc.get("status") != "draft":
        raise HTTPException(status_code=409, detail="This campaign is already published.")

    missing = [
        field
        for field in ("title", "brief", "deliverables", "category", "area")
        if not doc.get(field)
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Finish the brief before publishing — missing: {', '.join(missing)}.",
        )

    now = datetime.now(timezone.utc)
    status = "upcoming" if doc.get("start_date") and doc["start_date"] > now else "open"
    await db.campaigns.update_one(
        {"_id": doc["_id"], "status": "draft"},
        {"$set": {"status": status, "updated_at": now}},
    )
    await audit(user, "campaign.publish", "campaign", doc["_id"], before={"status": "draft"}, after={"status": status})
    return {"id": campaign_id, "status": status}


@brand_router.post("/campaigns/{campaign_id}/close")
async def close_brand_campaign(
    campaign_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles("brand")),
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
    )

    # Anyone still waiting on a decision is owed one.
    stale = await db.collaborations.find(
        {"campaign_id": doc["_id"], "state": {"$in": ["applied", "vetted"]}}
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
    user: dict = Depends(require_roles("brand")),
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
    await audit(user, "campaign.delete", "campaign", doc["_id"], before={"title": doc.get("title")})
    return {"success": True, "id": campaign_id}


# --- Applicant board (brand-facing) ----------------------------------------

# What the brand sees, keyed by where the collaboration has got to.
_BRAND_VISIBLE_STATES = [s for s in COLLAB_STATE_ORDER] + ["declined", "cancelled"]


def _serialize_applicant(
    collab: dict, creator_user: dict, profile: dict, payment: Optional[dict]
) -> dict:
    """An applicant as the brand sees them.

    Contact details stay hidden until the brand has accepted and the
    collaboration is under way — the directory makes the same promise.
    """
    state = collab.get("state", "applied")
    revealed = state not in ("applied", "vetted", "declined", "cancelled")
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
        "can_accept": state == "vetted",
        "can_decline": state in ("applied", "vetted", "accepted"),
        "can_review_content": state == "content_submitted",
        "creator": {
            "id": str((creator_user or {}).get("_id")) if creator_user else None,
            "name": (profile or {}).get("name") or (creator_user or {}).get("name"),
            "instagram_handle": (profile or {}).get("instagram_handle"),
            "instagram_profile_url": (profile or {}).get("instagram_profile_url"),
            "city": (profile or {}).get("city"),
            "niches": (profile or {}).get("niches") or [],
            "follower_count": (profile or {}).get("follower_count"),
            "base_rate": (profile or {}).get("base_rate"),
            "vetting_status": (profile or {}).get("vetting_status"),
            # Only once they're working together.
            "email": (creator_user or {}).get("email") if revealed else None,
            "phone": (creator_user or {}).get("phone") if revealed else None,
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
    }


@brand_router.get("/campaigns/{campaign_id}/applicants")
async def list_campaign_applicants(
    campaign_id: str,
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Who applied, what they pitched, what they want to be paid.

    This is the decision the brand came here to make; before this endpoint the
    brand side of the product could only show a count.
    """
    campaign = await _own_campaign_or_404(campaign_id, user)
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
            "creators_needed": needed,
            "filled_slots": filled,
            "spots_left": max(0, needed - filled),
            "area": campaign.get("area"),
            "category": campaign.get("category"),
        },
        "applicants": rows,
        "totals": {
            "all": len(rows),
            "awaiting_you": sum(1 for r in rows if r["state"] == "vetted"),
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
    if user.get("role") != "admin" and campaign.get("brand_id") != ObjectId(user["_id"]):
        raise HTTPException(status_code=404, detail="Application not found")
    return collab, campaign


@brand_router.post("/collaborations/{collab_id}/accept")
async def brand_accept_applicant(
    collab_id: str,
    payload: BrandAcceptPayload,
    user: dict = Depends(require_roles("brand", "admin")),
):
    """The brand picks a creator. Records who agreed to what, and when."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    if collab.get("state") != "vetted":
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
        {"_id": collab["_id"], "state": "vetted"},  # precondition, not a blind write
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
        before={"state": "vetted"},
        after={"state": "accepted", "agreed_amount": amount},
        note=payload.note,
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
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Say no, out loud. Every applicant gets an answer instead of silence."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
    if collab.get("state") not in ("applied", "vetted", "accepted"):
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
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Sign off the work. This is the step the landing page promises and the
    thing that should release payment."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
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
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Send the work back with a note. The creator can resubmit without an admin
    unpicking the state by hand."""
    collab, campaign = await _brand_collab_or_404(collab_id, user)
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
async def get_brand_dashboard(user: dict = Depends(require_roles("brand"))):
    await _expire_stale_campaigns()
    brand_oid = ObjectId(user["_id"])
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
    """Public projection of a creator profile for the brand-side directory."""
    return {
        "id": str(profile["_id"]),
        "user_id": str(profile["user_id"]),
        "name": profile.get("name"),
        "instagram_handle": profile.get("instagram_handle"),
        "instagram_profile_url": profile.get("instagram_profile_url"),
        "city": profile.get("city"),
        "niches": profile.get("niches") or [],
        "follower_count": profile.get("follower_count"),
        "base_rate": profile.get("base_rate"),
        # Intentionally omitted: email, address, phone — brands see them
        # only after inviting/accepting a collaboration.
    }


@brand_router.get("/creators")
async def brand_directory(
    city: Optional[str] = None,
    niche: Optional[str] = None,
    min_followers: Optional[int] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,  # "newest" | "followers_desc" | "rate_asc"
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Browse vetted creators with optional city/niche/keyword filters."""
    query: dict = {"vetting_status": "vetted"}
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
    user: dict = Depends(require_roles("brand", "admin")),
):
    """Distinct filter options across vetted creators."""
    base = {"vetting_status": "vetted"}
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


# Steps only the brand may take. The admin console shows them as waiting on the
# brand rather than offering an Advance button that bypasses the buyer.
_BRAND_OWNED_TRANSITIONS = {"accepted", "content_approved"}


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
        "city": profile.get("city"),
        "address": profile.get("address"),
        "niches": profile.get("niches") or [],
        "base_rate": profile.get("base_rate"),
        "follower_count": profile.get("follower_count"),
        "vetting_status": profile.get("vetting_status", "pending"),
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


@admin_router.get("/creators/pending")
async def list_pending_creators(user: dict = Depends(require_roles("admin"))):
    """Creators actually waiting on us.

    A profile stub is created at signup, so filtering on `pending` alone fills
    the queue with people who never finished onboarding. Requiring an Instagram
    handle is what separates "waiting on us" from "never applied".
    """
    profiles = (
        await db.creator_profiles.find(
            {
                "vetting_status": "pending",
                "instagram_handle": {"$type": "string", "$ne": ""},
            }
        )
        .sort("created_at", -1)
        .to_list(length=500)
    )
    return await _hydrate_creator_rows(profiles)


@admin_router.get("/creators/changed")
async def list_changed_creators(user: dict = Depends(require_roles("admin"))):
    """Vetted creators who changed something material since we approved them.

    They stay live and visible to brands while they're in this queue — an edit
    is not a reason to pull someone out of the directory.
    """
    profiles = (
        await db.creator_profiles.find(
            {"vetting_status": "vetted", "pending_review": True}
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
                "vetting_status": "pending",
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


async def _set_creator_vetting(
    user_id: str, status: str, actor: dict, reason: Optional[str] = None
) -> dict:
    if status not in ("vetted", "rejected"):
        raise HTTPException(status_code=422, detail="Invalid vetting status")
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
                "vetting_status": status,
                # A decision clears the re-review flag either way.
                "pending_review": False,
                "vetting_reason": reason,
                "vetted_at": now,
                "updated_at": now,
            }
        },
        return_document=True,
    )

    # Also flip the user's active status when vetted.
    if status == "vetted":
        await db.users.update_one({"_id": oid}, {"$set": {"status": "active"}})

    await audit(
        actor,
        f"creator.{status}",
        "creator_profile",
        before["_id"],
        before={"vetting_status": before.get("vetting_status")},
        after={"vetting_status": status},
        note=reason,
    )

    if status == "vetted":
        await notify(
            oid,
            "creator_vetted",
            title="You're vetted",
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
    return await _set_creator_vetting(
        user_id, "vetted", user, (payload.reason if payload else None)
    )


@admin_router.post("/creators/{user_id}/reject")
async def reject_creator(
    user_id: str,
    payload: DecisionPayload | None = None,
    user: dict = Depends(require_roles("admin")),
):
    return await _set_creator_vetting(
        user_id, "rejected", user, (payload.reason if payload else None)
    )


# --- Brand verification (GAP 5) --------------------------------------------


@admin_router.get("/brands")
async def list_brands_for_review(
    unverified_only: bool = True,
    user: dict = Depends(require_roles("admin")),
):
    """Brands awaiting review. The landing page promises both sides are checked;
    until this existed only one side was."""
    query: dict = {"verified": False} if unverified_only else {}
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
    campaign_counts = await db.campaigns.aggregate(
        [
            {"$match": {"brand_id": {"$in": user_ids}}},
            {"$group": {"_id": "$brand_id", "n": {"$sum": 1}}},
        ]
    ).to_list(length=len(user_ids))
    counts = {c["_id"]: c["n"] for c in campaign_counts}

    out = []
    for p in profiles:
        u = users_by_id.get(p["user_id"], {})
        out.append(
            {
                "user_id": str(p["user_id"]),
                "business_name": p.get("business_name"),
                "category": p.get("category"),
                "areas": p.get("areas") or [],
                "verified": bool(p.get("verified", False)),
                "email": u.get("email"),
                "phone": u.get("phone"),
                "campaign_count": counts.get(p["user_id"], 0),
                "created_at": _iso(p.get("created_at")),
            }
        )
    return out


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
        {"$set": {"verified": True, "verified_at": now, "updated_at": now}},
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
    return _serialize_brand_profile(result)


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
        {"$set": {"verified": False, "updated_at": now}},
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
            "vetting_status": (creator_profile or {}).get("vetting_status"),
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
        if payload.agreed_amount is None:
            raise HTTPException(
                status_code=422,
                detail="Agreed amount is required when moving to commercial_agreed",
            )
        update["agreed_amount"] = round(float(payload.agreed_amount), 2)
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
        await notify(
            collab["creator_id"],
            "commercial_agreed",
            title="Fee agreed",
            body=f"{campaign_title} — agreed at ₹{update['agreed_amount']:,.0f}.",
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


@admin_router.post("/collaborations/{collab_id}/cancel")
async def cancel_collaboration(
    collab_id: str,
    payload: DecisionPayload,
    user: dict = Depends(require_roles("admin")),
):
    """End a collaboration that is already under way — a no-show, a pull-out, a
    brand cancelling the shoot. Without this the only exit was to leave the row
    sitting mid-pipeline forever."""
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

    payment = await db.payments.find_one({"collaboration_id": oid})
    if payment and payment.get("state") == "paid":
        raise HTTPException(
            status_code=409,
            detail="This collaboration has already been paid out and can't be cancelled.",
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid, "state": current},
        {
            "$set": {
                "state": "cancelled",
                "active": False,
                "exit_reason": payload.reason,
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

    await audit(
        user,
        "collaboration.cancel",
        "collaboration",
        oid,
        before={"state": current},
        after={"state": "cancelled"},
        note=payload.reason,
    )
    await _sync_campaign_fill(collab["campaign_id"])
    await notify(
        collab["creator_id"],
        "application_declined",
        title="Collaboration cancelled",
        body=payload.reason or "This collaboration was cancelled.",
        link="/dashboard",
    )
    return {"id": collab_id, "state": "cancelled"}


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
    vetted_creators = await db.creator_profiles.count_documents(
        {"vetting_status": "vetted"}
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

    return {
        "open_campaigns": open_campaigns,
        "vetted_creators": vetted_creators,
        "total_paid_out": total_paid,
        "platform_revenue": platform_revenue,
        "platform_fee_percent": platform_fee_percent(),
        "payouts_pending": float(pending_agg[0]["total"]) if pending_agg else 0.0,
        "payouts_pending_count": int(pending_agg[0]["n"]) if pending_agg else 0,
        "brand_receivable": float(receivable_agg[0]["total"]) if receivable_agg else 0.0,
        # Queues that should be at zero.
        "creators_pending_review": await db.creator_profiles.count_documents(
            {"vetting_status": "pending", "instagram_handle": {"$type": "string", "$ne": ""}}
        ),
        "brands_unverified": await db.brand_profiles.count_documents({"verified": False}),
        "applicants_awaiting_vetting": await db.collaborations.count_documents(
            {"state": "applied"}
        ),
    }


@admin_router.get("/audit")
async def list_audit_log(
    limit: int = 100,
    subject_type: Optional[str] = None,
    user: dict = Depends(require_roles("admin")),
):
    """Who did what, most recent first."""
    query: dict = {}
    if subject_type:
        query["subject_type"] = subject_type
    limit = max(1, min(int(limit or 100), 500))
    docs = (
        await db.audit_log.find(query)
        .sort("created_at", -1)
        .to_list(length=limit)
    )
    return [
        {
            "id": str(d["_id"]),
            "actor_name": d.get("actor_name"),
            "actor_role": d.get("actor_role"),
            "action": d.get("action"),
            "subject_type": d.get("subject_type"),
            "subject_id": str(d.get("subject_id")),
            "before": _jsonable(d.get("before")),
            "after": _jsonable(d.get("after")),
            "note": d.get("note"),
            "created_at": _iso(d.get("created_at")),
        }
        for d in docs
    ]


api_router.include_router(admin_router)




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
        "category": doc.get("category"),
        "area": doc.get("area"),
        "creators_needed": doc.get("creators_needed"),
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
                "end_date": {"$ne": None, "$lt": now},
            },
            {"$set": {"status": "completed", "updated_at": now}},
        )
        if result.modified_count:
            logger.info("Expired %d campaign(s) past end_date", result.modified_count)
    except Exception as exc:
        logger.error("campaign expiry sweep failed: %s", exc)


# States that occupy one of a campaign's slots.
_FILLED_COLLAB_STATES = [
    s for s in COLLAB_STATE_ORDER if s not in ("applied", "vetted")
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
    """Return { brand_id (ObjectId): { business_name, name } } for the given ids."""
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
        }
    return out


@campaigns_router.get("")
async def list_campaigns(
    area: Optional[str] = None,
    category: Optional[str] = None,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,  # "newest" | "budget_desc" | "budget_asc"
    user: dict = Depends(require_roles("creator", "admin")),
):
    await _expire_stale_campaigns()
    query: dict = {"status": {"$in": list(_LIVE_STATUSES)}}
    if area:
        query["area"] = area
    if category:
        query["category"] = category
    if budget_min is not None or budget_max is not None:
        budget_q: dict = {}
        if budget_min is not None:
            budget_q["$gte"] = budget_min
        if budget_max is not None:
            budget_q["$lte"] = budget_max
        query["budget_per_creator"] = budget_q
    if q:
        # Case-insensitive keyword match against title / brief / deliverables.
        term = re.escape(q.strip())
        query["$or"] = [
            {"title": {"$regex": term, "$options": "i"}},
            {"brief": {"$regex": term, "$options": "i"}},
            {"deliverables": {"$regex": term, "$options": "i"}},
        ]

    sort_key: list = [("created_at", -1)]
    if sort == "budget_desc":
        sort_key = [("budget_per_creator", -1), ("created_at", -1)]
    elif sort == "budget_asc":
        sort_key = [("budget_per_creator", 1), ("created_at", -1)]

    docs = await db.campaigns.find(query).sort(sort_key).to_list(length=200)
    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    return [_serialize_campaign(d, brand_map.get(d["brand_id"])) for d in docs]


@campaigns_router.get("/filters")
async def campaign_filters(
    user: dict = Depends(require_roles("creator", "admin")),
):
    """Distinct areas + categories + budget bounds across listable campaigns."""
    await _expire_stale_campaigns()
    base = {"status": {"$in": list(_LIVE_STATUSES)}}
    areas = await db.campaigns.distinct("area", base)
    categories = await db.campaigns.distinct("category", base)

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
        "areas": sorted([a for a in areas if a]),
        "categories": sorted([c for c in categories if c]),
        "budget_bounds": budget_bounds,
    }


@campaigns_router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    user: dict = Depends(require_roles("creator", "brand", "admin")),
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
    if user["role"] == "brand":
        if doc.get("brand_id") != ObjectId(user["_id"]):
            raise HTTPException(status_code=404, detail="Campaign not found")
    elif user["role"] != "admin" and doc.get("status") not in _LIVE_STATUSES:
        # Creators can only view live/upcoming campaigns. Admins see anything.
        raise HTTPException(status_code=404, detail="Campaign not found")

    brand_map = await _load_brand_map([doc["brand_id"]])
    payload = _serialize_campaign(doc, brand_map.get(doc["brand_id"]))

    # Whether the current creator has already applied.
    payload["has_applied"] = False
    payload["application"] = None
    if user["role"] == "creator":
        existing = await db.collaborations.find_one(
            {"campaign_id": oid, "creator_id": ObjectId(user["_id"])}
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
    return payload


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

    # Vetting has to gate something, or the 48-hour review is decoration.
    profile = await db.creator_profiles.find_one({"user_id": creator_oid})
    vetting = (profile or {}).get("vetting_status", "pending")
    if vetting != "vetted":
        raise HTTPException(
            status_code=403,
            detail=(
                "Your profile is still with the WeAre team — you can apply to briefs "
                "as soon as it's approved."
                if vetting == "pending"
                else "Your profile wasn't approved. Update it to be reviewed again."
            ),
        )

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

    await notify(
        campaign["brand_id"],
        "new_applicant",
        title="New applicant",
        body=f"{user.get('name') or 'A creator'} applied to \"{campaign.get('title')}\".",
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
    docs = (
        await db.campaigns.find({"status": "open"})
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
                "category": d.get("category"),
                "area": d.get("area"),
                "budget_per_creator": d.get("budget_per_creator"),
                "teaser": brief[:180] + ("…" if len(brief) > 180 else ""),
                "spots_left": max(0, needed - filled.get(d["_id"], 0)),
            }
        )
    return {"campaigns": out, "total_open": await db.campaigns.count_documents({"status": "open"})}


@public_router.get("/stats")
async def public_stats():
    """Headline numbers for the landing page — no PII, no auth."""
    return {
        "vetted_creators": await db.creator_profiles.count_documents(
            {"vetting_status": "vetted"}
        ),
        "open_campaigns": await db.campaigns.count_documents({"status": "open"}),
        "cities": len(
            [
                c
                for c in await db.creator_profiles.distinct(
                    "city", {"vetting_status": "vetted"}
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


# --- Admin sample route ----------------------------------------------------


@api_router.get("/admin/ping")
async def admin_ping(user: dict = Depends(require_roles("admin"))):
    return {"pong": True, "admin_email": user["email"]}


app.include_router(api_router)

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
    await db.creator_profiles.create_index("vetting_status")
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

    # payments (one per collaboration)
    await db.payments.create_index("collaboration_id", unique=True)
    await db.payments.create_index("state")
    await db.payments.create_index("brand_invoice_state")

    # audit log + notifications
    await db.audit_log.create_index([("created_at", -1)])
    await db.audit_log.create_index([("subject_type", 1), ("subject_id", 1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1)])

    # --- Data migrations ---------------------------------------------------
    # `approved` was written by the demo seed while approvals wrote `vetted`,
    # so the brand directory could only ever see seeded creators.
    migrated = await db.creator_profiles.update_many(
        {"vetting_status": "approved"}, {"$set": {"vetting_status": "vetted"}}
    )
    if migrated.modified_count:
        logger.info(
            "Migrated %d creator profile(s) from vetting_status 'approved' to 'vetted'",
            migrated.modified_count,
        )
    await db.creator_profiles.update_many(
        {"pending_review": {"$exists": False}}, {"$set": {"pending_review": False}}
    )

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
    """Idempotently seed a small directory of vetted demo creators."""
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
                    "vetting_status": "vetted",
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
