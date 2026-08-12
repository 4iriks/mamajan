"""
Тесты расчётного движка СЛАЙД (slide_calc.py).
Покрывает: переменные профилей, формулы стёкол, профили, фурнитуру, саморезы.
"""

from dataclasses import asdict
from collections import Counter
from math import ceil
from types import SimpleNamespace

import pytest

from engine.slide_calc import (
    PanelGlassItem,
    SlideCalcResult,
    _apply_glass_total_correction,
    _aggregate_glass_profiles,
    _glass_correction_adjustments,
    _inter_glass_overlap_mm,
    _group_1row_glass_from_panels,
    _round_glass_difference_mm,
    calculate_slide,
)
from engine.project_documents import _expand_glass_for_order


def _make_section(**overrides):
    """Создаёт фейковый объект секции с дефолтами для СЛАЙД 1 ряд."""
    defaults = dict(
        width=2000,
        height=2400,
        panels=3,
        quantity=1,
        rails=3,
        threshold="Стандартный анод",
        painting_type="",
        ral_color="",
        glass_type="10ММ ПРОЗРАЧНОЕ",
        first_panel_inside="Справа",
        unused_track="",
        inter_glass_profile="Алюминиевый RS2061",
        profile_left_wall=True,
        profile_right_wall=True,
        profile_left_lock_bar=False,
        profile_right_lock_bar=False,
        profile_left_p_bar=False,
        profile_right_p_bar=False,
        profile_left_handle_bar=False,
        profile_right_handle_bar=False,
        profile_left_bubble=False,
        profile_right_bubble=False,
        lock_left="Без",
        lock_right="Без",
        handle_left="Без",
        handle_right="Без",
        handle_offset_left=0,
        handle_offset_right=0,
        floor_latches_left=False,
        floor_latches_right=False,
        slide_rows=1,
        center_handle=None,
        center_lock=None,
        center_handle_offset=0,
        center_floor_latches_left=False,
        center_floor_latches_right=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Хелперы для поиска элементов в результате ──────────────────────────────


def _find_profile(result: SlideCalcResult, article: str):
    return [p for p in result.profiles if p.article == article]


def _find_hardware(result: SlideCalcResult, article: str):
    return [h for h in result.hardware if h.article == article]


def _find_screw(result: SlideCalcResult, name_part: str):
    return [s for s in result.screws if name_part in s.name]


def _find_glass(result: SlideCalcResult, position: str):
    return [g for g in result.glass if g.position == position]


def _ceil_panel_widths(result: SlideCalcResult):
    return [ceil(panel.width_mm) for panel in result.panel_glass]


def _ceil_panel_profile_lengths(result: SlideCalcResult):
    return [ceil(panel.glass_profile_length) for panel in result.panel_glass]


def _assert_mm_close(actual: list[int], expected: list[int], tolerance: int = 1):
    assert len(actual) == len(expected)
    assert all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


class TestGlassProfileAggregation:
    @staticmethod
    def _aggregate(lengths: list[float]) -> list[tuple[int, int]]:
        result = SlideCalcResult(
            panel_glass=[
                PanelGlassItem(
                    panel=index,
                    position=f"Панель {index}",
                    width_mm=length,
                    height_mm=2400,
                    glass_profile_length=length,
                )
                for index, length in enumerate(lengths, start=1)
            ]
        )
        _aggregate_glass_profiles(result)
        return sorted((int(item.length_mm), item.qty) for item in result.profiles)

    def test_one_row_reference_uses_nearest_mm_for_rs2021_cutting(self):
        assert self._aggregate([654.2, 626.8, 626.8, 654.2]) == [
            (627, 2),
            (654, 2),
        ]

    def test_two_row_reference_uses_nearest_mm_for_rs2021_cutting(self):
        assert self._aggregate([829.2, 802.2, 832.2, 829.2, 802.2, 829.2]) == [
            (802, 2),
            (829, 3),
            (832, 1),
        ]


class TestGlassTotalCorrection:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.49, 0),
            (0.5, 1),
            (1.5, 2),
            (-0.49, 0),
            (-0.5, -1),
            (-1.5, -2),
        ],
    )
    def test_difference_rounds_half_away_from_zero(self, value, expected):
        assert _round_glass_difference_mm(value) == expected

    @pytest.mark.parametrize(
        ("panel_count", "difference", "expected"),
        [
            (5, 1, {2: 1}),
            (5, -1, {2: -1}),
            (5, 2, {0: 1, 4: 1}),
            (5, -2, {0: -1, 4: -1}),
            (5, 3, {0: 1, 2: 1, 4: 1}),
            (5, -3, {0: -1, 2: -1, 4: -1}),
            (5, 4, {}),
            (5, -4, {}),
            (6, 1, {2: 1, 3: 1}),
            (6, -1, {}),
            (6, 2, {0: 1, 5: 1}),
            (6, -2, {0: -1, 5: -1}),
            (6, 3, {0: 1, 2: 1, 3: 1, 5: 1}),
            (6, -3, {0: -1, 5: -1}),
            (6, 4, {}),
            (6, -4, {}),
        ],
    )
    def test_even_and_odd_distribution_rules(self, panel_count, difference, expected):
        assert _glass_correction_adjustments(panel_count, difference) == expected

    @pytest.mark.parametrize("difference", [4, -4])
    def test_four_millimetres_warns_without_changing_panels(self, difference):
        result = SlideCalcResult(
            panel_glass=[
                PanelGlassItem(index, f"Панель {index}", 500, 2200, 497)
                for index in range(1, 6)
            ]
        )
        original = [asdict(panel) for panel in result.panel_glass]

        applied = _apply_glass_total_correction(result, 2500 + difference)

        assert applied == difference
        assert [asdict(panel) for panel in result.panel_glass] == original
        assert len(result.warnings) == 1
        assert "Контрольная сумма" in result.warnings[0]
        assert "фактическая сумма" in result.warnings[0]
        assert f"{difference:+d} мм" in result.warnings[0]

    @pytest.mark.parametrize(
        ("profile", "expected_overlap"),
        [
            ("— Без межстекольного профиля —", 0.0),
            ("Прозрачный RS1006", 9.5),
            ("Алюминиевый RS2061", 9.5),
            ("Профиль с зацепом RS3061", 11.5),
        ],
    )
    def test_selected_profile_controls_overlap(self, profile, expected_overlap):
        article = {
            "— Без межстекольного профиля —": "",
            "Прозрачный RS1006": "RS1006",
            "Алюминиевый RS2061": "RS2061",
            "Профиль с зацепом RS3061": "RS3061",
        }[profile]
        assert _inter_glass_overlap_mm(article) == expected_overlap

    @pytest.mark.parametrize(
        ("slide_rows", "panels"),
        [(1, 5), (2, 6)],
    )
    @pytest.mark.parametrize(
        ("profile", "overlap"),
        [
            ("— Без межстекольного профиля —", 0.0),
            ("Алюминиевый RS2061", 9.5),
            ("Профиль с зацепом RS3061", 11.5),
        ],
    )
    def test_control_formula_uses_overlap_for_both_rows(
        self, slide_rows, panels, profile, overlap
    ):
        section = _make_section(
            width=4310,
            panels=panels,
            rails=5,
            slide_rows=slide_rows,
            inter_glass_profile=profile,
            profile_left_wall=False,
            profile_right_wall=False,
            first_panel_inside=None if slide_rows == 2 else "Справа",
        )

        result = calculate_slide(section)
        control_total = (
            4310
            - (3 if slide_rows == 2 else 0)
            + overlap * (panels - (2 if slide_rows == 2 else 1))
        )

        assert not result.warnings
        assert (
            abs(control_total - sum(panel.width_mm for panel in result.panel_glass))
            <= 1
        )

    def test_corrected_panels_drive_groups_profiles_rollers_and_glass_order(self):
        section = _make_section(
            slide_rows=2,
            panels=4,
            profile_left_p_bar=True,
            profile_left_bubble=True,
            handle_left="Ручка-кноб RS3014",
            first_panel_inside=None,
        )

        result = calculate_slide(section)
        physical = Counter(
            (
                round(panel.width_mm, 1),
                round(panel.height_mm, 1),
                round(panel.glass_profile_length, 1),
            )
            for panel in result.panel_glass
        )
        grouped = Counter()
        for glass in result.glass:
            grouped[
                (
                    round(glass.width_mm, 1),
                    round(glass.height_mm, 1),
                    round(glass.glass_profile_length, 1),
                )
            ] += glass.qty
        assert grouped == physical

        expected_profiles = Counter(
            int(panel.glass_profile_length + 0.5) for panel in result.panel_glass
        )
        actual_profiles = Counter(
            {
                int(profile.length_mm): profile.qty
                for profile in _find_profile(result, "RS2021")
            }
        )
        assert actual_profiles == expected_profiles

        expected_ru003 = sum(panel.width_mm <= 500 for panel in result.panel_glass) * 2
        expected_ru005 = sum(panel.width_mm > 500 for panel in result.panel_glass) * 2
        assert _find_hardware(result, "RU003")[0].value == expected_ru003
        assert _find_hardware(result, "RU005")[0].value == expected_ru005

        ordered = _expand_glass_for_order(section, result)
        assert [glass.width_mm for glass in ordered] == [
            panel.width_mm for panel in result.panel_glass
        ]
        assert [glass.height_mm for glass in ordered] == [
            panel.height_mm for panel in result.panel_glass
        ]

    def test_equal_edge_widths_with_different_profile_lengths_stay_separate(self):
        result = SlideCalcResult()
        panels = [
            PanelGlassItem(1, "Левое", 600, 2200, 597),
            PanelGlassItem(2, "Промежуточные", 600, 2200, 600),
            PanelGlassItem(3, "Правое", 600, 2200, 616),
        ]

        _group_1row_glass_from_panels(result, panels, 2)

        assert [
            (row.position, row.qty, row.glass_profile_length) for row in result.glass
        ] == [
            ("Левое", 2, 597),
            ("Промежуточные", 2, 600),
            ("Правое", 2, 616),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# БАЗОВЫЙ РАСЧЁТ — минимальная конфигурация
# ═══════════════════════════════════════════════════════════════════════════


class TestBasicSlide:
    """Базовая конфигурация: 2000×2400, 3 панели, Q=1, стандартный порог, пристеночные оба."""

    def setup_method(self):
        self.section = _make_section()
        self.result = calculate_slide(self.section)

    def test_returns_slide_calc_result(self):
        assert isinstance(self.result, SlideCalcResult)

    def test_system_text(self):
        assert self.result.system_text == "SLIDE-стандарт 1 ряд"

    def test_threshold_profile_article(self):
        profiles = _find_profile(self.result, "RS2323")
        assert len(profiles) == 1
        assert profiles[0].qty == 1

    def test_threshold_length(self):
        """Порог = W - 16 * wall_count = 2000 - 16*2 = 1968."""
        profiles = _find_profile(self.result, "RS2323")
        assert profiles[0].length_mm == 1968

    def test_top_guide_article_3_rails(self):
        profiles = _find_profile(self.result, "RS1313")
        assert len(profiles) == 1
        assert profiles[0].length_mm == 1968

    def test_wall_profile_article_3_rails(self):
        profiles = _find_profile(self.result, "RS2333")
        assert len(profiles) == 1
        assert profiles[0].length_mm == 2400
        assert profiles[0].qty == 2  # оба пристеночных

    def test_inter_glass_profile(self):
        profiles = _find_profile(self.result, "RS2061")
        assert len(profiles) == 1
        assert profiles[0].length_mm == 2400 - 162  # H - 162 для стандартного
        assert profiles[0].qty == 2  # (P-1)*Q = 2

    def test_glass_count(self):
        """3 панели, симметричные → крайние + промежуточные."""
        assert len(self.result.glass) == 2

    def test_glass_height_standard(self):
        """glass_H = H - 106 = 2294."""
        for g in self.result.glass:
            assert g.height_mm == 2294

    def test_glass_widths_symmetric(self):
        """Без ручек/замков, только пристеночные: ppl=ppr=16, остальные=0."""
        edge = _find_glass(self.result, "Крайние")[0]
        mid = _find_glass(self.result, "Промежуточные")[0]
        expected_mid = round((2000 - 16 - 16 + 9.5 * 2) / 3, 1)
        assert mid.width_mm == expected_mid
        assert edge.width_mm == expected_mid

    def test_glass_quantities(self):
        edge = _find_glass(self.result, "Крайние")[0]
        mid = _find_glass(self.result, "Промежуточные")[0]
        assert edge.qty == 2
        assert mid.qty == 1  # (3-2)*1


class TestGlassTypeLabel:
    def test_glass_type_does_not_change_one_or_two_row_calculations(self):
        cases = (
            {
                "slide_rows": 1,
                "panels": 3,
                "glass_type": "ТРИПЛЕКС 4.1.4",
                "expected": "ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ",
            },
            {
                "slide_rows": 2,
                "panels": 4,
                "glass_type": "СТЕКЛО ПОД ЗАКАЗ",
                "expected": "ЗАКАЛЕННОЕ СТЕКЛО ПОД ЗАКАЗ",
            },
        )

        for case in cases:
            baseline = asdict(
                calculate_slide(
                    _make_section(
                        slide_rows=case["slide_rows"],
                        panels=case["panels"],
                        glass_type="10ММ ПРОЗРАЧНОЕ",
                    )
                )
            )
            changed = asdict(
                calculate_slide(
                    _make_section(
                        slide_rows=case["slide_rows"],
                        panels=case["panels"],
                        glass_type=case["glass_type"],
                    )
                )
            )

            assert changed["glass_type"] == case["expected"]
            baseline.pop("glass_type")
            changed.pop("glass_type")
            assert changed == baseline


# ═══════════════════════════════════════════════════════════════════════════
# ПЕРЕМЕННЫЕ ПРОФИЛЕЙ (ppl, rpl, krlr, etc.)
# ═══════════════════════════════════════════════════════════════════════════


class TestProfileVariables:
    def test_ppl_ppr_with_wall(self):
        s = _make_section(profile_left_wall=True, profile_right_wall=True)
        r = calculate_slide(s)
        mid = _find_glass(r, "Промежуточные")[0]
        # middle_W с ppl=16, ppr=16
        expected = round((2000 - 16 - 16 + 9.5 * 2) / 3, 1)
        assert mid.width_mm == expected

    def test_no_wall_profiles(self):
        s = _make_section(profile_left_wall=False, profile_right_wall=False)
        r = calculate_slide(s)
        mid = _find_glass(r, "Промежуточные")[0]
        # ppl=0, ppr=0
        expected = round((2000 + 9.5 * 2) / 3, 1)
        assert mid.width_mm == expected

    def test_rpl_lock_bar(self):
        """Профиль-замок RS2081 слева → rpl = 60."""
        s = _make_section(
            profile_left_lock_bar=True,
        )
        r = calculate_slide(s)
        edge = _find_glass(r, "Крайние")[0]
        expected = round((2000 - 16 - 16 - 60 + 9.5 * 2) / 3, 1)
        assert edge.width_mm == expected

    def test_rpl_p_bar(self):
        """П-профиль RS1082 слева → rpl = 28."""
        s = _make_section(
            profile_left_p_bar=True,
        )
        r = calculate_slide(s)
        edge = _find_glass(r, "Крайние")[0]
        expected = round((2000 - 16 - 16 - 28 + 9.5 * 2) / 3, 1)
        assert edge.width_mm == expected

    def test_krlp_p_bar_and_bubble(self):
        """П-профиль + пузырьковый: pl/pz входят в базу, krlp возвращает 16 мм краю."""
        s = _make_section(
            profile_left_p_bar=True,
            profile_left_bubble=True,
        )
        r = calculate_slide(s)
        left = r.panel_glass[0]
        mid = _find_glass(r, "Промежуточные")[0]
        edge_base = round((2000 - 16 - 16 - 6 - 16 - 2 + 9.5 * 2) / 3, 1)
        expected_mid = edge_base
        assert left.width_mm == round(edge_base + 16, 1)
        assert mid.width_mm == expected_mid

    @pytest.mark.parametrize(
        "handle",
        ["Стеклянная ручка RS3017", "Стеклянная ручка"],
    )
    def test_handle_offset_left(self, handle):
        """Отступ a влияет на middle_W и left_W."""
        s = _make_section(
            handle_left=handle,
            handle_offset_left=100,
        )
        r = calculate_slide(s)
        left = _find_glass(r, "Левое")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        # left_W = mid_W + a + krlr + krlp = mid_W + 100
        assert left.width_mm == round(mid.width_mm + 100, 1)

    @pytest.mark.parametrize(
        (
            "slide_rows",
            "panels",
            "offset_left",
            "offset_right",
            "expected_middle",
            "expected_left",
            "expected_right",
        ),
        [
            pytest.param(1, 3, 0, 0, 979.7, 995.7, 995.7, id="one-row-zero"),
            pytest.param(1, 3, 100, 0, 951.7, 1051.7, 967.7, id="one-row-left"),
            pytest.param(1, 3, 0, 100, 951.7, 967.7, 1051.7, id="one-row-right"),
            pytest.param(1, 3, 100, 100, 923.7, 1023.7, 1023.7, id="one-row-both"),
            pytest.param(2, 6, 0, 0, 492.5, 508.5, 508.5, id="two-row-zero"),
            pytest.param(2, 6, 100, 0, 478.5, 578.5, 494.5, id="two-row-left"),
            pytest.param(2, 6, 0, 100, 478.5, 494.5, 578.5, id="two-row-right"),
            pytest.param(2, 6, 100, 100, 464.5, 564.5, 564.5, id="two-row-both"),
        ],
    )
    def test_side_offsets_replace_only_their_own_edge_compensation(
        self,
        slide_rows,
        panels,
        offset_left,
        offset_right,
        expected_middle,
        expected_left,
        expected_right,
    ):
        """a/b independently replace only their side's RS1082 + RS1002 16 mm."""
        result = calculate_slide(
            _make_section(
                width=3000,
                slide_rows=slide_rows,
                panels=panels,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Стеклянная ручка RS3017",
                handle_right="Стеклянная ручка RS3017",
                handle_offset_left=offset_left,
                handle_offset_right=offset_right,
            )
        )

        assert result.panel_glass[1].width_mm == expected_middle
        assert result.panel_glass[0].width_mm == expected_left
        assert result.panel_glass[-1].width_mm == expected_right

    @pytest.mark.parametrize("slide_rows", [1, 2])
    @pytest.mark.parametrize("side", ["left", "right"])
    def test_hidden_offset_is_ignored_for_handle_without_offset(self, slide_rows, side):
        """Скрытый отступ не меняет стекло и не подавляет крайний нахлёст."""
        common = {
            "slide_rows": slide_rows,
            "panels": 4 if slide_rows == 2 else 3,
            f"profile_{side}_p_bar": True,
            f"profile_{side}_bubble": True,
            f"handle_{side}": "Ручка-кноб RS3014",
        }
        offset_field = f"handle_offset_{side}"
        clean = calculate_slide(_make_section(**common, **{offset_field: 0}))
        stale = calculate_slide(_make_section(**common, **{offset_field: 100}))

        assert [panel.width_mm for panel in stale.panel_glass] == [
            panel.width_mm for panel in clean.panel_glass
        ]
        edge = 0 if side == "left" else -1
        neighbor = 1 if side == "left" else -2
        expected_edge_recovery = 17 if slide_rows == 2 else 16
        assert (
            round(
                stale.panel_glass[edge].width_mm - stale.panel_glass[neighbor].width_mm,
                1,
            )
            == expected_edge_recovery
        )


# ═══════════════════════════════════════════════════════════════════════════
# P=1 (ГЛУХАЯ ПАНЕЛЬ)
# ═══════════════════════════════════════════════════════════════════════════


class TestSinglePanel:
    def test_p1_glass_formula(self):
        """P=1: middle_W = W - ppr - ppl - pzl - pzr."""
        s = _make_section(panels=1)
        r = calculate_slide(s)
        assert len(r.glass) == 1
        g = r.glass[0]
        assert g.position == "Промежуточное"
        assert g.width_mm == 2000 - 16 - 16  # 1968
        assert g.qty == 1

    def test_p1_with_bubble(self):
        s = _make_section(panels=1, profile_left_bubble=True, profile_right_bubble=True)
        r = calculate_slide(s)
        g = r.glass[0]
        assert g.width_mm == 2000 - 16 - 16 - 6 - 6  # 1956


# ═══════════════════════════════════════════════════════════════════════════
# P=2 (НЕТ ПРОМЕЖУТОЧНЫХ)
# ═══════════════════════════════════════════════════════════════════════════


class TestTwoPanels:
    def test_p2_no_middle_glass(self):
        s = _make_section(panels=2)
        r = calculate_slide(s)
        assert not _find_glass(r, "Промежуточные")


# ═══════════════════════════════════════════════════════════════════════════
# АРТИКУЛЫ ПОРОГА (рельсы × порог)
# ═══════════════════════════════════════════════════════════════════════════


class TestThresholdArticles:
    def test_3_standard(self):
        r = calculate_slide(_make_section(rails=3, threshold="Стандартный анод"))
        assert _find_profile(r, "RS2323")
        assert r.threshold_text == "Порог 3-рельсовый анод"

    def test_3_overlay(self):
        r = calculate_slide(_make_section(rails=3, threshold="Накладной анод"))
        assert _find_profile(r, "RS23231")
        assert r.threshold_text == "Порог накладной 3-рельсовый анод"

    def test_5_standard(self):
        r = calculate_slide(_make_section(rails=5, threshold="Стандартный анод"))
        assert _find_profile(r, "RS2325")
        assert r.threshold_text == "Порог 5-рельсовый анод"

    def test_5_overlay(self):
        r = calculate_slide(_make_section(rails=5, threshold="Накладной анод"))
        assert _find_profile(r, "RS23251")
        assert r.threshold_text == "Порог накладной 5-рельсовый анод"

    def test_two_rows_threshold_text_uses_profile_name(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                threshold="Накладной окраш",
                painting_type="RAL стандарт",
            )
        )
        assert _find_profile(r, "RS23231")
        assert r.threshold_text == "Порог накладной 3-рельсовый окраш"


