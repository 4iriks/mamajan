"""Production rounding agreed after the invoice 71 handle-profile check."""

from collections import Counter
from math import ceil

import pytest

from engine.cs_calc import calculate_cs, split_profile_lengths
from engine.cs_cover_cutting import cover_cuts
from engine.slide_calc import (
    PanelGlassItem,
    SlideCalcResult,
    _apply_two_row_glass_total_correction,
    calculate_slide,
)
from tests.test_oct29_fixes import narrow_cs, slide


@pytest.mark.parametrize("count", [4, 6, 8, 10])
@pytest.mark.parametrize(
    "width,expected",
    [
        (600, 600),
        (600.5, 600),
        (600.599999, 600),
        (600.6, 601),
        (600.600001, 601),
        (600.9375, 601),
    ],
)
def test_two_row_rounding_threshold_and_linked_profiles(count, width, expected):
    result = SlideCalcResult(
        panel_glass=[
            PanelGlassItem(i + 1, "", width, 2200, width - 3) for i in range(count)
        ]
    )
    _apply_two_row_glass_total_correction(result, expected * count)
    assert [p.width_mm for p in result.panel_glass] == [expected] * count
    assert [p.glass_profile_length for p in result.panel_glass] == [
        expected - 3
    ] * count
    assert not result.warnings


@pytest.mark.parametrize("quantity", [1, 2, 7])
def test_invoice_71_central_rs112_rounds_to_six_961_and_two_969(quantity):
    result = calculate_slide(
        slide(quantity=quantity, center_handle="Ручки-профиль RS112 (2шт)")
    )
    assert [p.width_mm for p in result.panel_glass] == [961] * 3 + [969] * 2 + [961] * 3
    assert sum(p.width_mm for p in result.panel_glass) == 7704
    assert 7704 - 5 - 5 - 47.5 + 9.5 * 6 == 7703.5
    assert not result.warnings
    assert sum(row.qty for row in result.glass) == 8 * quantity
    assert Counter(
        {row.length_mm: row.qty for row in result.profiles if row.article == "RS2021"}
    ) == {
        961: 2 * quantity,
        958: 4 * quantity,
        988: quantity,
        985: quantity,
    }


@pytest.mark.parametrize(
    "length,expected",
    [
        (1604.5, [1605]),
        (1604.01, [1605]),
        (1605, [1605]),
        (2999.9, [3000]),
        (3000, [3000]),
        (3000.1, [3000, 1]),
        (4604.5, [3000, 1605]),
        (6000, [3000, 3000]),
        (6000.1, [3000, 3000, 1]),
        (7500.2, [3000, 3000, 1501]),
    ],
)
def test_t40t_whole_mm_cuts_and_total(length, expected):
    cuts = split_profile_lengths([length])
    assert cuts == expected
    assert sum(cuts) == ceil(length)
    assert all(0 < size <= 3000 and size == int(size) for size in cuts)


def test_t40t_rounding_keeps_cover_allowances_and_geometry():
    result = calculate_cs(narrow_cs())
    outer = next(p for p in result["profiles"] if p["role"] == "outer")
    assert outer["cut_lengths_mm"] == [3000, 1499, 3000, 1594, 967]
    assert outer["total_length_mm"] == 20120
    assert outer["pieces"] == 10
    assert "1594 мм × 2 шт." in outer["cutting_text"]
    assert result["cover_cuts"] == cover_cuts(result["outer_edge_lengths_mm"])
    assert len(result["installation_polygon"]) == 4
    assert len(result["panes"]) == 2
