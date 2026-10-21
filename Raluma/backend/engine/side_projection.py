"""Visible SLIDE assembly faces (Oct 12 drawing); never glass deductions."""

import json
from pathlib import Path

_RULES = json.loads(
    Path(__file__).with_name("slide_side_segments.json").read_text(encoding="utf-8")
)


def side_segments(section):
    result = {}
    for side in ("left", "right"):

        def selected(role):
            return bool(getattr(section, f"profile_{side}_{role}", False))

        offset = 0
        rows = []
        for rule in _RULES:
            if not selected(rule["flag"]) or any(
                selected(flag) for flag in rule.get("unless", [])
            ):
                continue
            width = (
                rule.get("with_handle_mm", rule["width_mm"])
                if selected("handle_bar")
                else rule["width_mm"]
            )
            rows.append({"role": rule["role"], "width_mm": width, "offset_mm": offset})
            offset += width
        result[side] = rows
    return result


def side_projection(section, calc=None):
    return {
        side: sum(row["width_mm"] for row in rows)
        for side, rows in side_segments(section).items()
    }


def snapshot_side_segments(details):
    saved = details.get("side_projection_segments")
    if isinstance(saved, dict):
        return saved
    return {
        side: [{"role": "legacy", "offset_mm": 0, "width_mm": width}] if width else []
        for side, width in snapshot_side_projection(details).items()
    }


def snapshot_side_projection(details):
    if isinstance(details.get("side_projection_segments"), dict):
        return {
            side: sum(
                row["width_mm"]
                for row in details["side_projection_segments"].get(side, [])
            )
            for side in ("left", "right")
        }
    saved = details.get("side_projection_mm")
    if isinstance(saved, dict):
        return {side: max(0, float(saved.get(side, 0))) for side in ("left", "right")}
    # Old immutable quotes have only the selected articles. Never consult the
    # live catalogue when rendering them.
    result = {}
    for side in ("left", "right"):
        articles = {
            row.get("article")
            for row in details.get(f"technical_{side}", [])
            if isinstance(row, dict)
        }
        result[side] = (16 if articles & {"RS2333", "RS2335"} else 0) + max(
            57 if "RS2081" in articles else 0,
            25 if "RS1082" in articles else 0,
            40 if "RS112" in articles else 0,
        )
    return result