# ═══════════════════════════════════════════════════════════════════════════
# НАКЛАДНОЙ ПОРОГ — ДРУГИЕ ДЛИНЫ
# ═══════════════════════════════════════════════════════════════════════════


class TestOverlayThreshold:
    def setup_method(self):
        self.section = _make_section(threshold="Накладной анод")
        self.result = calculate_slide(self.section)

    def test_glass_height_overlay(self):
        """glass_H = H - 94 = 2306."""
        for g in self.result.glass:
            assert g.height_mm == 2306

    def test_inter_glass_length_overlay(self):
        """H - 150 = 2250."""
        profiles = _find_profile(self.result, "RS2061")
        assert profiles[0].length_mm == 2250


# ═══════════════════════════════════════════════════════════════════════════
# ВЕРХНИЙ НАПРАВЛЯЮЩИЙ
# ═══════════════════════════════════════════════════════════════════════════


class TestTopGuide:
    def test_5_rails_article(self):
        r = calculate_slide(_make_section(rails=5))
        assert _find_profile(r, "RS1315")
        assert not _find_profile(r, "RS1313")


# ═══════════════════════════════════════════════════════════════════════════
# ПРИСТЕНОЧНЫЙ ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════════════════════


class TestWallProfile:
    def test_5_rails_article(self):
        r = calculate_slide(_make_section(rails=5))
        assert _find_profile(r, "RS2335")
        assert not _find_profile(r, "RS2333")

    def test_one_wall(self):
        r = calculate_slide(
            _make_section(profile_left_wall=True, profile_right_wall=False)
        )
        profiles = _find_profile(r, "RS2333")
        assert profiles[0].qty == 1

    def test_no_walls(self):
        r = calculate_slide(
            _make_section(profile_left_wall=False, profile_right_wall=False)
        )
        assert not _find_profile(r, "RS2333")
        assert not _find_profile(r, "RS2335")


