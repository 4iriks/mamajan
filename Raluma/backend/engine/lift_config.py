LIFT_DEFAULT_FILLING = "СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
LIFT_CUSTOM_FILLINGS = frozenset({"ДРУГОЕ 8мм", "ДРУГОЕ 20мм"})
LIFT_FILLING_OPTIONS = frozenset(
    {
        LIFT_DEFAULT_FILLING,
        "СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ",
        "СТЕКЛО 8мм ЗАКАЛЕННОЕ БРОНЗА В МАССЕ",
        "СТЕКЛО 8мм ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ",
        "СТЕКЛО 8мм ЗАКАЛЕННОЕ МАТОВОЕ",
        "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        *LIFT_CUSTOM_FILLINGS,
    }
)
LIFT_CONTROL_TYPES = frozenset({"Пульт ДУ", "Кнопка"})
LIFT_CABLE_SIDES = frozenset({"Слева", "Справа"})
LIFT_SPLIT_OPENING = "Верх/низ глухие, сдвиг вниз"
LIFT_OPENING_TYPES = frozenset({"Сдвиг вниз", "Сдвиг вверх", LIFT_SPLIT_OPENING})


def lift_filling_text(section: object) -> str:
    filling_type = str(
        getattr(section, "lift_filling_type", "") or LIFT_DEFAULT_FILLING
    ).strip()
    if filling_type in LIFT_CUSTOM_FILLINGS:
        custom = str(getattr(section, "lift_filling_custom", "") or "").strip()
        if custom:
            return custom
    return filling_type
