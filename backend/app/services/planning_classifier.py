import re
import unicodedata
from typing import Literal


PlanningApplicationCategory = Literal[
    "residential",
    "commercial",
    "industrial",
    "energy",
    "infrastructure",
    "mixed_use",
    "other",
]

PLANNING_APPLICATION_CATEGORIES: tuple[PlanningApplicationCategory, ...] = (
    "residential",
    "commercial",
    "industrial",
    "energy",
    "infrastructure",
    "mixed_use",
    "other",
)

_CATEGORY_KEYWORDS: dict[PlanningApplicationCategory, tuple[str, ...]] = {
    "residential": (
        "bungalow",
        "bungalows",
        "dwelling",
        "dwellings",
        "house",
        "houses",
        "apartment",
        "apartments",
        "residential",
        "housing",
        "residential unit",
        "residential units",
        "dwellinghouse",
        "dwellinghouses",
        "farmhouse",
        "farmhouses",
    ),
    "commercial": (
        "retail",
        "shop",
        "shops",
        "office",
        "offices",
        "hotel",
        "hotels",
        "guesthouse",
        "guesthouses",
        "guest house",
        "guest houses",
        "restaurant",
        "restaurants",
        "commercial",
        "convenience store",
        "convenience stores",
        "retail store",
        "retail stores",
        "dental surgery",
        "dental surgeries",
        "medical centre",
        "medical centres",
        "medical center",
        "medical centers",
        "clinic",
        "clinics",
        "museum",
        "museums",
    ),
    "industrial": (
        "warehouse",
        "warehouses",
        "factory",
        "factories",
        "manufacturing",
        "industrial",
        "production facility",
        "production facilities",
    ),
    "energy": (
        "solar",
        "photovoltaic",
        "solar farm",
        "solar farms",
        "wind farm",
        "wind farms",
        "wind turbine",
        "wind turbines",
        "battery storage",
        "renewable energy",
    ),
    "infrastructure": (
        "road",
        "roads",
        "bridge",
        "bridges",
        "cycleway",
        "cycleways",
        "water infrastructure",
        "wastewater",
        "waste water",
        "utility infrastructure",
        "transport infrastructure",
        "public transport",
        "railway",
        "railways",
    ),
}

_CONVENTIONAL_USE_PRECEDENCE: tuple[PlanningApplicationCategory, ...] = (
    "industrial",
    "commercial",
    "residential",
)

_PRIMARY_ENERGY_PHRASES = (
    "solar farm",
    "solar farms",
    "solar energy development",
    "photovoltaic development",
    "photovoltaic farm",
    "photovoltaic farms",
    "wind farm",
    "wind farms",
    "wind energy development",
    "battery energy storage",
    "battery storage development",
    "battery storage facility",
    "renewable energy development",
    "energy infrastructure",
    "electrical substation",
    "electricity substation",
    "substation",
    "substations",
)

_PRIMARY_INFRASTRUCTURE_PHRASES = (
    "public road",
    "public roads",
    "public cycleway",
    "public cycleways",
    "transport infrastructure",
    "public transport",
    "utility infrastructure",
    "water infrastructure",
    "wastewater infrastructure",
    "waste water infrastructure",
    "wastewater treatment plant",
    "waste water treatment plant",
    "water treatment plant",
    "railway",
    "railways",
)

_PRIMARY_OTHER_PHRASES = (
    "pig finishing unit",
    "pig finishing units",
    "training pitch",
    "training pitches",
    "playing pitch",
    "playing pitches",
    "sports pitch",
    "sports pitches",
    "sports ground",
    "sports grounds",
    "all weather pitch",
    "all weather pitches",
    "all weather playing pitch",
    "all weather playing pitches",
    "artificial turf pitch",
    "artificial turf pitches",
    "artificial turf playing pitch",
    "artificial turf playing pitches",
    "sports facility",
    "sports facilities",
    "recreation facility",
    "recreation facilities",
)

_PRIMARY_BUILDING_OR_DEVELOPMENT_PHRASES = (
    "building",
    "buildings",
    "development",
    "developments",
)

_ADDITIONAL_PERMISSION_PHRASES = (
    "permission is also sought for",
    "permission also sought for",
)

_DEMOLITION_PHRASES = (
    "demolish",
    "demolished",
    "demolition",
    "remove",
    "removal",
)

_CONVERSION_DESTINATION_WORD_LIMIT = 8

_CHANGE_OF_USE_PATTERNS = (
    re.compile(r"\bchange\s+of\s+use\b.*?\b(?:to|into|as)\b(?P<use>.+)$"),
    re.compile(
        rf"\bconvert(?:ed|ing)?\b"
        rf"(?:\s+\w+){{0,{_CONVERSION_DESTINATION_WORD_LIMIT}}}?"
        r"\s+(?:to|into)\b(?P<use>.+)$"
    ),
    re.compile(
        rf"\bconversion\b"
        rf"(?:\s+\w+){{0,{_CONVERSION_DESTINATION_WORD_LIMIT}}}?"
        r"\s+(?:to|into)\b(?P<use>.+)$"
    ),
)