# ═══════════════════════════════════════════════════════════════════════════
# МЕЖСТЕКОЛЬНЫЙ ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════════════════════


class TestInterGlass:
    def test_no_inter_glass(self):
        r = calculate_slide(_make_section(inter_glass_profile="Без"))
        assert not _find_profile(r, "RS2061")
        assert not _find_profile(r, "RS1006")
        assert not _find_profile(r, "RS3061")

    def test_no_inter_glass_frontend_label(self):
        r = calculate_slide(
            _make_section(inter_glass_profile="— Без межстекольного профиля —")
        )
        assert not _find_profile(r, "RS2061")
        assert not _find_profile(r, "RS1006")
        assert not _find_profile(r, "RS3061")
        assert not _find_hardware(r, "RS107L")
        assert not _find_hardware(r, "RS107R")
        brush = [h for h in r.hardware if h.field_key == "brush"][0]
        ru007 = [item for item in brush.sub_items if item.article == "RU007"][0]
        assert ru007.value == 0.0

    def test_rs1006(self):
        r = calculate_slide(_make_section(inter_glass_profile="Прозрачный RS1006"))
        assert _find_profile(r, "RS1006")

    def test_rs3061(self):
        r = calculate_slide(
            _make_section(inter_glass_profile="Профиль с зацепом RS3061")
        )
        assert _find_profile(r, "RS3061")

    def test_rs3061_uses_115_overlap(self):
        r = calculate_slide(
            _make_section(inter_glass_profile="Профиль с зацепом RS3061")
        )
        edge = _find_glass(r, "Крайние")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        expected = round((2000 - 16 - 16 + 11.5 * 2) / 3, 1)
        assert edge.width_mm == expected
        assert mid.width_mm == expected

    def test_legacy_rs1004_maps_to_rs3061(self):
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        assert _find_profile(r, "RS3061")
        assert not _find_profile(r, "RS1004")

    def test_not_painted_rs1006(self):
        """RS1006 не красится даже при RAL."""
        r = calculate_slide(
            _make_section(
                inter_glass_profile="Прозрачный RS1006",
                painting_type="RAL стандарт",
                ral_color="9016",
            )
        )
        p = _find_profile(r, "RS1006")[0]
        assert p.painted is False

    def test_painted_rs2061(self):
        """RS2061 красится при RAL."""
        r = calculate_slide(
            _make_section(
                painting_type="RAL стандарт",
                ral_color="9016",
            )
        )
        p = _find_profile(r, "RS2061")[0]
        assert p.painted is True


# ═══════════════════════════════════════════════════════════════════════════
# ФУРНИТУРА
# ═══════════════════════════════════════════════════════════════════════════


class TestHardware:
    def test_brushes_always_present(self):
        r = calculate_slide(_make_section())
        brush = [h for h in r.hardware if h.field_key == "brush"]
        assert len(brush) == 1
        assert brush[0].sub_items is not None
        assert len(brush[0].sub_items) == 2

    def test_ru008_formula(self):
        """RU008 = top_len * P * 2 * Q + (handle_bar_len + 30) * hb_count * Q, в метрах."""
        s = _make_section(profile_left_handle_bar=True)
        r = calculate_slide(s)
        brush = [h for h in r.hardware if h.field_key == "brush"][0]
        ru008 = [si for si in brush.sub_items if si.article == "RU008"][0]
        # top_len = 1968, handle_bar_len = 2400-162 = 2238, hb_count = 1
        expected = round(1968 / 1000 * 3 * 2 * 1 + (2238 / 1000 + 0.03) * 1 * 1, 3)
        assert ru008.value == expected

    def test_ru007_formula(self):
        """RU007 = (inter_glass_len + 30) * (P-1) * Q, в метрах."""
        s = _make_section(
            inter_glass_profile="Алюминиевый RS2061", panels=3, quantity=2
        )
        r = calculate_slide(s)
        brush = [h for h in r.hardware if h.field_key == "brush"][0]
        ru007 = [si for si in brush.sub_items if si.article == "RU007"][0]
        # inter_glass_len = 2400-162 = 2238, cnt = (3-1)*2 = 4
        expected = round((2238 / 1000 + 0.03) * 4, 3)
        assert ru007.value == expected

    def test_ru007_only_rs2061_rs1006(self):
        """RU007 только для RS2061 и RS1006."""
        r1 = calculate_slide(_make_section(inter_glass_profile="Алюминиевый RS2061"))
        brush1 = [h for h in r1.hardware if h.field_key == "brush"][0]
        ru007_1 = [si for si in brush1.sub_items if si.article == "RU007"][0]
        assert ru007_1.value > 0

        r2 = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        brush2 = [h for h in r2.hardware if h.field_key == "brush"][0]
        ru007_2 = [si for si in brush2.sub_items if si.article == "RU007"][0]
        assert ru007_2.value == 0

    def test_damper_compensator(self):
        """RSD1 = RSD2 = (P-1)*2*Q."""
        r = calculate_slide(_make_section(panels=3, quantity=2))
        rsd1 = _find_hardware(r, "RSD1")
        rsd2 = _find_hardware(r, "RSD2")
        assert len(rsd1) == 1
        assert rsd1[0].value == (3 - 1) * 2 * 2  # 8
        assert rsd2[0].value == rsd1[0].value

    def test_no_damper_p1(self):
        """P=1 → нет демпферов."""
        r = calculate_slide(_make_section(panels=1))
        assert not _find_hardware(r, "RSD1")

    def test_rs1121_with_handle_bar(self):
        """RS1121 = hb_count * Q."""
        r = calculate_slide(
            _make_section(
                profile_left_handle_bar=True,
                profile_right_handle_bar=True,
                quantity=2,
            )
        )
        rs1121 = _find_hardware(r, "RS1121")
        assert len(rs1121) == 1
        assert rs1121[0].value == 2 * 2  # 4

    def test_no_rs1121_without_handle_bar(self):
        r = calculate_slide(_make_section())
        assert not _find_hardware(r, "RS1121")

    def test_lock_rs3018(self):
        """1-сторонняя защёлка × Q."""
        r = calculate_slide(_make_section(lock_left="ЗАМОК-ЗАЩЁЛКА 1стор"))
        rs3018 = _find_hardware(r, "RS3018")
        assert len(rs3018) == 1
        assert rs3018[0].value == 1

    def test_lock_rs3020(self):
        """2-сторонний замок × Q."""
        r = calculate_slide(
            _make_section(lock_right="ЗАМОК двухсторонний с ключом RS3020")
        )
        rs3020 = _find_hardware(r, "RS3020")
        assert len(rs3020) == 1
        assert rs3020[0].value == 1

    def test_rs122_only_for_rs3018(self):
        """RS122 ставится только к односторонней защелке RS3018, не к RS3020."""
        r = calculate_slide(
            _make_section(
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                lock_right="ЗАМОК двухсторонний с ключом RS3020",
                quantity=2,
            )
        )
        rs122 = _find_hardware(r, "RS122")
        rs3020 = _find_hardware(r, "RS3020")
        assert rs122[0].value == 1 * 2
        assert rs3020[0].value == 1 * 2

    def test_rs3020_without_rs3018_has_no_rs122(self):
        r = calculate_slide(
            _make_section(lock_right="ЗАМОК двухсторонний с ключом RS3020")
        )
        assert _find_hardware(r, "RS3020")
        assert not _find_hardware(r, "RS122")

    def test_rs3020_adds_rs123_strike_plate(self):
        r = calculate_slide(
            _make_section(
                lock_left="ЗАМОК двухсторонний с ключом RS3020",
                quantity=2,
            )
        )
        rs123 = _find_hardware(r, "RS123")
        assert rs123[0].value == 2
        assert rs123[0].image == "RS123.jpg"

    def test_no_locks_no_rs122(self):
        r = calculate_slide(_make_section())
        assert not _find_hardware(r, "RS122")
        assert not _find_hardware(r, "RS3020")

    def test_rollers_ru005_for_wide_panels(self):
        """RU005 = 4-колесные ролики для панелей шире 500 мм."""
        r = calculate_slide(_make_section(panels=3, quantity=2))
        ru005 = _find_hardware(r, "RU005")
        assert ru005[0].value == 3 * 2 * 2  # 12
        assert not _find_hardware(r, "RU003")

    def test_rollers_ru003_for_narrow_panels(self):
        """RU003 = 2-колесные ролики для панелей до 500 мм."""
        r = calculate_slide(_make_section(width=1400, panels=3, quantity=2))
        ru003 = _find_hardware(r, "RU003")
        assert ru003[0].value == 3 * 2 * 2
        assert not _find_hardware(r, "RU005")

    def test_rs3017_glass_handle(self):
        r = calculate_slide(_make_section(handle_left="Стеклянная ручка RS3017"))
        rs3017 = _find_hardware(r, "RS3017")
        assert len(rs3017) == 1
        assert rs3017[0].value == 1

    def test_rs30201_brace_handle(self):
        r = calculate_slide(_make_section(handle_left="Ручка-скоба 600мм RS30201"))
        rs30201 = _find_hardware(r, "RS30201")
        assert len(rs30201) == 1
        assert rs30201[0].value == 1

    def test_legacy_brace_handle_maps_to_rs30201(self):
        r = calculate_slide(_make_section(handle_left="Ручка-скоба"))
        rs30201 = _find_hardware(r, "RS30201")
        assert len(rs30201) == 1
        assert rs30201[0].value == 1

    def test_rs3014_knob(self):
        r = calculate_slide(_make_section(handle_right="Ручка-кноб RS3014"))
        rs3014 = _find_hardware(r, "RS3014")
        assert len(rs3014) == 1
        assert rs3014[0].value == 1

    def test_no_handles_no_hardware(self):
        r = calculate_slide(_make_section())
        assert not _find_hardware(r, "RS3017")
        assert not _find_hardware(r, "RS3014")


