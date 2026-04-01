"""
Тесты расчётного движка СЛАЙД (slide_calc.py).
Покрывает: переменные профилей, формулы стёкол, профили, фурнитуру, саморезы.
"""

from types import SimpleNamespace
from engine.slide_calc import calculate_slide, SlideCalcResult


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
        glass_type="10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
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
        """3 панели → левое + промежуточные + правое."""
        assert len(self.result.glass) == 3

    def test_glass_height_standard(self):
        """glass_H = H - 106 = 2294."""
        for g in self.result.glass:
            assert g.height_mm == 2294

    def test_glass_widths_symmetric(self):
        """Без ручек/замков, только пристеночные: ppl=ppr=16, остальные=0."""
        left = _find_glass(self.result, "Левое")[0]
        mid = _find_glass(self.result, "Промежуточные")[0]
        right = _find_glass(self.result, "Правое")[0]
        # middle_W = (2000 - 16 - 16 + 9.5*2) / 3 = (2000 - 32 + 19) / 3 = 1987/3 ≈ 662.3
        expected_mid = round((2000 - 16 - 16 + 9.5 * 2) / 3, 1)
        assert mid.width_mm == expected_mid
        # Без ручек: left_W = middle_W, right_W = middle_W
        assert left.width_mm == expected_mid
        assert right.width_mm == expected_mid

    def test_glass_quantities(self):
        left = _find_glass(self.result, "Левое")[0]
        mid = _find_glass(self.result, "Промежуточные")[0]
        right = _find_glass(self.result, "Правое")[0]
        assert left.qty == 1
        assert mid.qty == 1  # (3-2)*1
        assert right.qty == 1


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

    def test_rpl_handle_bar_and_lock_bar(self):
        """Ручка-профиль + замок → rpl = 59.5."""
        s = _make_section(
            profile_left_handle_bar=True,
            profile_left_lock_bar=True,
        )
        r = calculate_slide(s)
        left = _find_glass(r, "Левое")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        # rpl=59.5, krlr=8, left_W = mid_W + 0 + 8 + 0
        assert left.width_mm > mid.width_mm

    def test_rpl_handle_bar_and_p_bar(self):
        """Ручка-профиль + П-профиль → rpl = 27."""
        s = _make_section(
            profile_left_handle_bar=True,
            profile_left_p_bar=True,
        )
        r = calculate_slide(s)
        left = _find_glass(r, "Левое")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        # krlr=8, left_W = mid_W + 0 + 8 + 0
        assert left.width_mm == round(mid.width_mm + 8, 1)

    def test_krlp_p_bar_and_bubble(self):
        """П-профиль + пузырьковый → krlp = 16."""
        s = _make_section(
            profile_left_p_bar=True,
            profile_left_bubble=True,
        )
        r = calculate_slide(s)
        left = _find_glass(r, "Левое")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        # krlp=16, left_W = mid_W + 0 + 0 + 16
        assert left.width_mm == round(mid.width_mm + 16, 1)

    def test_handle_offset_left(self):
        """Отступ a влияет на middle_W и left_W."""
        s = _make_section(handle_offset_left=100)
        r = calculate_slide(s)
        left = _find_glass(r, "Левое")[0]
        mid = _find_glass(r, "Промежуточные")[0]
        # left_W = mid_W + a + krlr + krlp = mid_W + 100
        assert left.width_mm == round(mid.width_mm + 100, 1)


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
        assert g.width_mm == 2000 - 16 - 16 - 5 - 5  # 1958


# ═══════════════════════════════════════════════════════════════════════════
# P=2 (НЕТ ПРОМЕЖУТОЧНЫХ)
# ═══════════════════════════════════════════════════════════════════════════


class TestTwoPanels:
    def test_p2_no_middle_glass(self):
        s = _make_section(panels=2)
        r = calculate_slide(s)
        mid = _find_glass(r, "Промежуточные")[0]
        assert mid.qty == 0  # (2-2)*1 = 0


# ═══════════════════════════════════════════════════════════════════════════
# АРТИКУЛЫ ПОРОГА (рельсы × порог)
# ═══════════════════════════════════════════════════════════════════════════