_PROPOSED_AFTER_DEMOLITION_PATTERNS = (
    re.compile(
        r"\b(?:construct|erect|build|develop|provide|install|reconstruct)\b"
    ),
    re.compile(
        r"\b(?:construction|erection|development|provision|installation|"
        r"reconstruction)\s+of\b"
    ),
    re.compile(r"\b(?:replace|replaced|replacement)\s+(?:it\s+)?with\b"),
    re.compile(r"\bto\s+be\s+replaced\s+by\b"),
)

_EXPLICIT_MIXED_USE_PHRASES = (
    "mixed use",
    "residential and commercial development",
    "commercial and residential development",
)

_MIXED_USE_LAYOUT_PHRASES = (
    "ground floor",
    "first floor",
    "upper floor",
    "upper floors",
    "above",
)

_VERBAL_HOUSE_PATTERN = re.compile(
    r"\b(?:(?:(?:designed|used|intended)\s+)?to|will|shall|may|might|can|"
    r"could|would|should)\s+house\b"
)

_AGRICULTURAL_HOUSE_PATTERN = re.compile(
    r"\b(?:cow|cattle|calf|livestock|poultry|pig|hen|animal)\s+"
    r"(?:(?:storage|cubicle)\s+){0,2}houses?\b"
)

_HOME_OFFICE_PATTERN = re.compile(r"\bhome\s+offices?\b")


