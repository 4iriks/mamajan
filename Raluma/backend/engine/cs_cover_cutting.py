"""Shared T40K stock cutting for individual sections and complete orders.

Lengths include the manufacturing allowance. A cut is never split by the
packer; long covers are explicitly jointed before packing. No prices live here.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
import re

STOCK_MM = 3000
ALLOWANCE_MM = 50
USEFUL_MM = STOCK_MM - ALLOWANCE_MM
MIN_TAIL_MM = 500
EPS = Decimal("0.000001")
INDIVIDUAL_COVER_NOTE = (
    "Т40К: расход на изделие рассчитан отдельно. Количество для заказа "
    "определяется совместным раскроем всех секций."
)


def _get(value, key, default=None):
    return (
        value.get(key, default)
        if isinstance(value, dict)
        else getattr(value, key, default)
    )


def cover_cuts(lengths):
    """Two covers per edge, with a 500 mm minimum only for a jointed tail."""
    cuts = []
    for edge, length in enumerate(lengths):
        for face in range(2):
            remaining = Decimal(str(length))
            part = 0
            while remaining > EPS:
                clean = min(remaining, Decimal(USEFUL_MM))
                blank = clean + ALLOWANCE_MM
                if part and remaining <= USEFUL_MM:
                    blank = max(blank, Decimal(MIN_TAIL_MM))
                cuts.append(
                    {
                        "edge": edge,
                        "face": face,
                        "part": part,
                        "clean_mm": float(clean),
                        "blank_mm": float(blank),
                    }
                )
                remaining -= clean
                part += 1
    return cuts


def pack_cuts(cuts):
    """Best fit decreasing, with stable ties and an explicit feasible layout."""
    stocks, remaining = [], []
    for cut in sorted(cuts, key=lambda c: -c["blank_mm"]):
        length = Decimal(str(cut["blank_mm"]))
        candidates = [
            (space - length, i)
            for i, space in enumerate(remaining)
            if space + EPS >= length
        ]
        if candidates:
            _, index = min(candidates)
            stocks[index].append(dict(cut))
            remaining[index] -= length
        else:
            if length > STOCK_MM + EPS:
                raise ValueError("Заготовка крышки длиннее 3000 мм")
            stocks.append([dict(cut)])
            remaining.append(Decimal(STOCK_MM) - length)
    return stocks


def finish_key(section):
    """Separate physical finishes; accept case/spacing and repeated RAL labels."""
    finish = str(_get(section, "painting_type", "") or "Анод/неокрас").casefold()
    ral = str(_get(section, "ral_color", "") or "").casefold()
    text = " ".join(re.findall(r"[\w]+", finish + " " + ral))
    if "анод" in finish or "неокрас" in finish:
        return "анод/неокрас"
    return " ".join(dict.fromkeys(text.split()))


def _allocate(stocks):
    # Integer micrometres of billed stock (1e-6 m) keep the sum exactly 3 m
    # per stick, including waste. Largest remainders avoid a rounding drift.
    totals = defaultdict(int)
    for cuts in stocks:
        lengths = defaultdict(Decimal)
        for cut in cuts:
            lengths[str(cut["section_index"])] += Decimal(str(cut["blank_mm"]))
        total = sum(lengths.values())
        exact = {
            key: Decimal(3_000_000) * value / total for key, value in lengths.items()
        }
        units = {
            key: int(value.to_integral_value(rounding=ROUND_FLOOR))
            for key, value in exact.items()
        }
        residual = 3_000_000 - sum(units.values())
        for key in sorted(
            exact, key=lambda key: (-(exact[key] - units[key]), int(key))
        )[:residual]:
            units[key] += 1
        for key, value in units.items():
            totals[key] += value
    return {
        key: str(Decimal(value) / 1_000_000) for key, value in sorted(totals.items())
    }


def build_cover_plan(entries):
    """Entries are (section, calculated CS result); indices identify their owners."""
    entries = list(entries)
    groups = {}
    for section_index, (section, calc) in enumerate(entries):
        profiles = _get(calc, "profiles", [])
        cover = next((row for row in profiles if _get(row, "role") == "cover"), None)
        if cover is None:
            continue
        cuts = _get(calc, "cover_cuts")
        if cuts is None:
            cuts = cover_cuts(_get(calc, "outer_edge_lengths_mm", []))
        cuts = [
            {
                key: _get(cut, key)
                for key in ("edge", "face", "part", "clean_mm", "blank_mm")
            }
            for cut in cuts
        ]
        key = (str(_get(cover, "article")), finish_key(section))
        group = groups.setdefault(
            key,
            {
                "article": _get(cover, "article"),
                "name": _get(cover, "name"),
                "image": _get(cover, "image", ""),
                "color": _get(calc, "color_text", ""),
                "finish_key": key[1],
                "requires_paint": _get(cover, "requires_paint", False),
                "stock_length_mm": STOCK_MM,
                "cuts": [],
                "individual_stocks": [],
            },
        )
        quantity = max(1, int(_get(section, "quantity", 1) or 1))
        for copy_index in range(quantity):
            owned = [
                {**cut, "section_index": section_index, "copy_index": copy_index}
                for cut in cuts
            ]
            group["cuts"].extend(owned)
            group["individual_stocks"].extend(pack_cuts(owned))
    for group in groups.values():
        stocks = pack_cuts(group.pop("cuts"))
        separate = group.pop("individual_stocks")
        if len(separate) < len(stocks):
            stocks = separate
        group.update(
            stocks=stocks,
            stock_count=len(stocks),
            total_length_mm=len(stocks) * STOCK_MM,
            allocations_m=_allocate(stocks),
        )
    return {
        "version": 1,
        "groups": list(groups.values()),
        "sections": [
            {
                "index": index,
                "id": _get(section, "id"),
                "name": _get(section, "name", ""),
                "quantity": max(1, int(_get(section, "quantity", 1) or 1)),
            }
            for index, (section, _) in enumerate(entries)
        ],
    }


def section_allocation_m(plan, index):
    return sum(
        (
            Decimal(group["allocations_m"].get(str(index), "0"))
            for group in plan["groups"]
        ),
        Decimal(0),
    )
