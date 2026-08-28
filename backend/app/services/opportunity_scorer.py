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

OpportunityScoreComponentName = Literal[
    "project_scope",
    "electrical_relevance",
    "project_scale",
    "lead_timing",
    "category_fit",
]

ElectricalEvidenceLevel = Literal["direct", "possible", "inferred", "unavailable"]
ElectricalWorkType = Literal[
    "ev_charging",
    "substation_distribution",
    "battery_storage",
    "renewable_generation",
    "lighting",
    "electrical_installation",
    "electrical_plant_equipment",
]

SCORE_COMPONENT_MAXIMUMS: dict[OpportunityScoreComponentName, int] = {
    "project_scope": 30,
    "electrical_relevance": 30,
    "project_scale": 20,
    "lead_timing": 10,
    "category_fit": 10,
}


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
class OpportunityScoreComponent:
    name: OpportunityScoreComponentName
    points_awarded: int
    maximum_points: int
    explanation: str


@dataclass(frozen=True)
class ElectricalWorkSignal:
    work_type: ElectricalWorkType
    evidence: str


@dataclass(frozen=True)
class ElectricalWorkBrief:
    evidence_level: ElectricalEvidenceLevel
    summary: str
    signals: tuple[ElectricalWorkSignal, ...]


@dataclass(frozen=True)
class _ElectricalAssessment:
    evidence_level: ElectricalEvidenceLevel
    signals: tuple[ElectricalWorkSignal, ...]
    score: int
    reason: str | None
    explanation: str
    brief_summary: str


@dataclass(frozen=True)
class OpportunityScoreResult:
    opportunity_score: int
    opportunity_level: OpportunityLevel
    score_breakdown: OpportunityScoreBreakdown
    score_components: tuple[OpportunityScoreComponent, ...]
    reasons: tuple[str, ...]
    electrical_work_brief: ElectricalWorkBrief


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

_SITE_ONLY_SCOPE_PHRASES = (
    "car park",
    "car parks",
    "car parking",
    "parking area",
    "parking areas",
    "road",
    "roads",
    "access road",
    "access roads",
    "service road",
    "service roads",
    "turning area",
    "turning areas",
    "play area",
    "play areas",
    "playground",
    "playgrounds",
    "garden",
    "gardens",
    "landscaping",
    "entrance",
    "entrances",
    "boundary",
    "boundaries",
    "boundary wall",
    "boundary walls",
    "fence",
    "fences",
    "footpath",
    "footpaths",
    "hardstanding",
    "drainage",
    "ancillary site works",
    "site works",
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
    r"\b(?P<count>\d+)\s*(?:no\s*)?"
    r"(?:residential\s+units?|dwellings?(?:\s+(?:houses?|units?))?|"
    r"houses?(?:\s+units?)?|apartments?(?:\s+units?)?|"
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
    "ev charge points",
    "electric vehicle charge points",
    "ev charging infrastructure",
    "electric vehicle charging infrastructure",
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
    "transformer substation",
    "substation infrastructure",
    "substation and switch room",
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
    "solar pv",
    "solar photovoltaic",
    "solar panels",
    "photovoltaic panels",
    "solar farm",
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
    "electrical plant",
    "switch room",
    "switchroom",
    "switchgear",
    "transformer",
)

_EXPLICIT_ELECTRICAL_EQUIPMENT_PHRASES = ("electrical equipment",)

_INSTITUTIONAL_BUILDING_PHRASES = (
    "school",
    "community centre",
    "community center",
    "community building",
    "public library",
)

_SUBSTANTIAL_EXTENSION_PHRASES = (
    "substantial extension",
    "major extension",
    "two storey extension",
    "extension and refurbishment",
    "new classroom block",
)

_NEW_RESIDENTIAL_DEVELOPMENT_PATTERN = re.compile(
    r"\b(?:construction|construct|erection|erect|development|develop)\b"
    r"(?:\s+of)?"
    r"(?:\s+(?:a|an|the|new|one|no|\d+(?:\s*no)?|detached|semi\s+detached|"
    r"terraced|own\s+door|dwelling|house|apartment|storey|storeys|building|"
    r"buildings|consisting|of)){0,16}"
    r"\s+(?:dwellings?|houses?|apartments?)(?:\s+units?)?\b"
)