class TestThresholdArticles:
    def test_3_standard(self):
        r = calculate_slide(_make_section(rails=3, threshold="Стандартный анод"))
        assert _find_profile(r, "RS2323")

    def test_3_overlay(self):
        r = calculate_slide(_make_section(rails=3, threshold="Накладной анод"))
        assert _find_profile(r, "RS23231")

    def test_5_standard(self):
        r = calculate_slide(_make_section(rails=5, threshold="Стандартный анод"))
        assert _find_profile(r, "RS2325")

    def test_5_overlay(self):
        r = calculate_slide(_make_section(rails=5, threshold="Накладной анод"))
        assert _find_profile(r, "RS23251")


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
        r = calculate_slide(_make_section(profile_left_wall=True, profile_right_wall=False))
        profiles = _find_profile(r, "RS2333")
        assert profiles[0].qty == 1

    def test_no_walls(self):
        r = calculate_slide(_make_section(profile_left_wall=False, profile_right_wall=False))
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
        assert not _find_profile(r, "RS1004")

    def test_rs1006(self):
        r = calculate_slide(_make_section(inter_glass_profile="Прозрачный RS1006"))
        assert _find_profile(r, "RS1006")

    def test_rs1004(self):
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        assert _find_profile(r, "RS1004")

    def test_not_painted_rs1006(self):
        """RS1006 не красится даже при RAL."""
        r = calculate_slide(_make_section(
            inter_glass_profile="Прозрачный RS1006",
            painting_type="RAL стандарт",
            ral_color="9016",
        ))
        p = _find_profile(r, "RS1006")[0]
        assert p.painted is False

    def test_painted_rs2061(self):
        """RS2061 красится при RAL."""
        r = calculate_slide(_make_section(
            painting_type="RAL стандарт",
            ral_color="9016",
        ))
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
        r = calculate_slide(_make_section(
            profile_left_handle_bar=True,
            profile_right_handle_bar=True,
            quantity=2,
        ))
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

    def test_lock_rs3019(self):
        """2-сторонняя защёлка × Q."""
        r = calculate_slide(_make_section(lock_right="ЗАМОК-ЗАЩЁЛКА 2стор с ключом"))
        rs3019 = _find_hardware(r, "RS3019")
        assert len(rs3019) == 1
        assert rs3019[0].value == 1

    def test_rs122_rs3020(self):
        """RS122 = RS3020 = (lock3018 + lock3019) * Q."""
        r = calculate_slide(_make_section(
            lock_left="ЗАМОК-ЗАЩЁЛКА 1стор",
            lock_right="ЗАМОК-ЗАЩЁЛКА 2стор с ключом",
            quantity=2,
        ))
        rs122 = _find_hardware(r, "RS122")
        rs3020 = _find_hardware(r, "RS3020")
        assert rs122[0].value == 2 * 2  # (1+1)*2
        assert rs3020[0].value == rs122[0].value

    def test_no_locks_no_rs122(self):
        r = calculate_slide(_make_section())
        assert not _find_hardware(r, "RS122")
        assert not _find_hardware(r, "RS3020")

    def test_rollers_ru005(self):
        """RU005 = P * 2 * Q."""
        r = calculate_slide(_make_section(panels=3, quantity=2))
        ru005 = _find_hardware(r, "RU005")
        assert ru005[0].value == 3 * 2 * 2  # 12

    def test_rs3017_glass_handle(self):
        r = calculate_slide(_make_section(handle_left="Стеклянная ручка RS3017"))
        rs3017 = _find_hardware(r, "RS3017")
        assert len(rs3017) == 1
        assert rs3017[0].value == 1

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

    def test_rs1004_no_plugs(self):
        """h-профиль RS1004 — нет заглушек межстекольного."""
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
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
        r = calculate_slide(_make_section(
            handle_left="Стеклянная ручка RS3017",
            handle_right="Ручка-кноб RS3014",
        ))
        rs106 = _find_hardware(r, "RS106")
        assert rs106[0].value == 2

    def test_rs106_one_deaf(self):
        """Одна глухая → RS106 = 1*Q."""
        r = calculate_slide(_make_section(
            handle_left="Стеклянная ручка RS3017",
            handle_right="Без",
            lock_right="Без",
        ))
        rs106 = _find_hardware(r, "RS106")
        assert rs106[0].value == 1

    def test_rs106_both_deaf(self):
        """Обе глухие → RS106 = 0."""
        r = calculate_slide(_make_section(
            handle_left="Без",
            handle_right="Без",
            lock_left="Без",
            lock_right="Без",
        ))
        assert not _find_hardware(r, "RS106")

    def test_rs107_total(self):
        """RS107 = RS105 + RS106."""
        r = calculate_slide(_make_section(
            panels=3,
            handle_left="Стеклянная ручка RS3017",
            handle_right="Ручка-кноб RS3014",
        ))
        rs105 = _find_hardware(r, "RS105")[0].value  # (3-1)*2 = 4
        rs106 = _find_hardware(r, "RS106")[0].value  # 2
        rs107 = [h for h in r.hardware if h.article == "RS107"][0].value
        assert rs107 == rs105 + rs106


