from engine.book_calc import calculate_book
from engine.book_sheet import BOOK_SHEET_WARNING, build_book_sheet_data
from schemas import SectionCreate


def _section(**overrides):
    values = {
        "name": "КНИЖКА",
        "system": "КНИЖКА",
        "width": 3000,
        "height": 2500,
        "panels": 4,
        "quantity": 2,
        "book_system": "B25",
        "door_side": "both",
        "doors": 2,
        "book_left_door_hardware": "handle",
        "book_right_door_hardware": "lock",
        "book_left_door_opening": "inside_in",
        "book_right_door_opening": "outside_out",
        "book_left_stack_panels": 2,
        "compensator": "both",
    }
    values.update(overrides)
    return SectionCreate(**values)


def test_book_sheet_groups_equal_glass_assemblies_and_profiles_for_quantity():
    section = _section()
    sheet = build_book_sheet_data(section, calculate_book(section))

    assert [(row.width_mm, row.height_mm, row.qty, row.positions) for row in sheet.glass_rows] == [
        (742.0, 2385.0, 8, [1, 2, 3, 4])
    ]
    assert [
        (row.width_mm, row.height_mm, row.qty, row.positions)
        for row in sheet.assembly_rows
    ] == [(745.0, 2418.0, 8, [1, 2, 3, 4])]
    assert [
        (row.article, row.length_mm, row.qty)
        for row in sheet.profile_rows
    ] == [
        ("RBP001", 3000.0, 4),
        ("RBP003", 3000.0, 4),
        ("RBP002", 745.0, 16),
    ]
    assert {row.image for row in sheet.profile_rows} == {
        "RBP001.png",
        "RBP002.png",
        "RBP003.png",
    }
    assert sheet.warning == BOOK_SHEET_WARNING


def test_book_sheet_merges_equal_doors_and_keeps_unsupplied_glass_dimensions():
    section = _section(
        quantity=1,
        book_left_door_width=800,
        book_right_door_width=800,
        glass_supplied=False,
    )
    sheet = build_book_sheet_data(section, calculate_book(section))

    assert sheet.glass_supplied is False
    assert [(row.width_mm, row.qty, row.positions) for row in sheet.glass_rows] == [
        (797.0, 2, [1, 4]),
        (687.0, 2, [2, 3]),
    ]
    rbp002 = [row for row in sheet.profile_rows if row.article == "RBP002"]
    assert [(row.length_mm, row.qty, row.positions) for row in rbp002] == [
        (800.0, 4, ["Панель 1", "Панель 4"]),
        (690.0, 4, ["Панель 2", "Панель 3"]),
    ]


def test_book_sheet_keeps_zero_compensator_row_and_only_included_hardware():
    section = _section(quantity=1, compensator="none")
    calc = calculate_book(section)
    sheet = build_book_sheet_data(section, calc)

    compensator = next(row for row in sheet.profile_rows if row.article == "RBP003")
    assert compensator.length_mm == 3000
    assert compensator.qty == 0
    assert all(row.qty > 0 for row in sheet.hardware_rows)
    assert {row.article for row in sheet.hardware_rows} == {
        item.article for item in calc.hardware if item.included and item.qty > 0
    }