_NEW_SINGLE_DWELLING_PROPOSAL_PATTERN = re.compile(
    r"\b(?:construction|construct|erection|erect|development|develop)\b"
    r"(?:\s+of)?\s+"
    r"(?:(?:a|an|one|1)\s+)?(?:new\s+)?"
    r"(?:(?:detached|semi\s+detached|terraced)\s+)?"
    r"(?:dwelling(?:\s+house)?|house)\b"
)

_INSTITUTIONAL_BUILDING_TERM_PATTERN = (
    r"(?:school(?:\s+building)?|community\s+(?:centre|center|building)|"
    r"public\s+library)"
)

_NEW_INSTITUTIONAL_BUILDING_PATTERN = re.compile(
    r"\b(?:construction|construct|erection|erect|development|develop)"
    r"\s+(?:of\s+)?(?:(?:a|an|the)\s+)?(?:new\s+)?"
    r"(?:(?:primary|secondary)\s+)?"
    + _INSTITUTIONAL_BUILDING_TERM_PATTERN
    + r"(?!\s+(?:car\s+park|parking|road|turning\s+area|play\s+area|"
    r"playground|garden|landscaping|entrance|boundary|site\s+works))"
)

_INSTITUTIONAL_BUILDING_EXTENSION_PATTERN = re.compile(
    r"\b(?:extension|refurbishment|refurbish)\s+(?:to|of)\s+"
    r"(?:(?:a|an|the)\s+)?(?:existing\s+)?(?:(?:primary|secondary)\s+)?"
    + _INSTITUTIONAL_BUILDING_TERM_PATTERN
    + r"|\b"
    + _INSTITUTIONAL_BUILDING_TERM_PATTERN
    + r"\s+(?:building\s+)?(?:extension|refurbishment)\b"
)

_POSSIBLE_BUILDING_CONTEXT_PHRASES = (
    "dwelling",
    "dwelling house",
    "house",
    "apartment",
    "cottage",
    "building",
    "premises",
    "unit",
    "garage",
    "store",
    "workshop",
    "shed",
    "outbuilding",
    "garden room",
    "home office",
    "ancillary accommodation",
    "conservatory",
    "porch",
    "utility room",
    "attic",
    "office",
    "retail unit",
    "shop",
    "hotel",
    "restaurant",
    "clinic",
    "medical centre",
    "school",
    "classroom",
    "community centre",
    "community center",
    "public library",
    "room",
)

_POSSIBLE_ENCLOSED_BUILDING_OBJECT_PATTERN = (
    r"(?:dwelling(?:\s+house)?|house|apartment|cottage|garage|store|workshop|"
    r"shed|outbuilding|garden\s+room|home\s+office|ancillary\s+accommodation|"
    r"conservatory|porch|utility\s+room|attic(?:\s+room|\s+conversion)?|"
    r"building|office|retail\s+unit|shop|clinic|medical\s+centre|"
    r"hotel|restaurant|"
    r"community\s+(?:centre|center|building)|school(?:\s+building)?|"
    r"classroom|room)"
)

_PROPOSED_ENCLOSED_BUILDING_PATTERN = re.compile(
    r"\b(?:construction\s+of|construct|erection\s+of|erect|build|rebuild|"
    r"provide|addition\s+of|add)\b"
    r"(?:\s+\w+){0,4}\s+"
    + _POSSIBLE_ENCLOSED_BUILDING_OBJECT_PATTERN
    + r"\b(?!\s+(?:car\s+park|parking|play\s+area|playground|garden|"
    r"boundary|entrance|road|footpath|hardstanding))"
)

_NEW_ENCLOSED_BUILDING_PATTERN = re.compile(
    r"\bnew\s+(?:(?:detached|domestic|ancillary)\s+){0,3}"
    + _POSSIBLE_ENCLOSED_BUILDING_OBJECT_PATTERN
    + r"\b(?!\s+(?:car\s+park|parking|play\s+area|playground|garden|"
    r"boundary|entrance|road|footpath|hardstanding))"
)