# ═══════════════════════════════════════════════════════════════════════════
# RS107R/L ЗАГЛУШКИ МЕЖСТЕКОЛЬНОГО
# ═══════════════════════════════════════════════════════════════════════════


class TestInterGlassPlugs:
    def test_first_right_gives_rs107l(self):
        """1-я справа → сдвиг влево → RS107L."""
        r = calculate_slide(_make_section(first_panel_inside="Справа"))
        assert _find_hardware(r, "RS107L")
        assert not _find_hardware(r, "RS107R")

    def test_first_left_gives_rs107r(self):
        """1-я слева → сдвиг вправо → RS107R."""
        r = calculate_slide(_make_section(first_panel_inside="Слева"))
        assert _find_hardware(r, "RS107R")
        assert not _find_hardware(r, "RS107L")

    def test_no_inter_glass_no_plugs(self):
        r = calculate_slide(_make_section(inter_glass_profile="Без"))
        assert not _find_hardware(r, "RS107L")
        assert not _find_hardware(r, "RS107R")

    def test_rs3061_no_plugs(self):
        """Профиль с зацепом RS3061 — нет заглушек межстекольного."""
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        assert _find_profile(r, "RS3061")
        assert not _find_hardware(r, "RS107L")
        assert not _find_hardware(r, "RS107R")

    def test_inter_glass_plug_qty(self):
        """Кол-во = (P-1)*Q."""
        r = calculate_slide(_make_section(panels=4, quantity=2))
        rs107l = _find_hardware(r, "RS107L")
        assert rs107l[0].value == (4 - 1) * 2  # 6


# ═══════════════════════════════════════════════════════════════════════════
# RS105, RS106, RS107 ЗАГЛУШКИ СТЕКОЛЬНОГО
# ═══════════════════════════════════════════════════════════════════════════


class TestGlassProfilePlugs:
    def test_rs105_qty(self):
        """RS105 = (P-1)*2*Q."""
        r = calculate_slide(_make_section(panels=3, quantity=2))
        rs105 = _find_hardware(r, "RS105")
        assert rs105[0].value == (3 - 1) * 2 * 2  # 8

    def test_rs106_both_not_deaf(self):
        """Обе панели не глухие → RS106 = 2*Q."""
        r = calculate_slide(
            _make_section(
                handle_left="Стеклянная ручка RS3017",
                handle_right="Ручка-кноб RS3014",
            )
        )
        rs106 = _find_hardware(r, "RS106")
        assert rs106[0].value == 2

    def test_rs106_one_deaf(self):
        """Одна глухая → RS106 = 1*Q."""
        r = calculate_slide(
            _make_section(
                handle_left="Стеклянная ручка RS3017",
                handle_right="Без",
                lock_right="Без",
            )
        )
        rs106 = _find_hardware(r, "RS106")
        assert rs106[0].value == 1

    def test_rs106_both_deaf(self):
        """Обе глухие → RS106 = 0."""
        r = calculate_slide(
            _make_section(
                handle_left="Без",
                handle_right="Без",
                lock_left="Без",
                lock_right="Без",
            )
        )
        assert not _find_hardware(r, "RS106")

    def test_rs106_ui_fixed_panel_value_is_deaf(self):
        """Точное значение из UI не должно добавлять RS106 на глухую панель."""
        r = calculate_slide(
            _make_section(
                handle_left="Без ручки (глухая)",
                handle_right="Без ручки (глухая)",
                lock_left="Без",
                lock_right="Без",
            )
        )
        assert not _find_hardware(r, "RS106")

    def test_rs106_name_matches_locking_profile(self):
        r = calculate_slide(
            _make_section(
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                lock_right="Замок двухсторонний с ключом RS3020",
            )
        )

        assert _find_hardware(r, "RS122")[0].name == "Ответная планка защелки RS3018"
        assert _find_hardware(r, "RS123")[0].name == "Ответная планка замка RS3020"

    def test_rs107_total(self):
        """RS107 = RS105 + RS106."""
        r = calculate_slide(
            _make_section(
                panels=3,
                handle_left="Стеклянная ручка RS3017",
                handle_right="Ручка-кноб RS3014",
            )
        )
        rs105 = _find_hardware(r, "RS105")[0].value  # (3-1)*2 = 4
        rs106 = _find_hardware(r, "RS106")[0].value  # 2
        rs107 = [h for h in r.hardware if h.article == "RS107"][0].value
        assert rs107 == rs105 + rs106


# ═══════════════════════════════════════════════════════════════════════════
# САМОРЕЗЫ
# ═══════════════════════════════════════════════════════════════════════════


