from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, Annotated

import bcrypt
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


api_router.include_router(creator_router)


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
