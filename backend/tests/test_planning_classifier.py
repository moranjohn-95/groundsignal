import pytest

from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
    classify_planning_application,
)


WAREHOUSE_DEMOLITION_DESCRIPTION = (
    "PLANNING PERMISSION FOR THE CONSTRUCTION OF A WAREHOUSE, HGV LOADING "
    "BAYS AND OFFICES TOGETHER WITH THE PROVISION OF NEW BOUNDARY FENCING, "
    "CAR PARKING AND DEMOLITION OF THE EXISTING WING WALLS ALONG THE SOUTH "
    "WESTERN BOUNDARY, INCLUSIVE OF ALL ANCILLARY SITE WORKS, LANDSCAPING "
    "AND DRAINAGE, ALL AT TONBWEE, CASTLEISLAND, CO. KERRY"
)

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

HOUSES_APARTMENTS_DUPLEXES_COMMERCIAL_DESCRIPTION = (
    "to construct a development consisting of: (A) 5 No. three-bedroom "
    "terrace dwelling houses, (B) 1 No. one bed apartment (C) 5 No. two "
    "bedrooms apartments, (D) 5 no. three bedrooms duplex (E) 2 No. "
    "commercial units (F) 1 No. office building (G) ancillary services "
    "including bins and bikes storage, (H) site services including roads, "
    "paths, green areas and associated site works"
)

DOCTORS_SURGERY_DESCRIPTION = (
    "Full planning permission to, A) change of use of the existing dwelling "
    "house to doctors surgery, B) demolish existing garage, C) permission for "
    "associated signage, D) internal alterations to existing dwelling house to "
    "accommodate doctors surgery and minor elevational alterations to the "
    "existing dwelling house and all ancillary site development works."
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


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        pytest.param(
            DOCTORS_SURGERY_DESCRIPTION,
            "commercial",
            id="2660737-dwelling-to-doctors-surgery",
        ),
        (
            "Change of use of an existing dwelling house to an office.",
            "commercial",
        ),
        (
            "Change of use of an existing house to a retail shop.",
            "commercial",
        ),
        (
            "Conversion of an existing warehouse to eight apartments.",
            "residential",
        ),
        (
            "Convert an existing commercial unit into six apartments.",
            "residential",
        ),
        (
            "Internal alterations to an existing dwelling house to accommodate a "
            "doctors surgery.",
            "commercial",
        ),
        (
            "Internal alterations to an existing dwelling house and porch.",
            "residential",
        ),
        (
            "Extension to the existing dwelling house to accommodate a larger "
            "kitchen.",
            "residential",
        ),
        (
            "Conversion of an existing warehouse into apartments and associated "
            "site works.",
            "residential",
        ),
        (
            "Alterations to an existing dwelling house with an ancillary office.",
            "residential",
        ),
    ],
)
def test_explicit_proposed_use_overrides_existing_use_context(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


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


def test_separate_residential_and_commercial_units_are_mixed_use() -> None:
    assert (
        classify_planning_application(
            HOUSES_APARTMENTS_DUPLEXES_COMMERCIAL_DESCRIPTION
        )
        == "mixed_use"
    )


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Construction of two commercial units and an ancillary office.",
            "commercial",
        ),
        (
            "Construction of eight apartments with a home office for each "
            "resident.",
            "residential",
        ),
        ("A warehouse containing ancillary offices.", "industrial"),
        ("A hotel containing a staff apartment.", "commercial"),
    ],
)
def test_separate_commercial_unit_rule_preserves_single_use_developments(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


def test_demolished_use_does_not_determine_replacement_use() -> None:
    result = classify_planning_application(
        "Demolition of an existing shop and construction of one dwelling."
    )

    assert result == "residential"


def test_primary_warehouse_before_ancillary_demolition_is_industrial() -> None:
    assert (
        classify_planning_application(WAREHOUSE_DEMOLITION_DESCRIPTION)
        == "industrial"
    )


def test_staff_accommodation_outranks_ancillary_photovoltaic_panels() -> None:
    assert (
        classify_planning_application(ACCOMMODATION_SOLAR_DESCRIPTION)
        == "residential"
    )


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Construction of a standalone warehouse.", "industrial"),
        (
            "Construction of a warehouse with ancillary loading bays and "
            "offices.",
            "industrial",
        ),
        ("Development of a standalone solar farm.", "energy"),
        (
            "Installation of a ground-mounted photovoltaic array with inverter "
            "equipment and associated electrical works.",
            "energy",
        ),
        (
            "Construction of a detached dwelling with ancillary roof-mounted "
            "photovoltaic panels.",
            "residential",
        ),
        (
            "Construction of a commercial office building with ancillary "
            "roof-mounted solar panels.",
            "commercial",
        ),
    ],
)
def test_warehouse_and_solar_scoping_protections(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


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
    "description",
    [
        (
            "to construct a new cow storage cubicle house and storage tank, "
            "new above ground slurry store, ..."
        ),
        "Construction of a cattle cubicle house and associated farm works.",
        "Permission for a poultry house and manure storage tank.",
    ],
)
def test_agricultural_house_uses_are_not_residential(
    description: str,
) -> None:
    assert classify_planning_application(description) == "other"


