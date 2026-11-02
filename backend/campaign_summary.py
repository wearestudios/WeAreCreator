"""The AI campaign summary: what one finished campaign did, in plain English.

**The model writes sentences; Python does the arithmetic.** Every number the
summary may quote is either in the analytics payload or computed here, in
`derive`, before the model sees anything: cost per 1,000 people reached,
averages by format, the share of reach the top creator carried. The model is
told to quote only what it is given, and `ground` checks that it did.

**`ground` is the part of this file that matters.** A summary is a claim made
to a paying client in our name, read by somebody who will quote it to their
business partner. A model that rounds 1,48,932 to "about 1.5 lakh" is fine; a
model that writes "3x the reach of your last campaign" when nothing in the data
says 3 has invented a result, and that is the one failure this feature cannot
have. So every number in the generated text is extracted — with ₹, Indian
commas, percentages, "1.49L", "38K" and number words normalised — and each must
match a value in the input or the derived set within display rounding. One
unmatched number rejects the summary; the shared module retries once naming the
offenders, and a second miss shows nothing at all.

The same check enforces three rules a prompt alone would only request:

- an evidence path must resolve to a real, non-empty value in the input;
- if fewer posts were measured than delivered, the text has to say both numbers;
- a metric the input does not carry (sales, footfall, likes, followers…) may
  not be named, because the brand would reasonably believe we measured it.

Averages by language are deliberately absent: there is no language or niche
tag on a post yet, and a grouping the data cannot support is a number the
model would be invited to invent. When tagging exists, `derive` grows a
`by_language` block beside `by_format` and nothing else changes.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

import ai

TASK = "campaign_summary"
# Fewer than three measured posts is an anecdote, and a summary of an anecdote
# reads as a verdict on the campaign.
MIN_MEASURED_POSTS = 3
REGENERATIONS_PER_DAY = 5
MAX_OUTPUT_TOKENS = 3000
TIMEOUT_S = 45


# ---------------------------------------------------------------------------
# The shape the model must return
# ---------------------------------------------------------------------------


class EvidencedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=240)
    # Paths into the input: `totals.reach`, `creators[0].engagement_rate`.
    evidence: list[str] = Field(min_length=1, max_length=6)


class CampaignSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=110)
    worked: list[EvidencedPoint] = Field(min_length=1, max_length=3)
    didnt: list[EvidencedPoint] = Field(default_factory=list, max_length=2)
    next: list[EvidencedPoint] = Field(min_length=1, max_length=2)


PROMPT = ai.register_prompt(
    ai.Prompt(
        task=TASK,
        version="campaign_summary.v1",
        system="""\
You summarise one finished influencer campaign for the owner of a small business — often a restaurant, café or shop — who paid for it and is deciding whether to run another. Write plain English a busy owner reads in thirty seconds. No marketing jargon: say "people reached", not "reach metrics"; say "cost per 1,000 people reached", not "CPM".

