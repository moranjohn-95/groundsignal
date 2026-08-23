import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite
from typing import Literal

from .planning_classifier import PlanningApplicationCategory


OpportunityLevel = Literal[
    "very_high",
    "high",
    "medium",
    "low",
    "very_low",
]


CATEGORY_FIT_SCORES: dict[PlanningApplicationCategory, int] = {
    "industrial": 10,
    "commercial": 10,
    "energy": 10,
    "mixed_use": 9,
    "residential": 7,
    "infrastructure": 7,
    "other": 3,
}


@dataclass(frozen=True)
class OpportunityScoreBreakdown:
    project_scope: int
    electrical_relevance: int
    project_scale: int
    lead_timing: int
    category_fit: int

    @property
    def total(self) -> int:
        return (
            self.project_scope
            + self.electrical_relevance
            + self.project_scale
            + self.lead_timing
            + self.category_fit
        )


@dataclass(frozen=True)
class OpportunityScoreResult:
    opportunity_score: int
    opportunity_level: OpportunityLevel
    score_breakdown: OpportunityScoreBreakdown
    reasons: tuple[str, ...]


_ANCILLARY_SCOPE_MARKERS = (
    "permission is also sought for",
    "permission also sought for",
)

_MEANINGFUL_SCOPE_PHRASES = (
    "extension",
    "extensions",
    "refurbishment",
    "refurbish",
    "renovation",
    "renovate",
    "conversion",
    "convert",
    "change of use",
    "fit out",
    "fitout",
)

_SMALL_SCOPE_PHRASES = (
    "alteration",
    "alterations",
    "upgrade",
    "upgrades",
    "replacement",
    "replace",
    "minor amendment",
    "minor amendments",
)

_MAJOR_SCOPE_PHRASES = (
    "new development",
    "new building",
    "new buildings",
    "new dwelling",
    "new dwellings",
    "new house",
    "new houses",
    "new apartment",
    "new apartments",
    "new hotel",
    "new warehouse",
    "new factory",
    "new facility",
    "mixed use development",
    "residential development",
    "commercial development",
    "industrial development",
    "solar farm",
    "wind farm",
    "battery energy storage",
)

_MAJOR_SCOPE_ACTION_PATTERN = re.compile(
    r"\b(?:construction|construct|erection|erect|development|develop)\b"
)

_MINOR_SCOPE_PATTERN = re.compile(
    r"\b(?:retention|construction|installation|replacement|replace|"
    r"alteration|alterations)\b"
    r"(?:\s+\w+){0,6}\s+"
    r"(?:advertising\s+)?(?:signage|signs?|boundary|boundaries|"
    r"boundary\s+walls?|light\s+fittings?|lighting\s+fixtures?)\b"
)

_ERECT_SIGNAGE_PATTERN = re.compile(
    r"\b(?:erect|erection\s+of)\s+"
    r"(?:(?:a|an|the|new|standalone|freestanding|free\s+standing|"
    r"advertising|commercial|illuminated)\s+){0,4}"
    r"(?:signage|signs?)\b"
)

_MINOR_LIGHTING_PATTERN = re.compile(
    r"\b(?:replacement\s+of|replace)\s+(?:one|1|a|an)\s+"
    r"(?:external\s+)?(?:light|lighting)\s+(?:fitting|fixture)\b"
)

_EXPLICIT_UNIT_COUNT_PATTERN = re.compile(
    r"\b(?P<count>\d+)\s+(?:no\s+)?"
    r"(?:residential\s+units?|dwellings?|houses?|apartments?|"
    r"(?:own\s+door\s+)?(?:maisonette|apartment|duplex)"
    r"(?:\s+(?:maisonette|apartment|duplex))*\s+units?)\b"
)

_EXPLICIT_FLOOR_AREA_PATTERN = re.compile(
    r"\b(?P<area>\d+(?:\.\d+)?)\s+(?:sqm|sq\s+m|m2)\b"
)

_EV_CHARGING_PHRASES = (
    "ev charging",
    "electric vehicle charging",
    "vehicle charging infrastructure",
    "charging points",
    "charging stations",
)

_BATTERY_ENERGY_PHRASES = (
    "battery energy storage",
    "battery storage facility",
    "battery storage development",
)

_SUBSTATION_PHRASES = (
    "electrical substation",
    "electricity substation",
    "esb substation",
    "substation",
    "substations",
)

_EXPLICIT_ELECTRICAL_PHRASES = (
    "electrical works",
    "electrical infrastructure",
    "electrical installation",
    "electrical installations",
    "electrical upgrade",
    "electrical upgrades",
)

_RENEWABLE_INSTALLATION_PHRASES = (
    "solar",
    "photovoltaic",
    "wind turbine",
    "wind turbines",
    "wind farm",
)