@pytest.mark.parametrize(
    "description",
    [
        "Construction of a house.",
        "Construction of a dwelling house.",
        "Construction of a detached house.",
        "Construction of a house extension.",
    ],
)
def test_agricultural_house_refinement_preserves_residential_uses(
    description: str,
) -> None:
    assert classify_planning_application(description) == "residential"


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        pytest.param(
            "Construction of a Pig Finishing Unit, two meal bins, two water "
            "tanks, roof mounted solar panels and all associated site works",
            "other",
            id="pig-unit-with-solar-panels-41",
        ),
        pytest.param(
            "the construction of a Pig Finishing Unit, Two Meal Bins, Two "
            "Water Tanks, Roof Mounted Solar Panels and all associated works",
            "other",
            id="pig-unit-with-solar-panels-135",
        ),
        pytest.param(
            "The removal of porch and gable end of existing farmhouse, "
            "construction of a new two storey extension to the side and rear "
            "of the existing farmhouse, a wastewater treatment system and "
            "all associated site works",
            "residential",
            id="farmhouse-extension-273-314",
        ),
        pytest.param(
            "Development of a sports ground including an all-weather "
            "artificial turf pitch, floodlighting, fencing and an access road",
            "other",
            id="sports-ground-17",
        ),
        pytest.param(
            "Construction of an all-weather playing pitch with artificial "
            "turf, car parking, wastewater works and associated site works",
            "other",
            id="all-weather-pitch-72",
        ),
        pytest.param(
            "construction of a detached storey and a half double garage and "
            "tool shed with home office at first floor level",
            "other",
            id="ancillary-home-office-129",
        ),
        pytest.param(
            "A new 2-storey quality operations building to the north-east "
            "elevation of the existing MSD main production facility. The "
            "proposed building will comprise ground floor and first floor "
            "accommodation with a new link to the main entrance, including "
            "associated plant, modifications to existing site utilities, a "
            "delivery road to the rear and landscaping",
            "industrial",
            id="production-facility-191",
        ),
    ],
)
def test_persisted_backfill_quality_regressions(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


def test_home_office_is_residential_when_dwelling_context_supports_it() -> None:
    result = classify_planning_application(
        "Construction of a detached garage with a home office at first floor "
        "level ancillary to the existing dwelling."
    )

    assert result == "residential"


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Construction of a forest access road.", "infrastructure"),
        (
            "Change of use of an existing building to light industrial use.",
            "industrial",
        ),
        ("Construction of a battery energy storage facility.", "energy"),
        (
            "Upgrade of wastewater treatment and sludge drying works.",
            "infrastructure",
        ),
        ("Development of a solar farm and associated works.", "energy"),
        ("Development of a wind farm and associated roads.", "energy"),
        (
            "Mixed-use development with ground-floor offices and apartments "
            "on the upper floors.",
            "mixed_use",
        ),
    ],
)
def test_backfill_refinements_preserve_primary_use_classifications(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    "description",
    [
        (
            "a new Advance Technology Building. Permission is also sought "
            "for signage, new timber post-and-rail site boundaries, car "
            "parking, cycle shelter, landscaping, underground water storage "
            "tank, ESB substation/switch room and all associated site works."
        ),
        (
            "a new Advance Technology Building. Permission is also sought "
            "for signage, new timber post-and-rail site boundaries, car "
            "parking, cycle shelter, landscaping, underground water storage "
            "tank, ESB substation, switch room, access road and all associated "
            "site works."
        ),
    ],
)
def test_additional_substation_does_not_override_primary_building(
    description: str,
) -> None:
    assert classify_planning_application(description) == "other"


