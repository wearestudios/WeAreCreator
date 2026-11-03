"""What a creator posts about, and what a brief is looking for — as tags.

**A controlled vocabulary, never free text.** `niches` on a creator profile is
free text, and free text cannot be matched: "craft beer", "breweries" and
"beer 🍺" are three filters and one interest. These tags are the opposite:
every value is a key in one of the tables below, mirrored by
`frontend/src/lib/niches.js` with a drift test. Adding a tag is one line here
and one line there.

The tables are the whole vocabulary the model may choose from, and three
fences hold it there:

1. the JSON schema sent to the model enumerates the allowed values;
2. the parsed reply drops any value not in the table (`_keep`), so an
   injection-style caption that talks the model into "luxury_yachts" produces
   nothing rather than a tag;
3. an area is kept only if its name actually appears in a caption — Instagram
   does not expose a post's location to this API, so "shoots in Indiranagar"
   must come from the creator having written "Indiranagar".

Pure: no database, so the vocabulary, the cleaning and the match score can be
read and tested on their own. `server.py` holds storage, routes and jobs.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

import ai

# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

# Niches, grouped under the existing campaign categories. F&B first and
# deepest, because that is where the operation is; three to five for the rest.
NICHES_BY_CATEGORY = {
    "fnb": {
        "fine_dining": "Fine dining",
        "casual_dining": "Casual dining",
        "cafes_coffee": "Cafés & coffee",
        "bakery_desserts": "Bakery & desserts",
        "street_food": "Street food",
        "south_indian": "South Indian",
        "north_indian": "North Indian",
        "coastal_regional": "Coastal & regional",
        "asian": "Asian",
        "continental": "Continental",
        "bars_cocktails": "Bars & cocktails",
        "craft_beer": "Craft beer",
        "vegan_vegetarian": "Vegan & vegetarian",
        "healthy_eating": "Healthy eating",
        "home_cooking": "Home cooking",
    },
    "hospitality": {
        "luxury_stays": "Luxury stays",
        "boutique_hotels": "Boutique hotels",
        "staycations": "Staycations",
        "events_weddings": "Events & weddings",
    },
    "retail": {
        "home_decor": "Home décor",
        "gadgets": "Gadgets",
        "books_stationery": "Books & stationery",
        "local_markets": "Local markets",
    },
    "real_estate": {
        "apartments": "Apartments",
        "villas_plots": "Villas & plots",
        "interiors": "Interiors",
    },
    "fashion": {
        "streetwear": "Streetwear",
        "ethnic_wear": "Ethnic wear",
        "jewellery_accessories": "Jewellery & accessories",
        "sustainable_fashion": "Sustainable fashion",
    },
    "travel": {
        "weekend_getaways": "Weekend getaways",
        "adventure": "Adventure",
        "heritage_culture": "Heritage & culture",
        "road_trips": "Road trips",
    },
    "wellness": {
        "fitness": "Fitness",
        "yoga_meditation": "Yoga & meditation",
        "skincare_beauty": "Skincare & beauty",
        "salons_spa": "Salons & spa",
    },
    "lifestyle": {
        "parenting_family": "Parenting & family",
        "pets": "Pets",
        "nightlife": "Nightlife",
        "art_design": "Art & design",
        "tech_gaming": "Tech & gaming",
    },
}
NICHE_LABELS = {k: v for group in NICHES_BY_CATEGORY.values() for k, v in group.items()}
NICHE_CATEGORY = {k: cat for cat, group in NICHES_BY_CATEGORY.items() for k in group}

LANGUAGE_LABELS = {
    "kannada": "Kannada",
    "english": "English",
    "hindi": "Hindi",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "malayalam": "Malayalam",
}

TONE_LABELS = {
    "reviews": "Reviews",
    "humour": "Humour",
    "aesthetic": "Aesthetic",
    "vlog": "Vlog",
    "educational": "Educational",
}

# Bengaluru localities. The operation is Bengaluru-first; another city's
# localities are a list that grows when the operation does.
AREA_LABELS = {
    "indiranagar": "Indiranagar",
    "koramangala": "Koramangala",
    "jayanagar": "Jayanagar",
    "jp_nagar": "JP Nagar",
    "hsr_layout": "HSR Layout",
    "whitefield": "Whitefield",
    "malleshwaram": "Malleshwaram",
    "mg_road": "MG Road",
    "brigade_road": "Brigade Road",
    "church_street": "Church Street",
    "ub_city": "UB City",
    "lavelle_road": "Lavelle Road",
    "residency_road": "Residency Road",
    "richmond_town": "Richmond Town",
    "frazer_town": "Frazer Town",
    "cox_town": "Cox Town",
    "ulsoor": "Ulsoor",
    "domlur": "Domlur",
    "btm_layout": "BTM Layout",
    "banashankari": "Banashankari",
    "basavanagudi": "Basavanagudi",
    "rajajinagar": "Rajajinagar",
    "sadashivanagar": "Sadashivanagar",
    "rt_nagar": "RT Nagar",
    "hebbal": "Hebbal",
    "yelahanka": "Yelahanka",
    "sahakar_nagar": "Sahakar Nagar",
    "marathahalli": "Marathahalli",
    "bellandur": "Bellandur",
    "sarjapur_road": "Sarjapur Road",
    "electronic_city": "Electronic City",
    "kalyan_nagar": "Kalyan Nagar",
    "hennur": "Hennur",
    "kammanahalli": "Kammanahalli",
    "banaswadi": "Banaswadi",
    "cv_raman_nagar": "CV Raman Nagar",
    "old_airport_road": "Old Airport Road",
    "vasanth_nagar": "Vasanth Nagar",
    "cunningham_road": "Cunningham Road",
    "bannerghatta_road": "Bannerghatta Road",
    "yeshwanthpur": "Yeshwanthpur",
}

# Spellings that mean the same place, for finding an area in a caption.
_AREA_ALIASES = {
    "hsr_layout": ("hsr",),
    "jp_nagar": ("j p nagar", "jpnagar"),
    "btm_layout": ("btm",),
    "mg_road": ("m g road", "mgroad"),
    "ulsoor": ("halasuru",),
    "electronic_city": ("e city", "ecity"),
    "cv_raman_nagar": ("c v raman nagar",),
    "indiranagar": ("indira nagar",),
}

FORMAT_LABELS = {"reel": "Reels", "carousel": "Carousels", "image": "Photos"}

NICHES = tuple(NICHE_LABELS)
LANGUAGES = tuple(LANGUAGE_LABELS)
TONES = tuple(TONE_LABELS)
AREAS = tuple(AREA_LABELS)
FORMATS = tuple(FORMAT_LABELS)

NICHE_LITERAL = Literal[NICHES]  # type: ignore[valid-type]
LANGUAGE_LITERAL = Literal[LANGUAGES]  # type: ignore[valid-type]
TONE_LITERAL = Literal[TONES]  # type: ignore[valid-type]
AREA_LITERAL = Literal[AREAS]  # type: ignore[valid-type]

TAG_KINDS = {"niche": NICHES, "languages": LANGUAGES, "tone": TONES, "shoots_in": AREAS}

# An AI niche below this confidence is not a suggestion anybody should see.
MIN_CONFIDENCE = 0.5
# How many of a creator's posts are read, per creator, per week. The cap is
# the brief's, and it is the cost ceiling: 24 captions is one call.
POSTS_PER_TAGGING = 24


def vocabulary() -> dict:
    """The vocabulary as the screens and the model read it."""
    return {
        "niche": {cat: dict(group) for cat, group in NICHES_BY_CATEGORY.items()},
        "languages": dict(LANGUAGE_LABELS),
        "tone": dict(TONE_LABELS),
        "shoots_in": dict(AREA_LABELS),
        "formats": dict(FORMAT_LABELS),
    }


def _keep(values, allowed, limit=None) -> list:
    """Only vocabulary values, de-duplicated, in order. Anything else is
    dropped silently — an out-of-vocabulary value is not an error to surface,
    it is a value that never existed."""
    out = []
    for v in values or []:
        key = str(v).strip().lower()
        if key in allowed and key not in out:
            out.append(key)
    return out[:limit] if limit else out


def clean_tag_set(raw: Optional[dict]) -> dict:
    """A tag set from a person (creator, admin or brand), held to the vocabulary."""
    raw = raw or {}
    return {kind: _keep(raw.get(kind), allowed) for kind, allowed in TAG_KINDS.items()}


# ---------------------------------------------------------------------------
# What the model returns
# ---------------------------------------------------------------------------


def _enum(values) -> dict:
    return {"items": {"type": "string", "enum": list(values)}}


class NicheGuess(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tag: str = Field(json_schema_extra={"enum": list(NICHES)})
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


class CreatorTagging(BaseModel):
    """The model's reading of a creator's captions.

    **Lenient on purpose.** An unknown value is dropped by the validators
    rather than failing the reply: one invented tag should cost that tag, not
    the creator's whole tagging (the same reason one unsupported Instagram
    metric costs a metric, not the post).
    """

    model_config = ConfigDict(extra="ignore")

    niche: list[NicheGuess] = Field(default_factory=list, max_length=8)
    languages: list[str] = Field(default_factory=list, json_schema_extra=_enum(LANGUAGES))
    tone: list[str] = Field(default_factory=list, json_schema_extra=_enum(TONES))
    shoots_in: list[str] = Field(default_factory=list, json_schema_extra=_enum(AREAS))

    @field_validator("niche", mode="after")
    @classmethod
    def _niches(cls, v):
        seen, out = set(), []
        for g in v:
            key = g.tag.strip().lower()
            if key in NICHE_LABELS and key not in seen:
                seen.add(key)
                out.append(NicheGuess(tag=key, confidence=g.confidence))
        return out[:5]

    @field_validator("languages", mode="after")
    @classmethod
    def _languages(cls, v):
        return _keep(v, LANGUAGES, 3)

    @field_validator("tone", mode="after")
    @classmethod
    def _tone(cls, v):
        return _keep(v, TONES, 3)

    @field_validator("shoots_in", mode="after")
    @classmethod
    def _areas(cls, v):
        return _keep(v, AREAS, 8)


class BriefTagging(BaseModel):
    model_config = ConfigDict(extra="ignore")

    niche: list[str] = Field(default_factory=list, json_schema_extra=_enum(NICHES))
    languages: list[str] = Field(default_factory=list, json_schema_extra=_enum(LANGUAGES))
    areas: list[str] = Field(default_factory=list, json_schema_extra=_enum(AREAS))

    @field_validator("niche", mode="after")
    @classmethod
    def _niche(cls, v):
        return _keep(v, NICHES, 3)

    @field_validator("languages", mode="after")
    @classmethod
    def _languages(cls, v):
        return _keep(v, LANGUAGES, 2)

    @field_validator("areas", mode="after")
    @classmethod
    def _areas(cls, v):
        return _keep(v, AREAS, 2)


CREATOR_PROMPT = ai.register_prompt(
    ai.Prompt(
        task="creator_tagging",
        version="creator_tagging.v1",
        system="""\
