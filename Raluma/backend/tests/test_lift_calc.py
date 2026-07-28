from types import SimpleNamespace

import pytest

from engine.lift_calc import calculate_lift
from engine.lift_config import LIFT_SPLIT_OPENING


def _section(**overrides):
    values = {
        "system": "ЛИФТ",
        "width": 2302,
        "height": 2229,
        "panels": 2,
        "quantity": 1,
        "painting_type": "RAL стандарт",
        "ral_color": "9016 МАТОВЫЙ",
        "lift_filling_type": "СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        "lift_filling_custom": None,
        "lift_control_type": "Пульт ДУ",
        "lift_remote_1ch_qty": 1,
        "lift_remote_6ch_qty": 0,
        "lift_cable_side": "Справа",
        "lift_opening_type": "Сдвиг вниз",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _profile_rows(result, article):
    return sorted(
        (row.length_mm, row.qty)
        for row in result.profiles
        if row.article == article
    )


def _hardware(result, article):
    return [row for row in result.hardware if row.article == article]


@pytest.mark.parametrize(
    ("section", "expected_panels", "expected_profiles"),
    [
        (
            _section(),
            [(2169, 1012.75), (2167, 1001.25)],
            {
                "RL113": [(955.25, 2), (2122, 1)],
                "RL112": [(966.75, 2)],
                "RL115": [(2122, 1), (2124, 1)],
                "RL114": [(2124, 1)],
                "RL105": [(1019.75, 2), (2067, 2)],
            },
        ),
        (
            _section(
                width=2600,
                height=2750,
                lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            ),
            [(2467, 1273.25), (2465, 1261.75)],
            {
                "RL123": [(1216.75, 2), (2423, 1)],
                "RL122": [(1228.25, 2)],
                "RL1241": [(2424, 2)],
                "RL1211": [(2424, 1)],
                "RL105": [(1280.25, 2), (2588, 2)],
            },
        ),
        (
            _section(width=3323, height=2910, panels=3),
            [
                (3190, 904.6666666667),
                (3188, 893.1666666667),
                (3188, 893.1666666667),
            ],
            {
                "RL113": [(848.1666666667, 4), (3146, 1)],
                "RL112": [(859.6666666667, 2)],
                "RL115": [(3146, 3), (3149, 1)],
                "RL114": [(3149, 1)],
                "RL105": [(916.6666666667, 2), (1809.8333333333, 2)],
            },
        ),
        (
            _section(
                width=2580,
                height=2140,
                panels=3,
                lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            ),
            [(2447, 648), (2447, 636.5), (2447, 636.5)],
            {
                "RL123": [(590.5, 4), (2402, 1)],
                "RL122": [(602, 2)],
                "RL1241": [(2402, 4)],
                "RL1211": [(2402, 1)],
                "RL105": [(660, 2), (1296.5, 2)],
            },
        ),
        (
            _section(width=2460, height=3950, panels=4),
            [
                (2326, 928.25),
                (2326, 917.25),
                (2326, 917.25),
                (2326, 917.25),
            ],
            {
                "RL113": [(883.25, 6), (2286, 3)],
                "RL112": [(872.25, 2)],
                "RL115": [(2286, 4)],
                "RL114": [(2286, 1)],
                "RL105": [(1903, 2), (2823, 2)],
            },
        ),
        (
            _section(
                width=2460,
                height=3950,
                panels=4,
                lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            ),
            [
                (2325, 927.25),
                (2325, 916.25),
                (2325, 916.25),
                (2325, 916.25),
            ],
            {
                "RL113": [(882.25, 6), (2286, 3)],
                "RL112": [(871.25, 2)],
                "RL115": [(2286, 4)],
                "RL114": [(2286, 1)],
                "RL105": [(1903, 2), (2823, 2)],
            },
        ),
        (
            _section(
                width=2460,
                height=3950,
                panels=4,
                lift_opening_type=LIFT_SPLIT_OPENING,
            ),
            [
                (2327, 914.5),
                (2327, 925.5),
                (2327, 914.5),
                (2327, 914.5),
            ],
            {
                "RL113": [(869.5, 6), (2282, 3)],
                "RL112": [(880.5, 2)],
                "RL115": [(2282, 4)],
                "RL114": [(2282, 1)],
                "RL105": [(1903, 2), (2823, 2)],
            },
        ),
        (
            _section(
                width=2460,
                height=3950,
                panels=4,
                lift_opening_type=LIFT_SPLIT_OPENING,
                lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            ),
            [
                (2327, 914.5),
                (2327, 925.5),
                (2327, 914.5),
                (2327, 914.5),
            ],
            {
                "RL113": [(869.5, 6), (2282, 3)],
                "RL112": [(880.5, 2)],
                "RL115": [(2282, 4)],
                "RL114": [(2282, 1)],
                "RL105": [(1903, 2), (2823, 2)],
            },
        ),
    ],
)
def test_lift_workbook_models(section, expected_panels, expected_profiles):
    result = calculate_lift(section)

    assert len(result.panels) == len(expected_panels)
    for panel, (width, height) in zip(result.panels, expected_panels, strict=True):
        assert panel.width_mm == pytest.approx(width)
        assert panel.height_mm == pytest.approx(height)

    for article, rows in expected_profiles.items():
        actual = _profile_rows(result, article)
        assert len(actual) == len(rows)
        for (actual_length, actual_qty), (length, qty) in zip(
            actual, sorted(rows), strict=True
        ):
            assert actual_length == pytest.approx(length)
            assert actual_qty == qty


def test_lift_common_profiles_are_aggregated_and_quantity_is_applied():
    result = calculate_lift(_section(quantity=2))

    assert _profile_rows(result, "RL101-1") == [(2296, 6)]
    assert _profile_rows(result, "RL101") == [(2296, 2)]
    assert _profile_rows(result, "RL103-2") == [(2068, 2)]
    assert all(panel.qty == 2 for panel in result.panels)


def test_lift_custom_20mm_filling_uses_igu_formulas():
    result = calculate_lift(
        _section(
            width=2600,
            height=2750,
            lift_filling_type="ДРУГОЕ 20мм",
            lift_filling_custom="СТЕКЛОПАКЕТ С МАТОВОЙ ПЛЕНКОЙ",
        )
    )

    assert result.filling_kind == "igu"
    assert result.filling_text == "СТЕКЛОПАКЕТ С МАТОВОЙ ПЛЕНКОЙ"
    assert _profile_rows(result, "RL123")
    assert not _profile_rows(result, "RL113")


def test_two_panel_igu_uses_penoplex_for_the_fixed_panel():
    result = calculate_lift(
        _section(
            width=2600,
            height=2750,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        )
    )

    assert [(panel.role, panel.filling) for panel in result.panels] == [
        ("Подвижная", "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)"),
        ("Глухая", "ПЕНОПЛЕКС 20 ММ"),
    ]


def test_two_panel_igu_penoplex_follows_the_fixed_panel_when_opening_up():
    result = calculate_lift(
        _section(
            width=2600,
            height=2750,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            lift_opening_type="Сдвиг вверх",
        )
    )

    assert [(panel.role, panel.filling) for panel in result.panels] == [
        ("Глухая", "ПЕНОПЛЕКС 20 ММ"),
        ("Подвижная", "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)"),
    ]


def test_lift_opening_changes_panel_order_but_not_dimensions():
    down = calculate_lift(_section(panels=3, width=3323, height=2910))
    up = calculate_lift(
        _section(
            panels=3,
            width=3323,
            height=2910,
            lift_opening_type="Сдвиг вверх",
        )
    )

    assert [panel.role for panel in down.panels] == [
        "Подвижная",
        "Подвижная",
        "Глухая",
    ]
    assert [panel.role for panel in up.panels] == [
        "Глухая",
        "Подвижная",
        "Подвижная",
    ]
    assert sorted(
        (panel.width_mm, panel.height_mm) for panel in down.panels
    ) == sorted((panel.width_mm, panel.height_mm) for panel in up.panels)


def test_lift_hardware_uses_torque_drive_and_cable_rules():
    one_drive = calculate_lift(
        _section(
            width=1500,
            height=1800,
            lift_remote_1ch_qty=2,
            lift_remote_6ch_qty=1,
        )
    )

    assert one_drive.torque is not None
    assert one_drive.torque.drive_count == 1
    assert _hardware(one_drive, "RL2085")[0].value == 1
    assert not _hardware(one_drive, "RL2095")
    assert _hardware(one_drive, "RL20901")[0].value == 1
    assert _hardware(one_drive, "RL20902")[0].value == 1
    assert _hardware(one_drive, "RL2087")[0].value == 2
    assert _hardware(one_drive, "RL2088")[0].value == 1

    two_drive = calculate_lift(
        _section(
            width=3000,
            height=3000,
            panels=3,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            lift_control_type="Кнопка",
            lift_cable_side="Слева",
        )
    )
    assert two_drive.torque is not None
    assert two_drive.torque.drive_count == 2
    assert _hardware(two_drive, "RL2095")[0].value == 2
    assert _hardware(two_drive, "RL2098")[0].value == 1
    assert not _hardware(two_drive, "RL203")
    assert not _hardware(two_drive, "RL207")
    assert _hardware(two_drive, "RL20904")[0].value == 1
    assert _hardware(two_drive, "RL2092")[0].value == 1


def test_lift_drive_boundary_uses_unrounded_weight_for_torque():
    result = calculate_lift(
        _section(
            width=2817,
            height=3660,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        )
    )

    assert result.torque is not None
    assert result.torque.moving_weight_kg == 160
    assert result.torque.torque_nm == 80
    assert result.torque.drive_count == 1


def test_lift_torque_over_160_adds_section_warning():
    result = calculate_lift(
        _section(
            width=5000,
            height=5000,
            panels=4,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        )
    )

    assert result.torque is not None
    assert result.torque.torque_nm > 160
    assert result.torque.warning
    assert result.torque.warning in result.warnings


def test_lift_chain_and_fasteners_follow_hardware_workbook():
    result = calculate_lift(_section(width=2302, height=2229, panels=2))

    chain = _hardware(result, "RL210")[0]
    expected_length = 1900
    assert chain.length_mm == expected_length
    assert chain.value == 2

    fasteners = {(item.name, item.value) for item in result.fasteners}
    assert ("Винт M6×10", 4) not in fasteners
    assert ("Винт M6×20", 8) in fasteners
    assert ("Саморез со сверлом 3,9×13 A2", 29) in fasteners


def test_lift_anodized_profiles_do_not_enter_painting():
    result = calculate_lift(
        _section(painting_type="Анодированный", ral_color="9016 МАТОВЫЙ")
    )

    assert result.color_text == "Анодированный"
    assert all(not profile.painted for profile in result.profiles)


def test_four_panel_igu_uses_profile_family_from_source_workbook():
    result = calculate_lift(
        _section(
            width=2460,
            height=3950,
            panels=4,
            lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        )
    )

    articles = {profile.article for profile in result.profiles}
    assert {"RL113", "RL112", "RL115", "RL114"} <= articles
    assert not {"RL123", "RL122", "RL1241", "RL1211"} & articles


def test_rl104_painting_depends_on_profile_application():
    result = calculate_lift(_section(width=3323, height=2910, panels=3))
    rows = [profile for profile in result.profiles if profile.article == "RL104"]

    assert len(rows) == 2
    assert {(row.length_mm, row.painted) for row in rows} == {
        (3168, True),
        (3261, False),
    }