_BUILDING_ENLARGEMENT_PATTERN = re.compile(
    r"\bextension\b(?:\s+\w+){0,10}\s+(?:to|of|at|on)\s+"
    r"(?:(?:a|an|the|existing|new|rear|front|side|north|south|east|west|"
    r"detached|semi\s+detached)\s+){0,6}"
    + _POSSIBLE_ENCLOSED_BUILDING_OBJECT_PATTERN
    + r"\b"
    r"|\b"
    + _POSSIBLE_ENCLOSED_BUILDING_OBJECT_PATTERN
    + r"\s+(?:building\s+)?extension\b"
)

_HABITABLE_EXTENSION_FEATURE_PATTERN = re.compile(
    r"\bextension\b(?:\s+\w+){0,8}\s+"
    r"(?:attic\s+space|bedrooms?|bathrooms?|kitchen|living\s+(?:room|area)|"
    r"habitable\s+(?:space|accommodation))\b"
)

_ANCILLARY_SITE_OR_STRUCTURE_PHRASES = (
    "car port",
    "carpark",
    "car park",
    "parking",
    "shed",
    "garden",
    "boundary",
    "driveway",
    "entrance",
    "site works",
)

_SUBSTANTIVE_BUILDING_WORK_PHRASES = (
    "renovation",
    "renovate",
    "refurbishment",
    "refurbish",
    "fit out",
    "fitout",
    "conversion",
    "convert",
    "change of use",
    "internal alterations",
    "internal modification",
    "attic conversion",
)

_NON_INTERNAL_BUILDING_WORK_PHRASES = tuple(
    phrase
    for phrase in _SUBSTANTIVE_BUILDING_WORK_PHRASES
    if phrase not in {"internal alterations", "internal modification"}
)

_MECHANICAL_BUILDING_SERVICE_PHRASES = (
    "mechanical plant",
    "mechanical treatment unit",
    "mechanical treatment plant",
)

_NON_RESIDENTIAL_BUILDING_CONSTRUCTION_PATTERN = re.compile(
    r"\b(?:construction|construct|erection|erect|development|develop)"
    r"\s+(?:of\s+)?"
    r"(?:(?:a|an|the|new|commercial|industrial|office|retail|school|"
    r"community|public|staff|accommodation)\s+){0,6}"
    r"(?:building|buildings|warehouse|warehouses|factory|factories|"
    r"facility|facilities|hotel|hotels|office|offices|shops?|retail\s+unit|"
    r"accommodation\s+lodges?|community\s+(?:centre|center|building)|"
    r"public\s+library)\b"
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


def _is_incidental_or_negated_electrical_reference(text: str, start: int) -> bool:
    preceding_words = text[:start].split()[-5:]
    return any(
        word
        in {
            "no", "not", "without", "exclude", "excluding", "existing",
            "retention", "retained", "remove", "removed", "removal",
            "demolish", "demolition", "decommission", "decommissioned",
        }
        for word in preceding_words
    )


def _first_supported_electrical_phrase(
    text: str,
    phrases: tuple[str, ...],
) -> str | None:
    for phrase in phrases:
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text):
            if not _is_incidental_or_negated_electrical_reference(text, match.start()):
                return phrase
    return None


