from dataclasses import asdict

import pytest

from engine.book_calc import BookCalculationError, calculate_book


def book_section(**overrides):
    section = {
        "name": "КНИЖКА",
        "system": "КНИЖКА",
        "width": 3000,
        "height": 2500,
        "panels": 4,
        "quantity": 1,
        "glass_type": "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        "book_system": "B25",
        "door_side": "right",
        "doors": 1,
        "book_right_door_hardware": "handle",
        "book_right_door_opening": "inside_in",
        "compensator": "lower",
    }
    section.update(overrides)
    return section


@pytest.mark.parametrize("panels", range(2, 7))
def test_direct_sections_two_to_six_panels_use_tz_width_formula(panels):
    width = 3000
    result = calculate_book(book_section(width=width, panels=panels))
    expected = round((width - 11.5 - 11.5 - 3 * (panels - 1)) / panels, 1)

    assert len(result.panels) == panels
    assert {panel.glass_width_mm for panel in result.panels} == {expected}
    assert {panel.glass_profile_width_mm for panel in result.panels} == {
        round(expected + 3, 1)
    }
    width_formula = next(item for item in result.formulas if item.key == "glass_width")
    assert width_formula.source == "tz"
    assert width_formula.status == "confirmed"
    assert result.configuration_status == "confirmed"
    assert result.documents_allowed is True
    assert result.production_sheet_implemented is True
    assert result.documents_implemented is False


def test_tz_formula_has_priority_over_conflicting_excel_width_formula():
    result = calculate_book(book_section(width=3000, panels=4))
    # ТЗ: 742,0; формула из нового Excel для тех же входных данных дала бы 741.
    assert result.panels[0].glass_width_mm == 742.0
    trace = next(item for item in result.formulas if item.key == "glass_width")
    assert trace.source == "tz"
    assert result.source_priority == ["tz", "excel", "legacy"]


@pytest.mark.parametrize(
    ("compensator", "expected_height"),
    [
        ("lower", 2365.0),
        ("both", 2385.0),
        ("upper", 2370.0),
        ("none", 2383.0),
    ],
)
def test_b25_height_depends_on_compensator(compensator, expected_height):
    result = calculate_book(book_section(compensator=compensator))

    assert {panel.glass_height_mm for panel in result.panels} == {expected_height}
    assert result.normalized_config["book_system"] == "B25"
    assert result.normalized_config["height_family"] == "B25"


@pytest.mark.parametrize("book_system", ["B16", "B17", "C16", "C17"])
def test_legacy_profile_systems_use_explicit_preliminary_height_family(book_system):
    result = calculate_book(book_section(book_system=book_system))
    standard = result.panels[0]
    door = result.panels[-1]

    assert standard.glass_height_mm == 2398.0
    assert door.glass_height_mm == 2365.0
    assert standard.panel_height_mm == 2365.0
    assert result.normalized_config["book_system"] == book_system
    assert result.normalized_config["height_family"] == "B16"
    assert result.configuration_status == "preliminary"
    assert result.documents_allowed is False
    assert any(book_system in reason for reason in result.document_block_reasons)
    height_formula = next(
        item for item in result.formulas if item.key == "glass_height"
    )
    assert height_formula.source == "legacy"


@pytest.mark.parametrize(
    ("compensator", "standard_height", "door_height"),
    [
        ("lower", 2398.0, 2365.0),
        ("both", 2385.0, 2352.0),
        ("upper", 2370.0, 2337.0),
        ("none", 2383.0, 2350.0),
    ],
)
def test_b16_height_matrix_depends_on_compensator(
    compensator,
    standard_height,
    door_height,
):
    result = calculate_book(
        book_section(book_system="B16", compensator=compensator)
    )

    assert result.panels[0].glass_height_mm == standard_height
    assert result.panels[-1].glass_height_mm == door_height
    assert {panel.panel_height_mm for panel in result.panels} == {door_height}


def test_first_form_legacy_system_value_preserves_previous_b25_result_with_warning():
    result = calculate_book(book_section(book_system="Без каретки"))

    assert result.normalized_config["book_system"] == "B25"
    assert result.panels[0].glass_height_mm == 2365.0
    assert any("перенесено в B25" in warning for warning in result.warnings)


def test_unknown_book_profile_system_is_rejected():
    with pytest.raises(BookCalculationError, match="B25, B16, B17, C16 или C17"):
        calculate_book(book_section(book_system="UNKNOWN"))


