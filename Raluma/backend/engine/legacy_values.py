"""Нормализация старых строковых значений секций.

Используется для сохраненных секций и шаблонов, чтобы UI не получал старые
варианты, которые уже убраны из списков выбора.
"""

from typing import Any


def handle_supports_offset(value: Any) -> bool:
    """Отступ применяется только к стеклянной ручке и ручке-скобе."""
    handle = str(value or "").strip().lower()
    return "rs3017" in handle or "стеклян" in handle or "скоб" in handle


def normalize_handle_offset(handle: Any, offset: Any) -> int | None:
    """Игнорировать сохранённый отступ, если выбранная ручка его не использует."""
    if not handle_supports_offset(handle):
        return None
    if offset in (None, ""):
        return None
    try:
        return max(0, int(float(offset)))
    except (TypeError, ValueError):
        return None


def center_handle_supports_offset(value: Any) -> bool:
    """Совместимый alias для старого имени проверки центральной ручки."""
    return handle_supports_offset(value)


def normalize_center_handle_offset(handle: Any, offset: Any) -> int | None:
    """Нормализовать сохраненный отступ C с учетом выбранной ручки."""
    return normalize_handle_offset(handle, offset)


_LEGACY_VALUE_REPLACEMENTS: dict[str, dict[str, str]] = {
    "inter_glass_profile": {
        "h-профиль RS1004": "Профиль с зацепом RS3061",
    },
    "lock_left": {
        "1-сторонний RS3018": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
        "ЗАМОК-ЗАЩЕЛКА 1стор": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
        "2-сторонний с ключом RS3019": "ЗАМОК двухсторонний с ключом RS3020",
        "ЗАМОК-ЗАЩЕЛКА 2стор с ключом": "ЗАМОК двухсторонний с ключом RS3020",
    },
    "lock_right": {
        "1-сторонний RS3018": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
        "ЗАМОК-ЗАЩЕЛКА 1стор": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
        "2-сторонний с ключом RS3019": "ЗАМОК двухсторонний с ключом RS3020",
        "ЗАМОК-ЗАЩЕЛКА 2стор с ключом": "ЗАМОК двухсторонний с ключом RS3020",
    },
    "lock": {
        "RS3019 С ключом": "ЗАМОК двухсторонний с ключом RS3020",
        "ЗАМОК-ЗАЩЕЛКА 2стор с ключом": "ЗАМОК двухсторонний с ключом RS3020",
    },
    "handle_left": {
        "Стеклянная ручка": "Стеклянная ручка RS3017",
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
    "handle_right": {
        "Стеклянная ручка": "Стеклянная ручка RS3017",
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
    "center_handle": {
        "Стеклянная ручка": "Стеклянная ручка RS3017",
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
    "handle": {
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
}


def normalize_section_data_values(data: dict[str, Any]) -> dict[str, Any]:
    """Вернуть копию данных секции с актуальными строковыми значениями."""
    normalized = dict(data or {})
    for field, replacements in _LEGACY_VALUE_REPLACEMENTS.items():
        value = normalized.get(field)
        if isinstance(value, str) and value in replacements:
            normalized[field] = replacements[value]
    if "center_handle_offset" in normalized:
        normalized["center_handle_offset"] = normalize_center_handle_offset(
            normalized.get("center_handle"),
            normalized.get("center_handle_offset"),
        )
    for side in ("left", "right"):
        offset_field = f"handle_offset_{side}"
        if offset_field in normalized:
            normalized[offset_field] = normalize_handle_offset(
                normalized.get(f"handle_{side}"),
                normalized.get(offset_field),
            )
    if str(normalized.get("system") or "").strip().upper() == "КНИЖКА":
        _populate_book_compatibility_fields(normalized)
    return normalized


def _book_door_layout(data: dict[str, Any]) -> str:
    raw = str(data.get("door_side") or "").strip().lower().replace("ё", "е")
    try:
        doors = int(data.get("doors") or 0)
    except (TypeError, ValueError):
        doors = 0
    if doors >= 2 or raw in {
        "both",
        "обе",
        "оба",
        "левая и правая",
        "слева и справа",
    }:
        return "both"
    if raw in {"left", "левая", "лев", "слева"}:
        return "left"
    if raw in {"right", "правая", "прав", "справа"}:
        return "right"
    return "none"


def _book_hardware(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "lock" if "зам" in text or "тип 4" in text else "handle"


def _book_opening(value: Any) -> str:
    text = " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("ё", "е")
        .replace("/", " ")
        .replace("_", " ")
        .split()
    )
    return {
        "изнутри внутрь": "inside_in",
        "изнутри наружу": "inside_out",
        "снаружи наружу": "outside_out",
        "снаружи внутрь": "outside_in",
        "наружу": "inside_out",
        "внутрь": "inside_in",
    }.get(text, "inside_in")


def _populate_book_compatibility_fields(data: dict[str, Any]) -> None:
    """Дополнить старые поля КНИЖКИ новой структурой, не удаляя оригиналы."""
    raw_system = str(data.get("book_system") or "").strip().upper().replace("Ё", "Е")
    data["book_system"] = {
        "": "B25",
        "В25": "B25",
        "В16": "B16",
        "В17": "B17",
        "С16": "C16",
        "С17": "C17",
        "С КАРЕТКОЙ": "B25",
        "БЕЗ КАРЕТКИ": "B25",
    }.get(raw_system, raw_system)
    layout = _book_door_layout(data)
    legacy_hardware = _book_hardware(data.get("door_type"))
    legacy_opening = _book_opening(data.get("door_opening"))
    if layout in {"left", "both"}:
        if not data.get("book_left_door_hardware"):
            data["book_left_door_hardware"] = legacy_hardware
        if not data.get("book_left_door_opening"):
            data["book_left_door_opening"] = legacy_opening
    if layout in {"right", "both"}:
        if not data.get("book_right_door_hardware"):
            data["book_right_door_hardware"] = legacy_hardware
        if not data.get("book_right_door_opening"):
            data["book_right_door_opening"] = legacy_opening
