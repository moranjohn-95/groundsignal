from datetime import date, timedelta

import pytest

from backend.app.services.opportunity_scorer import (
    CATEGORY_FIT_SCORES,
    OpportunityScoreBreakdown,
    opportunity_level_for_score,
    score_planning_application_opportunity,
)
from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
)


CURRENT_DATE = date(2025, 1, 15)

ACCOMMODATION_SOLAR_DESCRIPTION = (
    "Planning permission is sought for development comprising:\n"
    "The phased development of staff accommodation lodges in two connected "
    "three-storey blocks arranged around a central courtyard area, comprising:\n"
    "- Phase A development of 60 no. staff accommodation rooms and 6 no. "
    "common room areas; and\n"
    "- Optional Phase B development of a further 18 no. staff accommodation "
    "rooms in an extension to one of the blocks.\n"
    "- Roof-mounted photovoltaic panels and green roof systems on the proposed "
    "accommodation lodge buildings.\n"
    "- Construction of a single-storey gym building with attached bicycle and "
    "bin storage facilities.\n"
    "- Staff car parking facilities and associated internal vehicular and "
    "pedestrian connections to existing parking area, including provision for "
    "fire tender access.\n"
    "- Landscaping works including localised ground reprofiling, hard and soft "
    "landscaping works.\n"
    "- Lighting provision.\n"
    "- Localised connections to existing wastewater and water supply and "
    "provision of surface water drainage including soakaway area.\n"
    "- All associated site development works."
)


def _score(**overrides):
    values = {
        "description": None,
        "application_type": None,
        "number_residential_units": None,
        "floor_area": None,
        "received_date": None,
        "category": "other",
        "current_date": CURRENT_DATE,
    }
    values.update(overrides)
    return score_planning_application_opportunity(**values)


@pytest.mark.parametrize(
    ("values", "expected_score", "expected_level", "expected_breakdown"),
    [
        pytest.param(
            {
                "description": (
                    "Construction of a new commercial building including "
                    "12 EV charging points and associated site works."
                ),
                "floor_area": 6000.0,
                "received_date": date(2025, 1, 10),
                "category": "commercial",
            },
            100,
            "very_high",
            OpportunityScoreBreakdown(30, 30, 20, 10, 10),
            id="large-commercial-development-with-ev-charging",
        ),
        pytest.param(
            {
                "description": (
                    "Construction of a new industrial manufacturing facility."
                ),
                "floor_area": 2500.0,
                "received_date": date(2024, 12, 20),
                "category": "industrial",
            },
            76,
            "high",
            OpportunityScoreBreakdown(30, 12, 16, 8, 10),
            id="new-industrial-development",
        ),
        pytest.param(
            {
                "description": (
                    "Development of a solar farm with photovoltaic panels "
                    "and associated access tracks."
                ),
                "received_date": date(2024, 12, 1),
                "category": "energy",
            },
            70,
            "high",
            OpportunityScoreBreakdown(30, 25, 0, 5, 10),
            id="solar-energy-development",
        ),
        pytest.param(
            {
                "description": "Construction of 80 apartments.",
                "number_residential_units": 80,
                "received_date": date(2025, 1, 5),
                "category": "residential",
            },
            82,
            "very_high",
            OpportunityScoreBreakdown(30, 15, 20, 10, 7),
            id="large-multi-unit-residential-development",
        ),
        pytest.param(
            {
                "description": (
                    "Construction of a detached dwelling with an ancillary "
                    "wastewater treatment plant and associated site works."
                ),
                "number_residential_units": 1,
                "floor_area": 180.0,
                "received_date": date(2025, 1, 5),
                "category": "residential",
            },
            55,
            "medium",
            OpportunityScoreBreakdown(30, 0, 8, 10, 7),
            id="single-dwelling",
        ),
        pytest.param(
            {
                "description": (
                    "Construction of a single-storey extension to an existing "
                    "dwelling."
                ),
                "floor_area": 45.0,
                "received_date": date(2024, 12, 20),
                "category": "residential",
            },
            39,
            "low",
            OpportunityScoreBreakdown(20, 0, 4, 8, 7),
            id="residential-extension",
        ),
        pytest.param(
            {
                "description": (
                    "Change of use of an existing office to a medical centre."
                ),
                "floor_area": 800.0,
                "received_date": date(2024, 12, 1),
                "category": "commercial",
            },
            59,
            "medium",
            OpportunityScoreBreakdown(20, 12, 12, 5, 10),
            id="commercial-medical-centre-change-of-use",
        ),
        pytest.param(
            {
                "description": "Internal alterations to an existing hotel.",
                "floor_area": 300.0,
                "received_date": date(2025, 1, 5),
                "category": "commercial",
            },
            38,
            "low",
            OpportunityScoreBreakdown(10, 0, 8, 10, 10),
            id="hotel-alterations",
        ),
        pytest.param(
            {
                "description": "Retention of illuminated advertising signage.",
                "received_date": date(2025, 1, 10),
                "category": "commercial",
            },
            25,
            "low",
            OpportunityScoreBreakdown(5, 0, 0, 10, 10),
            id="small-signage-application",
        ),
        pytest.param(
            {
                "description": "Alterations to the site boundary and entrance.",
                "received_date": date(2025, 1, 10),
                "category": "other",
            },
            18,
            "very_low",
            OpportunityScoreBreakdown(5, 0, 0, 10, 3),
            id="boundary-alterations",
        ),
        pytest.param(
            {
                "description": "Replacement of one external light fitting.",
                "received_date": date(2025, 1, 10),
                "category": "commercial",
            },
            30,
            "low",
            OpportunityScoreBreakdown(5, 5, 0, 10, 10),
            id="minor-lighting-replacement",
        ),
    ],
)
def test_representative_electrician_opportunities(
    values: dict,
    expected_score: int,
    expected_level: str,
    expected_breakdown: OpportunityScoreBreakdown,
) -> None:
    result = _score(**values)

    assert result.opportunity_score == expected_score
    assert result.opportunity_level == expected_level
    assert result.score_breakdown == expected_breakdown