def _direct_electrical_signals(
    text: str,
    *,
    category: PlanningApplicationCategory,
    project_scope: int,
) -> tuple[ElectricalWorkSignal, ...]:
    signals: list[ElectricalWorkSignal] = []

    for work_type, phrases in (
        ("ev_charging", _EV_CHARGING_PHRASES),
        ("battery_storage", _BATTERY_ENERGY_PHRASES),
        ("substation_distribution", _SUBSTATION_PHRASES),
        ("electrical_installation", _EXPLICIT_ELECTRICAL_PHRASES),
        ("electrical_plant_equipment", _EXPLICIT_ELECTRICAL_EQUIPMENT_PHRASES),
        ("renewable_generation", _RENEWABLE_INSTALLATION_PHRASES),
        ("lighting", _SIGNIFICANT_LIGHTING_PHRASES),
    ):
        matched_phrase = _first_supported_electrical_phrase(text, phrases)
        if matched_phrase is not None:
            signals.append(ElectricalWorkSignal(work_type, matched_phrase))

    if project_scope >= 20 and category != "residential":
        matched_phrase = _first_supported_electrical_phrase(
            text,
            _PLANT_OR_EQUIPMENT_PHRASES,
        )
        if matched_phrase is not None:
            signals.append(
                ElectricalWorkSignal("electrical_plant_equipment", matched_phrase)
            )

    return tuple(signals)


def _signal_for(
    signals: tuple[ElectricalWorkSignal, ...],
    work_type: ElectricalWorkType,
) -> ElectricalWorkSignal | None:
    return next(
        (signal for signal in signals if signal.work_type == work_type),
        None,
    )


def _has_ancillary_extension_context(text: str, start: int, end: int) -> bool:
    """Keep site-only extensions from qualifying as enclosed building work."""
    context = text[max(0, start - 32) : min(len(text), end + 32)]
    return _contains_any_phrase(context, _ANCILLARY_SITE_OR_STRUCTURE_PHRASES)


def _has_enclosed_building_enlargement(text: str) -> bool:
    """Recognise building enlargement, without treating site work as an extension."""
    for match in _BUILDING_ENLARGEMENT_PATTERN.finditer(text):
        if not _has_ancillary_extension_context(text, match.start(), match.end()):
            return True
    return _has_habitable_extension_feature(text)


def _has_habitable_extension_feature(text: str) -> bool:
    """Recognise a specific room or accommodation feature in an extension."""
    for match in _HABITABLE_EXTENSION_FEATURE_PATTERN.finditer(text):
        if not _has_ancillary_extension_context(text, match.start(), match.end()):
            return True
    return False


def _has_non_minor_internal_alterations(text: str) -> bool:
    return (
        _contains_phrase(text, "internal alterations")
        and not _contains_phrase(text, "minor internal alterations")
    )


def _has_substantive_building_work(text: str) -> bool:
    """Identify a proposed enclosed-building, internal, conversion, or plant scope."""
    if (
        _PROPOSED_ENCLOSED_BUILDING_PATTERN.search(text)
        or _NEW_ENCLOSED_BUILDING_PATTERN.search(text)
        or _has_enclosed_building_enlargement(text)
    ):
        return True

    if not _contains_any_phrase(text, _POSSIBLE_BUILDING_CONTEXT_PHRASES):
        return False

    return (
        _has_non_minor_internal_alterations(text)
        or _contains_any_phrase(text, _NON_INTERNAL_BUILDING_WORK_PHRASES)
        or _contains_any_phrase(text, _MECHANICAL_BUILDING_SERVICE_PHRASES)
    )


def _is_retention_only_application(primary_text: str) -> bool:
    return primary_text.startswith(
        (
            "retention",
            "permission for retention",
            "permission to retain",
            "permission sought for retention",
            "permission is sought for retention",
        )
    )


def _possible_building_electrical_assessment(
    text: str,
    *,
    primary_text: str,
) -> _ElectricalAssessment | None:
    if (
        _is_retention_only_application(primary_text)
        or _MINOR_SCOPE_PATTERN.search(primary_text)
        or _ERECT_SIGNAGE_PATTERN.search(primary_text)
        or not _has_substantive_building_work(text)
    ):
        return None

    return _ElectricalAssessment(
        "possible", (), 6,
        "Electrical work possible for substantive building work",
        "The proposal includes substantive enclosed-building, internal, "
        "conversion, or mechanical work that could require electrical work, "
        "but no electrical work is explicitly described.",
        "Possible electrical work associated with proposed building, internal, "
        "conversion, or mechanical work -- review plans for confirmation.",
    )