@pytest.mark.parametrize(
    ("layout", "expected_roles", "expected_movements"),
    [
        ("left", ["door", "standard", "standard", "standard"], {"left"}),
        ("right", ["standard", "standard", "standard", "door"], {"right"}),
        ("both", ["door", "standard", "standard", "door"], {"left", "right"}),
    ],
)
def test_left_right_and_both_door_layouts(
    layout,
    expected_roles,
    expected_movements,
):
    doors = 2 if layout == "both" else 1
    result = calculate_book(
        book_section(
            door_side=layout,
            doors=doors,
            book_left_stack_panels=2,
            book_left_door_hardware="handle",
            book_right_door_hardware="lock",
        )
    )

    assert [panel.role for panel in result.panels] == expected_roles
    assert {
        panel.movement_direction
        for panel in result.panels
        if panel.movement_direction != "none"
    } == expected_movements


@pytest.mark.parametrize(
    "opening",
    ["inside_in", "inside_out", "outside_out", "outside_in"],
)
@pytest.mark.parametrize("side", ["left", "right"])
def test_all_four_openings_are_bound_to_the_physical_door(side, opening):
    kwargs = {
        "door_side": side,
        "doors": 1,
        f"book_{side}_door_hardware": "lock",
        f"book_{side}_door_opening": opening,
    }
    result = calculate_book(book_section(**kwargs))
    door = next(panel for panel in result.panels if panel.role == "door")

    assert door.door_side == side
    assert door.door_hardware == "lock"
    assert door.door_opening == opening
    assert door.door_opening_label


@pytest.mark.parametrize(
    ("compensator", "expected_qty", "position"),
    [
        ("lower", 1, "Низ"),
        ("upper", 1, "Верх"),
        ("both", 2, "Верх и низ"),
    ],
)
def test_compensator_variants_keep_profile_quantity_and_position(
    compensator,
    expected_qty,
    position,
):
    result = calculate_book(book_section(compensator=compensator, quantity=2))
    profile = next(item for item in result.profiles if item.article == "RBP003")

    assert profile.qty == expected_qty * 2
    assert profile.position == position
    assert profile.source == "tz"


@pytest.mark.parametrize(
    "feature",
    [
        {"angle_left": 90},
        {
            "book_extra_door_enabled": True,
            "book_extra_door_panel": 2,
            "book_extra_door_width": 700,
            "book_extra_door_opening": "inside_out",
        },
    ],
)
def test_unconfirmed_configurations_are_preliminary_and_block_documents(feature):
    result = calculate_book(book_section(**feature))

    assert result.configuration_status == "preliminary"
    assert result.documents_allowed is False
    assert result.document_block_reasons
    assert any("заблокированы" in warning for warning in result.warnings)


def test_legacy_fixed_panel_is_confirmed_and_does_not_block_documents():
    result = calculate_book(
        book_section(
            book_extra_fixed_enabled=True,
            book_extra_fixed_width=500,
            book_extra_fixed_side="left",
        )
    )

    fixed = next(panel for panel in result.panels if panel.role == "fixed")
    assert fixed.role == "fixed"
    assert fixed.panel_width_mm == 500
    assert fixed.status == "confirmed"
    assert fixed.hardware_articles == []
    assert result.configuration_status == "confirmed"
    assert result.documents_allowed is True


def test_left_fixed_panel_keeps_physical_numbering_for_extra_door():
    result = calculate_book(
        book_section(
            door_side="left",
            doors=1,
            book_left_door_hardware="handle",
            book_extra_fixed_enabled=True,
            book_extra_fixed_width=500,
            book_extra_fixed_side="left",
            book_extra_door_enabled=True,
            book_extra_door_panel=5,
            book_extra_door_width=700,
        )
    )

    assert [(panel.number, panel.role) for panel in result.panels] == [
        (1, "fixed"),
        (2, "door"),
        (3, "standard"),
        (4, "standard"),
        (5, "moving_door"),
    ]
    assert result.normalized_config["extra_fixed_panel_number"] == 1
    assert result.normalized_config["extra_door_panel_number"] == 5


def test_result_is_serializable_and_contains_physical_panel_sources():
    payload = asdict(calculate_book(book_section()))

    assert payload["panels"][0]["number"] == 1
    assert payload["panels"][0]["dimension_sources"]["glass_width_mm"] == {
        "source": "tz",
        "status": "confirmed",
    }
    assert payload["formulas"]
    assert all(item["source"] in {"tz", "excel", "legacy"} for item in payload["formulas"])


