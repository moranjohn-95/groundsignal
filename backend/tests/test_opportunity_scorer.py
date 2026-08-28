from datetime import date, timedelta

import pytest

from backend.app.services.opportunity_scorer import (
    CATEGORY_FIT_SCORES,
    ELECTRICAL_EVIDENCE_SCORE_CEILINGS,
    SCORE_COMPONENT_MAXIMUMS,
    OpportunityScoreBreakdown,
    _effective_opportunity_score,
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

OWN_DOOR_MAISONETTE_DESCRIPTION = (
    "amendments to the Large-Scale Residential Development (LRD) permitted "
    "by Kerry County Council (Reference 2560640) and An Coimisiún Pleanála "
    "(Reference ACP-323735-25).\n\n"
    "The proposed amendments relate to alterations to 66 no. own-door "
    "maisonette/apartment units over 2 no. storeys (32 no. 1 bed units, 34 "
    "no. 2 bed units) comprising units 78 – 109 Hanafin Park Maisonette "
    "Block and units 01 – 34 Racecourse Demesne Maisonette Block. The "
    "amendments will consist of: a change in plan of the own-door "
    "maisonette/apartment blocks, including reconfiguration of units, and "
    "consequent increase in external communal amenity space; roofline and "
    "elevational changes, including balconies, window openings, treatment "
    "and finish materials; and all associated landscaping and associated "
    "site development works."
)

DOCTORS_SURGERY_DESCRIPTION = (
    "Full planning permission to, A) change of use of the existing dwelling "
    "house to doctors surgery, B) demolish existing garage, C) permission for "
    "associated signage, D) internal alterations to existing dwelling house to "
    "accommodate doctors surgery and minor elevational alterations to the "
    "existing dwelling house and all ancillary site development works."
)

CONSERVATORY_ATTIC_EXTENSION_DESCRIPTION = (
    "(a) conservatory at south side of dwelling, (b) extension with attic space "
    "over, incorporating 2 no. rooflights at north side of dwelling, (c) "
    "domestic garage/car port to rear of dwelling, (d) fuel shed/garden tools "
    "storage shed to rear of dwelling and (e) all ancillary works"
)

KERRY_2660732_DESCRIPTION = (
    "FULL PLANNING PERMISSION FOR PERMISSION TO CONSTRUCT A DOMESTIC GARAGE / "
    "STORE, TO BE CONSTRUCTED IN CONJUNCTION WITH THE DEVELOPMENT PREVIOUSLY "
    "GRANTED UNDER REFERENCE NO. 25/60740, TOGETHER WITH ALL ASSOCIATED "
    "ANCILLARY SITE WORKS"
)

KERRY_2660719_DESCRIPTION = (
    "permission to a) renovate the existing dwelling, b) demolish and rebuild "
    "the existing porch, c) decommission the existing septic tank, d) install a "
    "mechanical treatment unit and raised polishing filter and e) construct all "
    "associated site works"
)

KERRY_2660717_DESCRIPTION = (
    "PERMISSION for: (1)The demolition of existing glazed conservatory "
    "extension, internal stone chimneybreast and internal blockwork partitions. "
    "(2) Renovation and fabric upgrade of the existing stone cottage; (3) Change "
    "of use of adjacent original stone outbuilding to ancillary accommodation "
    "with the addition of a conservatory extension; and (4) All associated site "
    "services. RETENTION PERMISSION for: Retention of two existing outbuildings "
    "for use as a store and home office"
)

KERRY_2660734_DESCRIPTION = (
    "Planning permission to refurbish and extend our existing dwelling house by "
    "erecting a new single-story pitched roof extension to the east side, with "
    "two Velux roof windows to the rear of the new roof and one Velux to the rear "
    "of the existing roof. The development will include all associated ancillary "
    "site works, including the demolition of the front boundary wall to the side "
    "patio area"
)

KERRY_2660747_DESCRIPTION = (
    "Retention permission to Retain as built garage/storage shed and associated "
    "site works"
)

KERRY_2660736_DESCRIPTION = (
    "Retention Permission to Retain utility room extension to dwelling house "
    "previously granted permission under Ref 2560667, all in accordance with "
    "the plans and particulars submitted"
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
            79,
            "high",
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
            59,
            "medium",
            OpportunityScoreBreakdown(30, 6, 8, 10, 7),
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
            45,
            "medium",
            OpportunityScoreBreakdown(20, 6, 4, 8, 7),
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
            53,
            "medium",
            OpportunityScoreBreakdown(20, 6, 12, 5, 10),
            id="commercial-medical-centre-change-of-use",
        ),
        pytest.param(
            {
                "description": "Internal alterations to an existing hotel.",
                "floor_area": 300.0,
                "received_date": date(2025, 1, 5),
                "category": "commercial",
            },
            44,
            "medium",
            OpportunityScoreBreakdown(10, 6, 8, 10, 10),
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


@pytest.mark.parametrize(
    "description",
    [
        "Construction of an off-road car park.",
        "Construction of a service road.",
        (
            "Construction of an off-road car park, service road, play area, and "
            "landscaping."
        ),
        "Development of a playground.",
        "Provision of landscaping and a community garden.",
        "Construction of a new access entrance.",
        "Construction of boundary walls and fences.",
        "Provision of drainage and ancillary site works.",
        "Development of a public car park.",
    ],
)
def test_site_only_works_receive_limited_project_scope(description: str) -> None:
    result = _score(description=description, category="other")

    assert result.score_breakdown.project_scope == 5
    assert result.score_breakdown.electrical_relevance == 0
    assert result.opportunity_score == 8
    assert result.opportunity_level == "very_low"


def test_demolition_only_does_not_receive_major_project_scope() -> None:
    result = _score(
        description="Demolition of an existing warehouse.",
        category="industrial",
    )

    assert result.score_breakdown.project_scope == 0
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    ("description", "category", "expected_electrical_points"),
    [
        (
            "Construction of a new school building with car parking and landscaping.",
            "other",
            12,
        ),
        (
            "Construction of a warehouse and associated parking.",
            "industrial",
            12,
        ),
        (
            "Construction of 20 dwellings with roads, parking, and landscaping.",
            "residential",
            15,
        ),
    ],
)
def test_building_construction_remains_major_with_ancillary_site_works(
    description: str,
    category: str,
    expected_electrical_points: int,
) -> None:
    result = _score(description=description, category=category)

    assert result.score_breakdown.project_scope == 30
    assert result.score_breakdown.electrical_relevance == expected_electrical_points
    assert result.electrical_work_brief.evidence_level == "inferred"


def test_ev_charging_in_a_car_park_retains_direct_electrical_evidence() -> None:
    result = _score(
        description="Construction of a car park with EV charging points.",
        category="other",
    )

    assert result.score_breakdown.project_scope == 5
    assert result.score_breakdown.electrical_relevance == 30
    assert result.electrical_work_brief.evidence_level == "direct"


def test_significant_car_park_lighting_retains_direct_electrical_evidence() -> None:
    result = _score(
        description="Construction of a car park with a car park lighting installation.",
        category="other",
    )

    assert result.score_breakdown.project_scope == 5
    assert result.score_breakdown.electrical_relevance == 20
    assert result.electrical_work_brief.evidence_level == "direct"


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


def test_commercial_fit_out_has_possible_electrical_relevance() -> None:
    result = _score(
        description="Fit-out of an existing retail unit as a medical clinic.",
        category="commercial",
    )

    assert result.score_breakdown.project_scope == 20
    assert result.score_breakdown.electrical_relevance == 6
    assert result.electrical_work_brief.evidence_level == "possible"
    assert (
        "Electrical work possible for substantive building work"
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
    ("description", "units", "expected_evidence", "expected_points"),
    [
        (
            "Construction of a new detached dwelling house.",
            1,
            "possible",
            6,
        ),
        (
            "Construction of 2 new dwelling houses.",
            2,
            "inferred",
            10,
        ),
        (
            "Construction of 5 new dwelling houses.",
            5,
            "inferred",
            10,
        ),
        (
            "Construction of 6 new dwelling houses.",
            6,
            "inferred",
            12,
        ),
        (
            "Construction of 9 new dwelling houses.",
            9,
            "inferred",
            12,
        ),
        (
            "Construction of 10 new dwelling houses.",
            10,
            "inferred",
            15,
        ),
    ],
)
def test_new_residential_developments_have_proportionate_electrical_inference(
    description: str,
    units: int,
    expected_evidence: str,
    expected_points: int,
) -> None:
    result = _score(
        description=description,
        number_residential_units=units,
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == expected_evidence
    assert result.score_breakdown.electrical_relevance == expected_points
    assert result.electrical_work_brief.signals == ()


def test_large_apartment_development_retains_strong_inferred_electrical_work() -> None:
    result = _score(
        description="Construction of 80 apartments.",
        number_residential_units=80,
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == "inferred"
    assert result.score_breakdown.electrical_relevance == 15
    assert result.electrical_work_brief.signals == ()


@pytest.mark.parametrize(
    "description",
    [
        "Construct a dwelling house.",
        "Construct a dwelling.",
        "Construct one dwelling.",
        "Construct 1 dwelling.",
    ],
)
def test_new_single_dwelling_text_is_parsed_as_possible_electrical_work(
    description: str,
) -> None:
    result = _score(description=description, category="residential")

    assert result.opportunity_score == 47
    assert result.opportunity_level == "medium"
    assert result.score_breakdown == OpportunityScoreBreakdown(30, 6, 4, 0, 7)
    assert result.electrical_work_brief.evidence_level == "possible"


@pytest.mark.parametrize(
    "unit_phrase",
    [
        "8 apartments",
        "8 no. apartments",
        "8 no apartments",
        "8no. apartments",
        "8no apartments",
        "8 dwelling units",
        "8 house units",
    ],
)
def test_common_irish_numeric_residential_unit_formats_are_parsed(
    unit_phrase: str,
) -> None:
    result = _score(
        description=f"Construction of {unit_phrase}.",
        category="residential",
    )

    assert result.score_breakdown.project_scale == 8
    assert result.score_breakdown.electrical_relevance == 12
    assert result.electrical_work_brief.evidence_level == "inferred"


def test_real_apartment_application_parses_compact_unit_count_after_demolition() -> None:
    result = _score(
        description=(
            "Demolish the existing warehouse on site b) construct a new 4 storey "
            "building consisting of 8no. apartments with associated circulation and "
            "service spaces"
        ),
        category="residential",
    )

    assert result.opportunity_score == 57
    assert result.opportunity_level == "medium"
    assert result.score_breakdown == OpportunityScoreBreakdown(30, 12, 8, 0, 7)
    assert result.electrical_work_brief.evidence_level == "inferred"


def test_substantial_residential_extension_is_possible_electrical_work() -> None:
    result = _score(
        description=(
            "Construction of a substantial two-storey extension to an existing "
            "dwelling."
        ),
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.score_breakdown.electrical_relevance == 6
    assert result.electrical_work_brief.signals == ()


def test_real_doctors_surgery_conversion_is_possible_electrical_work() -> None:
    result = _score(
        description=DOCTORS_SURGERY_DESCRIPTION,
        application_type="PERMISSION",
        category="residential",
    )

    assert result.score_breakdown == OpportunityScoreBreakdown(20, 6, 0, 0, 7)
    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.electrical_work_brief.summary == (
        "Possible electrical work associated with proposed building, internal, "
        "conversion, or mechanical work -- review plans for confirmation."
    )


def test_real_conservatory_attic_extension_is_possible_electrical_work() -> None:
    result = _score(
        description=CONSERVATORY_ATTIC_EXTENSION_DESCRIPTION,
        application_type="RETENTION",
        category="residential",
    )

    assert result.score_breakdown == OpportunityScoreBreakdown(20, 6, 0, 0, 7)
    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.electrical_work_brief.summary == (
        "Possible electrical work associated with proposed building, internal, "
        "conversion, or mechanical work -- review plans for confirmation."
    )


@pytest.mark.parametrize(
    ("application_number", "description", "application_type", "category", "expected_evidence"),
    [
        ("2660732", KERRY_2660732_DESCRIPTION, "PERMISSION", "other", "possible"),
        ("2660719", KERRY_2660719_DESCRIPTION, "PERMISSION", "other", "possible"),
        ("2660717", KERRY_2660717_DESCRIPTION, "PERMISSION", "other", "possible"),
        ("2660734", KERRY_2660734_DESCRIPTION, "PERMISSION", "other", "possible"),
        ("2660747", KERRY_2660747_DESCRIPTION, "RETENTION", "other", "unavailable"),
        ("2660736", KERRY_2660736_DESCRIPTION, "RETENTION", "residential", "unavailable"),
    ],
)
def test_real_kerry_building_work_regressions(
    application_number: str,
    description: str,
    application_type: str,
    category: str,
    expected_evidence: str,
) -> None:
    result = _score(
        description=description,
        application_type=application_type,
        category=category,
    )

    assert result.electrical_work_brief.evidence_level == expected_evidence
    assert result.score_breakdown.electrical_relevance == (
        6 if expected_evidence == "possible" else 0
    ), application_number


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("Construction of a new workshop.", "other"),
        ("Construction of a new detached garage.", "residential"),
        ("Construction of a new garden room for a home office.", "residential"),
        ("Internal alterations to an existing office.", "commercial"),
        ("Fit-out of an existing retail unit.", "commercial"),
        ("Conversion of an attic to a bedroom in an existing dwelling.", "residential"),
        (
            "Construction of a substantial kitchen and living-room extension to "
            "an existing dwelling.",
            "residential",
        ),
        ("Construction of a utility-room extension to an existing dwelling.", "residential"),
        ("Rebuild an existing porch at a dwelling house.", "residential"),
        ("Construction of a new conservatory at an existing dwelling.", "residential"),
        (
            "Installation of a mechanical treatment plant serving an existing "
            "dwelling.",
            "residential",
        ),
    ],
)
def test_substantive_building_work_is_possible_electrical_work(
    description: str,
    category: str,
) -> None:
    result = _score(description=description, category=category)

    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.score_breakdown.electrical_relevance == 6


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("Landscaping and garden works at an existing dwelling.", "residential"),
        ("Drainage works serving an existing dwelling.", "residential"),
        ("Construction of a car park and turning area.", "other"),
        ("Demolition of an existing dwelling.", "residential"),
        ("Retention of a completed domestic garage.", "residential"),
        ("Construction of a boundary wall and fence.", "residential"),
        ("Retention of an existing garage/storage shed.", "residential"),
        ("Minor internal alterations to an existing dwelling.", "residential"),
        ("Construction of a car park extension at an existing dwelling.", "residential"),
    ],
)
def test_site_only_retention_or_minor_work_remains_without_electrical_evidence(
    description: str,
    category: str,
) -> None:
    result = _score(description=description, category=category)

    assert result.electrical_work_brief.evidence_level == "unavailable"
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    ("electrical_words", "expected_points"),
    [
        ("EV charging points", 30),
        ("solar PV", 25),
        ("electrical substation", 30),
        ("external lighting scheme", 20),
        ("electrical works", 30),
    ],
)
def test_direct_electrical_evidence_overrides_possible_conversion_inference(
    electrical_words: str,
    expected_points: int,
) -> None:
    result = _score(
        description=f"{DOCTORS_SURGERY_DESCRIPTION} Including {electrical_words}.",
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == "direct"
    assert result.score_breakdown.electrical_relevance == expected_points


def test_trivial_residential_alteration_remains_without_electrical_evidence() -> None:
    result = _score(
        description="Minor alterations to an existing dwelling.",
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == "unavailable"
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    "description",
    [
        "Retention of an existing dwelling house.",
        "Demolition of a dwelling house.",
    ],
)
def test_existing_dwelling_references_do_not_create_textual_unit_counts(
    description: str,
) -> None:
    result = _score(description=description, category="residential")

    assert result.score_breakdown.project_scale == 0
    assert result.score_breakdown.electrical_relevance == 0
    assert result.electrical_work_brief.evidence_level == "unavailable"


def test_new_school_building_has_inferred_electrical_work() -> None:
    result = _score(
        description="Construction of a new school building.",
        category="other",
    )

    assert result.electrical_work_brief.evidence_level == "inferred"
    assert result.score_breakdown.electrical_relevance == 12
    assert result.electrical_work_brief.signals == ()


def test_substantial_school_extension_has_inferred_electrical_work() -> None:
    result = _score(
        description=(
            "Construction of a substantial two-storey extension to an existing "
            "school building."
        ),
        category="other",
    )

    assert result.electrical_work_brief.evidence_level == "inferred"
    assert result.score_breakdown.electrical_relevance == 10
    assert result.electrical_work_brief.signals == ()


def test_plausible_small_school_alterations_are_possible_electrical_work() -> None:
    result = _score(
        description="Internal alterations to an existing school classroom.",
        category="other",
    )

    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.score_breakdown.electrical_relevance == 6
    assert result.electrical_work_brief.signals == ()


@pytest.mark.parametrize(
    "description",
    [
        "Construction of a school car park, service road, turning area, and entrance works.",
        "Construction of a new school car park.",
        "Construction of a school play area, garden, landscaping, and boundary works.",
        "Construction of a community centre boundary wall.",
        "Demolition of a public library building.",
        "Demolition of a public building.",
        "School playground redevelopment.",
        "Community garden works.",
        "Public car park extension.",
        "School entrance alterations.",
    ],
)
def test_school_site_only_work_remains_without_electrical_evidence(
    description: str,
) -> None:
    result = _score(description=description, category="other")

    assert result.electrical_work_brief.evidence_level == "unavailable"
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    "description",
    [
        "Demolition of a dwelling house.",
        "Retention of an existing dwelling.",
        "Alterations to an existing dwelling.",
        "Construction of garden works at an existing dwelling.",
        "Construction of a 120 sqm car park extension at an existing dwelling.",
        "Construction of a boundary wall at an existing dwelling.",
    ],
)
def test_existing_dwelling_work_does_not_infer_new_electrical_work(
    description: str,
) -> None:
    result = _score(
        description=description,
        number_residential_units=1,
        category="residential",
    )

    assert result.electrical_work_brief.evidence_level == "unavailable"
    assert result.score_breakdown.electrical_relevance == 0


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("Construction of a new commercial building.", "commercial"),
        ("Construction of a new industrial manufacturing facility.", "industrial"),
    ],
)
def test_substantial_business_development_retains_inferred_electrical_work(
    description: str,
    category: str,
) -> None:
    result = _score(description=description, category=category)

    assert result.electrical_work_brief.evidence_level == "inferred"
    assert result.score_breakdown.electrical_relevance == 12


