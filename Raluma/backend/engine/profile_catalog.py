from __future__ import annotations

from dataclasses import dataclass


DEFAULT_COLOR_VARIANTS = ("Анод", "RAL стандарт", "RAL нестандарт")


@dataclass(frozen=True)
class ProfileCatalogItem:
    article: str
    name: str
    image: str
    section_width_mm: float
    section_height_mm: float
    paint_mode: str
    color_variants: tuple[str, ...] = DEFAULT_COLOR_VARIANTS
    paint_note: str = ""
    group: str = "Профили"
    system: str = "СЛАЙД"
    unit: str = "м.п."
    purchase_price: float = 0
    markup_percent: float = 35
    weight: float = 0
    waste_percent: float = 4
    supplier: str = "Raluma"
    is_active: bool = True
    note: str = ""


PROFILE_CATALOG: dict[str, ProfileCatalogItem] = {
    "RS1313": ProfileCatalogItem(
        "RS1313",
        "Верхний направляющий профиль 3-рельсовый",
        "RS1313.png",
        72,
        53,
        "Красится",
        system="СЛАЙД 3",
        purchase_price=420,
        weight=0.72,
        note="Длина считается формулой, сечение используется для схем и документов",
    ),
    "RS1315": ProfileCatalogItem(
        "RS1315",
        "Верхний направляющий профиль 5-рельсовый",
        "RS1315.png",
        119,
        53,
        "Красится",
        system="СЛАЙД 5",
        purchase_price=580,
        weight=0.96,
        note="Пять рельсов, геометрия нужна для масштабной схемы",
    ),
    "RS2323": ProfileCatalogItem(
        "RS2323",
        "Порог 3-рельсовый",
        "RS2323.jpg",
        76,
        23,
        "Частично",
        paint_note="НЕ КРАСИТЬ!!!",
        system="СЛАЙД 3",
        purchase_price=380,
        weight=0.61,
        note="В заявке на покраску отмечать область, которую не красить",
    ),
    "RS2325": ProfileCatalogItem(
        "RS2325",
        "Порог 5-рельсовый",
        "RS1325.jpg",
        122,
        23,
        "Красится",
        system="СЛАЙД 5",
        purchase_price=520,
        weight=0.88,
        note="Стандартный нижний направляющий профиль",
    ),
    "RS23231": ProfileCatalogItem(
        "RS23231",
        "Накладной порог 3-рельсовый",
        "RS2323.jpg",
        76,
        11,
        "Красится",
        system="СЛАЙД 3",
        purchase_price=340,
        weight=0.32,
        note="Накладной порог, профиль отправляется на покраску по цвету секции",
    ),
    "RS23251": ProfileCatalogItem(
        "RS23251",
        "Накладной порог 5-рельсовый",
        "RS1325.jpg",
        122,
        11,
        "Красится",
        system="СЛАЙД 5",
        purchase_price=460,
        weight=0.46,
        note="Накладной порог, профиль отправляется на покраску по цвету секции",
    ),
    "RS2333": ProfileCatalogItem(
        "RS2333",
        "Пристеночный профиль 3-рельсовый",
        "RS2333.jpg",
        76,
        16,
        "Красится",
        system="СЛАЙД 3",
        purchase_price=330,
        weight=0.42,
        note="На схеме сверху добавляет 16 мм с выбранной стороны",
    ),
    "RS2335": ProfileCatalogItem(
        "RS2335",
        "Пристеночный профиль 5-рельсовый",
        "RS2335.jpg",
        122,
        16,
        "Красится",
        system="СЛАЙД 5",
        purchase_price=450,
        weight=0.58,
        note="На схеме сверху добавляет 16 мм с выбранной стороны",
    ),
    "RS2081": ProfileCatalogItem(
        "RS2081",
        "Боковой П-образный профиль-замок",
        "RS2081.jpg",
        57,
        25,
        "Красится",
        paint_note="КРАСИТЬ ВЕСЬ ПЕРИМЕТР",
        purchase_price=510,
        markup_percent=38,
        weight=0.82,
        note="Используется при боковом замыкании, красить весь периметр",
    ),
    "RS1082": ProfileCatalogItem(
        "RS1082",
        "Боковой П-профиль",
        "RS1082.jpg",
        25,
        25,
        "Красится",
        purchase_price=260,
        weight=0.36,
        note="Боковой профиль без замка",
    ),
    "RS112": ProfileCatalogItem(
        "RS112",
        "Профиль-ручка",
        "RS112.jpg",
        52,
        40,
        "Красится",
        purchase_price=420,
        weight=0.74,
        note="Основная ручка для стандартного СЛАЙД",
    ),
    "RS2061": ProfileCatalogItem(
        "RS2061",
        "Межстекольный профиль",
        "RS2061.jpg",
        20,
        12,
        "Красится",
        purchase_price=210,
        weight=0.28,
        note="В схеме сверху зеркалится по направлению первой панели",
    ),
    "RS2021": ProfileCatalogItem(
        "RS2021",
        "Стекольный профиль",
        "RS2021.jpg",
        75,
        18,
        "Красится",
        purchase_price=190,
        weight=0.24,
        note="Длина считается отдельно по каждому стеклу",
    ),
    "RS1002": ProfileCatalogItem(
        "RS1002",
        "Пузырьковый уплотнитель",
        "RS1002.jpg",
        0,
        0,
        "Не красится",
        ("Без цвета",),
        group="Уплотнители",
        purchase_price=86,
        markup_percent=45,
        weight=0.09,
        waste_percent=8,
        supplier="Склад",
        note="Норма зависит от стороны установки",
    ),
    "RS205": ProfileCatalogItem(
        "RS205",
        "Защёлка в пол",
        "RS205.jpg",
        0,
        0,
        "Не красится",
        ("Без цвета",),
        group="Защёлки",
        unit="шт",
        purchase_price=185,
        markup_percent=40,
        weight=0.12,
        waste_percent=0,
        supplier="Фурнитура СПБ",
        note="Ставится слева/справа по настройкам секции",
    ),
    "DIN7504M": ProfileCatalogItem(
        "DIN7504M",
        "Саморез сверлоконечный",
        "DIN7504M.png",
        0,
        0,
        "Не красится",
        ("Без цвета",),
        group="Крепёж",
        system="Все",
        unit="шт",
        purchase_price=3.8,
        markup_percent=60,
        weight=0.004,
        waste_percent=3,
        supplier="Метизы",
        note="Формула количества будет уточняться отдельно",
    ),
}


def get_profile_catalog_item(article: str | None) -> ProfileCatalogItem | None:
    if not article:
        return None
    return PROFILE_CATALOG.get(article)


def apply_profile_catalog(profile) -> None:
    item = get_profile_catalog_item(getattr(profile, "article", ""))
    if not item:
        return
    profile.image = item.image
    profile.section_width_mm = item.section_width_mm
    profile.section_height_mm = item.section_height_mm
    profile.paint_mode = item.paint_mode
    profile.color_variants = list(item.color_variants)
    profile.paint_note = item.paint_note
