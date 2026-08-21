import pytest

from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
    classify_planning_application,
)


def test_supported_categories_are_stable() -> None:
    assert PLANNING_APPLICATION_CATEGORIES == (
        "residential",
        "commercial",
        "industrial",
        "energy",
        "infrastructure",
        "mixed_use",
        "other",
    )


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Permission for construction of a dwelling, domestic garage, "
            "proprietary effluent treatment system and associated site works.",
            "residential",
        ),
        (
            "Construction of a single-storey discount retail store and offices.",
            "commercial",
        ),
        (
            "Extension to an existing warehouse and manufacturing facility.",
            "industrial",
        ),
        (
            "A 10-year solar photovoltaic development with battery storage.",
            "energy",
        ),
        (
            "Upgrade of wastewater and water infrastructure, including a bridge.",
            "infrastructure",
        ),
        (
            "Mixed-use development comprising a shop and eight apartments.",
            "mixed_use",
        ),
        (
            "Retention of an agricultural storage shed and associated site works.",
            "other",
        ),
    ],
)
def test_each_category(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


def test_matching_is_case_insensitive_and_normalizes_punctuation() -> None:
    result = classify_planning_application(
        "INSTALLATION OF A BATTERY-STORAGE FACILITY."
    )

    assert result == "energy"


@pytest.mark.parametrize("description", [None, "", "   \r\n\t"])
def test_null_or_empty_description_falls_back_to_other(
    description: str | None,
) -> None:
    assert classify_planning_application(description) == "other"


def test_application_type_is_classification_input() -> None:
    result = classify_planning_application(
        description="Ancillary site development works.",
        application_type="Industrial Development",
    )

    assert result == "industrial"


def test_positive_residential_unit_count_is_residential_evidence() -> None:
    result = classify_planning_application(
        description="Construction of a new two-storey development.",
        application_type="Permission",
        number_residential_units=4,
        floor_area=420.0,
    )

    assert result == "residential"


@pytest.mark.parametrize("number_residential_units", [None, 0, -1, True])
def test_non_positive_or_boolean_unit_count_is_not_residential_evidence(
    number_residential_units: int | None,
) -> None:
    result = classify_planning_application(
        description="Construction of a new development.",
        number_residential_units=number_residential_units,
    )

    assert result == "other"


def test_floor_area_alone_does_not_imply_a_land_use() -> None:
    result = classify_planning_application(
        description=None,
        application_type="Permission",
        floor_area=5000.0,
    )

    assert result == "other"


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Solar panels on the roof of an existing dwelling.", "residential"),
        ("A new access road serving residential units.", "residential"),
        ("A warehouse containing ancillary offices.", "industrial"),
        ("A hotel containing a staff apartment.", "commercial"),
    ],
)
def test_overlapping_keywords_use_documented_precedence(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


def test_explicit_mixed_use_phrase_is_strong_evidence() -> None:
    result = classify_planning_application(
        "A MIXED-USE scheme comprising retail, offices and housing."
    )

    assert result == "mixed_use"


def test_separate_commercial_and_residential_floors_are_mixed_use() -> None:
    result = classify_planning_application(
        "Ground-floor retail unit with six apartments on the upper floors."
    )

    assert result == "mixed_use"


def test_layout_and_residential_unit_count_can_establish_mixed_use() -> None:
    result = classify_planning_application(
        description="A ground-floor retail unit with accommodation above.",
        number_residential_units=3,
    )

    assert result == "mixed_use"


def test_demolished_use_does_not_determine_replacement_use() -> None:
    result = classify_planning_application(
        "Demolition of an existing shop and construction of one dwelling."
    )

    assert result == "residential"


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "construction of a bungalow dwelling, wastewater treatment "
            "system, bored well, new entrance and associated site works",
            "residential",
        ),
        (
            "construction of a dwelling house with domestic solar panels",
            "residential",
        ),
        (
            "demolish existing derelict dwelling and erect fully serviced "
            "two storey dental surgery",
            "commercial",
        ),
        (
            "change of use of existing warehouse to convenience store",
            "commercial",
        ),
        (
            "development of a wind farm and associated site works",
            "energy",
        ),
        (
            "construction of a solar farm with photovoltaic panels and "
            "associated access tracks",
            "energy",
        ),
        (
            "construction of public cycleway and associated road works",
            "infrastructure",
        ),
        (
            "construction of warehouse and associated offices",
            "industrial",
        ),
        (
            "mixed-use development comprising ground floor retail and first "
            "floor residential apartments",
            "mixed_use",
        ),
        (
            "construction of dwelling with new entrance and access driveway",
            "residential",
        ),
    ],
)
def test_real_data_primary_purpose_regressions(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Permission to install an above-ground enclosure to house a new "
            "natural gas district regulating installation.",
            "other",
        ),
        (
            "Single-storey extension to the rear of a dwelling with domestic "
            "solar panels and a detached domestic garage.",
            "residential",
        ),
        (
            "Construct an extension to the rear of the existing dwelling and "
            "install a new wastewater treatment unit.",
            "residential",
        ),
        (
            "Construction of a dwellinghouse and detached garage with a new "
            "site entrance, access road and wastewater treatment unit.",
            "residential",
        ),
        (
            "Single-storey dwellinghouse, domestic garage and wastewater "
            "treatment system.",
            "residential",
        ),
        (
            "Demolition of temporary structures and construction of a museum "
            "with exhibition space, cafe, gift shop, parking and a wastewater "
            "treatment system.",
            "commercial",
        ),
        (
            "Development of training and playing pitches, dugouts, fencing, "
            "a public amenity walkway, exercise equipment and an access road.",
            "other",
        ),
    ],
)
def test_second_evaluation_primary_purpose_regressions(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Construction of a detached house.", "residential"),
        ("Solar farm with an associated access road.", "energy"),
        ("Wind farm with associated access roads.", "energy"),
        ("Public cycleway with associated site works.", "infrastructure"),
    ],
)
def test_context_refinement_preserves_legitimate_primary_uses(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Single storey extension to rear of dwelling, internal alterations "
            "to dwelling including conversion of garage for domestic use, "
            "external alterations including new slate/tile to roof, velux "
            "windows & solar panels, & new detached domestic garage",
            "residential",
        ),
        (
            "(a) Construct a split-level single-story extension to rear of "
            "existing dwelling. (b) demolish existing outhouse, construct new "
            "box dormer to front roof elevation and carry out alterations to "
            "existing dwelling. (c) install new wastewater treatment unit.",
            "residential",
        ),
        (
            "Permission for i) the demolition of existing temporary structures "
            "and removal of existing wastewater treatment plant, ii) the "
            "construction of a single storey museum incorporating exhibition "
            "space, cafe and gift shop, iii) provision of parking, iv) "
            "installation of a new wastewater treatment system.",
            "commercial",
        ),
    ],
)
def test_description_scoping_regressions(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Conversion of warehouse to retail store.", "commercial"),
        ("Convert an existing warehouse into a retail store.", "commercial"),
        (
            "Demolish an existing building and construct a dwelling.",
            "residential",
        ),
        (
            "Demolition of a building. Construction of a dwelling. Install "
            "solar panels.",
            "residential",
        ),
    ],
)
def test_scoping_fixes_preserve_supported_replacement_forms(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Installation of a broadband telecommunications cabinet.", "other"),
        ("Extension to an existing warehouse.", "industrial"),
        ("Alterations to an existing guesthouse.", "commercial"),
        ("Construction of a household waste storage enclosure.", "other"),
        ("A non-residential agricultural storage building.", "other"),
    ],
)
def test_whole_words_and_negated_uses_prevent_false_positives(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


def test_unclassified_application_returns_other() -> None:
    result = classify_planning_application(
        description="Retention of boundary walls and revised site entrance.",
        application_type="Retention",
        floor_area=42.0,
    )

    assert result == "other"
