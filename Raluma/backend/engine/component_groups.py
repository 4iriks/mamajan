"""Document-only grouping. Never rewrite source rows or their prices."""
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


def group_extra_sources(rows):
    if not isinstance(rows, list):
        return []
    groups = OrderedDict()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = (
            row.get("catalogItemId") or row.get("catalog_item_id"),
            row.get("sku") or row.get("article") or row.get("art"), row.get("name"), row.get("category"),
            row.get("finishVariantId") or row.get("finish_variant_id"),
            row.get("finishName") or row.get("finish_name"), row.get("color"),
            row.get("requiresPaint", row.get("requires_paint")),
            row.get("unit") or "шт", row.get("deliveryStage") or row.get("delivery_stage") or "both",
            row.get("imageFile") or row.get("image_file"), row.get("imageData") or row.get("image_data"),
        )
        key = sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        size = str(row.get("size") or "").strip()
        try:
            size_key = str(Decimal(size.replace(",", ".").removesuffix("мм").strip()).normalize())
        except InvalidOperation:
            size_key = size
        sizes = groups.setdefault(key, OrderedDict())
        try:
            qty = Decimal(str(row.get("qty") or row.get("quantity") or 0).replace(",", "."))
            if not qty.is_finite() or qty <= 0:
                continue
        except InvalidOperation:
            continue
        if size_key not in sizes:
            sizes[size_key] = {**row, "qty": 0, "_view_group": key}
        sizes[size_key]["qty"] += float(qty)
    return [row for sizes in groups.values() for row in sizes.values()]


def group_display_rows(rows):
    groups = OrderedDict()
    for row in rows:
        key = row.get("_view_group") or tuple(str(row.get(k) or "") for k in ("article", "name", "color", "unit", "stage", "image"))
        groups.setdefault(key, []).append(dict(row))
    result = []
    for group in groups.values():
        for index, row in enumerate(group):
            row.update(group_start=index == 0, group_span=len(group))
            result.append(row)
    return result


def display_groups(rows):
    """Keep document groups separate so their headings can repeat on page breaks."""
    result = []
    for row in group_display_rows(rows):
        if row["group_start"]:
            result.append([])
        result[-1].append(row)
    return result