Rules you must follow:
1. Quote only numbers that appear in the data, exactly or rounded for display. Money in rupees with Indian notation: ₹1,48,932, 1.49L or 38K are all fine for the values they round. Never calculate a new number: no sums, differences, ratios, multiples such as "2x", and no percentages that are not already in the data. The "derived" block already holds the averages, shares and costs you may need.
2. Each point lists evidence: the paths of the data fields it relies on, written like totals.reach, creators[0].engagement_rate, derived.by_format[0].average_reach or baseline.reach.change_percent. Every path must exist in the data.
3. If derived.posts_measured is less than derived.posts_total, say so in the headline or the first "worked" point, naming both numbers (for example "4 of 6 posts measured").
4. Never mention a measure that is not in the data — no sales, revenue, footfall, orders, followers, likes, comments, saves, clicks or ROI. If there is no "baseline" block, do not compare with earlier campaigns.
5. headline: one sentence, at most 110 characters. worked: one to three points. didnt: zero to two points — leave it empty rather than invent a weakness. next: one or two concrete suggestions for the next campaign that follow from the data.
6. Refer to creators only by the name given. Say nothing else about them.""",
    )
)


# ---------------------------------------------------------------------------
# The input, built from the analytics payload
# ---------------------------------------------------------------------------


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _positive(value):
    return value if value else None


def build_summary_input(
    analytics: dict,
    versus: Optional[dict],
    formats: dict,
    *,
    category_label: Optional[str] = None,
) -> dict:
    """The model's whole world, from `_campaign_analytics` and the history.

    `formats` maps a creator id to the format label of what they delivered
    ("reel", "reel + 3 stories"); the server builds it from the brief.

    **Absent is absent.** A field nobody measured is left out rather than sent
    as `null` or `0`, so the model has nothing to mention and an evidence path
    to it fails the check. That is how "never mention a field absent from the
    input" becomes a property of the input rather than a request.
    """
    campaign = analytics.get("campaign") or {}
    totals = analytics.get("totals") or {}

    creators = []
    for row in analytics.get("creators") or []:
        creators.append(
            _drop_none(
                {
                    "name": row.get("name") or "A creator",
                    "format": formats.get(row.get("creator_id")),
                    "reach": row.get("reach"),
                    "impressions": row.get("impressions"),
                    "engagements": row.get("engagements"),
                    "engagement_rate": row.get("engagement_rate"),
                    "fee": _positive(row.get("cost")),
                    "cost_per_thousand_reach": row.get("cost_per_thousand_reach"),
                    "measured": bool(row.get("measured")),
                }
            )
        )

    data = {
        "campaign": _drop_none(
            {
                "title": campaign.get("title"),
                "category": category_label or campaign.get("category"),
                "city": campaign.get("city"),
                "campaign_type": campaign.get("campaign_type"),
                "compensation": campaign.get("compensation_type"),
            }
        ),
        "totals": _drop_none(
            {
                "reach": totals.get("total_reach"),
                "impressions": _positive(totals.get("total_impressions")),
                "views": _positive(totals.get("total_views")),
                "engagements": _positive(totals.get("total_engagements")),
                "engagement_rate": totals.get("engagement_rate"),
                "spend": _positive(totals.get("total_spend")),
                "cost_per_thousand_reach": totals.get("cost_per_thousand_reach"),
            }
        ),
        "creators": creators,
    }
    if versus:
        baseline = {"campaigns_before": versus.get("campaigns_before")}
        for key in ("reach", "engagement_rate", "cost_per_thousand_reach"):
            delta = versus.get(key)
            if delta:
                baseline[key] = _drop_none(
                    {
                        "this_campaign": delta.get("value"),
                        "earlier_average": delta.get("previous"),
                        "change_percent": delta.get("change_percent"),
                        "better": delta.get("better"),
                    }
                )
        data["baseline"] = baseline
    data["derived"] = derive(data)
    return data


def _rate(engagements: float, reach: float) -> Optional[float]:
    return round(engagements / reach * 100, 2) if reach else None


def _cpm(fees: float, reach: float) -> Optional[float]:
    return round(fees / reach * 1000, 2) if reach and fees else None


def derive(data: dict) -> dict:
    """Every figure the model may need that is not a field. Pure.

    Aggregates are computed from the sums, never averaged from per-post rates —
    the arithmetic and the reason `_rollup_performance` holds.
    """
    creators = data.get("creators") or []
    measured = [c for c in creators if c.get("reach")]
    total_reach = sum(c["reach"] for c in measured)

    out: dict = {
        "posts_total": len(creators),
        "posts_measured": len(measured),
        "posts_unmeasured": len(creators) - len(measured),
    }
    if measured:
        out["average_reach_per_measured_post"] = round(total_reach / len(measured))
        top = max(measured, key=lambda c: c["reach"])
        if total_reach:
            out["top_creator_share_of_reach_percent"] = round(top["reach"] / total_reach * 100, 1)
    cpm = (data.get("totals") or {}).get("cost_per_thousand_reach")
    if cpm is not None:
        out["cost_per_thousand_reach"] = cpm

    groups: dict = {}
    for c in creators:
        groups.setdefault(c.get("format") or "unspecified", []).append(c)
    by_format = []
    for label, rows in groups.items():
        got = [r for r in rows if r.get("reach")]
        reach = sum(r["reach"] for r in got)
        engaged = [r for r in got if r.get("engagements") is not None]
        paid = [r for r in got if r.get("fee")]
        by_format.append(
            _drop_none(
                {
                    "format": label,
                    "posts": len(rows),
                    "posts_measured": len(got),
                    "average_reach": round(reach / len(got)) if got else None,
                    "engagement_rate": _rate(
                        sum(r["engagements"] for r in engaged),
                        sum(r["reach"] for r in engaged),
                    ),
                    "cost_per_thousand_reach": _cpm(
                        sum(r["fee"] for r in paid), sum(r["reach"] for r in paid)
                    ),
                }
            )
        )
    out["by_format"] = by_format
    return out


def post_counts(data: dict) -> tuple[int, int]:
    d = data.get("derived") or {}
    return int(d.get("posts_measured") or 0), int(d.get("posts_total") or 0)


def input_digest(data: dict) -> str:
    """The cache key: the input and the prompt that would read it. A reworded
    prompt is a different summary, so it is a different key."""
    canonical = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(f"{PROMPT.version}\n{canonical}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------

_SCALE = {
    "k": 1e3, "thousand": 1e3,
    "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
    "m": 1e6, "mn": 1e6, "million": 1e6,
    "cr": 1e7, "crore": 1e7, "crores": 1e7,
}

_NUMBER = re.compile(
    r"""
    (?P<cur>₹\s?|\bRs\.?\s?|\bINR\s?)?
    (?<![\d.,])
    (?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    (?:
        (?P<sfx>k|l|m|mn|cr)(?![a-z])
      | \s?(?P<word>thousand|lakhs?|lacs?|crores?|million)\b
    )?
    (?P<ord>st|nd|rd|th)?
    (?P<pct>\s?(?:%|percent\b|per\s?cent\b))?
    (?P<mult>(?:x|×)(?![a-z])|\s?(?:times|fold)\b|-fold\b)?
    """,
    re.I | re.X,
)

_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_WORD_NUMBER = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.I)

# "cost per 1,000 people reached" is the name of a measure, not a figure.
_UNIT_PHRASE = re.compile(r"\bper\s+(?:1,000|1000|1k|thousand)\b", re.I)

# Measures this input never carries. Naming one tells a brand we measured it.
_ABSENT_MEASURES = {
    "sales": r"\bsales\b",
    "revenue": r"\brevenue\b",
    "footfall": r"\bfoot\s?falls?\b",
    "orders": r"\borders\b",
    "followers": r"\bfollowers?\b",
    "likes": r"\blikes\b",
    "comments": r"\bcomments\b",
    "saves": r"\bsaves\b",
    "clicks": r"\bclicks?\b",
    "ROI": r"\bROI\b|\breturn on investment\b",
    "conversions": r"\bconversions?\b",
    "bookings": r"\bbookings\b",
}
# Measures the input *may* carry; named only if it does.
_OPTIONAL_MEASURES = {
    "impressions": (r"\bimpressions?\b", "impressions"),
    "views": (r"\bviews\b", "views"),
}


class Found:
    __slots__ = ("raw", "value", "tol", "kind")

    def __init__(self, raw: str, value: float, tol: float, kind: str):
        self.raw, self.value, self.tol, self.kind = raw, value, tol, kind

    def __repr__(self):  # pragma: no cover — for a failing test's message
        return f"Found({self.raw!r}={self.value}±{self.tol} {self.kind})"


def extract_numbers(text: str, *, strip: tuple = ()) -> list:
    """Every number in `text`, normalised, with the tolerance its display
    implies. `strip` removes known strings (a creator called "Foodie42") first,
    so a digit inside a name is not read as a claim."""
    for s in sorted((s for s in strip if s), key=len, reverse=True):
        text = re.sub(re.escape(s), " ", text, flags=re.I)
    text = _UNIT_PHRASE.sub(" ", text)

    found = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0).strip()
        digits = m.group("num").replace(",", "")
        value = float(digits)
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        scale_word = (m.group("sfx") or m.group("word") or "").lower()
        scale = _SCALE.get(scale_word, 1.0)
        if m.group("ord"):
            found.append(Found(raw, value, 0.0, "ordinal"))
            continue
        if scale != 1.0:
            # "1.49L" is any value that displays as 1.49 lakh.
            tol = 0.5 * 10 ** -decimals * scale
        elif decimals:
            tol = 0.5 * 10 ** -decimals
        else:
            # "1,49,000" for 1,48,932: trailing zeros are rounding, but never
            # by more than half a percent, or "100" would vouch for 60.
            trailing = len(digits) - len(digits.rstrip("0")) if value else 0
            tol = min(0.5 * 10 ** trailing, max(0.5, 0.005 * value))
        # **A multiple is a ratio, and no field is one.** "3x the reach" is a
        # claim about two numbers divided, and the 3 in it would otherwise be
        # vouched for by any count of three in the data — which is exactly how
        # the first version of this let "3x" through on a campaign with three
        # measured posts. Nothing in the input is of this kind, so every
        # multiple is rejected; the prompt says the same.
        kind = (
            "multiple" if m.group("mult")
            else "percent" if m.group("pct")
            else "money" if m.group("cur")
            else "plain"
        )
        found.append(Found(raw, value * scale, tol, kind))
    for m in _WORD_NUMBER.finditer(text):
        found.append(Found(m.group(0), float(_WORDS[m.group(0).lower()]), 0.0, "plain"))
    return found


def _kind_of(path: str) -> str:
    leaf = path.rsplit(".", 1)[-1]
    if "percent" in leaf or "rate" in path:
        return "percent"
    if any(w in path for w in ("fee", "spend", "cost")):
        return "money"
    return "count"


def allowed_values(data: dict) -> list:
    """Every number in the input and the derived block, with the kind its
    path says it is. Booleans are not numbers."""
    out = []

    def walk(node, path):
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            out.append((path, abs(float(node)), _kind_of(path)))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(data, "")
    return out


def _strings_in(data) -> list:
    out = []
    if isinstance(data, dict):
        for v in data.values():
            out += _strings_in(v)
    elif isinstance(data, list):
        for v in data:
            out += _strings_in(v)
    elif isinstance(data, str) and re.search(r"\d", data):
        out.append(data)
    return out


_PATH_TOKEN = re.compile(r"([A-Za-z_][\w]*)|\[(\d+)\]")


def resolve(data: dict, path: str):
    """The value at `totals.reach` / `creators[2].fee`, or a sentinel."""
    node: Any = data
    pos = 0
    path = path.strip()
    while pos < len(path):
        if path[pos] == ".":
            pos += 1
            continue
        m = _PATH_TOKEN.match(path, pos)
        if not m:
            return _MISSING
        pos = m.end()
        if m.group(1) is not None:
            if not isinstance(node, dict) or m.group(1) not in node:
                return _MISSING
            node = node[m.group(1)]
        else:
            i = int(m.group(2))
            if not isinstance(node, list) or i >= len(node):
                return _MISSING
            node = node[i]
    return node


_MISSING = object()


def _matches(found: Found, values: list) -> bool:
    if found.kind == "multiple":
        return False
    for _path, value, kind in values:
        if found.kind == "percent" and kind != "percent":
            continue
        if found.kind == "money" and kind != "money":
            continue
        if abs(found.value - value) <= found.tol + 1e-9:
            return True
    return False


def ground(summary: CampaignSummary, data: dict) -> list:
    """Every reason this summary may not be shown. Empty means grounded."""
    problems = []
    values = allowed_values(data)
    strip = tuple(_strings_in(data))
    creators = len(data.get("creators") or [])
    measured, total = post_counts(data)

    points = (
        [("headline", summary.headline, [])]
        + [(f"worked[{i}]", p.text, p.evidence) for i, p in enumerate(summary.worked)]
        + [(f"didnt[{i}]", p.text, p.evidence) for i, p in enumerate(summary.didnt)]
        + [(f"next[{i}]", p.text, p.evidence) for i, p in enumerate(summary.next)]
    )

    seen_numbers: list = []
    for where, text, evidence in points:
        for f in extract_numbers(text, strip=strip):
            seen_numbers.append(f)
            if f.kind == "ordinal":
                if not (1 <= f.value <= max(creators, 1)):
                    problems.append(f'{where}: "{f.raw}" is not a position in the creator list')
                continue
            # "one creator", "0 complaints": the two numbers any sentence uses.
            if f.kind == "plain" and f.value in (0.0, 1.0):
                continue
            if not _matches(f, values):
                problems.append(
                    f'{where}: the number "{f.raw}" is not in the data — quote only '
                    "values given, or rounded displays of them"
                )
        for path in evidence:
            value = resolve(data, path)
            if value is _MISSING or value is None or value == [] or value == {}:
                problems.append(f'{where}: evidence path "{path}" does not exist in the data')
        for name, pattern in _ABSENT_MEASURES.items():
            if re.search(pattern, text, re.I):
                problems.append(f"{where}: mentions {name}, which is not in the data")
        for name, (pattern, field) in _OPTIONAL_MEASURES.items():
            if re.search(pattern, text, re.I) and not (data.get("totals") or {}).get(field):
                problems.append(f"{where}: mentions {name}, which is not in the data")
        if "baseline" not in data and re.search(
            r"\b(last|previous|earlier|past) campaigns?\b", text, re.I
        ):
            problems.append(f"{where}: compares with earlier campaigns, but there are none")

    if measured < total:
        said = {f.value for f in seen_numbers if f.kind == "plain"}
        if float(measured) not in said or float(total) not in said:
            problems.append(
                f"only {measured} of {total} posts were measured — say so in the "
                "headline or the first worked point, naming both numbers"
            )
    return problems


def summary_text(summary: CampaignSummary) -> str:
    """Everything a person will read, joined — for tests and the leak sweep."""
    parts = [summary.headline]
    for p in summary.worked + summary.didnt + summary.next:
        parts.append(p.text)
    return "\n".join(parts)