def _residential_electrical_assessment(
    text: str,
    *,
    category: PlanningApplicationCategory,
    project_scope: int,
    project_scale: int,
    residential_unit_count: int | None,
) -> _ElectricalAssessment | None:
    if category not in ("residential", "mixed_use"):
        return None

    is_new_residential_development = bool(
        _NEW_RESIDENTIAL_DEVELOPMENT_PATTERN.search(text)
    )
    if residential_unit_count is not None and is_new_residential_development:
        if residential_unit_count >= 10 and project_scope >= 10:
            return _ElectricalAssessment(
                "inferred", (), 15,
                "Electrical work implied by large residential development",
                "Electrical work is implied by the scale and scope of the "
                "residential development.",
                "Potential electrical package associated with a large "
                f"{category.replace('_', ' ')} development -- review plans for "
                "confirmation.",
            )
        if project_scope == 30 and residential_unit_count >= 6:
            return _ElectricalAssessment(
                "inferred", (), 12,
                "Electrical work implied by multi-dwelling development",
                "Electrical work is implied by the scope of this multi-dwelling "
                "development.",
                "Potential electrical package associated with a multi-dwelling "
                "development -- review plans for confirmation.",
            )
        if project_scope == 30 and residential_unit_count >= 2:
            return _ElectricalAssessment(
                "inferred", (), 10,
                "Electrical work implied by small multi-dwelling development",
                "Electrical work is implied by the new multi-dwelling "
                "development.",
                "Potential electrical package associated with a small "
                "multi-dwelling development -- review plans for confirmation.",
            )
        if project_scope == 30 and residential_unit_count == 1:
            return _ElectricalAssessment(
                "possible", (), 6,
                "Electrical work possible for new dwelling",
                "Electrical work is possible for the new dwelling, but it is "
                "not explicitly described.",
                "Possible electrical work associated with a new dwelling -- "
                "review plans for confirmation.",
            )

    if (
        is_new_residential_development
        and project_scope == 30
        and project_scale >= 12
    ):
        return _ElectricalAssessment(
            "inferred", (), 15,
            "Electrical work implied by large residential development",
            "Electrical work is implied by the scale and scope of the "
            "residential development.",
            "Potential electrical package associated with a large "
            f"{category.replace('_', ' ')} development -- review plans for "
            "confirmation.",
        )

    return None


def _institutional_electrical_assessment(
    text: str,
    *,
    project_scope: int,
    project_scale: int,
) -> _ElectricalAssessment | None:
    if not _contains_any_phrase(text, _INSTITUTIONAL_BUILDING_PHRASES):
        return None

    if _NEW_INSTITUTIONAL_BUILDING_PATTERN.search(text):
        return _ElectricalAssessment(
            "inferred", (), 12,
            "Electrical work implied by new institutional building",
            "Electrical work is implied by the new school or public/community "
            "building.",
            "Potential electrical package associated with a new school or "
            "public/community building -- review plans for confirmation.",
        )

    if (
        project_scope >= 20
        and _INSTITUTIONAL_BUILDING_EXTENSION_PATTERN.search(text)
        and (
            project_scale >= 8
            or _contains_any_phrase(text, _SUBSTANTIAL_EXTENSION_PHRASES)
        )
    ):
        return _ElectricalAssessment(
            "inferred", (), 10,
            "Electrical work implied by substantial institutional extension",
            "Electrical work is implied by the substantial school or "
            "public/community building extension.",
            "Potential electrical package associated with a substantial school "
            "or public/community building extension -- review plans for "
            "confirmation.",
        )

    return None


