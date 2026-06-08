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


PROFILE_CATALOG: dict[str, ProfileCatalogItem] = {
    "RS1313": ProfileCatalogItem(
        "RS1313", "Верхний направляющий профиль 3-рельсовый", "RS1313.png", 72, 53, "Красится"
    ),
    "RS1315": ProfileCatalogItem(
        "RS1315", "Верхний направляющий профиль 5-рельсовый", "RS1315.png", 119, 53, "Красится"
    ),
    "RS2323": ProfileCatalogItem(
        "RS2323", "Порог 3-рельсовый", "RS2323.jpg", 76, 23, "Частично", paint_note="НЕ КРАСИТЬ!!!"
    ),
    "RS2325": ProfileCatalogItem(
        "RS2325", "Порог 5-рельсовый", "RS1325.jpg", 122, 23, "Красится"
    ),
    "RS23231": ProfileCatalogItem(
        "RS23231", "Накладной порог 3-рельсовый", "RS2323.jpg", 76, 11, "Красится"
    ),
    "RS23251": ProfileCatalogItem(
        "RS23251", "Накладной порог 5-рельсовый", "RS1325.jpg", 122, 11, "Красится"
    ),
    "RS2333": ProfileCatalogItem(
        "RS2333", "Пристеночный профиль 3-рельсовый", "RS2333.jpg", 76, 16, "Красится"
    ),
    "RS2335": ProfileCatalogItem(
        "RS2335", "Пристеночный профиль 5-рельсовый", "RS2335.jpg", 122, 16, "Красится"
    ),
    "RS2081": ProfileCatalogItem(
        "RS2081", "Боковой П-образный профиль-замок", "RS2081.jpg", 57, 25, "Красится", paint_note="КРАСИТЬ ВЕСЬ ПЕРИМЕТР"
    ),
    "RS1082": ProfileCatalogItem(
        "RS1082", "Боковой П-профиль", "RS1082.jpg", 25, 25, "Красится"
    ),
    "RS112": ProfileCatalogItem(
        "RS112", "Профиль-ручка", "RS112.jpg", 52, 40, "Красится"
    ),
    "RS2061": ProfileCatalogItem(
        "RS2061", "Межстекольный профиль", "RS2061.jpg", 20, 12, "Красится"
    ),
    "RS2021": ProfileCatalogItem(
        "RS2021", "Стекольный профиль", "RS2021.jpg", 75, 18, "Красится"
    ),
    "RS1002": ProfileCatalogItem(
        "RS1002", "Пузырьковый уплотнитель", "RS1002.jpg", 0, 0, "Не красится", ("Без цвета",)
    ),
    "RS205": ProfileCatalogItem(
        "RS205", "Защёлка в пол", "RS205.jpg", 0, 0, "Не красится", ("Без цвета",)
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
