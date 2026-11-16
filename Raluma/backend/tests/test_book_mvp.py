"""Customer examples: ±2 mm is an MVP comparison criterion, not a shop tolerance."""

from dataclasses import asdict
from copy import deepcopy

import pytest

from engine.book_calc import BookCalculationError, calculate_book


# Expected dimensions transcribed from the paired cutting PDFs; 4323 from Excel.
CASES = [
    ("4012", 3660, 2400, 5, "right", "upper", "inside_in", None, [728] * 5, 2270),
    ("4018-1", 1500, 2350, 2, "right", "none", "inside_out", 840, [640, 840], 2233),
    ("4018-2", 1500, 2360, 2, "left", "none", "inside_out", 840, [840, 640], 2243),
    ("4025", 1500, 2000, 3, "left", "lower", "inside_in", None, [493] * 3, 1865),
    ("4039", 1650, 1800, 3, "left", "lower", "inside_in", None, [543] * 3, 1665),
    ("2014-1", 3197, 2745, 4, "left", "lower", "inside_in", None, [794] * 4, 2610),
    ("2014-2", 3199, 2745, 4, "right", "lower", "inside_in", None, [794] * 4, 2610),
    ("4256", 2890, 2430, 4, "left", "lower", "inside_in", None, [717] * 4, 2295),
    (
        "4347",
        5357,
        1547,
        7,
        "both",
        "lower",
        "inside_in",
        None,
        [763] + [762] * 5 + [763],
        1412,
    ),
    (
        "4375",
        4159,
        2664,
        6,
        "left",
        "lower",
        "inside_out",
        None,
        [774] + [673] * 5,
        2529,
    ),
    ("4323", 8044, 2875, 11, "right", "lower", "inside_in", None, [729] * 11, 2740),
]


def payload(**kw):
    return dict(
        dict(
            system="КНИЖКА",
            width=3000,
            height=2500,
            panels=4,
            quantity=1,
            door_side="left",
            book_system="B25",
            compensator="lower",
        ),
        **kw,
    )


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_customer_geometry(case):
    code, w, h, n, side, comp, opening, manual, expected, glass_height = case
    section = payload(
        width=w,
        height=h,
        panels=n,
        door_side=side,
        compensator=comp,
        book_left_stack_panels=4 if code == "4347" else n // 2,
        book_left_door_opening=opening,
        book_right_door_opening=opening,
        book_left_door_hardware="lock" if manual else "handle",
        book_right_door_hardware="lock" if manual else "handle",
    )
    if manual:
        section[f"book_{side}_door_width"] = manual
    result = calculate_book(section)
    assert len(result.panels) == n
    for panel, expected_width in zip(result.panels, expected, strict=True):
        assert abs(panel.panel_width_mm - expected_width) <= 2
        assert abs(panel.glass_width_mm - (expected_width - 3)) <= 2
        assert panel.glass_height_mm == glass_height
        assert panel.panel_height_mm == glass_height + 33
    if code == "4375":
        assert result.panels[0].panel_width_mm == 772
        assert result.panels[1].panel_width_mm == 672
    if code == "4323":
        assert {p.panel_width_mm for p in result.panels} == {729}


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize(
    "opening,hardware,delta",
    [
        ("inside_in", "handle", 0),
        ("outside_in", "handle", 0),
        ("inside_out", "handle", 100),
        ("outside_out", "handle", 100),
        ("inside_in", "lock", 220),
        ("outside_out", "lock", 220),
    ],
)
def test_automatic_door_additions_and_zero(side, opening, hardware, delta):
    section = payload(
        door_side=side,
        **{
            f"book_{side}_door_opening": opening,
            f"book_{side}_door_hardware": hardware,
        },
    )
    original = deepcopy(section)
    result = calculate_book(section)
    assert section == original
    door = next(p for p in result.panels if p.role == "door")
    standard = next(p for p in result.panels if p.role == "standard")
    assert door.panel_width_mm - standard.panel_width_mm == delta
    assert (
        asdict(calculate_book(dict(section, **{f"book_{side}_door_width": 0})))[
            "panels"
        ]
        == asdict(result)["panels"]
    )


def test_manual_width_is_preserved_and_advisory_does_not_block():
    result = calculate_book(
        payload(book_left_door_width=700, book_left_door_hardware="lock")
    )
    assert result.panels[0].panel_width_mm == 700
    assert any("Ручной размер сохранён" in w for w in result.warnings)
    assert result.documents_allowed


@pytest.mark.parametrize(
    "comp,count", [("none", 0), ("lower", 1), ("upper", 1), ("both", 2)]
)
@pytest.mark.parametrize("n,doors", [(4, 1), (5, 1), (6, 2), (7, 2)])
def test_quantities_scale_once_and_compensators_follow_profiles(comp, count, n, doors):
    section = payload(
        panels=n,
        doors=doors,
        door_side="both" if doors == 2 else "left",
        compensator=comp,
    )
    once = calculate_book(section)
    triple = calculate_book(dict(section, quantity=3))
    by_article = {h.article: h for h in triple.hardware}
    assert by_article["RBA0009"].qty == (3 * doors + n - doors) * count * 3
    assert by_article["RBA0009"].included == bool(count)
    assert by_article["RBA0006"].qty == 3 * doors * 3
    assert by_article["RBA0005"].qty == 2 * doors * 3
    for first, many in zip(once.hardware, triple.hardware, strict=True):
        assert many.qty == pytest.approx(first.qty * 3)
    for first, many in zip(once.profiles, triple.profiles, strict=True):
        assert first.length_mm == many.length_mm
        assert many.qty == first.qty * 3
        assert many.total_length_mm == many.length_mm * many.qty
    assert once.operations == triple.operations
    assert by_article["Артикул уточнить"].name != by_article["RBA0013"].name


def test_machining_direction_two_stacks_and_missing_rules():
    left = calculate_book(payload())
    right = calculate_book(payload(door_side="right"))
    left_ops = {op.key: op for op in left.operations}
    r = {op.key: op for op in right.operations}
    assert left_ops["d13_lower"].coordinates_mm == [93, 185, 714, 1458, 2202, 2946]
    assert left_ops["d6_lower"].coordinates_mm == [124, 246, 674, 1418, 2162, 2906]
    assert r["d13_lower"].coordinates_mm == left_ops["d13_lower"].coordinates_mm
    assert r["d13_lower"].reference_side == "right"
    both = calculate_book(payload(door_side="both", doors=2, book_left_stack_panels=2))
    b = {op.key: op for op in both.operations}
    assert b["d13_lower"].coordinates_mm == [93, 185, 714, 1458, 1542, 2286, 2815, 2907]
    assert b["d13_lower"].reference_side == "left"
    for op in both.operations:
        assert all(0 < x < 3000 for x in op.coordinates_mm)
        assert op.status == ("preliminary" if op.coordinates_mm else "manual_required")
    assert b["outlet_left"].coordinates_mm == []
    assert b["drain_extra"].coordinates_mm == []
    no_comp = calculate_book(payload(compensator="none"))
    assert not any(op.key.startswith("d13_") for op in no_comp.operations)


@pytest.mark.parametrize(
    "kw",
    [
        {"quantity": 1.5},
        {"panels": 2.5},
        {"width": float("nan")},
        {"height": float("inf")},
        {"book_left_door_width": -2},
        {"width": 23},
        {"book_left_door_width": 3000},
    ],
)
def test_invalid_geometry_is_blocked(kw):
    with pytest.raises(BookCalculationError):
        calculate_book(payload(**kw))