class TestScrews:
    def test_screw_4825(self):
        """4,8×25 = (RS105 + RS106) * 2."""
        r = calculate_slide(
            _make_section(
                panels=3,
                handle_left="Стеклянная ручка RS3017",
                handle_right="Ручка-кноб RS3014",
            )
        )
        rs105_val = _find_hardware(r, "RS105")[0].value
        rs106_val = _find_hardware(r, "RS106")[0].value
        screw = _find_screw(r, "4,8×25")[0]
        assert screw.qty == (rs105_val + rs106_val) * 2

    def test_screw_3913m_no_lock_bar(self):
        """DIN7504M без RS2081: только ролики."""
        r = calculate_slide(_make_section(panels=3))
        ru005 = _find_hardware(r, "RU005")[0].value  # 3*2*1 = 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2  # 12

    def test_screw_3913m_with_one_lock_bar_by_height(self):
        """DIN7504M: ролики + ceil((H-200)/300) на одну сторону RS2081."""
        r = calculate_slide(
            _make_section(
                panels=3,
                profile_left_lock_bar=True,
            )
        )
        ru005 = _find_hardware(r, "RU005")[0].value  # 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2 + 8  # 12 + 8 = 20

    def test_screw_3913m_with_two_lock_bars_by_height(self):
        """DIN7504M: при H=2400 на две стороны RS2081 нужно 16 шт."""
        r = calculate_slide(
            _make_section(
                panels=3,
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
            )
        )
        ru005 = _find_hardware(r, "RU005")[0].value  # 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2 + 2 * 8 * 1  # 12 + 16 = 28

    def test_screw_3913m_lock_bar_uses_actual_height(self):
        """DIN7504M для RS2081 меняется от высоты секции."""
        r = calculate_slide(
            _make_section(
                height=3000,
                panels=3,
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
            )
        )
        ru005 = _find_hardware(r, "RU005")[0].value  # 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2 + 2 * 9 * 1

    def test_screw_3913m_lock_bar_respects_quantity(self):
        """DIN7504M для RS2081 умножается на количество одинаковых секций."""
        r = calculate_slide(
            _make_section(
                panels=3,
                quantity=2,
                profile_left_lock_bar=True,
            )
        )
        ru005 = _find_hardware(r, "RU005")[0].value  # 12
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2 + 8 * 1 * 2  # 24 + 16 = 40

    def test_screw_3913m_customer_2720_two_rs2081(self):
        """Эталон заказчика: 8 на ролики + 16 на две стороны RS2081 = 24."""
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
            )
        )
        ru005 = _find_hardware(r, "RU005")[0].value
        screw = _find_screw(r, "DIN7504M")[0]
        assert ru005 == 4
        assert screw.qty == 24

    def test_screw_4838_standard_3rails(self):
        screw = _find_screw(calculate_slide(_make_section(rails=3)), "4,8×38")[0]
        assert screw.qty == 8

    def test_screw_4838_standard_5rails(self):
        screw = _find_screw(calculate_slide(_make_section(rails=5)), "4,8×38")[0]
        assert screw.qty == 12

    def test_screw_4838_overlay_3rails(self):
        screw = _find_screw(
            calculate_slide(_make_section(rails=3, threshold="Накладной анод")),
            "4,8×38",
        )[0]
        assert screw.qty == 4

    def test_screw_4838_overlay_5rails(self):
        screw = _find_screw(
            calculate_slide(_make_section(rails=5, threshold="Накладной анод")),
            "4,8×38",
        )[0]
        assert screw.qty == 6

    def test_screw_3913o_with_p_bar(self):
        """Для каждого RS1082 всегда нужно 7 саморезов."""
        r = calculate_slide(_make_section(profile_left_p_bar=True, quantity=2))
        screw = _find_screw(r, "DIN7504О")[0]
        assert screw.qty == 1 * 7 * 2

    def test_screw_3913o_does_not_depend_on_height(self):
        r = calculate_slide(
            _make_section(height=2501, profile_left_p_bar=True, quantity=2)
        )
        screw = _find_screw(r, "DIN7504О")[0]
        assert screw.qty == 1 * 7 * 2

    def test_screw_3913o_two_rows_uses_seven_per_rs1082(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
            )
        )
        screw = _find_screw(r, "DIN7504О")[0]
        assert screw.qty == 2 * 7
        assert screw.note == "Прикрутить RS1082 к RS2333"

    def test_screw_3913o_no_p_bar(self):
        r = calculate_slide(_make_section())
        assert not _find_screw(r, "DIN7504О")

    def test_screw_5425_deaf_panels(self):
        """5,4×25 = deaf_count * Q."""
        r = calculate_slide(
            _make_section(
                handle_left="Без",
                handle_right="Без",
                lock_left="Без",
                lock_right="Без",
                quantity=2,
            )
        )
        screw = _find_screw(r, "5,4×25")[0]
        assert screw.qty == 2 * 2  # оба глухие × Q
        assert screw.note == "Крепление глухой панели"

    def test_screw_5425_no_deaf(self):
        r = calculate_slide(
            _make_section(
                handle_left="Стеклянная ручка RS3017",
                handle_right="Ручка-кноб RS3014",
            )
        )
        assert not _find_screw(r, "5,4×25")

    def test_screw_3513_with_locks(self):
        """3,5×13 = (RS122 + RS123) * 2."""
        r = calculate_slide(
            _make_section(
                lock_left="ЗАМОК-ЗАЩЁЛКА 1стор",
                lock_right="ЗАМОК двухсторонний с ключом RS3020",
            )
        )
        rs122_val = _find_hardware(r, "RS122")[0].value
        rs123_val = _find_hardware(r, "RS123")[0].value
        screw = _find_screw(r, "3,5×13")[0]
        assert screw.qty == (rs122_val + rs123_val) * 2
        assert screw.note == "Прикрутить ответные планки RS122/123"

    def test_screw_notes_reference_current_profile_articles(self):
        r = calculate_slide(
            _make_section(
                rails=5,
                profile_left_p_bar=True,
                profile_left_lock_bar=True,
            )
        )
        assert _find_screw(r, "DIN7504M")[0].note == (
            "Прикрутить ролики, RS2081 к RS2335"
        )
        assert _find_screw(r, "4,8×38")[0].note == (
            "Прикрутить RS2335 к RS1315 и порогу"
        )
        assert _find_screw(r, "DIN7504О")[0].note == ("Прикрутить RS1082 к RS2335")

    def test_screw_notes_omit_profiles_missing_from_section(self):
        r = calculate_slide(
            _make_section(
                profile_left_wall=False,
                profile_right_wall=False,
                profile_left_p_bar=True,
            )
        )
        assert _find_screw(r, "DIN7504M")[0].note == "Прикрутить ролики"
        assert _find_screw(r, "4,8×38")[0].note == "Прикрутить RS1313 и порог"
        assert _find_screw(r, "DIN7504О")[0].note == "Прикрутить RS1082"

    def test_sticker_and_instruction(self):
        r = calculate_slide(_make_section(quantity=3))
        sticker = _find_screw(r, "Наклейка")[0]
        instruction = _find_screw(r, "Инструкция")[0]
        assert sticker.qty == 3
        assert instruction.qty == 3


# ═══════════════════════════════════════════════════════════════════════════
# RS2021 СТЕКОЛЬНЫЙ ПРОФИЛЬ
# ═══════════════════════════════════════════════════════════════════════════


class TestGlassProfile:
    def test_rs2021_basic(self):
        """Без ручек/пузырьковых — длина = ширина стекла."""
        r = calculate_slide(_make_section())
        rs2021 = _find_profile(r, "RS2021")
        assert len(rs2021) >= 1
        assert all(item.image == "RS2021.png" for item in rs2021)

    def test_rs2021_handle_bar_adds_16(self):
        """Ручка-профиль слева → левое стекло RS2021 +16."""
        r = calculate_slide(_make_section(profile_left_handle_bar=True))
        left_glass = _find_glass(r, "Левое")[0]
        # RS2021 для левого = left_glass.width + 16
        assert left_glass.glass_profile_length == round(left_glass.width_mm + 16, 1)

    def test_rs2021_bubble_subtracts_3(self):
        """Пузырьковый на подвижной → RS2021 -3."""
        r = calculate_slide(
            _make_section(
                profile_left_bubble=True,
                handle_left="Стеклянная ручка RS3017",
            )
        )
        left_panel = r.panel_glass[0]
        assert left_panel.glass_profile_length == round(left_panel.width_mm - 3, 1)

    def test_rs2021_bubble_deaf_no_subtract(self):
        """Пузырьковый на глухой → RS2021 НЕ вычитает 3."""
        r = calculate_slide(
            _make_section(
                profile_left_bubble=True,
                handle_left="Без",
                lock_left="Без",
            )
        )
        edge = _find_glass(r, "Крайние")[0]
        assert edge.glass_profile_length == edge.width_mm

    def test_rs2021_handle_bar_and_bubble(self):
        """Ручка-профиль RS112 важнее пузырькового: RS2021 = стекло + 16."""
        r = calculate_slide(
            _make_section(
                profile_left_handle_bar=True,
                profile_left_bubble=True,
                handle_left="Стеклянная ручка RS3017",
            )
        )
        left_glass = _find_glass(r, "Левое")[0]
        assert left_glass.glass_profile_length == round(left_glass.width_mm + 16, 1)

    def test_rs2021_middle_with_inter_glass(self):
        """Промежуточные с межстекольным → RS2021 -3."""
        r = calculate_slide(_make_section(inter_glass_profile="Алюминиевый RS2061"))
        mid = _find_glass(r, "Промежуточные")[0]
        assert mid.glass_profile_length == round(mid.width_mm - 3, 1)

    def test_rs2021_middle_no_inter_glass(self):
        """Промежуточные без межстекольного → RS2021 = ширина."""
        r = calculate_slide(_make_section(inter_glass_profile="Без"))
        mid = _find_glass(r, "Промежуточные")[0]
        assert mid.glass_profile_length == mid.width_mm

    def test_rs2021_ignores_zero_qty_glass_rows(self):
        """2 панели не должны создавать нулевую строку RS2021 для промежуточных."""
        r = calculate_slide(_make_section(panels=2, inter_glass_profile="Без"))
        rs2021 = _find_profile(r, "RS2021")

        assert rs2021
        assert all(item.qty > 0 for item in rs2021)
        assert all("Промежуточ" not in item.glass_positions for item in rs2021)

    def test_customer_two_panel_pbar_bubble_glass_width(self):
        """При pzl/pzr=6 профиль 1082 + RS1002 дает стекло 931 мм."""
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Ручка-кноб RS3014",
                handle_right="Без",
                lock_left="Без",
                lock_right="Без",
            )
        )
        assert [ceil(panel.width_mm) for panel in r.panel_glass] == [931, 931]

    def test_customer_two_panel_pbar_bubble_rs2021_physical_lengths(self):
        """Одинаковые крайние стекла могут иметь разный RS2021: 928 и 931."""
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Ручка-кноб RS3014",
                handle_right="Без",
                lock_left="Без",
                lock_right="Без",
            )
        )
        assert [ceil(panel.glass_profile_length) for panel in r.panel_glass] == [
            928,
            931,
        ]
        rs2021 = sorted(
            ceil(profile.length_mm) for profile in _find_profile(r, "RS2021")
        )
        assert rs2021 == [928, 931]

    def test_customer_two_panel_handle_bar_rs2021_matches_scheme_rounding(self):
        """Схема и таблица RS2021 должны давать одну цифру: 879 (895)."""
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
                profile_left_handle_bar=True,
                profile_right_handle_bar=True,
                handle_left="Без",
                handle_right="Без",
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                lock_right="ЗАМОК двухсторонний с ключом RS3020",
            )
        )
        assert [ceil(panel.width_mm) for panel in r.panel_glass] == [879, 879]
        assert [ceil(panel.glass_profile_length) for panel in r.panel_glass] == [
            895,
            895,
        ]
        assert sorted(
            ceil(profile.length_mm) for profile in _find_profile(r, "RS2021")
        ) == [895]