_SIGNIFICANT_LIGHTING_PHRASES = (
    "floodlighting",
    "flood lights",
    "street lighting",
    "public lighting",
    "lighting installation",
    "lighting installations",
    "external lighting scheme",
    "car park lighting",
)

_PLANT_OR_EQUIPMENT_PHRASES = (
    "plant",
    "equipment",
    "switch room",
    "switchroom",
)


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _normalize_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _primary_scope_text(
    description: str | None,
    application_type: str | None,
) -> str:
    description_text = _normalize_text(description)
    marker_positions = [
        position
        for marker in _ANCILLARY_SCOPE_MARKERS
        if (position := description_text.find(marker)) >= 0
    ]
    if marker_positions:
        description_text = description_text[: min(marker_positions)].strip()

    application_type_text = _normalize_text(application_type)
    return " ".join(
        text for text in (description_text, application_type_text) if text
    )


def _major_scope_reason(category: PlanningApplicationCategory) -> str:
    labels = {
        "commercial": "New commercial development",
        "industrial": "New industrial development",
        "energy": "New energy development",
        "mixed_use": "New mixed-use development",
        "residential": "New residential development",
    }
    return labels.get(category, "Substantial new development")


def _score_project_scope(
    primary_text: str,
    category: PlanningApplicationCategory,
) -> tuple[int, str | None]:
    if not primary_text:
        return 0, None

    if _MINOR_SCOPE_PATTERN.search(primary_text) or _ERECT_SIGNAGE_PATTERN.search(
        primary_text
    ):
        return 5, "Minor signage, boundary or lighting works"

    if primary_text.startswith("retention ") or primary_text == "retention":
        return 5, "Retention application"

    meaningful_positions = [
        primary_text.find(phrase)
        for phrase in _MEANINGFUL_SCOPE_PHRASES
        if primary_text.find(phrase) >= 0
    ]
    major_match = _MAJOR_SCOPE_ACTION_PATTERN.search(primary_text)
    has_major_phrase = _contains_any_phrase(primary_text, _MAJOR_SCOPE_PHRASES)
    first_meaningful = min(meaningful_positions) if meaningful_positions else None

    construction_of_meaningful_work = re.search(
        r"\b(?:construction|provision)\s+of\b"
        r"(?:\s+\w+){0,5}\s+"
        r"(?:extension|refurbishment|conversion|fit\s+out)\b",
        primary_text,
    )
    if construction_of_meaningful_work or (
        first_meaningful is not None
        and (major_match is None or first_meaningful < major_match.start())
    ):
        if _contains_phrase(primary_text, "change of use") or _contains_any_phrase(
            primary_text,
            ("conversion", "convert", "fit out", "fitout"),
        ):
            return 20, "Conversion or change of use"
        return 20, "Meaningful extension or refurbishment"

    small_positions = [
        primary_text.find(phrase)
        for phrase in _SMALL_SCOPE_PHRASES
        if primary_text.find(phrase) >= 0
    ]
    first_small = min(small_positions) if small_positions else None
    if first_small is not None and (
        major_match is None or first_small < major_match.start()
    ):
        return 10, "Smaller alterations or upgrades"

    if has_major_phrase or major_match is not None:
        return 30, _major_scope_reason(category)

    if first_meaningful is not None:
        return 20, "Meaningful extension, refurbishment or conversion"
    if first_small is not None:
        return 10, "Smaller alterations or upgrades"
    return 0, None


def _score_units(units: int) -> tuple[int, str]:
    if units >= 50:
        return 20, "Large residential unit count"
    if units >= 20:
        return 16, "Significant residential unit count"
    if units >= 10:
        return 12, "Multi-unit residential development"
    if units >= 2:
        return 8, "Multiple residential units"
    return 4, "Single residential unit"


def _score_floor_area(floor_area: float) -> tuple[int, str]:
    if floor_area >= 5000:
        return 20, "Very large floor area"
    if floor_area >= 2000:
        return 16, "Large floor area"
    if floor_area >= 500:
        return 12, "Substantial floor area"
    if floor_area >= 100:
        return 8, "Moderate floor area"
    return 4, "Small recorded floor area"


def _valid_units(value: int | None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _valid_floor_area(value: float | None) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value <= 0
    ):
        return None
    return float(value)


def _textual_units(text: str) -> int | None:
    match = _EXPLICIT_UNIT_COUNT_PATTERN.search(text)
    return int(match.group("count")) if match else None


def _textual_floor_area(text: str) -> float | None:
    match = _EXPLICIT_FLOOR_AREA_PATTERN.search(text)
    return float(match.group("area")) if match else None