def test_advance_technology_building_alone_is_not_energy() -> None:
    assert (
        classify_planning_application("A new Advance Technology Building.")
        == "other"
    )


def test_ancillary_energy_scoping_is_not_specific_to_technology_buildings(
) -> None:
    result = classify_planning_application(
        "A new community building. Permission is also sought for an "
        "electrical substation, access road and associated site works."
    )

    assert result == "other"


@pytest.mark.parametrize(
    "description",
    [
        "Construction of a standalone ESB substation and switch room.",
        (
            "Development of a new electrical substation. Permission is also "
            "sought for an access road and landscaping."
        ),
        "Permission is also sought for a new electricity substation.",
    ],
)
def test_ancillary_energy_scoping_preserves_primary_substations(
    description: str,
) -> None:
    assert classify_planning_application(description) == "energy"


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


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Construction of a single-storey workshop for a haulage business "
            "with a new entrance from the public road.",
            "industrial",
        ),
        (
            "Retention of a conversion of attic space at Blackrock Road, Cork.",
            "other",
        ),
        (
            "Construction of an extension and internal alterations at "
            "Carleton Road, Dublin.",
            "other",
        ),
        (
            "Refurbishment of a protected mews building with roof lights and "
            "photovoltaic panels.",
            "other",
        ),
        (
            "Minor alterations to a previously approved sports-pitch "
            "development, including an ESB substation.",
            "other",
        ),
        (
            "Permission to construct an agricultural slatted shed and a new "
            "farmyard entrance from the public road.",
            "other",
        ),
    ],
)
def test_context_does_not_promote_ancillary_infrastructure_or_energy_terms(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        (
            "Minor alterations to a previously approved development, "
            "including changes near an ESB substation.",
            "other",
        ),
        (
            "Amendments to an approved development involving minor changes "
            "around the existing substation.",
            "other",
        ),
        (
            "Construction of a standalone ESB substation and switch room.",
            "energy",
        ),
        (
            "Development of a solar farm with a new electrical substation.",
            "energy",
        ),
        (
            "Amendments to an approved solar farm development, including an "
            "ESB substation.",
            "energy",
        ),
        (
            "Amendments to an approved residential development, including "
            "changes around an ESB substation.",
            "residential",
        ),
    ],
)
def test_approved_development_amendments_keep_the_primary_category(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category


@pytest.mark.parametrize(
    ("description", "expected_category"),
    [
        ("Construction of a vehicle repair workshop.", "industrial"),
        ("Internal alterations at Bridge Street, Cork.", "other"),
        (
            "Construction of a dwelling with a new entrance from the public "
            "road.",
            "residential",
        ),
    ],
)
def test_general_term_refinements_apply_outside_the_benchmark(
    description: str,
    expected_category: str,
) -> None:
    assert classify_planning_application(description) == expected_category
