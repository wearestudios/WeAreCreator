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


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class CreatorProfileUpdate(BaseModel):
    """Payload for creator onboarding / profile edits."""

    name: str = Field(min_length=1, max_length=120)
    instagram_handle: str = Field(min_length=1, max_length=60)
    instagram_profile_url: str = Field(min_length=1, max_length=300)
    email: EmailStr
    address: str = Field(min_length=1, max_length=500)
    niches: list[str] = Field(default_factory=list, max_length=25)
    base_rate: Optional[float] = Field(default=None, ge=0)
    follower_count: Optional[int] = Field(default=None, ge=0)


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
    category: Literal["fnb", "hospitality", "retail", "lifestyle"]
    areas: list[str] = Field(default_factory=list, max_length=30)


class PostCampaignPayload(BaseModel):
    """Payload for a brand posting a new campaign."""

    title: str = Field(min_length=1, max_length=140)
    brief: str = Field(min_length=1, max_length=5000)
    deliverables: str = Field(min_length=1, max_length=1000)
    budget_per_creator: float = Field(ge=0)
    category: Literal["fnb", "hospitality", "retail", "lifestyle"]
    area: str = Field(min_length=1, max_length=80)
    creators_needed: int = Field(ge=1, le=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Literal["draft", "open"] = "open"


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
    "in_payment",
    "closed",
]
PaymentState = Literal["pending", "paid"]