class TestCustomerSections0107:
    """Регрессии по сверке с ПЛ заказчика от 01.07.

    Значения из старых ПЛ сравниваем с допуском 1 мм: согласовано, что такие
    расхождения допустимы и не должны ломать текущую физическую модель панелей.
    """

    def test_section_4_rs2021_uses_left_physical_rs112(self):
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                first_panel_inside="Слева",
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_lock_bar=True,
                profile_left_handle_bar=True,
                profile_right_p_bar=True,
                profile_right_bubble=True,
                handle_left="Без",
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                handle_right="Без",
                lock_right="Без",
            )
        )

        _assert_mm_close(_ceil_panel_widths(r), [901, 909])
        _assert_mm_close(_ceil_panel_profile_lengths(r), [917, 909])
        assert r.panel_glass[0].width_mm < r.panel_glass[-1].width_mm

    def test_section_5_rs2021_does_not_follow_visual_order(self):
        r = calculate_slide(
            _make_section(
                width=1900,
                height=2720,
                panels=2,
                first_panel_inside="Слева",
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_handle_bar=True,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_right_bubble=True,
                handle_left="Без",
                lock_left="Без",
                handle_right="Без",
                lock_right="Без",
            )
        )

        assert _ceil_panel_widths(r) == [917, 925]
        assert _ceil_panel_profile_lengths(r) == [933, 925]
        assert sorted(
            int(profile.length_mm) for profile in _find_profile(r, "RS2021")
        ) == [925, 933]

    def test_section_7_physical_panels_and_rs2021(self):
        r = calculate_slide(
            _make_section(
                width=2295,
                height=1810,
                panels=3,
                profile_left_p_bar=True,
                profile_left_bubble=True,
                profile_right_lock_bar=True,
                profile_right_handle_bar=True,
                handle_left="Без",
                lock_left="Без",
                handle_right="Без",
                lock_right="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
            )
        )
        _assert_mm_close(_ceil_panel_widths(r), [746, 730, 738])
        _assert_mm_close(_ceil_panel_profile_lengths(r), [746, 727, 754])

    def test_section_8_physical_panels_and_rs2021(self):
        r = calculate_slide(
            _make_section(
                width=2682,
                height=2915,
                panels=3,
                profile_left_p_bar=True,
                profile_left_bubble=True,
                profile_right_p_bar=True,
                profile_right_handle_bar=True,
                handle_left="Без",
                lock_left="Без",
                handle_right="Без",
                lock_right="Без",
            )
        )
        assert _ceil_panel_widths(r) == [886, 870, 878]
        assert _ceil_panel_profile_lengths(r) == [886, 867, 894]

    def test_section_9_physical_panels_and_rs2021(self):
        r = calculate_slide(
            _make_section(
                width=2613,
                height=2546,
                panels=3,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Без ручки (подвижная)",
                lock_left="Без",
                handle_right="Без ручки (подвижная)",
                lock_right="Без",
            )
        )
        _assert_mm_close(_ceil_panel_widths(r), [867, 851, 867])
        _assert_mm_close(_ceil_panel_profile_lengths(r), [864, 848, 864])

    def test_section_10_physical_panels_and_rs2021(self):
        r = calculate_slide(
            _make_section(
                width=2206,
                height=2880,
                panels=3,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_handle_bar=True,
                profile_right_handle_bar=True,
                handle_left="Без",
                lock_left="Без",
                handle_right="Без",
                lock_right="Без",
            )
        )
        _assert_mm_close(_ceil_panel_widths(r), [716, 708, 716])
        _assert_mm_close(_ceil_panel_profile_lengths(r), [732, 705, 732])

    def test_section_11_rs3020_does_not_create_rs122(self):
        r = calculate_slide(
            _make_section(
                width=2560,
                height=2045,
                panels=3,
                profile_left_lock_bar=True,
                profile_left_handle_bar=True,
                profile_right_p_bar=True,
                profile_right_handle_bar=True,
                handle_left="Без",
                lock_left="ЗАМОК двухсторонний с ключом RS3020",
                handle_right="Без",
                lock_right="Без",
            )
        )
        assert _ceil_panel_widths(r) == [823, 815, 823]
        assert _ceil_panel_profile_lengths(r) == [839, 812, 839]
        assert _find_hardware(r, "RS3020")
        assert not _find_hardware(r, "RS122")

    def test_rs2081_screws_include_rollers_and_lock_bar_fastening(self):
        r = calculate_slide(
            _make_section(
                width=2295,
                height=1810,
                panels=3,
                profile_left_lock_bar=True,
                handle_left="Без",
                lock_left="Без",
            )
        )
        rollers = sum(item.value for item in _find_hardware(r, "RU005"))
        screw = _find_screw(r, "DIN7504M")[0]
        assert rollers == 6
        assert screw.qty == rollers * 2 + 8


# ═══════════════════════════════════════════════════════════════════════════
# QUANTITY > 1
# ═══════════════════════════════════════════════════════════════════════════


class TestQuantity:
    """Проверяем что Q корректно множит кол-во но НЕ длины."""

    def setup_method(self):
        self.r = calculate_slide(_make_section(quantity=3))

    def test_threshold_qty(self):
        assert _find_profile(self.r, "RS2323")[0].qty == 3

    def test_threshold_length_unchanged(self):
        assert _find_profile(self.r, "RS2323")[0].length_mm == 1968

    def test_wall_qty(self):
        assert _find_profile(self.r, "RS2333")[0].qty == 6  # 2 стены × Q=3

    def test_glass_qty(self):
        edge = _find_glass(self.r, "Крайние")[0]
        assert edge.qty == 6  # 2 крайних × Q=3

    def test_rollers_qty(self):
        ru005 = _find_hardware(self.r, "RU005")[0]
        assert ru005.value == 3 * 2 * 3  # P=3, 2 ролика, Q=3


# ═══════════════════════════════════════════════════════════════════════════
# НАРЕЗКА ДЛИННЫХ ПРОФИЛЕЙ
# ═══════════════════════════════════════════════════════════════════════════


class TestLongProfileCuts:
    def test_short_threshold_and_top_are_not_split(self):
        r = calculate_slide(_make_section(width=5982))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [5950]
        assert [p.length_mm for p in top] == [5950]
        assert threshold[0].field_key == "threshold_length"
        assert top[0].field_key == "top_guide_length"

    def test_fractional_length_above_limit_is_rounded_up_before_split(self):
        r = calculate_slide(_make_section(width=5982.4))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [2975, 2976]
        assert [p.length_mm for p in top] == [2975, 2976]
        assert sum(p.length_mm for p in threshold) == 5951
        assert all(p.length_mm <= 5950 for p in threshold + top)

    def test_6123_threshold_and_top_split_to_two_parts(self):
        r = calculate_slide(_make_section(width=6155))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [3061, 3062]
        assert [p.length_mm for p in top] == [3061, 3062]
        assert sum(p.length_mm * p.qty for p in threshold) == 6123
        assert all(p.length_mm <= 5950 for p in threshold + top)

    def test_7000_threshold_splits_evenly(self):
        r = calculate_slide(_make_section(width=7032))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [3500, 3500]
        assert [p.length_mm for p in top] == [3500, 3500]

    def test_7001_threshold_split_respects_quantity(self):
        r = calculate_slide(_make_section(width=7033, quantity=2))
        threshold = _find_profile(r, "RS2323")
        assert [p.length_mm for p in threshold] == [3500, 3501]
        assert [p.qty for p in threshold] == [2, 2]
        assert sum(p.length_mm * p.qty for p in threshold) == 7001 * 2

    def test_12000_threshold_splits_to_three_parts(self):
        r = calculate_slide(_make_section(width=12032))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [4000, 4000, 4000]
        assert [p.length_mm for p in top] == [4000, 4000, 4000]

    def test_two_row_threshold_and_top_are_split_too(self):
        r = calculate_slide(_make_section(slide_rows=2, panels=4, width=6155))
        threshold = _find_profile(r, "RS2323")
        top = _find_profile(r, "RS1313")
        assert [p.length_mm for p in threshold] == [3061, 3062]
        assert [p.length_mm for p in top] == [3061, 3062]


# ═══════════════════════════════════════════════════════════════════════════
# ПОКРАСКА
# ═══════════════════════════════════════════════════════════════════════════


class TestPainting:
    def test_ral_profiles_painted_and_anod_threshold_not_painted(self):
        r = calculate_slide(
            _make_section(painting_type="RAL стандарт", ral_color="9016")
        )
        threshold = _find_profile(r, "RS2323")[0]
        top = _find_profile(r, "RS1313")[0]
        assert threshold.painted is False
        assert top.painted is True
        assert r.threshold_text == "Порог 3-рельсовый анод"
        assert r.color_text == "RAL 9016"

    def test_painted_threshold_goes_to_paint_order(self):
        r = calculate_slide(
            _make_section(
                threshold="Стандартный окраш",
                painting_type="RAL стандарт",
                ral_color="9016",
            )
        )
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.painted is True

    def test_anod_section_forces_painted_threshold_to_anod(self):
        r = calculate_slide(
            _make_section(
                threshold="Накладной окраш",
                painting_type="Анодированный",
                ral_color="9016",
            )
        )
        overlay_threshold = _find_profile(r, "RS23231")[0]
        assert overlay_threshold.painted is False
        assert r.threshold_text == "Порог накладной 3-рельсовый анод"
        assert r.color_text == "Анодированный"

    def test_anod_profiles_not_painted(self):
        r = calculate_slide(_make_section(painting_type="Анодированный"))
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.painted is False

    def test_color_text_ral(self):
        r = calculate_slide(
            _make_section(painting_type="RAL стандарт", ral_color="9016")
        )
        assert "RAL" in r.color_text
        assert "9016" in r.color_text
        assert "СТАНДАРТ" not in r.color_text

    def test_color_text_ral_nonstandard_drops_service_word(self):
        r = calculate_slide(
            _make_section(painting_type="RAL нестандарт", ral_color="9016 МАТОВЫЙ")
        )
        assert r.color_text == "RAL 9016 МАТОВЫЙ"

    def test_color_text_anod(self):
        r = calculate_slide(
            _make_section(
                threshold="Стандартный анод",
                painting_type="",
            )
        )
        assert "Анодированный" in r.color_text

    def test_profile_catalog_metadata_is_attached(self):
        r = calculate_slide(_make_section(painting_type="RAL стандарт"))
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.section_width_mm == 76
        assert threshold.section_height_mm == 23
        assert threshold.paint_mode == "Частично"
        assert threshold.paint_note == "НЕ КРАСИТЬ!!!"
        assert threshold.color_variants == ["Анод", "RAL стандарт", "RAL нестандарт"]

    def test_catalog_overrides_profile_image(self):
        r = calculate_slide(_make_section(rails=5))
        threshold = _find_profile(r, "RS2325")[0]
        assert threshold.image == "RS2325.png"

    def test_overlay_threshold_has_own_name_image_and_drain_note(self):
        r = calculate_slide(_make_section(threshold="Накладной окраш"))
        threshold = _find_profile(r, "RS23231")[0]
        assert threshold.name == "Порог накладной 3-рельсовый"
        assert threshold.image == "RS23231.png"
        assert threshold.note == "рассверлить дренажные отверстия"

    def test_standard_threshold_has_drain_note(self):
        r = calculate_slide(_make_section(threshold="Стандартный анод"))
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.note == "рассверлить дренажные отверстия"


# ═══════════════════════════════════════════════════════════════════════════
# ЧЕКЛИСТ
# ═══════════════════════════════════════════════════════════════════════════


