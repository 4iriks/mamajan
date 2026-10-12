"""Front elevation of selected SLIDE side assemblies, in millimetres.

Wall backing and the largest overlapping face of the side assembly are shown;
overlapping lock/P/handle faces must not be added twice. No glass deduction is
derived from this visual description.
"""


def side_projection(section, calc=None):
    def dimension(article, axis, fallback):
        for profile in getattr(calc, "profiles", []) or []:
            if getattr(profile, "article", "") == article:
                value = getattr(profile, axis, None)
                if value and float(value) > 0:
                    return float(value)
        return fallback

    wall_article = "RS2335" if getattr(section, "rails", 3) == 5 else "RS2333"
    result = {}
    for side in ("left", "right"):
        def selected(role):
            return bool(getattr(section, f"profile_{side}_{role}", False))
        wall = dimension(wall_article, "section_height_mm", 16) if selected("wall") else 0
        face = max(
            dimension("RS2081", "section_width_mm", 57) if selected("lock_bar") else 0,
            dimension("RS1082", "section_width_mm", 25) if selected("p_bar") else 0,
            dimension("RS112", "section_height_mm", 40) if selected("handle_bar") else 0,
        )
        result[side] = wall + face
    return result


def snapshot_side_projection(details):
    saved = details.get("side_projection_mm")
    if isinstance(saved, dict):
        return {side: max(0, float(saved.get(side, 0))) for side in ("left", "right")}
    # Old immutable quotes have only the selected articles. Never consult the
    # live catalogue when rendering them.
    result = {}
    for side in ("left", "right"):
        articles = {row.get("article") for row in details.get(f"technical_{side}", []) if isinstance(row, dict)}
        result[side] = (16 if articles & {"RS2333", "RS2335"} else 0) + max(
            57 if "RS2081" in articles else 0, 25 if "RS1082" in articles else 0, 40 if "RS112" in articles else 0)
    return result
