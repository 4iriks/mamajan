from decimal import Decimal
from types import SimpleNamespace

from engine.quote_pricing import (
    _allocate_whole_rubles,
    _allocate_whole_rubles_to_target,
    _price_requirement,
    _public_line,
    _section_breakdown_exact,
    _section_requirements,
    _vat_values,
    safe_public_payload,
)
from engine.glass_types import SLIDE_GLASS_TYPES, normalize_slide_glass_type
from schemas import SectionCreate


def _version(**overrides):
    values = {
        "id": 17,
        "cost": Decimal("100.00"),
        "profile_markup_percent": Decimal("100"),
        "profile_discount_percent": Decimal("25"),
        "waste_markup_percent": Decimal("30"),
        "construction_markup_percent": Decimal("200"),
        "construction_discount_percent": Decimal("35"),
        "category": "profile",
        "unit": "п.м.",
        "min_margin_percent": Decimal("10"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_construction_formula_uses_all_item_coefficients_and_automatic_waste():
    required = {
        "sku": "FORMULA-1",
        "name": "Проверка формулы",
        "category": "profile",
        "unit": "п.м.",
        "quantity": Decimal("3"),
        "source": "profile",
    }
    active = {"FORMULA-1": (SimpleNamespace(sku="FORMULA-1"), _version())}

    without_waste, issue = _price_requirement(
        required, active, {}, False, mode="construction"
    )
    assert issue is None
    # 100 × 3 × profile terms × construction terms × 30% waste.
    assert without_waste["internal_total"] == "1140.75"
    assert without_waste["minimum_total"] == "330.00"
    assert without_waste["waste_markup_applied"] is True

    with_waste, issue = _price_requirement(
        required, active, {}, True, mode="construction"
    )
    assert issue is None
    assert with_waste["internal_total"] == "1140.75"
    assert with_waste["waste_markup_applied"] is True


def test_standalone_requirement_uses_only_profile_terms():
    required = {
        "sku": "FORMULA-STANDALONE",
        "name": "Отдельная продажа",
        "category": "profile",
        "unit": "п.м.",
        "quantity": Decimal("3"),
        "source": "profile",
    }
    active = {
        "FORMULA-STANDALONE": (
            SimpleNamespace(sku="FORMULA-STANDALONE"),
            _version(),
        )
    }

    priced, issue = _price_requirement(required, active, {}, True)

    assert issue is None
    # 100 × 3 × (1 + 100%) × (1 − 25%); no waste/production coefficients.
    assert priced["internal_total"] == "450.00"
    assert priced["waste_markup_applied"] is False


def test_dealer_markup_then_visible_category_discount():
    terms = {
        "dealer_markup_percent": Decimal("20"),
        "profile_discount_percent": Decimal("5"),
        "construction_discount_percent": Decimal("10"),
        "component_discount_percent": Decimal("7"),
        "service_discount_percent": Decimal("3"),
    }
    public, exact = _public_line(
        line_id="section-1",
        name="Секция 1",
        category="construction",
        quantity=Decimal("2"),
        unit="изд.",
        internal_total=Decimal("1000"),
        terms=terms,
    )

    assert public["line_total_before_discount"] == "1200.00"
    assert public["discount_percent"] == "10"
    assert public["line_discount_amount"] == "120.00"
    assert public["line_total"] == "1080.00"
    assert public["unit_final_price"] == "540.00"
    assert exact["total"] == Decimal("1080.00")


def test_ready_slide_uses_only_construction_discount_and_manual_service_uses_service():
    terms = {
        "dealer_markup_percent": Decimal("20"),
        "profile_discount_percent": Decimal("99"),
        "construction_discount_percent": Decimal("10"),
        "component_discount_percent": Decimal("88"),
        "service_discount_percent": Decimal("3"),
    }
    construction, _ = _public_line(
        line_id="section-1",
        name="Секция 1",
        category="construction",
        quantity=Decimal("1"),
        unit="изд.",
        internal_total=Decimal("1000"),
        terms=terms,
    )
    assert construction["line_total_before_discount"] == "1200.00"
    assert construction["discount_percent"] == "10"
    assert construction["line_total"] == "1080.00"

    service, _ = _public_line(
        line_id="delivery",
        name="Доставка",
        category="service",
        quantity=Decimal("1"),
        unit="шт.",
        internal_total=Decimal("1000"),
        terms=terms,
    )
    assert service["discount_percent"] == "3"
    assert service["line_total"] == "1164.00"


def test_vat_modes_and_whole_ruble_distribution_are_exact():
    included = _vat_values(Decimal("120.00"), "included", Decimal("20"))
    assert included == (Decimal("20.00"), Decimal("120.00"), Decimal("1"))

    on_top = _vat_values(Decimal("100.00"), "on_top", Decimal("20"))
    assert on_top == (Decimal("20.00"), Decimal("120.00"), Decimal("1.2"))

    assert _vat_values(Decimal("100.00"), "none", Decimal("20")) == (
        Decimal("0"),
        Decimal("100.00"),
        Decimal("1"),
    )

    allocated = _allocate_whole_rubles(
        [Decimal("10.40"), Decimal("20.40"), Decimal("30.40")]
    )
    assert allocated == [11, 20, 30]
    assert sum(allocated) == 61


def test_public_quote_allowlist_removes_bom_costs_and_missing_skus():
    safe = safe_public_payload(
        {
            "project": {"id": 1, "number": "Q-1", "customer": "Клиент", "cost": 1},
            "lines": [
                {
                    "id": "1",
                    "name": "Секция",
                    "quantity": "1",
                    "unit": "изд.",
                    "line_total": "100.00",
                    "internal_total": "50.00",
                    "bom": [{"sku": "SECRET"}],
                    "section_details": {
                        "width_mm": "2400",
                        "cost": "SECRET",
                        "panel_geometry": [
                            {"number": 1, "rail": 0, "internal_total": "SECRET"}
                        ],
                    },
                    "breakdown": [
                        {
                            "sku": "RS100",
                            "name": "Профиль",
                            "quantity": "2",
                            "unit": "п.м.",
                            "unit_price": 50,
                            "line_total": 100,
                            "cost": "SECRET",
                            "margin": "SECRET",
                        }
                    ],
                }
            ],
            "totals": {"grand_total": "100.00", "base_cost": "50.00"},
            "vat": {"mode": "none", "rate": "20", "amount": "0.00", "cost": 1},
            "missing_prices": [{"sku": "SECRET"}],
            "dealer_markup_percent": "20",
        }
    )

    assert safe["missing_price_count"] == 1
    assert "missing_prices" not in safe
    assert "cost" not in safe["project"]
    assert "internal_total" not in safe["lines"][0]
    assert "bom" not in safe["lines"][0]
    assert "base_cost" not in safe["totals"]
    assert "dealer_markup_percent" not in safe
    assert safe["lines"][0]["section_details"] == {
        "width_mm": "2400",
        "panel_geometry": [{"number": 1, "rail": 0}],
    }
    assert safe["lines"][0]["breakdown"][0] == {
        "sku": "RS100",
        "name": "Профиль",
        "quantity": "2",
        "unit": "п.м.",
        "unit_price": 50,
        "line_total": 100,
    }


def test_slide_glass_names_are_canonical_and_catalog_sku_uses_them():
    aliases = (
        ("10ММ ПРОЗРАЧНОЕ", SLIDE_GLASS_TYPES[0]),
        ("10ММ БРОНЗА В МАССЕ", SLIDE_GLASS_TYPES[1]),
        ("10ММ СЕРОЕ В МАССЕ", SLIDE_GLASS_TYPES[2]),
        ("10ММ МАТОВОЕ", SLIDE_GLASS_TYPES[3]),
        ("10ММ ПРОСВЕТЛЕННОЕ", SLIDE_GLASS_TYPES[4]),
        ("ТРИПЛЕКС 4.1.4", SLIDE_GLASS_TYPES[5]),
    )
    for legacy, expected in aliases:
        assert normalize_slide_glass_type(legacy) == expected
        assert normalize_slide_glass_type(expected) == expected

    custom = normalize_slide_glass_type("12мм закалённое стекло по ТЗ")
    assert custom == "12ММ ЗАКАЛЕННОЕ СТЕКЛО ПО ТЗ"
    assert normalize_slide_glass_type(custom) == custom

    _, requirements = _section_requirements(
        _slide_section(glass_type="10ММ ПРОЗРАЧНОЕ")
    )
    glass = next(row for row in requirements if row["source"] == "glass")
    assert glass["sku"] == f"GLASS|{SLIDE_GLASS_TYPES[0]}"
    assert glass["name"] == SLIDE_GLASS_TYPES[0]


def test_public_breakdown_uses_construction_sale_factor_and_exact_ruble_target():
    rows = [
        {
            "sku": "RS1",
            "name": "Профиль",
            "unit": "п.м.",
            "quantity": "2",
            "internal_total": "100.00",
            "source": "profile",
        },
        {
            "sku": "RU1",
            "name": "Фурнитура",
            "unit": "шт",
            "quantity": "1",
            "internal_total": "50.00",
            "source": "component",
        },
        {
            "sku": "GLASS|SAFE",
            "name": "Стекло",
            "unit": "м²",
            "quantity": "1",
            "internal_total": "50.00",
            "source": "glass",
        },
    ]
    breakdown = _section_breakdown_exact(
        rows,
        Decimal("1.08"),
        Decimal("216.00"),
    )
    assert [row["name"] for row in breakdown] == [
        "Профиль",
        "Фурнитура",
        "Стекло",
    ]
    assert all("GLASS" not in row["sku"] for row in breakdown)

    allocated = _allocate_whole_rubles_to_target(
        [row["exact_total"] * Decimal("1.2") for row in breakdown],
        259,
    )
    assert sum(allocated) == 259
    assert allocated == _allocate_whole_rubles_to_target(
        [row["exact_total"] * Decimal("1.2") for row in breakdown],
        259,
    )


def _slide_section(**overrides):
    values = {
        "name": "Секция",
        "system": "СЛАЙД",
        "width": 2400,
        "height": 2200,
        "panels": 4,
        "rails": 3,
        "quantity": 1,
        "first_panel_inside": "Справа",
        "painting_type": "RAL стандарт",
        "ral_color": "9005",
    }
    values.update(overrides)
    payload = SectionCreate(**values).model_dump()
    return SimpleNamespace(id=1, project_id=1, **payload)


def test_slide_bom_uses_finish_prices_without_synthetic_paint_or_work_rows():
    calc, requirements = _section_requirements(_slide_section())
    sources = {row["source"] for row in requirements}

    assert {"profile", "component", "glass"} <= sources
    assert "paint" not in sources
    assert "fabrication" not in sources
    assert all(row["sku"] != "WORK-SLIDE" for row in requirements)
    assert all(not row["sku"].startswith("PAINT|") for row in requirements)
    assert all(
        row.get("finish")
        for row in requirements
        if row["source"] == "profile"
    )
    assert not {screw.article for screw in calc.screws} & {
        row["sku"] for row in requirements
    }
    assert all(row["quantity"] > 0 for row in requirements)


def test_slide_quantities_scale_for_multiple_products_and_two_rows():
    _, single = _section_requirements(
        _slide_section(
            quantity=1,
            slide_rows=2,
            rails=5,
        )
    )
    _, doubled = _section_requirements(
        _slide_section(
            quantity=2,
            slide_rows=2,
            rails=5,
        )
    )
    single_by_key = {
        (row["sku"], row["source"]): row["quantity"] for row in single
    }
    doubled_by_key = {
        (row["sku"], row["source"]): row["quantity"] for row in doubled
    }

    assert single_by_key.keys() == doubled_by_key.keys()
    for key, quantity in single_by_key.items():
        assert doubled_by_key[key] == quantity * 2