You tag an Instagram creator from the captions of their recent posts, for a platform that matches creators to businesses' campaigns.

Use only the values listed in the "vocabulary" part of the data. A value that is not in the vocabulary must not appear in your reply.
- niche: up to 5 subjects the creator actually posts about, each with a confidence from 0 to 1. Base it on what the captions show, not on hashtags alone.
- languages: the languages the captions are written in (romanised Kannada or Hindi count as Kannada or Hindi).
- tone: up to 3 that describe how they post.
- shoots_in: only neighbourhoods a caption names. If no caption names one, return an empty list.
If the captions say too little to decide something, leave it empty rather than guess.""",
    )
)

BRIEF_PROMPT = ai.register_prompt(
    ai.Prompt(
        task="brief_tagging",
        version="brief_tagging.v1",
        system="""\
You suggest tags for a business's influencer campaign brief, so it can be matched to creators.

Use only values from the "vocabulary" part of the data.
- niche: up to 3 subjects the brief is about.
- languages: up to 2 languages the brief asks creators to post in; empty if it does not say.
- areas: the neighbourhood of the venue, taken only from the venue text given; empty if none is named.
These are suggestions a person confirms; leave a field empty rather than guess.""",
    )
)


# ---------------------------------------------------------------------------
# Deterministic: format mix and cadence, from media type alone
# ---------------------------------------------------------------------------


def media_format(item: dict) -> Optional[str]:
    product = (item.get("media_product_type") or "").upper()
    kind = (item.get("media_type") or "").upper()
    if product == "REELS" or kind == "VIDEO":
        return "reel"
    if kind == "CAROUSEL_ALBUM":
        return "carousel"
    if kind == "IMAGE":
        return "image"
    return None


def format_mix(media: list) -> dict:
    """`{reel: 14, carousel: 6, image: 4}` over the posts read."""
    out: dict = {}
    for item in media:
        fmt = media_format(item)
        if fmt:
            out[fmt] = out.get(fmt, 0) + 1
    return out


def formats_posted(mix: dict) -> list:
    """The formats a creator actually posts: any with at least a fifth of
    their recent posts. One carousel in twenty-four is not a carousel creator."""
    total = sum(mix.values())
    if not total:
        return []
    return [f for f in FORMATS if mix.get(f, 0) / total >= 0.2]


def posts_per_week(timestamps: list) -> Optional[float]:
    """Cadence over the span of the posts read. `None` below two posts."""
    times = sorted(t for t in timestamps if t)
    if len(times) < 2:
        return None
    days = max((times[-1] - times[0]).total_seconds() / 86400, 1.0)
    return round(len(times) / days * 7, 1)


def areas_mentioned(text: str) -> set:
    """Areas whose name (or a known spelling of it) appears in `text`."""
    hay = " " + re.sub(r"[^a-z0-9]+", " ", (text or "").lower()) + " "
    found = set()
    for key, label in AREA_LABELS.items():
        names = (label.lower(), key.replace("_", " ")) + _AREA_ALIASES.get(key, ())
        for name in names:
            needle = " " + re.sub(r"[^a-z0-9]+", " ", name) + " "
            if needle in hay:
                found.add(key)
                break
    return found


def caption_payload(media: list) -> dict:
    """What the model reads: captions and their format, and the vocabulary.
    Never the comments, never a DM — this API is not asked for either."""
    return {
        "posts": [
            {"caption": (item.get("caption") or "")[:1200], "format": media_format(item)}
            for item in media[:POSTS_PER_TAGGING]
        ],
        "vocabulary": {
            "niche": list(NICHES),
            "languages": list(LANGUAGES),
            "tone": list(TONES),
            "shoots_in": list(AREAS),
        },
    }


def ground_creator_tags(result: CreatorTagging, media: list) -> dict:
    """The model's reply, held to what the captions can support.

    Areas survive only if a caption names them. Niches below
    `MIN_CONFIDENCE` are dropped. What remains is vocabulary-only by
    construction (the validators already dropped the rest).
    """
    mentioned = areas_mentioned(" ".join(item.get("caption") or "" for item in media))
    return {
        "niche": [
            {"tag": g.tag, "confidence": round(g.confidence, 2)}
            for g in result.niche
            if g.confidence >= MIN_CONFIDENCE
        ],
        "languages": list(result.languages),
        "tone": list(result.tone),
        "shoots_in": [a for a in result.shoots_in if a in mentioned],
    }


# ---------------------------------------------------------------------------
# Effective tags: what the creator said beats what the model guessed
# ---------------------------------------------------------------------------


def effective_tags(creator_tags: Optional[dict]) -> dict:
    """The tags a creator is matched on.

    **Confirmed beats suggested, and a removal sticks.** A tag the creator (or
    an admin) confirmed is in, whatever the model says next week; a suggestion
    they removed stays out, whatever the model says next week; everything else
    the model suggested is in as a suggestion. Each niche says where it came
    from, so a screen can mark the ones nobody has confirmed.
    """
    ct = creator_tags or {}
    mine = ct.get("confirmed") or {}
    gone = ct.get("rejected") or {}
    guessed = ct.get("ai") or {}
    source = ct.get("confirmed_by") or "creator"

    niche = [{"tag": t, "confidence": None, "source": source} for t in mine.get("niche") or []]
    for g in guessed.get("niche") or []:
        if g["tag"] not in (mine.get("niche") or []) and g["tag"] not in (gone.get("niche") or []):
            niche.append({"tag": g["tag"], "confidence": g.get("confidence"), "source": "ai"})
    out = {"niche": niche}
    for kind in ("languages", "tone", "shoots_in"):
        kept = list(mine.get(kind) or [])
        for v in guessed.get(kind) or []:
            if v not in kept and v not in (gone.get(kind) or []):
                kept.append(v)
        out[kind] = kept
    out["formats"] = list(ct.get("formats") or [])
    return out


def suggestions(creator_tags: Optional[dict]) -> dict:
    """The model's tags nobody has confirmed or removed yet — the chips under
    "Suggested from your posts"."""
    ct = creator_tags or {}
    mine = ct.get("confirmed") or {}
    gone = ct.get("rejected") or {}
    guessed = ct.get("ai") or {}
    out = {
        "niche": [
            g for g in guessed.get("niche") or []
            if g["tag"] not in (mine.get("niche") or []) and g["tag"] not in (gone.get("niche") or [])
        ]
    }
    for kind in ("languages", "tone", "shoots_in"):
        out[kind] = [
            v for v in guessed.get(kind) or []
            if v not in (mine.get(kind) or []) and v not in (gone.get(kind) or [])
        ]
    return out


def flattened(creator_tags: Optional[dict]) -> dict:
    """The stored fields filters query — `tag_niches` and the rest — so a
    filter is an indexed equality test on the profile and never a call to a
    model at query time."""
    eff = effective_tags(creator_tags)
    return {
        "tag_niches": [n["tag"] for n in eff["niche"]],
        "tag_languages": eff["languages"],
        "tag_tone": eff["tone"],
        "tag_areas": eff["shoots_in"],
        "tag_formats": eff["formats"],
    }


# ---------------------------------------------------------------------------
# Why this creator: a transparent weighted match
# ---------------------------------------------------------------------------

MATCH_WEIGHTS = {"niche": 35, "language": 20, "area": 20, "tier": 15, "reliability": 10}
# The same rule the suggestions scorer holds: an unmeasured signal scores at
# the midpoint, never zero, or every creator who has not been tagged yet —
# which is everyone, at the start — sorts last.
UNKNOWN = 0.5

# The bands `_reliability_band` returns. "new" is deliberately absent: not
# enough history is an unknown, and it scores at the midpoint like one.
_RELIABILITY_SIGNAL = {"strong": 1.0, "steady": 0.75, "mixed": 0.3}


def match_score(
    creator_tags: dict,
    campaign_tags: dict,
    *,
    tier_fit: Optional[float] = None,
    reliability_band: Optional[str] = None,
) -> dict:
    """`{score, components, why}` for one creator against one brief. Pure.

    `creator_tags` is `effective_tags(...)`; `campaign_tags` is the brief's
    **confirmed** tags (`{niche, languages, areas}`) — a suggestion nobody
    confirmed is not something the brief asked for. `tier_fit` (0–1) and the
    reliability band come from the readers that already compute them, so this
    is one more view of the same facts rather than a second calculation.
    The components are returned and **sum to the score**.
    """
    niches = {n["tag"] for n in creator_tags.get("niche") or []}
    langs = set(creator_tags.get("languages") or [])
    areas = set(creator_tags.get("shoots_in") or [])
    want_n = set(campaign_tags.get("niche") or [])
    want_l = set(campaign_tags.get("languages") or [])
    want_a = set(campaign_tags.get("areas") or [])

    def part(have, want):
        if not want or not have:
            return UNKNOWN, set()
        hit = have & want
        return (1.0 if hit else 0.0), hit

    n_sig, n_hit = part(niches, want_n)
    l_sig, l_hit = part(langs, want_l)
    a_sig, a_hit = part(areas, want_a)
    t_sig = UNKNOWN if tier_fit is None else max(0.0, min(1.0, tier_fit))
    r_sig = _RELIABILITY_SIGNAL.get(reliability_band or "", UNKNOWN)

    w = MATCH_WEIGHTS
    components = {
        "niche": round(w["niche"] * n_sig, 1),
        "language": round(w["language"] * l_sig, 1),
        "area": round(w["area"] * a_sig, 1),
        "tier": round(w["tier"] * t_sig, 1),
        "reliability": round(w["reliability"] * r_sig, 1),
    }
    why = []
    why += [NICHE_LABELS[t] for t in sorted(n_hit)]
    why += [LANGUAGE_LABELS[t] for t in sorted(l_hit)]
    why += [f"shoots in {AREA_LABELS[t]}" for t in sorted(a_hit)]
    return {
        "score": round(sum(components.values()), 1),
        "components": components,
        "why": " · ".join(why) or None,
    }


def label_of(kind: str, key: str) -> str:
    table = {"niche": NICHE_LABELS, "languages": LANGUAGE_LABELS, "tone": TONE_LABELS,
             "shoots_in": AREA_LABELS, "areas": AREA_LABELS, "formats": FORMAT_LABELS}[kind]
    return table.get(key, key)


def brief_payload(campaign: dict, venue: Optional[str]) -> dict:
    """What the brief tagger reads: the brief's own words and the venue text.
    Brand-written, so untrusted — `ai.generate_json` wraps it as data."""
    return {
        "brief": {
            "title": campaign.get("title"),
            "category": campaign.get("category"),
            "description": (campaign.get("brief") or "")[:3000],
            "dos": campaign.get("brief_dos") or [],
            "caption_guidance": campaign.get("caption_guidance"),
        },
        "venue": venue or "",
        "vocabulary": {"niche": list(NICHES), "languages": list(LANGUAGES), "areas": list(AREAS)},
    }


def ground_brief_tags(result: BriefTagging, venue: Optional[str]) -> dict:
    """An area is suggested only if the venue text names it."""
    named = areas_mentioned(venue or "")
    return {
        "niche": list(result.niche),
        "languages": list(result.languages),
        "areas": [a for a in result.areas if a in named],
    }