class TestChecklist:
    def test_always_has_rollers(self):
        r = calculate_slide(_make_section())
        assert any("ролики" in c.lower() for c in r.checklist)

    def test_always_has_plugs(self):
        r = calculate_slide(_make_section())
        assert any("заглушки" in c.lower() for c in r.checklist)

    def test_felt_for_rs2061(self):
        r = calculate_slide(_make_section(inter_glass_profile="Алюминиевый RS2061"))
        assert any("фетровое" in c and "RS2061" in c for c in r.checklist)

    def test_no_felt_for_rs3061(self):
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        assert not any("RS3061" in c for c in r.checklist)

    def test_felt_for_handle_bar(self):
        r = calculate_slide(_make_section(profile_left_handle_bar=True))
        assert any("RS112" in c for c in r.checklist)

    def test_milling_for_locks(self):
        r = calculate_slide(_make_section(lock_left="ЗАМОК-ЗАЩЁЛКА 1стор"))
        assert any(
            "фрезеровк" in c.lower() and "защелк" in c.lower() for c in r.checklist
        )

    def test_milling_rs2081_slots(self):
        r = calculate_slide(_make_section(profile_left_lock_bar=True))
        assert any("RS2081" in c for c in r.checklist)

    def test_sticker(self):
        r = calculate_slide(_make_section())
        assert any("наклейк" in c.lower() for c in r.checklist)

    def test_felt_for_rs1006_full_name(self):
        """Прозрачный с фетром RS1006 (полное название с фронта) → чеклист фетр."""
        r = calculate_slide(
            _make_section(inter_glass_profile="Прозрачный с фетром RS1006")
        )
        assert any("фетровое" in c and "RS1006" in c for c in r.checklist)


# ═══════════════════════════════════════════════════════════════════════════
# КРАЙНИЕ СТЁКЛА (объединение левого и правого)
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeGlass:
    """Когда left_W == right_W → объединяем в 'Крайние'."""

    def test_symmetric_gives_edge(self):
        """Симметричная конфигурация → 'Крайние' вместо 'Левое'+'Правое'."""
        r = calculate_slide(_make_section())
        edge = _find_glass(r, "Крайние")
        assert len(edge) == 1
        assert edge[0].qty == 2
        assert _find_glass(r, "Левое") == []
        assert _find_glass(r, "Правое") == []

    def test_asymmetric_gives_left_right(self):
        """Ассиметрия (ручка-профиль только слева) → 'Левое' + 'Правое'."""
        r = calculate_slide(_make_section(profile_left_handle_bar=True))
        assert len(_find_glass(r, "Левое")) == 1
        assert len(_find_glass(r, "Правое")) == 1
        assert _find_glass(r, "Крайние") == []

    def test_edge_qty_with_quantity(self):
        """Q=2, симметрия → Крайние qty = 2*Q = 4."""
        r = calculate_slide(_make_section(quantity=2))
        edge = _find_glass(r, "Крайние")[0]
        assert edge.qty == 4

    def test_two_panels_symmetric(self):
        """2 панели, симметрия → Крайние qty=2*Q, нет промежуточных."""
        r = calculate_slide(_make_section(panels=2))
        edge = _find_glass(r, "Крайние")[0]
        assert edge.qty == 2
        mid = _find_glass(r, "Промежуточные")
        assert len(mid) == 0 or mid[0].qty == 0

    def test_rs2021_for_edge_glass(self):
        """RS2021 для Крайних — одна запись с суммарным qty."""
        r = calculate_slide(_make_section())
        edge = _find_glass(r, "Крайние")[0]
        rs2021 = _find_profile(r, "RS2021")
        total_qty = sum(p.qty for p in rs2021)
        assert total_qty >= edge.qty


# ═══════════════════════════════════════════════════════════════════════════
# ПРОЗРАЧНЫЙ С ФЕТРОМ RS1006 (полное название)
# ═══════════════════════════════════════════════════════════════════════════


class TestRS1006FullName:
    """Фронт отправляет 'Прозрачный с фетром RS1006' — проверяем маппинг."""

    def test_inter_glass_profile_created(self):
        r = calculate_slide(
            _make_section(inter_glass_profile="Прозрачный с фетром RS1006")
        )
        rs1006 = _find_profile(r, "RS1006")
        assert len(rs1006) == 1
        assert rs1006[0].qty == 2  # (P-1)*Q = 2*1

    def test_ru007_calculated(self):
        """Щётка 7×12 должна считаться для RS1006."""
        r = calculate_slide(
            _make_section(inter_glass_profile="Прозрачный с фетром RS1006")
        )
        brush = _find_hardware(r, "")[0]  # первый элемент — щётка
        ru007 = [s for s in brush.sub_items if s.article == "RU007"]
        assert len(ru007) == 1
        assert ru007[0].value > 0

    def test_rs107l_plug_created(self):
        """Заглушка RS107L для RS1006."""
        r = calculate_slide(
            _make_section(
                inter_glass_profile="Прозрачный с фетром RS1006",
                first_panel_inside="Справа",
            )
        )
        rs107l = _find_hardware(r, "RS107L")
        assert len(rs107l) == 1


# ═══════════════════════════════════════════════════════════════════════════
# СЛАЙД 2 РЯДА
# ═══════════════════════════════════════════════════════════════════════════