@pytest.mark.parametrize(
    ("description", "category", "units", "expected_points"),
    [
        (
            "Construction of a new dwelling with EV charging points.",
            "residential",
            1,
            30,
        ),
        (
            "Construction of 10 apartments with solar PV.",
            "residential",
            10,
            25,
        ),
        (
            "Construction of a new school with an electrical substation.",
            "other",
            None,
            30,
        ),
    ],
)
def test_direct_electrical_evidence_overrides_contextual_inference(
    description: str,
    category: str,
    units: int | None,
    expected_points: int,
) -> None:
    result = _score(
        description=description,
        category=category,
        number_residential_units=units,
    )

    assert result.electrical_work_brief.evidence_level == "direct"
    assert result.score_breakdown.electrical_relevance == expected_points


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


def test_existing_own_door_maisonette_amendments_do_not_infer_new_electrical_work() -> None:
    result = _score(
        description=OWN_DOOR_MAISONETTE_DESCRIPTION,
        number_residential_units=0,
        floor_area=0.0,
        received_date=date(2024, 12, 16),
        category="residential",
    )

    assert result.raw_opportunity_score == 65
    assert result.opportunity_score == 39
    assert result.opportunity_level == "low"
    assert result.score_breakdown == OpportunityScoreBreakdown(30, 0, 20, 8, 7)
    assert "Large residential unit count" in result.reasons
    assert result.electrical_work_brief.evidence_level == "unavailable"