def test_ancillary_major_phrase_does_not_inflate_primary_minor_scope() -> None:
    result = _score(
        description=(
            "Retention of advertising signage. Permission is also sought for "
            "construction of a new commercial building."
        ),
        category="commercial",
    )

    assert result.score_breakdown.project_scope == 5
    assert result.score_breakdown.electrical_relevance == 0


def test_erect_signage_is_minor_without_commercial_electrical_inference() -> None:
    result = _score(
        description="ERECT SIGNAGE TO FRONT OF EXISTING OFFICE",
        floor_area=50.0,
        received_date=date(2024, 1, 1),
        category="commercial",
    )

    assert result.opportunity_score == 19
    assert result.opportunity_level == "very_low"
    assert result.score_breakdown == OpportunityScoreBreakdown(5, 0, 4, 0, 10)
    assert "Minor signage, boundary or lighting works" in result.reasons
    assert not any("implied" in reason.casefold() for reason in result.reasons)


@pytest.mark.parametrize(
    "description",
    [
        "Erect standalone signage.",
        "Erect a free-standing sign.",
        "Erection of new illuminated advertising signage.",
    ],
)
def test_erect_signage_variants_remain_minor(description: str) -> None:
    result = _score(description=description, category="commercial")

    assert result.score_breakdown.project_scope == 5
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("Erect warehouse.", "industrial"),
        ("Erect industrial unit.", "industrial"),
        ("Erect dwelling house.", "residential"),
        ("Erect commercial building.", "commercial"),
    ],
)
def test_erect_legitimate_buildings_remain_major(
    description: str,
    category: str,
) -> None:
    result = _score(description=description, category=category)

    assert result.score_breakdown.project_scope == 30
    assert "Minor signage, boundary or lighting works" not in result.reasons


def test_accommodation_solar_retains_strong_electrical_relevance() -> None:
    result = _score(
        description=ACCOMMODATION_SOLAR_DESCRIPTION,
        received_date=CURRENT_DATE,
        category="residential",
    )

    assert result.opportunity_score == 72
    assert result.opportunity_level == "high"
    assert result.score_breakdown == OpportunityScoreBreakdown(30, 25, 0, 10, 7)
    assert "Renewable electrical installation identified" in result.reasons


def test_commercial_fit_out_has_contextual_electrical_relevance() -> None:
    result = _score(
        description="Fit-out of an existing retail unit as a medical clinic.",
        category="commercial",
    )

    assert result.score_breakdown.project_scope == 20
    assert result.score_breakdown.electrical_relevance == 12
    assert (
        "Electrical work implied by substantial business development"
        in result.reasons
    )


def test_significant_lighting_is_distinct_from_one_light_fitting() -> None:
    significant = _score(
        description="Installation of a floodlighting scheme for playing pitches.",
        category="other",
    )
    minor = _score(
        description="Replacement of one external light fitting.",
        category="other",
    )

    assert significant.score_breakdown.electrical_relevance == 20
    assert minor.score_breakdown.electrical_relevance == 5
    assert "Significant lighting installation identified" in significant.reasons
    assert "Significant lighting installation identified" not in minor.reasons


@pytest.mark.parametrize(
    ("units", "expected_scale"),
    [(1, 4), (2, 8), (10, 12), (20, 16), (50, 20)],
)
def test_residential_unit_scale_thresholds(
    units: int,
    expected_scale: int,
) -> None:
    result = _score(number_residential_units=units)

    assert result.score_breakdown.project_scale == expected_scale


@pytest.mark.parametrize(
    ("floor_area", "expected_scale"),
    [(1.0, 4), (100.0, 8), (500.0, 12), (2000.0, 16), (5000.0, 20)],
)
def test_floor_area_scale_thresholds(
    floor_area: float,
    expected_scale: int,
) -> None:
    result = _score(floor_area=floor_area)

    assert result.score_breakdown.project_scale == expected_scale


def test_explicit_textual_scale_is_used_when_structured_values_are_missing() -> None:
    result = _score(
        description=(
            "Construction of 24 apartments with a stated floor area of 1800 sqm."
        ),
        category="residential",
    )

    assert result.score_breakdown.project_scale == 16
    assert "Significant residential unit count" in result.reasons