def _assess_electrical_relevance(
    text: str,
    *,
    primary_text: str,
    category: PlanningApplicationCategory,
    project_scope: int,
    project_scale: int,
    residential_unit_count: int | None,
) -> _ElectricalAssessment:
    signals = _direct_electrical_signals(
        text,
        category=category,
        project_scope=project_scope,
    )
    for work_type, score, reason, explanation in (
        ("ev_charging", 30, "EV charging infrastructure identified", "a strong electrical indicator."),
        ("battery_storage", 30, "Battery energy storage identified", "a strong electrical indicator."),
        ("substation_distribution", 30, "Electrical substation identified", "a strong electrical indicator."),
        ("electrical_installation", 30, "Explicit electrical works identified", "a strong electrical indicator."),
        ("renewable_generation", 25, "Renewable electrical installation identified", "indicating a renewable electrical installation."),
        ("lighting", 20, "Significant lighting installation identified", "indicating significant lighting work."),
        ("electrical_plant_equipment", 15, "Plant or electrical equipment identified", "in a substantial non-residential project."),
    ):
        if signal := _signal_for(signals, work_type):
            return _ElectricalAssessment(
                "direct", signals, score, reason,
                f'The planning description includes "{signal.evidence}", {explanation}',
                "",
            )
    if (
        project_scope == 30
        and category in ("commercial", "industrial")
    ):
        return _ElectricalAssessment(
            "inferred", (), 12,
            "Electrical work implied by substantial business development",
            "Electrical work is implied by the substantial commercial or industrial development scope.",
            "Potential electrical package associated with a substantial "
            f"{category} development -- review plans for confirmation.",
        )
    if assessment := _residential_electrical_assessment(
        text,
        category=category,
        project_scope=project_scope,
        project_scale=project_scale,
        residential_unit_count=residential_unit_count,
    ):
        return assessment
    if assessment := _institutional_electrical_assessment(
        text,
        project_scope=project_scope,
        project_scale=project_scale,
    ):
        return assessment
    if assessment := _possible_building_electrical_assessment(
        text,
        primary_text=primary_text,
    ):
        return assessment
    if _MINOR_LIGHTING_PATTERN.search(text):
        return _ElectricalAssessment(
            "possible", (), 5, "Minor lighting replacement",
            "The application includes replacement of one external light fitting.",
            "Possible limited electrical work: replacement of one external "
            "light fitting.",
        )
    return _ElectricalAssessment(
        "unavailable", (), 0, None,
        "No qualifying electrical work indicators were identified.",
        "Electrical work is not evidenced by the available planning data.",
    )


def _electrical_work_brief_for_assessment(
    assessment: _ElectricalAssessment,
) -> ElectricalWorkBrief:
    if assessment.evidence_level == "direct":
        labels = {
            "ev_charging": "EV charging infrastructure",
            "battery_storage": "battery storage",
            "substation_distribution": "substation or distribution infrastructure",
            "electrical_installation": "electrical installation work",
            "renewable_generation": "renewable or solar electrical infrastructure",
            "lighting": "lighting work",
            "electrical_plant_equipment": "electrical plant or equipment",
        }
        work_types = list(dict.fromkeys(signal.work_type for signal in assessment.signals))
        return ElectricalWorkBrief(
            "direct",
            "Electrical work evidenced: "
            + ", ".join(labels[work_type] for work_type in work_types) + ".",
            assessment.signals,
        )
    return ElectricalWorkBrief(
        assessment.evidence_level,
        assessment.brief_summary,
        (),
    )


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


def _has_primary_building_scope(text: str) -> bool:
    """Return whether a major-scope action is tied to a genuine building proposal."""
    return bool(
        _contains_any_phrase(text, _MAJOR_SCOPE_PHRASES)
        or _NEW_RESIDENTIAL_DEVELOPMENT_PATTERN.search(text)
        or _NEW_INSTITUTIONAL_BUILDING_PATTERN.search(text)
        or _NON_RESIDENTIAL_BUILDING_CONSTRUCTION_PATTERN.search(text)
    )


def _is_site_only_scope(text: str) -> bool:
    """Identify primary site works without a proposed building to justify major scope."""
    return _contains_any_phrase(text, _SITE_ONLY_SCOPE_PHRASES) and not (
        _has_primary_building_scope(text)
    )