@pytest.mark.parametrize(
    ("unit_count", "expected_scale"),
    [(1, 4), (8, 8)],
)
def test_own_door_wording_does_not_inflate_single_or_small_developments(
    unit_count: int,
    expected_scale: int,
) -> None:
    unit_label = "unit" if unit_count == 1 else "units"
    result = _score(
        description=(
            f"Alterations to {unit_count} no. own-door maisonette/apartment "
            f"{unit_label}."
        ),
        category="residential",
    )

    assert result.score_breakdown.project_scope == 10
    assert result.score_breakdown.project_scale == expected_scale
    assert result.score_breakdown.electrical_relevance == 0


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


def test_explicit_non_residential_electrical_equipment_evidence_is_preserved() -> None:
    result = _score(
        description=(
            "Construction of a new industrial manufacturing facility with "
            "substantial electrical plant and electrical equipment."
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
def test_scores_are_bounded_and_breakdown_sums_to_raw_score(values: dict) -> None:
    result = _score(**values)

    assert 0 <= result.opportunity_score <= 100
    assert result.score_breakdown.total == result.raw_opportunity_score
    assert result.opportunity_score <= result.raw_opportunity_score
    assert result.score_breakdown.project_scope <= 30
    assert result.score_breakdown.electrical_relevance <= 30
    assert result.score_breakdown.project_scale <= 20
    assert result.score_breakdown.lead_timing <= 10
    assert result.score_breakdown.category_fit <= 10


@pytest.mark.parametrize(
    ("raw_score", "evidence_level", "expected_score", "expected_level"),
    [
        (35, "unavailable", 35, "low"),
        (70, "unavailable", 39, "low"),
        (35, "possible", 35, "low"),
        (70, "possible", 59, "medium"),
        (55, "inferred", 55, "medium"),
        (85, "inferred", 79, "high"),
        (85, "direct", 85, "very_high"),
    ],
)
def test_electrical_evidence_ceiling_controls_effective_score_and_level(
    raw_score: int,
    evidence_level: str,
    expected_score: int,
    expected_level: str,
) -> None:
    effective_score = _effective_opportunity_score(raw_score, evidence_level)

    assert effective_score == expected_score
    assert opportunity_level_for_score(effective_score) == expected_level
    assert ELECTRICAL_EVIDENCE_SCORE_CEILINGS[evidence_level] in {39, 59, 79, 100}


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


def test_score_components_use_the_same_awarded_points_and_triggered_evidence() -> None:
    result = _score(
        description=(
            "Construction of a new commercial building including 12 EV "
            "charging points and associated site works."
        ),
        floor_area=6000.0,
        received_date=date(2025, 1, 10),
        category="commercial",
    )

    assert result.opportunity_score == 100
    assert result.score_breakdown == OpportunityScoreBreakdown(30, 30, 20, 10, 10)
    components = {component.name: component for component in result.score_components}
    assert tuple(components) == tuple(SCORE_COMPONENT_MAXIMUMS)
    assert {
        name: (component.points_awarded, component.maximum_points)
        for name, component in components.items()
    } == {
        "project_scope": (30, 30),
        "electrical_relevance": (30, 30),
        "project_scale": (20, 20),
        "lead_timing": (10, 10),
        "category_fit": (10, 10),
    }
    assert components["project_scope"].explanation == (
        "New commercial development indicators were identified."
    )
    assert components["electrical_relevance"].explanation == (
        'The planning description includes "ev charging", a strong electrical '
        "indicator."
    )
    assert components["project_scale"].explanation == (
        "A floor area of 6,000 square metres was identified, indicating a very large "
        "development."
    )
    assert components["lead_timing"].explanation == (
        "The application was received 5 days ago, within the last 14 days."
    )
    assert components["category_fit"].explanation == (
        "The application is classified as Commercial, which receives 10 "
        "points for category fit."
    )


def test_zero_point_components_explain_missing_or_unmatched_evidence() -> None:
    result = _score(category="other")

    assert result.opportunity_score == 3
    assert result.score_breakdown == OpportunityScoreBreakdown(0, 0, 0, 0, 3)
    components = {component.name: component for component in result.score_components}
    assert components["project_scope"].explanation == (
        "No qualifying project scope was identified."
    )
    assert components["electrical_relevance"].explanation == (
        "No qualifying electrical work indicators were identified."
    )
    assert components["project_scale"].explanation == (
        "No valid residential unit count or floor area was available."
    )
    assert components["lead_timing"].explanation == (
        "No received date was available, so no lead timing points were awarded."
    )
    assert all(component.explanation for component in result.score_components)


def test_invalid_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported planning category"):
        _score(category="agricultural")


@pytest.mark.parametrize(
    ("description", "category", "floor_area", "work_type", "evidence"),
    [
        (
            "Construction of a commercial building with EV charging points.",
            "commercial",
            800.0,
            "ev_charging",
            "ev charging",
        ),
        (
            "Construction of an electrical substation and associated site works.",
            "infrastructure",
            None,
            "substation_distribution",
            "electrical substation",
        ),
        (
            "Development of a battery energy storage facility.",
            "energy",
            None,
            "battery_storage",
            "battery energy storage",
        ),
        (
            "Development of a solar farm with associated infrastructure.",
            "energy",
            None,
            "renewable_generation",
            "solar farm",
        ),
        (
            "Construction of a commercial car park lighting installation.",
            "commercial",
            None,
            "lighting",
            "lighting installation",
        ),
        (
            "Construction of an industrial facility with electrical equipment.",
            "industrial",
            900.0,
            "electrical_plant_equipment",
            "electrical equipment",
        ),
    ],
)
def test_electrical_work_brief_reports_direct_evidence(
    description: str,
    category: str,
    floor_area: float | None,
    work_type: str,
    evidence: str,
) -> None:
    result = _score(
        description=description,
        category=category,
        floor_area=floor_area,
    )

    assert result.electrical_work_brief.evidence_level == "direct"
    assert result.electrical_work_brief.signals[0].work_type == work_type
    assert result.electrical_work_brief.signals[0].evidence == evidence


def test_electrical_work_brief_groups_multiple_direct_signals() -> None:
    result = _score(
        description=(
            "Construction of a commercial development with EV charging, solar "
            "photovoltaic panels and car park lighting."
        ),
        category="commercial",
        floor_area=1200.0,
    )

    brief = result.electrical_work_brief
    assert brief.evidence_level == "direct"
    assert [signal.work_type for signal in brief.signals] == [
        "ev_charging",
        "renewable_generation",
        "lighting",
    ]
    assert brief.summary == (
        "Electrical work evidenced: EV charging infrastructure, renewable or solar "
        "electrical infrastructure, lighting work."
    )


def test_large_development_without_direct_evidence_has_an_inferred_brief() -> None:
    result = _score(
        description="Construction of a new industrial manufacturing facility.",
        category="industrial",
        floor_area=2500.0,
        received_date=date(2024, 12, 20),
    )

    assert result.opportunity_score == 76
    assert result.electrical_work_brief.evidence_level == "inferred"
    assert result.electrical_work_brief.signals == ()
    assert "review plans for confirmation" in result.electrical_work_brief.summary


def test_weak_application_has_an_unavailable_electrical_work_brief() -> None:
    result = _score(description="Retention of a shop sign.", category="other")

    assert result.electrical_work_brief.evidence_level == "unavailable"
    assert result.electrical_work_brief.signals == ()
    assert result.electrical_work_brief.summary == (
        "Electrical work is not evidenced by the available planning data."
    )


def test_minor_lighting_replacement_is_a_possible_electrical_work_brief() -> None:
    result = _score(
        description="Replacement of one external light fitting.",
        category="other",
    )

    assert result.score_breakdown.electrical_relevance == 5
    assert result.electrical_work_brief.evidence_level == "possible"
    assert result.electrical_work_brief.signals == ()
    assert result.electrical_work_brief.summary == (
        "Possible limited electrical work: replacement of one external light "
        "fitting."
    )


def test_explicit_electrical_equipment_is_direct_regardless_of_project_scope() -> None:
    result = _score(
        description="Electrical equipment upgrade to an existing retail unit.",
        category="commercial",
    )

    assert result.electrical_work_brief.evidence_level == "direct"
    assert result.electrical_work_brief.signals[0].work_type == (
        "electrical_plant_equipment"
    )
    assert result.electrical_work_brief.signals[0].evidence == "electrical equipment"
    assert result.score_breakdown.electrical_relevance == 15


@pytest.mark.parametrize(
    "description",
    [
        "Installation of mechanical equipment in a retail unit.",
        "New playground equipment at a school.",
        "Replacement kitchen equipment in a restaurant.",
    ],
)
def test_generic_equipment_does_not_create_direct_electrical_evidence(
    description: str,
) -> None:
    result = _score(description=description, category="commercial")

    assert result.electrical_work_brief.evidence_level != "direct"
    assert result.electrical_work_brief.signals == ()


@pytest.mark.parametrize(
    ("description", "work_type"),
    [
        (
            "Replacement of one external light fitting and installation of solar PV.",
            "renewable_generation",
        ),
        (
            "Replacement of one external light fitting and EV charging points.",
            "ev_charging",
        ),
    ],
)
def test_minor_lighting_does_not_hide_stronger_direct_evidence(
    description: str,
    work_type: str,
) -> None:
    result = _score(description=description, category="commercial")

    assert result.electrical_work_brief.evidence_level == "direct"
    assert work_type in [
        signal.work_type for signal in result.electrical_work_brief.signals
    ]


def test_direct_electrical_evidence_takes_precedence_over_inference() -> None:
    result = _score(
        description=(
            "Construction of a new industrial manufacturing facility with EV "
            "charging points."
        ),
        category="industrial",
        floor_area=2500.0,
        received_date=date(2024, 12, 20),
    )

    assert result.opportunity_score == 94
    assert result.electrical_work_brief.evidence_level == "direct"
    assert [signal.work_type for signal in result.electrical_work_brief.signals] == [
        "ev_charging"
    ]


@pytest.mark.parametrize(
    "description",
    [
        "Construction of a new industrial facility with a wastewater treatment plant.",
        "Construction of a new commercial development with solar shading.",
        "Construction of a new commercial development; no EV charging is proposed.",
        "Construction of a new commercial development with bicycle charging points.",
        "Construction of a new commercial development; no external lighting scheme is proposed.",
        "Development without solar PV.",
        "Development that does not include battery storage.",
    ],
)
def test_generic_or_negated_terms_do_not_create_direct_electrical_evidence(
    description: str,
) -> None:
    result = _score(description=description, category="commercial")

    assert result.electrical_work_brief.evidence_level != "direct"
    assert result.electrical_work_brief.signals == ()


@pytest.mark.parametrize(
    ("description", "work_type"),
    [
        ("Construction of a building with EV charging points.", "ev_charging"),
        ("Construction of an electrical substation.", "substation_distribution"),
        ("Development of a battery energy storage facility.", "battery_storage"),
        ("Development with solar PV and photovoltaic panels.", "renewable_generation"),
        ("Installation of a new external lighting scheme.", "lighting"),
        ("Construction with explicit electrical installation works.", "electrical_installation"),
    ],
)
def test_specific_electrical_terms_remain_direct_evidence(
    description: str,
    work_type: str,
) -> None:
    result = _score(description=description, category="commercial")

    assert result.electrical_work_brief.evidence_level == "direct"
    assert work_type in [
        signal.work_type for signal in result.electrical_work_brief.signals
    ]
