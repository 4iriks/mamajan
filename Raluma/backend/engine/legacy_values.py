"""Нормализация старых строковых значений секций.

Используется для сохраненных секций и шаблонов, чтобы UI не получал старые
варианты, которые уже убраны из списков выбора.
"""

from typing import Any


def center_handle_supports_offset(value: Any) -> bool:
    """Отступ C применяется только к стеклянной ручке и ручке-скобе."""
    handle = str(value or "").strip().lower()
    return "rs3017" in handle or "ручка-скоба" in handle


def normalize_center_handle_offset(handle: Any, offset: Any) -> int | None:
    """Нормализовать сохраненный отступ C с учетом выбранной ручки."""
    if not center_handle_supports_offset(handle):
        return None
    if offset in (None, ""):
        return None
    try:
        return max(0, int(float(offset)))
    except (TypeError, ValueError):
        return None


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
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
    "handle_right": {
        "Ручка-скоба": "Ручка-скоба 600мм RS30201",
    },
    "center_handle": {
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
    return normalized