def _score_project_scope(
    primary_text: str,
    category: PlanningApplicationCategory,
) -> tuple[int, str | None, str]:
    if not primary_text:
        return 0, None, "No qualifying project scope was identified."

    if _MINOR_SCOPE_PATTERN.search(primary_text) or _ERECT_SIGNAGE_PATTERN.search(
        primary_text
    ):
        return (
            5,
            "Minor signage, boundary or lighting works",
            "The application is for minor signage, boundary, or lighting works.",
        )

    if primary_text.startswith("retention ") or primary_text == "retention":
        return (
            5,
            "Retention application",
            "The application is primarily for retention of existing works.",
        )

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
            return (
                20,
                "Conversion or change of use",
                "A conversion, fit-out, or change of use was identified.",
            )
        return (
            20,
            "Meaningful extension or refurbishment",
            "A meaningful extension or refurbishment was identified.",
        )

    small_positions = [
        primary_text.find(phrase)
        for phrase in _SMALL_SCOPE_PHRASES
        if primary_text.find(phrase) >= 0
    ]
    first_small = min(small_positions) if small_positions else None
    if first_small is not None and (
        major_match is None or first_small < major_match.start()
    ):
        return (
            10,
            "Smaller alterations or upgrades",
            "Smaller alterations, upgrades, or replacement works were identified.",
        )

    if _is_site_only_scope(primary_text):
        return (
            5,
            "Site-only works",
            "The application is primarily for site works rather than a new building.",
        )

    if has_major_phrase or major_match is not None:
        reason = _major_scope_reason(category)
        return 30, reason, f"{reason} indicators were identified."

    if first_meaningful is not None:
        return (
            20,
            "Meaningful extension, refurbishment or conversion",
            "An extension, refurbishment, or conversion was identified.",
        )
    if first_small is not None:
        return (
            10,
            "Smaller alterations or upgrades",
            "Smaller alterations, upgrades, or replacement works were identified.",
        )
    return 0, None, "No qualifying project scope was identified."


def _score_units(units: int) -> tuple[int, str, str]:
    if units >= 50:
        return (
            20,
            "Large residential unit count",
            f"{units} residential units were identified, indicating a large development.",
        )
    if units >= 20:
        return (
            16,
            "Significant residential unit count",
            f"{units} residential units were identified, indicating a significant development.",
        )
    if units >= 10:
        return (
            12,
            "Multi-unit residential development",
            f"{units} residential units were identified in this multi-unit development.",
        )
    if units >= 2:
        return (
            8,
            "Multiple residential units",
            f"{units} residential units were identified.",
        )
    return 4, "Single residential unit", "A single residential unit was identified."


def _format_floor_area(floor_area: float) -> str:
    return (
        f"{floor_area:,.0f}"
        if floor_area.is_integer()
        else f"{floor_area:,.1f}"
    )


def _score_floor_area(floor_area: float) -> tuple[int, str, str]:
    displayed_area = _format_floor_area(floor_area)
    if floor_area >= 5000:
        return (
            20,
            "Very large floor area",
            f"A floor area of {displayed_area} square metres was identified, indicating a very large development.",
        )
    if floor_area >= 2000:
        return (
            16,
            "Large floor area",
            f"A floor area of {displayed_area} square metres was identified, indicating a large development.",
        )
    if floor_area >= 500:
        return (
            12,
            "Substantial floor area",
            f"A floor area of {displayed_area} square metres was identified, indicating a substantial development.",
        )
    if floor_area >= 100:
        return (
            8,
            "Moderate floor area",
            f"A floor area of {displayed_area} square metres was identified, indicating a moderate development.",
        )
    return (
        4,
        "Small recorded floor area",
        f"A floor area of {displayed_area} square metres was identified.",
    )


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
    if match:
        return int(match.group("count"))
    if _NEW_SINGLE_DWELLING_PROPOSAL_PATTERN.search(text):
        return 1
    return None


def _textual_floor_area(text: str) -> float | None:
    match = _EXPLICIT_FLOOR_AREA_PATTERN.search(text)
    return float(match.group("area")) if match else None


def _score_project_scale(
    text: str,
    number_residential_units: int | None,
    floor_area: float | None,
) -> tuple[int, str | None, str]:
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
    return (
        max(evidence, key=lambda item: item[0])
        if evidence
        else (
            0,
            None,
            "No valid residential unit count or floor area was available.",
        )
    )