def test_hardware_preserves_shipment_stage_and_tz_override():
    result = calculate_book(book_section(panels=5))
    compensator = next(item for item in result.hardware if item.article == "RBA0009")

    assert len(result.hardware) == 38
    assert {item.shipment_stage for item in result.hardware} == {1, 2}
    assert compensator.qty == 6
    assert compensator.source == "tz"
    assert "P + 1" in compensator.formula


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"width": 20}, "Суммарная ширина стекол"),
        ({"height": 100}, "Высота стекла"),
        ({"panels": 1}, "не меньше 2"),
        ({"quantity": 0}, "больше нуля"),
        ({"book_obstacle_distance": -1}, "не может быть отрицательным"),
        ({"book_handle_height": 2600}, "от 0 до высоты"),
    ],
)
def test_invalid_or_non_positive_dimensions_return_clear_error(overrides, message):
    with pytest.raises(BookCalculationError, match=message):
        calculate_book(book_section(**overrides))


def test_more_than_six_panels_are_supported():
    result = calculate_book(book_section(width=9000, panels=12))

    assert len(result.panels) == 12
    assert result.normalized_config["base_panel_count"] == 12
    assert result.documents_allowed is True


def test_four_fixed_positions_and_two_door_widths_have_stable_physical_order():
    result = calculate_book(
        book_section(
            width=5000,
            door_side="both",
            doors=2,
            book_left_stack_panels=2,
            book_left_door_hardware="handle",
            book_left_door_opening="inside_in",
            book_right_door_hardware="lock",
            book_right_door_opening="outside_out",
            book_left_door_width=700,
            book_right_door_width=710,
            book_left_fixed_left_enabled=True,
            book_left_fixed_left_width=400,
            book_left_fixed_right_enabled=True,
            book_left_fixed_right_width=410,
            book_right_fixed_left_enabled=True,
            book_right_fixed_left_width=420,
            book_right_fixed_right_enabled=True,
            book_right_fixed_right_width=430,
        )
    )

    assert [panel.role for panel in result.panels] == [
        "fixed",
        "door",
        "fixed",
        "standard",
        "standard",
        "fixed",
        "door",
        "fixed",
    ]
    assert [panel.panel_width_mm for panel in result.panels] == [
        400,
        700,
        410,
        955,
        955,
        420,
        710,
        430,
    ]
    assert [panel.movement_direction for panel in result.panels] == [
        "none",
        "left",
        "none",
        "left",
        "right",
        "none",
        "right",
        "none",
    ]
    assert sum(panel.panel_width_mm for panel in result.panels) == 4980
    assert result.normalized_config["physical_panel_count"] == 8
    assert result.normalized_config["fixed_panel_numbers"] == [1, 3, 6, 8]
    assert result.normalized_config["fixed_panels"] == {
        "left_fixed_left": 1,
        "left_fixed_right": 3,
        "right_fixed_left": 6,
        "right_fixed_right": 8,
    }
    assert result.documents_allowed is True


def test_fixed_panels_do_not_change_left_stack_counting():
    result = calculate_book(
        book_section(
            width=5000,
            door_side="both",
            doors=2,
            book_left_stack_panels=2,
            book_left_door_hardware="handle",
            book_left_fixed_left_enabled=True,
            book_left_fixed_left_width=400,
            book_left_fixed_right_enabled=True,
            book_left_fixed_right_width=410,
        )
    )

    moving = [panel.movement_direction for panel in result.panels if panel.role != "fixed"]
    assert moving == ["left", "left", "right", "right"]


def test_glass_dimensions_remain_available_when_dealer_orders_without_glass():
    result = calculate_book(book_section(glass_supplied=False))

    assert result.normalized_config["glass_supplied"] is False
    assert all(panel.glass_width_mm > 0 for panel in result.panels)
    assert all(panel.glass_type == "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ" for panel in result.panels)


def test_impossible_sum_of_specified_panel_widths_is_rejected():
    with pytest.raises(BookCalculationError, match="Ширина стекла стандартной панели"):
        calculate_book(
            book_section(
                width=1500,
                book_right_door_width=1000,
                book_right_fixed_left_enabled=True,
                book_right_fixed_left_width=900,
            )
        )


def test_legacy_book_fields_are_migrated_without_losing_semantics():
    result = calculate_book(
        book_section(
            door_side="Левая",
            doors=1,
            door_type="Тип 4",
            door_opening="Наружу",
            book_left_door_hardware=None,
            book_left_door_opening=None,
        )
    )
    door = next(panel for panel in result.panels if panel.role == "door")

    assert door.door_side == "left"
    assert door.door_hardware == "lock"
    assert door.door_opening == "inside_out"