@pytest.mark.parametrize(
    ("units", "floor_area"),
    [(None, None), (0, 0), (-1, -50), (True, True)],
)
def test_missing_or_non_positive_scale_data_is_not_large(
    units: int | None,
    floor_area: float | None,
) -> None:
    result = _score(
        description="Construction of a new retail shop.",
        number_residential_units=units,
        floor_area=floor_area,
        category="commercial",
    )

    assert result.score_breakdown.project_scale == 0
    assert not any("floor area" in reason.casefold() for reason in result.reasons)


@pytest.mark.parametrize(
    ("days_old", "expected_timing"),
    [(0, 10), (14, 10), (15, 8), (30, 8), (31, 5), (60, 5), (61, 2), (90, 2), (91, 0)],
)
def test_lead_timing_thresholds(days_old: int, expected_timing: int) -> None:
    result = _score(received_date=CURRENT_DATE - timedelta(days=days_old))

    assert result.score_breakdown.lead_timing == expected_timing


def test_old_otherwise_attractive_application_loses_timing_points() -> None:
    values = {
        "description": (
            "Construction of a large commercial building with EV charging."
        ),
        "floor_area": 6000.0,
        "category": "commercial",
    }
    recent = _score(**values, received_date=CURRENT_DATE)
    old = _score(**values, received_date=CURRENT_DATE - timedelta(days=120))

    assert recent.score_breakdown.lead_timing == 10
    assert old.score_breakdown.lead_timing == 0
    assert recent.opportunity_score - old.opportunity_score == 10


def test_future_received_date_receives_no_timing_points() -> None:
    result = _score(received_date=CURRENT_DATE + timedelta(days=3))

    assert result.score_breakdown.lead_timing == 0
    assert not any("received" in reason.casefold() for reason in result.reasons)


def test_non_residential_plant_and_equipment_evidence_is_preserved() -> None:
    result = _score(
        description=(
            "Construction of a new industrial manufacturing facility with "
            "substantial plant and equipment."
        ),
        floor_area=2500.0,
        received_date=date(2024, 12, 20),
        category="industrial",
    )

    assert result.opportunity_score == 79
    assert result.opportunity_level == "high"
    assert result.score_breakdown.electrical_relevance == 15
    assert "Plant or electrical equipment identified" in result.reasons


def test_missing_received_date_has_no_timing_evidence() -> None:
    result = _score(received_date=None)

    assert result.score_breakdown.lead_timing == 0
    assert not any("received" in reason.casefold() for reason in result.reasons)


@pytest.mark.parametrize(
    "category",
    PLANNING_APPLICATION_CATEGORIES,
)
def test_all_category_fit_weights(category: str) -> None:
    result = _score(category=category)

    assert result.score_breakdown.category_fit == CATEGORY_FIT_SCORES[category]
    assert result.opportunity_score == CATEGORY_FIT_SCORES[category]
    assert result.score_breakdown.category_fit <= 10


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0, "very_low"),
        (19, "very_low"),
        (20, "low"),
        (39, "low"),
        (40, "medium"),
        (59, "medium"),
        (60, "high"),
        (79, "high"),
        (80, "very_high"),
        (100, "very_high"),
    ],
)
def test_exact_opportunity_level_boundaries(
    score: int,
    expected_level: str,
) -> None:
    assert opportunity_level_for_score(score) == expected_level


@pytest.mark.parametrize("score", [-1, 101, True, 20.5])
def test_opportunity_level_rejects_invalid_scores(score: object) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        opportunity_level_for_score(score)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {
            "description": "Construction of a new commercial building with EV charging.",
            "floor_area": 9000.0,
            "received_date": CURRENT_DATE,
            "category": "commercial",
        },
        {
            "description": "Residential extension with solar panels.",
            "floor_area": 55.0,
            "received_date": CURRENT_DATE - timedelta(days=45),
            "category": "residential",
        },
        {
            "description": "Boundary alterations.",
            "category": "other",
        },
    ],
)
def test_score_is_bounded_and_breakdown_sums_exactly(values: dict) -> None:
    result = _score(**values)

    assert 0 <= result.opportunity_score <= 100
    assert result.score_breakdown.total == result.opportunity_score
    assert result.score_breakdown.project_scope <= 30
    assert result.score_breakdown.electrical_relevance <= 30
    assert result.score_breakdown.project_scale <= 20
    assert result.score_breakdown.lead_timing <= 10
    assert result.score_breakdown.category_fit <= 10


def test_reasons_only_report_detected_evidence() -> None:
    result = _score(
        description="Construction of a detached dwelling.",
        number_residential_units=1,
        category="residential",
    )

    assert "New residential development" in result.reasons
    assert "Single residential unit" in result.reasons
    assert "Residential category fit" in result.reasons
    assert not any("EV charging" in reason for reason in result.reasons)
    assert not any("floor area" in reason.casefold() for reason in result.reasons)
    assert not any("received" in reason.casefold() for reason in result.reasons)


def test_invalid_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported planning category"):
        _score(category="agricultural")