def _score_lead_timing(
    received_date: date | None,
    current_date: date,
) -> tuple[int, str | None, str]:
    if received_date is None:
        return (
            0,
            None,
            "No received date was available, so no lead timing points were awarded.",
        )

    age_days = (current_date - received_date).days
    if age_days < 0:
        return (
            0,
            None,
            "The received date is in the future, so no lead timing points were awarded.",
        )
    age_description = "today" if age_days == 0 else f"{age_days} days ago"
    if age_days <= 14:
        return (
            10,
            "Application received within the last 14 days",
            f"The application was received {age_description}, within the last 14 days.",
        )
    if age_days <= 30:
        return (
            8,
            "Application received within the last 30 days",
            f"The application was received {age_description}, within the last 30 days.",
        )
    if age_days <= 60:
        return (
            5,
            "Application received within the last 60 days",
            f"The application was received {age_description}, within the last 60 days.",
        )
    if age_days <= 90:
        return (
            2,
            "Application received within the last 90 days",
            f"The application was received {age_description}, within the last 90 days.",
        )
    return (
        0,
        None,
        f"The application was received {age_description}, so no lead timing points were awarded.",
    )


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

    project_scope, scope_reason, scope_explanation = _score_project_scope(
        primary_text,
        category,
    )
    project_scale, scale_reason, scale_explanation = _score_project_scale(
        full_text,
        number_residential_units,
        floor_area,
    )
    residential_units = _valid_units(number_residential_units)
    if residential_units is None:
        residential_units = _textual_units(full_text)
    electrical_assessment = _assess_electrical_relevance(
        full_text,
        primary_text=primary_text,
        category=category,
        project_scope=project_scope,
        project_scale=project_scale,
        residential_unit_count=residential_units,
    )
    electrical_relevance = electrical_assessment.score
    electrical_reason = electrical_assessment.reason
    electrical_explanation = electrical_assessment.explanation
    electrical_work_brief = _electrical_work_brief_for_assessment(
        electrical_assessment,
    )
    lead_timing, timing_reason, timing_explanation = _score_lead_timing(
        received_date,
        current_date,
    )
    category_fit = CATEGORY_FIT_SCORES[category]
    category_label = category.replace("_", " ").title()
    category_reason = f"{category_label} category fit"
    category_explanation = (
        f"The application is classified as {category_label}, which receives "
        f"{category_fit} points for category fit."
    )

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
    score_components = (
        OpportunityScoreComponent(
            name="project_scope",
            points_awarded=score_breakdown.project_scope,
            maximum_points=SCORE_COMPONENT_MAXIMUMS["project_scope"],
            explanation=scope_explanation,
        ),
        OpportunityScoreComponent(
            name="electrical_relevance",
            points_awarded=score_breakdown.electrical_relevance,
            maximum_points=SCORE_COMPONENT_MAXIMUMS["electrical_relevance"],
            explanation=electrical_explanation,
        ),
        OpportunityScoreComponent(
            name="project_scale",
            points_awarded=score_breakdown.project_scale,
            maximum_points=SCORE_COMPONENT_MAXIMUMS["project_scale"],
            explanation=scale_explanation,
        ),
        OpportunityScoreComponent(
            name="lead_timing",
            points_awarded=score_breakdown.lead_timing,
            maximum_points=SCORE_COMPONENT_MAXIMUMS["lead_timing"],
            explanation=timing_explanation,
        ),
        OpportunityScoreComponent(
            name="category_fit",
            points_awarded=score_breakdown.category_fit,
            maximum_points=SCORE_COMPONENT_MAXIMUMS["category_fit"],
            explanation=category_explanation,
        ),
    )

    return OpportunityScoreResult(
        opportunity_score=score_breakdown.total,
        opportunity_level=opportunity_level_for_score(score_breakdown.total),
        score_breakdown=score_breakdown,
        score_components=score_components,
        reasons=reasons,
        electrical_work_brief=electrical_work_brief,
    )
