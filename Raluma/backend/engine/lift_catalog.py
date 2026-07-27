"""Catalog seed data owned by the LIFT system.

The main catalog imports these specifications at the boundary. Keeping the
data here prevents LIFT additions from being mixed into the SLIDE catalog
definitions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiftCatalogSpec:
    article: str
    name: str
    image: str
    group: str
    unit: str = "шт"
    paint_mode: str = "Не красится"
    color_variants: tuple[str, ...] = ("Без цвета",)
    note: str = ""


def _profile(
    article: str,
    name: str,
    *,
    painted: bool = True,
    note: str = "Длина и количество рассчитываются по формулам системы ЛИФТ",
) -> LiftCatalogSpec:
    return LiftCatalogSpec(
        article=article,
        name=name,
        image=f"{article}.png",
        group="Профили",
        unit="м.п.",
        paint_mode="Красится" if painted else "Не красится",
        color_variants=(
            ("Анод", "RAL стандарт", "RAL нестандарт")
            if painted
            else ("Без цвета",)
        ),
        note=note,
    )


def _hardware(
    article: str,
    name: str,
    *,
    image: str | None = None,
    unit: str = "шт",
    group: str = "Фурнитура",
) -> LiftCatalogSpec:
    return LiftCatalogSpec(
        article=article,
        name=name,
        image=image or f"{article}.png",
        group=group,
        unit=unit,
        note="Количество рассчитывается по формулам системы ЛИФТ",
    )


LIFT_CATALOG_SPECS = (
    _profile("RL101-1", "Крышка верхнего короба"),
    _profile("RL101", "Верхний короб"),
    _profile("RL102", "Боковой профиль рамы"),
    _profile("RL103", "Боковой профиль рамы"),
    _profile("RL103-1", "Боковой профиль рамы"),
    _profile("RL103-2", "Боковой профиль рамы"),
    _profile("RL104", "Нижний профиль рамы", painted=False),
    _profile("RL105", "Вертикальный профиль панели"),
    _profile("RL112", "Профиль панели под стекло 8 мм"),
    _profile("RL113", "Профиль панели под стекло 8 мм"),
    _profile("RL114", "Профиль панели под стекло 8 мм"),
    _profile("RL115", "Профиль панели под стекло 8 мм"),
    _profile("RL1211", "Профиль панели под стеклопакет 20 мм"),
    _profile("RL122", "Профиль панели под стеклопакет 20 мм"),
    _profile("RL123", "Профиль панели под стеклопакет 20 мм"),
    _profile("RL1241", "Профиль панели под стеклопакет 20 мм"),
    _hardware("RL001", "Угловой соединитель панели 8 мм"),
    _hardware("RL011", "Угловой соединитель панели 20 мм"),
    _hardware("RL002", "Заглушка панели"),
    _hardware("RL005", "Успокоитель цепи"),
    _hardware("RL201", "Угловой соединитель рамы"),
    _hardware("RL203", "Заглушка вала"),
    _hardware("RL204", "Вал привода"),
    _hardware("RL206", "Шестерня под цепь"),
    _hardware("RL207", "Подшипник"),
    _hardware("RL2085", "Привод с радиосвязью"),
    _hardware("RL2095", "Привод фазный"),
    _hardware("RL2087", "Пульт 1-канальный"),
    _hardware("RL2088", "Пульт 6-канальный"),
    _hardware("RL20901", "Боковая крышка короба под подшипник левая"),
    _hardware("RL20902", "Боковая крышка короба под мотор правая"),
    _hardware("RL20903", "Боковая крышка короба под подшипник правая"),
    _hardware("RL20904", "Боковая крышка короба под мотор левая"),
    _hardware("RL2092", "Кнопка"),
    _hardware("RL2096", "Комплект переходников для привода"),
    _hardware("RL2097", "Крепление для привода"),
    _hardware("RL2098", "Блок синхронизации приводов"),
    _hardware("RL210", "Цепь", unit="м.п."),
)