# ═══════════════════════════════════════════════════════════════════════════
# САМОРЕЗЫ
# ═══════════════════════════════════════════════════════════════════════════


class TestScrews:
    def test_screw_4819(self):
        """4,8×19 = (RS105 + RS106) * 2."""
        r = calculate_slide(_make_section(
            panels=3,
            handle_left="Стеклянная ручка RS3017",
            handle_right="Ручка-кноб RS3014",
        ))
        rs105_val = _find_hardware(r, "RS105")[0].value
        rs106_val = _find_hardware(r, "RS106")[0].value
        screw = _find_screw(r, "4,8×19")[0]
        assert screw.qty == (rs105_val + rs106_val) * 2

    def test_screw_3913m_no_p_bar(self):
        """DIN7504M = RU005*2 + pb_count*7*Q. Без П-профиля: только ролики."""
        r = calculate_slide(_make_section(panels=3))
        ru005 = _find_hardware(r, "RU005")[0].value  # 3*2*1 = 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2  # 12

    def test_screw_3913m_with_p_bar(self):
        """DIN7504M = RU005*2 + pb_count*7*Q."""
        r = calculate_slide(_make_section(
            panels=3,
            profile_left_p_bar=True,
            profile_right_p_bar=True,
        ))
        ru005 = _find_hardware(r, "RU005")[0].value  # 6
        screw = _find_screw(r, "DIN7504M")[0]
        assert screw.qty == ru005 * 2 + 2 * 7 * 1  # 12 + 14 = 26

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
        """DIN7504O = pb_count * 7 * Q."""
        r = calculate_slide(_make_section(profile_left_p_bar=True, quantity=2))
        screw = _find_screw(r, "DIN7504О")[0]
        assert screw.qty == 1 * 7 * 2  # 14

    def test_screw_3913o_no_p_bar(self):
        r = calculate_slide(_make_section())
        assert not _find_screw(r, "DIN7504О")

    def test_screw_5425_deaf_panels(self):
        """5,4×25 = deaf_count * Q."""
        r = calculate_slide(_make_section(
            handle_left="Без",
            handle_right="Без",
            lock_left="Без",
            lock_right="Без",
            quantity=2,
        ))
        screw = _find_screw(r, "5,4×25")[0]
        assert screw.qty == 2 * 2  # оба глухие × Q

    def test_screw_5425_no_deaf(self):
        r = calculate_slide(_make_section(
            handle_left="Стеклянная ручка RS3017",
            handle_right="Ручка-кноб RS3014",
        ))
        assert not _find_screw(r, "5,4×25")

    def test_screw_3513_with_locks(self):
        """3,5×13 = RS122 * 2."""
        r = calculate_slide(_make_section(
            lock_left="ЗАМОК-ЗАЩЁЛКА 1стор",
            lock_right="ЗАМОК-ЗАЩЁЛКА 2стор с ключом",
        ))
        rs122_val = _find_hardware(r, "RS122")[0].value
        screw = _find_screw(r, "3,5×13")[0]
        assert screw.qty == rs122_val * 2

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

    def test_rs2021_handle_bar_adds_16(self):
        """Ручка-профиль слева → левое стекло RS2021 +16."""
        r = calculate_slide(_make_section(profile_left_handle_bar=True))
        left_glass = _find_glass(r, "Левое")[0]
        # RS2021 для левого = left_glass.width + 16
        assert left_glass.glass_profile_length == round(left_glass.width_mm + 16, 1)

    def test_rs2021_bubble_subtracts_3(self):
        """Пузырьковый на подвижной → RS2021 -3."""
        r = calculate_slide(_make_section(
            profile_left_bubble=True,
            handle_left="Стеклянная ручка RS3017",  # не глухая
        ))
        left_glass = _find_glass(r, "Левое")[0]
        assert left_glass.glass_profile_length == round(left_glass.width_mm - 3, 1)

    def test_rs2021_bubble_deaf_no_subtract(self):
        """Пузырьковый на глухой → RS2021 НЕ вычитает 3."""
        r = calculate_slide(_make_section(
            profile_left_bubble=True,
            handle_left="Без",
            lock_left="Без",
        ))
        left_glass = _find_glass(r, "Левое")[0]
        assert left_glass.glass_profile_length == left_glass.width_mm

    def test_rs2021_handle_bar_and_bubble(self):
        """Ручка-профиль + пузырьковый (подвижная) → +16 -3 = +13."""
        r = calculate_slide(_make_section(
            profile_left_handle_bar=True,
            profile_left_bubble=True,
            handle_left="Стеклянная ручка RS3017",
        ))
        left_glass = _find_glass(r, "Левое")[0]
        assert left_glass.glass_profile_length == round(left_glass.width_mm + 16 - 3, 1)

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
        left = _find_glass(self.r, "Левое")[0]
        assert left.qty == 3

    def test_rollers_qty(self):
        ru005 = _find_hardware(self.r, "RU005")[0]
        assert ru005.value == 3 * 2 * 3  # P=3, 2 ролика, Q=3