class TestSlideTwoRows:
    """Отдельная ветка расчета СЛАЙД стандарт 2 ряда."""

    def test_system_text_and_panel_rails_3rail_4panels_center_first(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                unused_track="Внешний",
                first_panel_inside=None,
            )
        )
        assert r.system_text == "SLIDE-стандарт 2 ряда"
        assert r.panel_rails == [1, 2, 2, 1]

    def test_glass_formula_has_central_pair(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                unused_track="Внешний",
                first_panel_inside=None,
            )
        )
        left = _find_glass(r, "Левое")[0]
        center = _find_glass(r, "Центральные")[0]
        right = _find_glass(r, "Правое")[0]
        expected = round((2000 - 3 - 16 - 16 + 9.5 * 2) / 4, 1)
        assert left.width_mm == expected
        assert center.width_mm == expected
        assert center.qty == 2
        assert right.width_mm == expected

    def test_center_offset_zero_matches_four_panel_reference(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                width=3635,
                height=2780,
                unused_track="Внешний",
                inter_glass_profile="Профиль с зацепом RS3061",
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                center_handle="Стеклянная ручка RS3017",
                center_handle_offset=0,
                first_panel_inside=None,
            )
        )

        assert [
            (item.width_mm, item.glass_profile_length) for item in r.panel_glass
        ] == [
            (909.8, 909.8),
            (893.8, 890.8),
            (893.8, 890.8),
            (909.8, 909.8),
        ]

    def test_hidden_center_offset_is_ignored_for_six_panel_knob_reference(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=6,
                width=3837,
                height=2274,
                unused_track="Внешний",
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_wall=False,
                profile_right_wall=False,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Без ручки (глухая)",
                handle_right="Без ручки (глухая)",
                center_handle="Ручка-кноб RS3014",
                center_handle_offset=100,
                first_panel_inside=None,
            )
        )

        assert [
            (item.width_mm, item.glass_profile_length) for item in r.panel_glass
        ] == [
            (653.3, 653.3),
            (637.3, 634.3),
            (637.3, 634.3),
            (637.3, 634.3),
            (637.3, 634.3),
            (653.3, 653.3),
        ]

    def test_hidden_center_offset_is_ignored_for_all_panel_counts(self):
        unsupported_handles = (
            "Ручка-кноб RS3014",
            "Ручки-профиль RS112 (2шт)",
            "Без ручки (глухие)",
            "Без ручки (подвижные)",
        )
        for panels in (4, 6, 8, 10):
            rails = 3 if panels <= 6 else 5
            for handle in unsupported_handles:
                baseline = calculate_slide(
                    _make_section(
                        slide_rows=2,
                        rails=rails,
                        panels=panels,
                        center_handle=handle,
                        center_handle_offset=0,
                        first_panel_inside=None,
                    )
                )
                stale = calculate_slide(
                    _make_section(
                        slide_rows=2,
                        rails=rails,
                        panels=panels,
                        center_handle=handle,
                        center_handle_offset=100,
                        first_panel_inside=None,
                    )
                )
                assert stale.panel_glass == baseline.panel_glass

    def test_manual_center_offset_is_kept_for_supported_handles(self):
        for handle in (
            "Стеклянная ручка RS3017",
            "Ручка-скоба 600мм RS30201",
        ):
            baseline = calculate_slide(
                _make_section(
                    slide_rows=2,
                    panels=4,
                    center_handle=handle,
                    center_handle_offset=0,
                    first_panel_inside=None,
                )
            )
            with_offset = calculate_slide(
                _make_section(
                    slide_rows=2,
                    panels=4,
                    center_handle=handle,
                    center_handle_offset=100,
                    first_panel_inside=None,
                )
            )

            assert (
                baseline.panel_glass[0].width_mm - with_offset.panel_glass[0].width_mm
                == 50
            )
            assert (
                with_offset.panel_glass[1].width_mm - baseline.panel_glass[1].width_mm
                == 50
            )

    def test_two_rows_rs3061_uses_115_overlap(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                unused_track="Внешний",
                inter_glass_profile="Профиль с зацепом RS3061",
                first_panel_inside=None,
            )
        )
        left = _find_glass(r, "Левое")[0]
        center = _find_glass(r, "Центральные")[0]
        expected = round((2000 - 3 - 16 - 16 + 11.5 * 2) / 4, 1)
        assert left.width_mm == expected
        assert center.width_mm == expected
        assert _find_profile(r, "RS3061")

    def test_5rail_8panels_has_middle_glass(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=5,
                panels=8,
                unused_track="Внешний",
                first_panel_inside=None,
            )
        )
        middle = _find_glass(r, "Промежуточные")[0]
        assert middle.qty == 4
        assert r.panel_rails == [1, 2, 3, 4, 4, 3, 2, 1]

    def test_center_rs112_adds_profiles_and_skips_rs3110(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )
        rs112 = _find_profile(r, "RS112")[0]
        rs1083 = _find_profile(r, "RS1083")[0]
        ru010 = _find_profile(r, "RU010")[0]
        assert rs112.qty == 2
        assert rs1083.length_mm == 2255
        assert rs1083.name == "Соединительный профиль 30×20×30"
        assert ru010.qty == 2
        assert ru010.length_mm == rs1083.length_mm
        assert not _find_hardware(r, "RS3110")
        assert not _find_profile(r, "RS3110")

    def test_center_rs112_uses_updated_465_center_offset(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )

        edge_width = round((2000 - 3 - 16 - 16 - 46.5 - 8 + 9.5 * 2) / 4, 1)
        center_width = round(edge_width + 8, 1)
        assert [panel.width_mm for panel in r.panel_glass] == [
            edge_width,
            center_width,
            center_width,
            edge_width,
        ]

    def test_center_rs112_splits_glass_profile_lengths(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=4,
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )
        center_left = _find_glass(r, "Центральное левое")[0]
        center_right = _find_glass(r, "Центральное правое")[0]
        assert center_left.glass_profile_length == round(center_left.width_mm + 19, 1)
        assert center_right.glass_profile_length == round(center_right.width_mm + 16, 1)
        assert r.panel_glass[1].glass_profile_length == center_left.glass_profile_length
        assert (
            r.panel_glass[2].glass_profile_length == center_right.glass_profile_length
        )
        assert not _find_hardware(r, "RS106")
        assert _find_hardware(r, "RS108")[0].value == 2

    def test_center_rs112_does_not_create_rs106_for_fixed_outer_panels(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                quantity=2,
                handle_left="Без ручки (глухая)",
                handle_right="Без ручки (глухая)",
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )

        assert not _find_hardware(r, "RS106")
        assert _find_hardware(r, "RS108")[0].value == 4

    def test_center_rs112_keeps_only_two_outer_rs106(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=6,
                handle_left="Ручка-кноб RS3014",
                handle_right="Ручка-кноб RS3014",
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )

        assert _find_hardware(r, "RS105")[0].value == 8
        assert _find_hardware(r, "RS106")[0].value == 2
        assert _find_hardware(r, "RS108")[0].value == 2
        assert _find_hardware(r, "RS107")[0].value == 10
        assert _find_screw(r, "4,8×25")[0].qty == 24

    def test_two_rows_central_sashes_use_rs108(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                handle_left="Без ручки (глухая)",
                handle_right="Без ручки (глухая)",
                center_handle="Без ручки (глухие)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )
        rs108 = _find_hardware(r, "RS108")[0]
        rs105 = _find_hardware(r, "RS105")[0]
        screw = _find_screw(r, "4,8×25")[0]
        assert rs108.value == 2
        assert rs105.value == 4
        assert not _find_hardware(r, "RS106")
        assert screw.qty == (rs105.value + rs108.value) * 2

    def test_center_rs3110_is_cut_profile_with_image(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                center_handle="Без ручки (глухие)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )
        rs3110 = _find_profile(r, "RS3110")[0]
        assert rs3110.length_mm == 2238
        assert rs3110.qty == 1
        assert rs3110.image == "RS3110.jpg"
        assert not _find_hardware(r, "RS3110")

    def test_center_locks_are_separate_hardware(self):
        glass_lock = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                center_handle="Ручка-кноб RS3014",
                center_lock="Замок стекло-стекло RS30301",
                first_panel_inside=None,
            )
        )
        latch = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                center_handle="Ручки-профиль RS112 (2шт)",
                center_lock="Накидная защёлка RS206",
                first_panel_inside=None,
            )
        )
        assert _find_hardware(glass_lock, "RS30301")[0].value == 1
        assert _find_hardware(latch, "RS206")[0].value == 1

    def test_center_floor_latches_are_counted_with_side_latches(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                center_floor_latches_left=True,
                center_floor_latches_right=True,
                floor_latches_left=True,
                first_panel_inside=None,
            )
        )
        assert _find_hardware(r, "RS205")[0].value == 3
        assert not _find_profile(r, "RS205")

    def test_two_rows_six_panels_use_noncentral_and_central_plugs(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=6,
                handle_left="Ручка-кноб RS3014",
                handle_right="Ручка-кноб RS3014",
                center_handle="Без ручки (глухие)",
                center_lock="Без",
                first_panel_inside=None,
            )
        )
        assert _find_hardware(r, "RS105")[0].value == 8
        assert _find_hardware(r, "RS106")[0].value == 2
        assert _find_hardware(r, "RS108")[0].value == 2
        assert _find_hardware(r, "RS107")[0].value == 10
        assert _find_screw(r, "4,8×25")[0].qty == 24

    def test_two_rows_section_13_treats_empty_outer_handles_as_moving_panels(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                rails=3,
                panels=6,
                unused_track="Внешний",
                handle_left=None,
                handle_right=None,
                lock_left=None,
                lock_right=None,
                center_handle="Ручка-кноб RS3014",
                center_lock=None,
                profile_left_handle_bar=False,
                profile_right_handle_bar=False,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                first_panel_inside=None,
            )
        )

        assert _find_hardware(r, "RS105")[0].value == 8
        assert _find_hardware(r, "RS106")[0].value == 2
        assert _find_hardware(r, "RS108")[0].value == 2
        assert _find_hardware(r, "RS107")[0].value == 10
        assert _find_screw(r, "4,8×25")[0].qty == 24

    def test_two_rows_brush_and_inter_glass_use_half_tracks(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=6,
                quantity=2,
                inter_glass_profile="Алюминиевый RS2061",
                center_handle="Без ручки (глухие)",
                first_panel_inside=None,
            )
        )
        brush = _find_hardware(r, "")[0]
        ru008 = next(item for item in brush.sub_items if item.article == "RU008")
        ru007 = next(item for item in brush.sub_items if item.article == "RU007")
        top_len_m = 1968 / 1000
        inter_len_m = 2238 / 1000
        assert ru008.value == round(top_len_m * (6 // 2) * 2 * 2, 3)
        assert ru007.value == round((inter_len_m + 0.03) * (6 - 2) * 2, 3)
        assert _find_profile(r, "RS2061")[0].qty == (6 - 2) * 2

    def test_inter_glass_plugs_use_both_sides_and_half_panel_formula(self):
        cases = [
            (4, 1),
            (6, 2),
            (8, 3),
            (10, 4),
        ]
        for panels, expected_per_side in cases:
            r = calculate_slide(
                _make_section(
                    slide_rows=2,
                    panels=panels,
                    quantity=1,
                    inter_glass_profile="Алюминиевый RS2061",
                    first_panel_inside=None,
                )
            )
            assert _find_hardware(r, "RS107L")[0].value == expected_per_side
            assert _find_hardware(r, "RS107R")[0].value == expected_per_side

    def test_inter_glass_plugs_two_rows_respect_quantity(self):
        r = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=4,
                quantity=2,
                inter_glass_profile="Алюминиевый RS2061",
                first_panel_inside=None,
            )
        )
        assert _find_hardware(r, "RS107L")[0].value == 2
        assert _find_hardware(r, "RS107R")[0].value == 2

    def test_inter_glass_plugs_two_rows_do_not_depend_on_unused_track(self):
        external = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=8,
                unused_track="Внешний",
                inter_glass_profile="Алюминиевый RS2061",
                first_panel_inside=None,
            )
        )
        internal = calculate_slide(
            _make_section(
                slide_rows=2,
                panels=8,
                unused_track="Внутренний",
                inter_glass_profile="Алюминиевый RS2061",
                first_panel_inside=None,
            )
        )
        assert [
            _find_hardware(external, "RS107L")[0].value,
            _find_hardware(external, "RS107R")[0].value,
        ] == [3, 3]
        assert [
            _find_hardware(internal, "RS107L")[0].value,
            _find_hardware(internal, "RS107R")[0].value,
        ] == [3, 3]

    def test_inter_glass_plugs_two_rows_absent_without_supported_profile(self):
        for inter_glass_profile in ("Без", "h-профиль RS1004"):
            r = calculate_slide(
                _make_section(
                    slide_rows=2,
                    panels=4,
                    inter_glass_profile=inter_glass_profile,
                    first_panel_inside=None,
                )
            )
            assert not _find_hardware(r, "RS107L")
            assert not _find_hardware(r, "RS107R")


class TestInterGlassProfileDefaults:
    def test_legacy_null_uses_aluminum_profile_for_reference_section(self):
        result = calculate_slide(
            _make_section(
                width=2003,
                height=2750,
                panels=3,
                inter_glass_profile=None,
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
                profile_left_handle_bar=True,
                profile_right_handle_bar=True,
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                lock_right="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                handle_left=None,
                handle_right=None,
            )
        )

        assert _ceil_panel_widths(result) == [626, 618, 626]
        assert _ceil_panel_profile_lengths(result) == [642, 615, 642]
        assert _find_profile(result, "RS2061")[0].qty == 2

    def test_explicit_no_profile_keeps_zero_overlap(self):
        result = calculate_slide(
            _make_section(
                width=2003,
                height=2750,
                panels=3,
                inter_glass_profile="— Без межстекольного профиля —",
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
                profile_left_handle_bar=True,
                profile_right_handle_bar=True,
                lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                lock_right="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                handle_left=None,
                handle_right=None,
            )
        )

        assert _ceil_panel_widths(result) == [620, 612, 620]
        assert _ceil_panel_profile_lengths(result) == [636, 612, 636]
        assert not _find_profile(result, "RS2061")

    def test_five_panel_reference_keeps_side_specific_offsets(self):
        result = calculate_slide(
            _make_section(
                width=4310,
                height=2620,
                panels=5,
                rails=5,
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_lock_bar=False,
                profile_right_lock_bar=False,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left=None,
                handle_right="Ручка-скоба 600мм RS30201",
                handle_offset_right=100,
                lock_left=None,
                lock_right=None,
            )
        )

        assert _ceil_panel_widths(result) == [853, 837, 837, 837, 937]
        assert _ceil_panel_profile_lengths(result) == [853, 834, 834, 834, 934]

    def test_reference_4186_keeps_right_offset_and_left_deaf_recovery(self):
        result = calculate_slide(
            _make_section(
                width=2960,
                height=2940,
                panels=3,
                rails=3,
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_wall=True,
                profile_right_wall=False,
                profile_left_lock_bar=False,
                profile_right_lock_bar=False,
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Без ручки (глухая)",
                handle_right="Ручка-скоба 600мм RS30201",
                handle_offset_left=0,
                handle_offset_right=100,
                lock_left=None,
                lock_right=None,
            )
        )

        assert _ceil_panel_widths(result) == [960, 944, 1044]
        assert _ceil_panel_profile_lengths(result) == [960, 941, 1041]

    def test_two_rows_keep_handle_offset_separate_from_fixed_edge_recovery(self):
        result = calculate_slide(
            _make_section(
                width=5000,
                height=2620,
                panels=6,
                rails=5,
                slide_rows=2,
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_p_bar=True,
                profile_right_p_bar=True,
                profile_left_bubble=True,
                profile_right_bubble=True,
                handle_left="Без ручки (глухая)",
                handle_right="Ручка-скоба 600мм RS30201",
                handle_offset_right=100,
                lock_left=None,
                lock_right=None,
            )
        )

        widths = [panel.width_mm for panel in result.panel_glass]
        assert round(widths[0] - widths[1], 1) == 16
        assert round(widths[-1] - widths[1], 1) == 100