class CreatorProfile(BaseModel):
    """Collection: creator_profiles (1:1 with users where role='creator')."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    name: str
    instagram_handle: Optional[str] = None
    instagram_profile_url: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    niches: list[str] = Field(default_factory=list)
    base_rate: Optional[float] = None
    follower_count: Optional[int] = None
    vetting_status: VettingStatus = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrandProfile(BaseModel):
    """Collection: brand_profiles (1:1 with users where role='brand')."""

    model_config = ConfigDict(populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    business_name: str
    category: Optional[Literal["fnb", "hospitality", "retail", "lifestyle"]] = None
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
    content_url: Optional[str] = None
    state: CollabState = "applied"
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
    state: PaymentState = "pending"
    paid_at: Optional[datetime] = None
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
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

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
        "address": doc.get("address"),
        "niches": doc.get("niches") or [],
        "base_rate": doc.get("base_rate"),
        "follower_count": doc.get("follower_count"),
        "vetting_status": doc.get("vetting_status", "pending"),
        "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        "updated_at": doc["updated_at"].isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at"),
    }


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

    now = datetime.now(timezone.utc)
    update = {
        "name": payload.name.strip(),
        "instagram_handle": handle,
        "instagram_profile_url": payload.instagram_profile_url.strip(),
        "email": payload.email.lower().strip(),
        "address": payload.address.strip(),
        "niches": [n.strip().lower() for n in payload.niches if n and n.strip()],
        "base_rate": payload.base_rate,
        "follower_count": payload.follower_count,
        # Any user-side edit resubmits the profile for review.
        "vetting_status": "pending",
        "updated_at": now,
    }

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


def _serialize_collab_row(
    collab: dict,
    campaign: Optional[dict],
    brand_name: Optional[str],
) -> dict:
    return {
        "id": str(collab["_id"]),
        "campaign_id": str(collab["campaign_id"]),
        "campaign_title": (campaign or {}).get("title"),
        "brand_name": brand_name,
        "area": (campaign or {}).get("area"),
        "category": (campaign or {}).get("category"),
        "quoted_rate": collab.get("quoted_rate"),
        "agreed_amount": collab.get("agreed_amount"),
        "content_url": collab.get("content_url"),
        "content_urls": collab.get("content_urls")
        or ([collab["content_url"]] if collab.get("content_url") else []),
        "state": collab.get("state", "applied"),
        "created_at": collab["created_at"].isoformat()
        if isinstance(collab.get("created_at"), datetime)
        else collab.get("created_at"),
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
        "niches": (profile or {}).get("niches") or [],
        "follower_count": (profile or {}).get("follower_count"),
        "base_rate": (profile or {}).get("base_rate"),
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

    if collab.get("state") != "attended":
        raise HTTPException(
            status_code=400,
            detail="Content can only be submitted after the collaboration is marked attended",
        )

    now = datetime.now(timezone.utc)
    updated = await db.collaborations.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "content_url": urls[0],          # keep legacy field in sync
                "content_urls": urls,
                "state": "content_submitted",
                "updated_at": now,
            }
        },
        return_document=True,
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


def _serialize_brand_campaign(doc: dict, applicant_count: int) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title"),
        "brief": doc.get("brief"),
        "deliverables": doc.get("deliverables"),
        "budget_per_creator": doc.get("budget_per_creator"),
        "category": doc.get("category"),
        "area": doc.get("area"),
        "creators_needed": doc.get("creators_needed"),
        "start_date": doc["start_date"].isoformat()
        if isinstance(doc.get("start_date"), datetime)
        else doc.get("start_date"),
        "end_date": doc["end_date"].isoformat()
        if isinstance(doc.get("end_date"), datetime)
        else doc.get("end_date"),
        "status": doc.get("status"),
        "created_at": doc["created_at"].isoformat()
        if isinstance(doc.get("created_at"), datetime)
        else doc.get("created_at"),
        "applicant_count": applicant_count,
    }


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
    brand_oid = ObjectId(user["_id"])
    docs = (
        await db.campaigns.find({"brand_id": brand_oid})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    count_map = await _applicant_counts_for([d["_id"] for d in docs])
    return [
        _serialize_brand_campaign(d, count_map.get(d["_id"], 0)) for d in docs
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
    return _serialize_brand_campaign(doc, 0)


@brand_router.get("/dashboard")
async def get_brand_dashboard(user: dict = Depends(require_roles("brand"))):
    brand_oid = ObjectId(user["_id"])
    profile = await db.brand_profiles.find_one({"user_id": brand_oid})
    campaigns = (
        await db.campaigns.find({"brand_id": brand_oid})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    count_map = await _applicant_counts_for([c["_id"] for c in campaigns])
    campaign_rows = [
        _serialize_brand_campaign(c, count_map.get(c["_id"], 0)) for c in campaigns
    ]

    total_applications = sum(count_map.values())
    live = sum(1 for c in campaign_rows if c["status"] in ("open", "upcoming"))
    drafts = sum(1 for c in campaign_rows if c["status"] == "draft")

    return {
        "profile": _serialize_brand_profile(profile),
        "campaigns": campaign_rows,
        "totals": {
            "total_campaigns": len(campaign_rows),
            "live_campaigns": live,
            "draft_campaigns": drafts,
            "total_applications": total_applications,
        },
    }


api_router.include_router(brand_router)


# --- Admin router ----------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["admin"])

COLLAB_STATE_ORDER = [
    "applied",
    "vetted",
    "accepted",
    "commercial_agreed",
    "slot_booked",
    "attended",
    "content_submitted",
    "in_payment",
    "closed",
]


def _next_collab_state(current: str) -> Optional[str]:
    try:
        idx = COLLAB_STATE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(COLLAB_STATE_ORDER):
        return None
    return COLLAB_STATE_ORDER[idx + 1]


class AdvanceCollabPayload(BaseModel):
    """Payload to advance a collaboration one step forward."""

    # Required only when the NEXT state is 'commercial_agreed'.
    agreed_amount: Optional[float] = Field(default=None, ge=0)
    # Required only when the NEXT state is 'in_payment'.
    platform_fee: Optional[float] = Field(default=None, ge=0)


def _serialize_admin_creator(profile: dict, user: dict) -> dict:
    return {
        "user_id": str(user["_id"]),
        "profile_id": str(profile["_id"]),
        "name": profile.get("name") or user.get("name"),
        "email": profile.get("email") or user.get("email"),
        "phone": user.get("phone"),
        "instagram_handle": profile.get("instagram_handle"),
        "instagram_profile_url": profile.get("instagram_profile_url"),
        "address": profile.get("address"),
        "niches": profile.get("niches") or [],
        "base_rate": profile.get("base_rate"),
        "follower_count": profile.get("follower_count"),
        "vetting_status": profile.get("vetting_status", "pending"),
        "created_at": profile["created_at"].isoformat()
        if isinstance(profile.get("created_at"), datetime)
        else profile.get("created_at"),
    }


@admin_router.get("/creators/pending")
async def list_pending_creators(user: dict = Depends(require_roles("admin"))):
    profiles = (
        await db.creator_profiles.find({"vetting_status": "pending"})
        .sort("created_at", -1)
        .to_list(length=500)
    )
    if not profiles:
        return []
    user_ids = [p["user_id"] for p in profiles]
    users = await db.users.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
    users_by_id = {u["_id"]: u for u in users}
    return [
        _serialize_admin_creator(p, users_by_id.get(p["user_id"], {}))
        for p in profiles
    ]


async def _set_creator_vetting(user_id: str, status: str) -> dict:
    if status not in ("vetted", "rejected"):
        raise HTTPException(status_code=422, detail="Invalid vetting status")
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Creator not found")

    now = datetime.now(timezone.utc)
    result = await db.creator_profiles.find_one_and_update(
        {"user_id": oid},
        {"$set": {"vetting_status": status, "updated_at": now}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Creator profile not found")

    # Also flip the user's active status when vetted.
    if status == "vetted":
        await db.users.update_one({"_id": oid}, {"$set": {"status": "active"}})

    user = await db.users.find_one({"_id": oid})
    return _serialize_admin_creator(result, user or {})


@admin_router.post("/creators/{user_id}/approve")
async def approve_creator(user_id: str, user: dict = Depends(require_roles("admin"))):
    return await _set_creator_vetting(user_id, "vetted")


@admin_router.post("/creators/{user_id}/reject")
async def reject_creator(user_id: str, user: dict = Depends(require_roles("admin"))):
    return await _set_creator_vetting(user_id, "rejected")


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
        "created_at": collab["created_at"].isoformat()
        if isinstance(collab.get("created_at"), datetime)
        else collab.get("created_at"),
        "updated_at": collab["updated_at"].isoformat()
        if isinstance(collab.get("updated_at"), datetime)
        else collab.get("updated_at"),
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
        },
        "payment": (
            {
                "id": str(payment["_id"]),
                "agreed_amount": payment.get("agreed_amount"),
                "platform_fee": payment.get("platform_fee"),
                "creator_payout": payment.get("creator_payout"),
                "state": payment.get("state"),
                "paid_at": payment["paid_at"].isoformat()
                if isinstance(payment.get("paid_at"), datetime)
                else payment.get("paid_at"),
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

    by_state: dict = {s: [] for s in COLLAB_STATE_ORDER}
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
        row["next_state"] = _next_collab_state(row["state"])
        by_state[row["state"]].append(row)
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

    now = datetime.now(timezone.utc)
    update: dict = {"state": to_state, "updated_at": now}

    if to_state == "commercial_agreed":
        if payload.agreed_amount is None:
            raise HTTPException(
                status_code=422,
                detail="Agreed amount is required when moving to commercial_agreed",
            )
        update["agreed_amount"] = float(payload.agreed_amount)

    if to_state == "in_payment":
        if payload.platform_fee is None:
            raise HTTPException(
                status_code=422,
                detail="Platform fee is required when moving to in_payment",
            )
        agreed = collab.get("agreed_amount")
        if agreed is None:
            raise HTTPException(
                status_code=422,
                detail="Collaboration has no agreed amount yet",
            )
        # Create the payment record (idempotent by unique index on collaboration_id).
        existing_payment = await db.payments.find_one({"collaboration_id": oid})
        if existing_payment is None:
            await db.payments.insert_one(
                {
                    "collaboration_id": oid,
                    "agreed_amount": float(agreed),
                    "platform_fee": float(payload.platform_fee),
                    "creator_payout": float(agreed),
                    "state": "pending",
                    "paid_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    updated = await db.collaborations.find_one_and_update(
        {"_id": oid}, {"$set": update}, return_document=True
    )
    return {
        "id": collab_id,
        "state": updated["state"],
        "agreed_amount": updated.get("agreed_amount"),
        "next_state": _next_collab_state(updated["state"]),
    }


@admin_router.post("/payments/{payment_id}/mark_paid")
async def mark_payment_paid(
    payment_id: str,
    user: dict = Depends(require_roles("admin")),
):
    try:
        pid = ObjectId(payment_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Payment not found")

    now = datetime.now(timezone.utc)
    payment = await db.payments.find_one_and_update(
        {"_id": pid},
        {"$set": {"state": "paid", "paid_at": now, "updated_at": now}},
        return_document=True,
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Move the linked collaboration to 'closed'.
    await db.collaborations.update_one(
        {"_id": payment["collaboration_id"]},
        {"$set": {"state": "closed", "updated_at": now}},
    )

    return {
        "id": payment_id,
        "state": payment["state"],
        "paid_at": payment["paid_at"].isoformat(),
        "collaboration_id": str(payment["collaboration_id"]),
    }


@admin_router.get("/metrics")
async def admin_metrics(user: dict = Depends(require_roles("admin"))):
    open_campaigns = await db.campaigns.count_documents({"status": "open"})
    vetted_creators = await db.creator_profiles.count_documents(
        {"vetting_status": "vetted"}
    )
    agg = await db.payments.aggregate(
        [
            {"$match": {"state": "paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$creator_payout"}}},
        ]
    ).to_list(length=1)
    total_paid = float(agg[0]["total"]) if agg else 0.0
    return {
        "open_campaigns": open_campaigns,
        "vetted_creators": vetted_creators,
        "total_paid_out": total_paid,
    }


api_router.include_router(admin_router)




# --- Campaigns router ------------------------------------------------------

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_LIVE_STATUSES = ("open", "upcoming")


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
    user: dict = Depends(require_roles("creator", "admin")),
):
    query: dict = {"status": {"$in": list(_LIVE_STATUSES)}}
    if area:
        query["area"] = area
    if category:
        query["category"] = category

    docs = await db.campaigns.find(query).sort("created_at", -1).to_list(length=200)
    brand_map = await _load_brand_map([d["brand_id"] for d in docs])
    return [_serialize_campaign(d, brand_map.get(d["brand_id"])) for d in docs]


@campaigns_router.get("/filters")
async def campaign_filters(
    user: dict = Depends(require_roles("creator", "admin")),
):
    """Distinct areas + categories across currently-listable campaigns."""
    base = {"status": {"$in": list(_LIVE_STATUSES)}}
    areas = await db.campaigns.distinct("area", base)
    categories = await db.campaigns.distinct("category", base)
    return {
        "areas": sorted([a for a in areas if a]),
        "categories": sorted([c for c in categories if c]),
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

    # Creators can only view live/upcoming campaigns. Admins see anything.
    if user["role"] != "admin" and doc.get("status") not in _LIVE_STATUSES:
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
                "state": "applied",
                "created_at": now,
                "updated_at": now,
            }
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409, detail="You've already applied to this campaign"
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
    await db.users.create_index("email", unique=True)
    await db.users.create_index("role")
    await db.users.create_index("status")

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
    # A creator can only apply once per campaign
    await db.collaborations.create_index(
        [("campaign_id", 1), ("creator_id", 1)], unique=True
    )
    await db.collaborations.create_index("state")

    # payments (one per collaboration)
    await db.payments.create_index("collaboration_id", unique=True)
    await db.payments.create_index("state")

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
                "created_at": now,
            }
        )
        logger.info("Seeded admin user %s", admin_email)
    else:
        update = {"role": "admin", "status": existing.get("status") or "active"}
        if not verify_password(admin_password, existing["password_hash"]):
            update["password_hash"] = hash_password(admin_password)
        await db.users.update_one({"email": admin_email}, {"$set": update})

    # Backfill status field on any legacy users that were created before the
    # schema was extended so downstream code can rely on the field existing.
    await db.users.update_many(
        {"status": {"$exists": False}}, {"$set": {"status": "pending"}}
    )

    # Seed a handful of demo brand accounts + campaigns so the Campaigns page
    # is not empty on a fresh install. Fully idempotent — keyed by email/title.
    await _seed_demo_campaigns()


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
    brand_id_by_email: dict[str, ObjectId] = {}
    demo_password_hash = hash_password("DemoBrand!2026")
    for b in _DEMO_BRANDS:
        existing = await db.users.find_one({"email": b["email"]})
        if existing is None:
            result = await db.users.insert_one(
                {
                    "email": b["email"],
                    "password_hash": demo_password_hash,
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
