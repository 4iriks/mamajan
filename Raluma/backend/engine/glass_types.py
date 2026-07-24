SLIDE_DEFAULT_GLASS_TYPE = "10ММ ПРОЗРАЧНОЕ"
NON_SLIDE_DEFAULT_GLASS_TYPE = "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"


def default_glass_type(system: str | None) -> str:
    return (
        SLIDE_DEFAULT_GLASS_TYPE
        if (system or "").strip().upper() == "СЛАЙД"
        else NON_SLIDE_DEFAULT_GLASS_TYPE
    )