def _normalize_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized, flags=re.UNICODE).strip()
    return re.sub(
        r"\bnon\s+(residential|commercial|industrial)\b",
        r"non\1",
        normalized,
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _first_phrase_position(
    text: str,
    phrases: tuple[str, ...],
) -> int | None:
    padded_text = f" {text} "
    positions = []
    for phrase in phrases:
        position = padded_text.find(f" {phrase} ")
        if position >= 0:
            positions.append(position)

    return min(positions) if positions else None


def _first_evidence_position(
    texts: tuple[str, ...],
    phrases: tuple[str, ...],
) -> tuple[int, int] | None:
    positions = []
    for text_index, text in enumerate(texts):
        position = _first_phrase_position(text, phrases)
        if position is not None:
            positions.append((text_index, position))

    return min(positions) if positions else None


def _first_ancillary_addition_boundary(
    texts: tuple[str, ...],
) -> tuple[int, int] | None:
    positions = []
    for text_index, text in enumerate(texts):
        boundary_position = _first_phrase_position(
            text,
            _ADDITIONAL_PERMISSION_PHRASES,
        )
        if boundary_position is None:
            continue

        preceding_text = text[:boundary_position]
        if _contains_any_phrase(
            preceding_text,
            _PRIMARY_BUILDING_OR_DEVELOPMENT_PHRASES,
        ):
            positions.append((text_index, boundary_position))

    return min(positions) if positions else None


def _extract_change_of_use_destination(text: str) -> str:
    for pattern in _CHANGE_OF_USE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("use").strip()

    return ""


def _extract_primary_proposal(text: str) -> str:
    demolition_position = _first_phrase_position(text, _DEMOLITION_PHRASES)
    if demolition_position is None:
        return text

    demolition_section = text[demolition_position:]
    replacement_candidates = []
    for pattern in _PROPOSED_AFTER_DEMOLITION_PATTERNS:
        replacement_candidates.extend(pattern.finditer(demolition_section))

    if replacement_candidates:
        earliest_replacement = min(
            replacement_candidates,
            key=lambda match: (match.start(), match.end()),
        )
        return demolition_section[earliest_replacement.end() :].strip()

    # A demolished use is historical evidence, not evidence of the new land use.
    return ""


def _mask_non_residential_house_uses(text: str) -> str:
    text = _VERBAL_HOUSE_PATTERN.sub("contain", text)
    return _AGRICULTURAL_HOUSE_PATTERN.sub("agricultural building", text)


def _mask_non_commercial_office_uses(text: str) -> str:
    return _HOME_OFFICE_PATTERN.sub("domestic workspace", text)


def _has_category_evidence(
    texts: tuple[str, ...],
    category: PlanningApplicationCategory,
) -> bool:
    if category == "residential":
        texts = tuple(_mask_non_residential_house_uses(text) for text in texts)
    elif category == "commercial":
        texts = tuple(_mask_non_commercial_office_uses(text) for text in texts)
    keywords = _CATEGORY_KEYWORDS[category]
    return any(_contains_any_phrase(text, keywords) for text in texts)


def _first_category_evidence_position(
    texts: tuple[str, ...],
    category: PlanningApplicationCategory,
) -> tuple[int, int] | None:
    if category == "residential":
        texts = tuple(_mask_non_residential_house_uses(text) for text in texts)
    elif category == "commercial":
        texts = tuple(_mask_non_commercial_office_uses(text) for text in texts)
    return _first_evidence_position(texts, _CATEGORY_KEYWORDS[category])


def _has_residential_unit_evidence(number_residential_units: int | None) -> bool:
    return (
        isinstance(number_residential_units, int)
        and not isinstance(number_residential_units, bool)
        and number_residential_units > 0
    )


def _has_mixed_use_evidence(
    texts: tuple[str, ...],
    has_residential_units: bool,
) -> bool:
    if any(
        _contains_any_phrase(text, _EXPLICIT_MIXED_USE_PHRASES)
        for text in texts
    ):
        return True

    for text in texts:
        has_commercial_use = _has_category_evidence((text,), "commercial")
        has_residential_use = has_residential_units or _has_category_evidence(
            (text,),
            "residential",
        )
        has_separate_layout = _contains_any_phrase(
            text,
            _MIXED_USE_LAYOUT_PHRASES,
        )
        if has_commercial_use and has_residential_use and has_separate_layout:
            return True

    return False


def _classify_primary_use(
    texts: tuple[str, ...],
    has_residential_units: bool,
) -> PlanningApplicationCategory:
    conventional_positions = [
        position
        for category in _CONVENTIONAL_USE_PRECEDENCE
        if (
            position := _first_category_evidence_position(
                texts,
                category,
            )
        )
        is not None
    ]
    first_conventional_position = (
        min(conventional_positions) if conventional_positions else None
    )
    primary_other_position = _first_evidence_position(
        texts,
        _PRIMARY_OTHER_PHRASES,
    )
    ancillary_addition_boundary = _first_ancillary_addition_boundary(texts)
    if ancillary_addition_boundary is not None:
        # A building/development stated before an explicit request for
        # additional works is the primary proposal when it has no more specific
        # category. Specialist evidence before this boundary can still win.
        primary_other_position = min(
            position
            for position in (
                primary_other_position,
                ancillary_addition_boundary,
            )
            if position is not None
        )

    primary_specialist_evidence = []
    for specialist_priority, (category, phrases) in enumerate(
        (
            ("energy", _PRIMARY_ENERGY_PHRASES),
            ("infrastructure", _PRIMARY_INFRASTRUCTURE_PHRASES),
        )
    ):
        position = _first_evidence_position(texts, phrases)
        if position is not None:
            primary_specialist_evidence.append(
                (position, specialist_priority, category)
            )

    if primary_specialist_evidence:
        position, _, category = min(primary_specialist_evidence)
        if (
            (
                first_conventional_position is None
                or position < first_conventional_position
            )
            and (
                primary_other_position is None
                or position < primary_other_position
            )
        ):
            return category

    for category in _CONVENTIONAL_USE_PRECEDENCE:
        if category == "residential" and has_residential_units:
            return category
        if _has_category_evidence(texts, category):
            return category

    if primary_other_position is not None:
        return "other"

    # Generic specialist words only classify otherwise unclaimed proposals. This
    # keeps roads, wastewater and solar panels ancillary to a clear primary use.
    if _has_category_evidence(texts, "energy"):
        return "energy"
    if _has_category_evidence(texts, "infrastructure"):
        return "infrastructure"

    return "other"


def classify_planning_application(
    description: str | None = None,
    application_type: str | None = None,
    number_residential_units: int | None = None,
    floor_area: float | None = None,
) -> PlanningApplicationCategory:
    """Classify stored planning fields using deterministic land-use rules.

    ``floor_area`` is an explicit input but is not sufficient evidence of a land use
    by itself; areas of the same size can represent any supported category.
    """
    description_text = _normalize_text(description)
    application_type_text = _normalize_text(application_type)
    has_residential_units = _has_residential_unit_evidence(
        number_residential_units
    )

    change_of_use_destination = _extract_change_of_use_destination(
        description_text
    )
    if change_of_use_destination:
        destination_texts = tuple(
            text
            for text in (
                change_of_use_destination,
                application_type_text,
            )
            if text
        )
        if _has_mixed_use_evidence(
            destination_texts,
            has_residential_units,
        ):
            return "mixed_use"
        return _classify_primary_use(
            destination_texts,
            has_residential_units,
        )

    primary_proposal = _extract_primary_proposal(description_text)
    texts = tuple(
        text
        for text in (primary_proposal, application_type_text)
        if text
    )

    if _has_mixed_use_evidence(texts, has_residential_units):
        return "mixed_use"

    return _classify_primary_use(texts, has_residential_units)