def _score_project_scale(
    text: str,
    number_residential_units: int | None,
    floor_area: float | None,
) -> tuple[int, str | None]:
    units = _valid_units(number_residential_units)
    area = _valid_floor_area(floor_area)
    if units is None:
        units = _textual_units(text)
    if area is None:
        area = _textual_floor_area(text)

    evidence = []
    if units is not None:
        evidence.append(_score_units(units))
    if area is not None:
        evidence.append(_score_floor_area(area))
    return max(evidence, key=lambda item: item[0]) if evidence else (0, None)


def _score_electrical_relevance(
    text: str,
    category: PlanningApplicationCategory,
    project_scope: int,
    project_scale: int,
    has_large_residential_unit_count: bool,
) -> tuple[int, str | None]:
    if _MINOR_LIGHTING_PATTERN.search(text):
        return 5, "Minor lighting replacement"
    if _contains_any_phrase(text, _EV_CHARGING_PHRASES):
        return 30, "EV charging infrastructure identified"
    if _contains_any_phrase(text, _BATTERY_ENERGY_PHRASES):
        return 30, "Battery energy storage identified"
    if _contains_any_phrase(text, _SUBSTATION_PHRASES):
        return 30, "Electrical substation identified"
    if _contains_any_phrase(text, _EXPLICIT_ELECTRICAL_PHRASES):
        return 30, "Explicit electrical works identified"
    if _contains_any_phrase(text, _RENEWABLE_INSTALLATION_PHRASES):
        return 25, "Renewable electrical installation identified"
    if _contains_any_phrase(text, _SIGNIFICANT_LIGHTING_PHRASES):
        return 20, "Significant lighting installation identified"
    if (
        project_scope >= 20
        and category != "residential"
        and _contains_any_phrase(text, _PLANT_OR_EQUIPMENT_PHRASES)
    ):
        return 15, "Plant or electrical equipment identified"
    if project_scope >= 20 and category in ("commercial", "industrial"):
        return 12, "Electrical work implied by substantial business development"
    if category in ("residential", "mixed_use") and (
        (project_scope == 30 and project_scale >= 12)
        or (project_scope >= 10 and has_large_residential_unit_count)
    ):
        return 15, "Electrical work implied by large residential development"
    return 0, None


def _score_lead_timing(
    received_date: date | None,
    current_date: date,
) -> tuple[int, str | None]:
    if received_date is None:
        return 0, None

    age_days = (current_date - received_date).days
    if age_days < 0:
        return 0, None
    if age_days <= 14:
        return 10, "Application received within the last 14 days"
    if age_days <= 30:
        return 8, "Application received within the last 30 days"
    if age_days <= 60:
        return 5, "Application received within the last 60 days"
    if age_days <= 90:
        return 2, "Application received within the last 90 days"
    return 0, None


def opportunity_level_for_score(score: int) -> OpportunityLevel:
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("score must be an integer between 0 and 100")
    if score >= 80:
        return "very_high"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "very_low"


def score_planning_application_opportunity(
    description: str | None = None,
    application_type: str | None = None,
    number_residential_units: int | None = None,
    floor_area: float | None = None,
    received_date: date | None = None,
    category: PlanningApplicationCategory = "other",
    *,
    current_date: date | None = None,
) -> OpportunityScoreResult:
    """Score an electrician lead from planning values without persistence."""
    if category not in CATEGORY_FIT_SCORES:
        raise ValueError(f"Unsupported planning category: {category}")

    current_date = _current_utc_date() if current_date is None else current_date
    primary_text = _primary_scope_text(description, application_type)
    full_text = " ".join(
        text
        for text in (
            _normalize_text(description),
            _normalize_text(application_type),
        )
        if text
    )

    project_scope, scope_reason = _score_project_scope(primary_text, category)
    project_scale, scale_reason = _score_project_scale(
        full_text,
        number_residential_units,
        floor_area,
    )
    residential_units = _valid_units(number_residential_units)
    if residential_units is None:
        residential_units = _textual_units(full_text)
    electrical_relevance, electrical_reason = _score_electrical_relevance(
        full_text,
        category,
        project_scope,
        project_scale,
        residential_units is not None and residential_units >= 10,
    )
    lead_timing, timing_reason = _score_lead_timing(
        received_date,
        current_date,
    )
    category_fit = CATEGORY_FIT_SCORES[category]
    category_reason = f"{category.replace('_', ' ').title()} category fit"

    score_breakdown = OpportunityScoreBreakdown(
        project_scope=project_scope,
        electrical_relevance=electrical_relevance,
        project_scale=project_scale,
        lead_timing=lead_timing,
        category_fit=category_fit,
    )
    reasons = tuple(
        reason
        for reason in (
            scope_reason,
            electrical_reason,
            scale_reason,
            timing_reason,
            category_reason,
        )
        if reason is not None
    )

    return OpportunityScoreResult(
        opportunity_score=score_breakdown.total,
        opportunity_level=opportunity_level_for_score(score_breakdown.total),
        score_breakdown=score_breakdown,
        reasons=reasons,
    )