# ═══════════════════════════════════════════════════════════════════════════
# ПОКРАСКА
# ═══════════════════════════════════════════════════════════════════════════


class TestPainting:
    def test_ral_profiles_painted(self):
        r = calculate_slide(_make_section(painting_type="RAL стандарт", ral_color="9016"))
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.painted is True

    def test_anod_profiles_not_painted(self):
        r = calculate_slide(_make_section(painting_type="Анодированный"))
        threshold = _find_profile(r, "RS2323")[0]
        assert threshold.painted is False

    def test_color_text_ral(self):
        r = calculate_slide(_make_section(painting_type="RAL стандарт", ral_color="9016"))
        assert "RAL" in r.color_text
        assert "9016" in r.color_text

    def test_color_text_anod(self):
        r = calculate_slide(_make_section(
            threshold="Стандартный анод",
            painting_type="",
        ))
        assert "Анодированный" in r.color_text


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

    def test_no_felt_for_rs1004(self):
        r = calculate_slide(_make_section(inter_glass_profile="h-профиль RS1004"))
        assert not any("RS1004" in c for c in r.checklist)

    def test_felt_for_handle_bar(self):
        r = calculate_slide(_make_section(profile_left_handle_bar=True))
        assert any("RS112" in c for c in r.checklist)

    def test_milling_for_locks(self):
        r = calculate_slide(_make_section(lock_left="ЗАМОК-ЗАЩЁЛКА 1стор"))
        assert any("фрезеровк" in c.lower() and "защелк" in c.lower() for c in r.checklist)

    def test_milling_rs2081_slots(self):
        r = calculate_slide(_make_section(profile_left_lock_bar=True))
        assert any("RS2081" in c for c in r.checklist)

    def test_sticker(self):
        r = calculate_slide(_make_section())
        assert any("наклейк" in c.lower() for c in r.checklist)
