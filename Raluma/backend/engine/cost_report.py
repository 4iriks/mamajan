"""Internal cost, profit and margin report for a project quote revision."""

from __future__ import annotations

import io
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

import xlsxwriter
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

import models
from engine.pdf import TEMPLATES_DIR
from engine.quote_pricing import (
    QuoteExportBlocked,
    decimal_value,
    freeze_quote,
    get_or_create_quote_state,
    quote_is_stale,
    refresh_draft_quote,
)


MONEY = Decimal("0.01")
BLOCKING_COST_CODES = {
    "missing_price",
    "missing_finish_price",
    "unit_mismatch",
    "unsupported_section_pricing",
    "no_slide_sections",
}


def _money(value: object) -> Decimal:
    return decimal_value(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _display_money(value: object) -> str:
    number = _money(value)
    text = f"{number:,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} ₽"


def _display_percent(value: Decimal | None) -> str:
    if value is None:
        return "—"
    text = f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):f}"
    return f"{text.replace('.', ',')} %"


def _metrics(cost: Decimal, sale: Decimal, *, complete: bool) -> dict[str, Any]:
    if not complete or cost <= 0 or sale <= 0:
        return {
            "profit": None,
            "markup_percent": None,
            "margin_percent": None,
        }
    profit = _money(sale - cost)
    return {
        "profit": profit,
        "markup_percent": (profit / cost * Decimal("100")),
        "margin_percent": (profit / sale * Decimal("100")),
    }


def _decorate_metrics(row: dict[str, Any]) -> dict[str, Any]:
    metrics = _metrics(row["cost_total"], row["client_total"], complete=row["complete"])
    row.update(metrics)
    row.update(
        {
            "cost_text": _display_money(row["cost_total"]),
            "internal_text": _display_money(row["internal_total"]),
            "client_text": _display_money(row["client_total"]),
            "profit_text": _display_money(metrics["profit"]) if metrics["profit"] is not None else "—",
            "markup_text": _display_percent(metrics["markup_percent"]),
            "margin_text": _display_percent(metrics["margin_percent"]),
        }
    )
    return row


def _allocate(total: Decimal, weights: Iterable[Decimal]) -> list[Decimal]:
    normalized = [max(Decimal("0"), value) for value in weights]
    weight_total = sum(normalized, Decimal("0"))
    if not normalized:
        return []
    if weight_total <= 0:
        return [Decimal("0") for _ in normalized]
    allocated = [
        _money(total * weight / weight_total) for weight in normalized
    ]
    difference = _money(total - sum(allocated, Decimal("0")))
    target = next(
        (index for index in range(len(normalized) - 1, -1, -1) if normalized[index] > 0),
        len(normalized) - 1,
    )
    allocated[target] = _money(allocated[target] + difference)
    return allocated


def _issue_text(issue: dict[str, Any]) -> str:
    code = str(issue.get("code") or "")
    sku = str(issue.get("sku") or "").strip()
    name = str(issue.get("name") or "").strip()
    finish = str(issue.get("finish") or "").strip()
    labels = {
        "missing_price": "Нет себестоимости",
        "missing_finish_price": "Нет себестоимости исполнения",
        "unit_mismatch": "Не совпадает единица измерения",
        "unsupported_section_pricing": "Система пока не поддержана расчётом",
        "no_slide_sections": "Нет рассчитываемых позиций",
        "below_minimum_margin": "Цена ниже минимальной маржи",
    }
    detail = " — ".join(value for value in (sku, name, finish) if value)
    label = labels.get(code, code or "Предупреждение расчёта")
    return f"{label}: {detail}" if detail else label


def _snapshot(
    db: Session,
    project: models.Project,
    *,
    freeze_for_export: bool,
    actor: models.User | None,
) -> tuple[models.ProjectQuoteState, dict[str, Any], bool]:
    state = get_or_create_quote_state(db, project)
    if state.status != "fixed" or state.internal_payload in (None, "", "{}"):
        refresh_draft_quote(db, project, state)
        draft = _json_object(state.internal_payload)
        draft_public = draft.get("public") if isinstance(draft.get("public"), dict) else {}
        if freeze_for_export and actor is not None and draft_public.get("export_allowed"):
            try:
                freeze_quote(db, project, actor)
            except QuoteExportBlocked:
                # An incomplete report remains exportable with an explicit warning.
                pass
    internal = _json_object(state.internal_payload)
    stale = state.status == "fixed" and quote_is_stale(db, project, state)
    return state, internal, stale


def build_cost_report_context(
    db: Session,
    project: models.Project,
    *,
    freeze_for_export: bool = False,
    actor: models.User | None = None,
) -> dict[str, Any]:
    """Build a report from the persisted quote snapshot, never from public data alone."""

    state, internal, stale = _snapshot(
        db,
        project,
        freeze_for_export=freeze_for_export,
        actor=actor,
    )
    public = internal.get("public") if isinstance(internal.get("public"), dict) else {}
    public_lines = {
        str(row.get("id") or ""): row
        for row in public.get("lines") or []
        if isinstance(row, dict)
    }
    issues = [row for row in internal.get("issues") or [] if isinstance(row, dict)]
    issue_skus = {
        str(row.get("sku") or "").strip().upper()
        for row in issues
        if str(row.get("code") or "") in BLOCKING_COST_CODES
    }

    missing: list[dict[str, str]] = []
    sections: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []

    for section in internal.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_id = section.get("section_id")
        line = public_lines.get(f"section-{section_id}", {})
        client_total = _money(line.get("line_total") or section.get("final_price"))
        bom = [row for row in section.get("bom") or [] if isinstance(row, dict)]
        weights = [_money(row.get("internal_total")) for row in bom]
        allocated = _allocate(client_total, weights)
        rows: list[dict[str, Any]] = []
        for index, source in enumerate(bom):
            sku = str(source.get("sku") or "").strip()
            cost = _money(source.get("base_cost_total"))
            unit_cost = _money(source.get("cost"))
            complete = cost > 0 and sku.upper() not in issue_skus
            if not complete:
                missing.append(
                    {
                        "scope": str(section.get("name") or f"Секция {section_id}"),
                        "sku": sku,
                        "name": str(source.get("name") or sku or "Позиция"),
                        "reason": "Себестоимость не заполнена",
                    }
                )
            row = _decorate_metrics(
                {
                    "scope": str(section.get("name") or f"Секция {section_id}"),
                    "kind": "Конструкция",
                    "sku": sku,
                    "name": str(source.get("name") or sku),
                    "finish": str(source.get("finish") or ""),
                    "quantity": decimal_value(source.get("quantity")),
                    "unit": str(source.get("unit") or source.get("price_unit") or "шт"),
                    "unit_cost": unit_cost,
                    "cost_total": cost,
                    "internal_total": _money(source.get("internal_total")),
                    "client_total": allocated[index] if index < len(allocated) else Decimal("0"),
                    "complete": complete,
                }
            )
            rows.append(row)
            component_rows.append(row)
        section_complete = not section.get("issues") and all(row["complete"] for row in rows)
        cost_total = sum((row["cost_total"] for row in rows), Decimal("0"))
        section_summary = _decorate_metrics(
            {
                "cost_total": _money(cost_total),
                "internal_total": _money(section.get("internal_total")),
                "client_total": client_total,
                "complete": section_complete,
            }
        )
        sections.append(
            {
                "id": section_id,
                "name": str(section.get("name") or f"Секция {section_id}"),
                "rows": rows,
                "summary": section_summary,
            }
        )

    extras: list[dict[str, Any]] = []
    for source in internal.get("project_extras") or []:
        if not isinstance(source, dict):
            continue
        line_id = str(source.get("line_id") or f"project-extra-{source.get('index')}")
        line = public_lines.get(line_id, {})
        sku = str(source.get("sku") or "").strip()
        cost_total = _money(source.get("base_cost_total"))
        complete = cost_total > 0 and sku.upper() not in issue_skus
        if not complete:
            missing.append(
                {
                    "scope": "Доп. комплектующие",
                    "sku": sku,
                    "name": str(source.get("name") or sku or "Позиция"),
                    "reason": "Себестоимость не заполнена в зафиксированной редакции",
                }
            )
        row = _decorate_metrics(
            {
                "scope": "Доп. комплектующие",
                "kind": "Доп. комплектующее",
                "sku": sku,
                "name": str(source.get("name") or sku),
                "finish": str(source.get("finish") or ""),
                "quantity": decimal_value(source.get("quantity")),
                "unit": str(source.get("unit") or "шт"),
                "unit_cost": _money(source.get("cost")),
                "cost_total": cost_total,
                "internal_total": _money(source.get("internal_total")),
                "client_total": _money(line.get("line_total") or source.get("final_price")),
                "complete": complete,
            }
        )
        extras.append(row)
        component_rows.append(row)

    services: list[dict[str, Any]] = []
    for index, source in enumerate(internal.get("services") or [], start=1):
        if not isinstance(source, dict):
            continue
        line_id = str(source.get("id") or f"service-{index}")
        line = public_lines.get(line_id, {})
        quantity = decimal_value(source.get("quantity"))
        unit_cost = _money(source.get("base_cost"))
        cost_total = _money(unit_cost * quantity)
        complete = cost_total > 0
        if not complete:
            missing.append(
                {
                    "scope": "Услуги",
                    "sku": line_id,
                    "name": str(source.get("name") or "Услуга"),
                    "reason": "Себестоимость услуги не заполнена",
                }
            )
        services.append(
            _decorate_metrics(
                {
                    "scope": "Услуги",
                    "kind": "Услуга",
                    "sku": line_id,
                    "name": str(source.get("name") or "Услуга"),
                    "finish": "",
                    "quantity": quantity,
                    "unit": str(source.get("unit") or "услуга"),
                    "unit_cost": unit_cost,
                    "cost_total": cost_total,
                    "internal_total": _money(source.get("internal_total")),
                    "client_total": _money(line.get("line_total") or source.get("final_price")),
                    "complete": complete,
                }
            )
        )

    for issue in issues:
        if str(issue.get("code") or "") not in BLOCKING_COST_CODES:
            continue
        entry = {
            "scope": "Расчёт",
            "sku": str(issue.get("sku") or ""),
            "name": str(issue.get("name") or ""),
            "reason": _issue_text(issue),
        }
        if entry not in missing:
            missing.append(entry)

    all_rows = [*component_rows, *services]
    cost_total = _money(sum((row["cost_total"] for row in all_rows), Decimal("0")))
    internal_total = _money(sum((row["internal_total"] for row in all_rows), Decimal("0")))
    client_total = _money(
        (public.get("totals") or {}).get("grand_total")
        or sum((row["client_total"] for row in all_rows), Decimal("0"))
    )
    incomplete = bool(missing) or any(
        str(issue.get("code") or "") in BLOCKING_COST_CODES for issue in issues
    )
    summary = _decorate_metrics(
        {
            "cost_total": cost_total,
            "internal_total": internal_total,
            "client_total": client_total,
            "complete": not incomplete,
        }
    )
    project_snapshot = public.get("project") if isinstance(public.get("project"), dict) else {}
    warnings = [_issue_text(issue) for issue in issues]
    if stale:
        warnings.insert(
            0,
            "Проект или каталог изменён после фиксации: отчёт показывает сохранённую редакцию.",
        )
    if incomplete:
        warnings.insert(
            0,
            "Себестоимость заполнена не полностью. Прибыль, наценка и маржа по итогу не рассчитываются.",
        )
    report_project = {
        "id": project_snapshot.get("id") or project.id,
        "number": project_snapshot.get("number") or project.number,
        "invoice_number": project_snapshot.get("invoice_number")
        or project.invoice_number,
        "order_number": project_snapshot.get("order_number") or project.order_number,
        "customer": project_snapshot.get("customer") or project.customer,
    }
    project_number = str(
        report_project["invoice_number"]
        or report_project["order_number"]
        or report_project["number"]
        or "project"
    )
    return {
        "title": "Себестоимость и наценка",
        "project": report_project,
        "project_number": project_number,
        "revision": int(public.get("revision") or state.revision or 1),
        "status": str(public.get("status") or state.status or "draft"),
        "fixed_at": public.get("fixed_at"),
        "generated_at": datetime.utcnow().isoformat(),
        "stale": stale,
        "incomplete": incomplete,
        "warnings": list(dict.fromkeys(warnings)),
        "missing": missing,
        "sections": sections,
        "extras": extras,
        "services": services,
        "component_rows": component_rows,
        "summary": summary,
    }


def render_cost_report_html(context: dict[str, Any], *, is_pdf: bool = False) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template("cost_report.html")
    return template.render(**context, is_pdf=is_pdf)


def _xlsx_formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    return {
        "title": workbook.add_format(
            {"bold": True, "font_size": 18, "font_color": "#123B44", "align": "left"}
        ),
        "meta": workbook.add_format({"font_color": "#52666B", "font_size": 9}),
        "warning": workbook.add_format(
            {"font_color": "#9C2F1B", "bg_color": "#FDE8E2", "text_wrap": True, "valign": "vcenter"}
        ),
        "section": workbook.add_format(
            {"bold": True, "font_color": "#FFFFFF", "bg_color": "#164E59", "border": 1}
        ),
        "header": workbook.add_format(
            {"bold": True, "font_color": "#FFFFFF", "bg_color": "#0F766E", "border": 1, "text_wrap": True, "align": "center", "valign": "vcenter"}
        ),
        "text": workbook.add_format({"border": 1, "valign": "top", "text_wrap": True}),
        "center": workbook.add_format({"border": 1, "align": "center", "valign": "top"}),
        "number": workbook.add_format({"border": 1, "num_format": "0.###", "align": "right"}),
        "money": workbook.add_format({"border": 1, "num_format": '#,##0.00 [$₽-ru-RU]', "align": "right"}),
        "percent": workbook.add_format({"border": 1, "num_format": "0.00%", "align": "right"}),
        "missing": workbook.add_format(
            {"border": 1, "font_color": "#9C2F1B", "bg_color": "#FFF1ED", "text_wrap": True}
        ),
        "total_label": workbook.add_format(
            {"bold": True, "bg_color": "#DCEFF0", "border": 1, "align": "right"}
        ),
        "total_money": workbook.add_format(
            {"bold": True, "bg_color": "#DCEFF0", "border": 1, "num_format": '#,##0.00 [$₽-ru-RU]'}
        ),
        "total_percent": workbook.add_format(
            {"bold": True, "bg_color": "#DCEFF0", "border": 1, "num_format": "0.00%"}
        ),
    }


DETAIL_HEADERS = (
    "Раздел",
    "Артикул",
    "Наименование",
    "Исполнение",
    "Количество",
    "Ед.",
    "Себестоимость за ед.",
    "Себестоимость",
    "Внутренняя цена",
    "Цена клиенту",
    "Прибыль",
    "Наценка на себестоимость",
    "Маржа",
    "Статус",
)


def _write_detail_sheet(
    workbook: xlsxwriter.Workbook,
    formats: dict[str, Any],
    name: str,
    title: str,
    rows: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    sheet = workbook.add_worksheet(name)
    sheet.hide_gridlines(2)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_margins(0.3, 0.3, 0.45, 0.45)
    sheet.merge_range(0, 0, 0, len(DETAIL_HEADERS) - 1, title, formats["title"])
    sheet.merge_range(
        1,
        0,
        1,
        len(DETAIL_HEADERS) - 1,
        f"Счёт {context['project_number']} · редакция {context['revision']} · {context['project']['customer']}",
        formats["meta"],
    )
    row_index = 3
    if context["incomplete"]:
        sheet.merge_range(
            row_index,
            0,
            row_index,
            len(DETAIL_HEADERS) - 1,
            "ВНИМАНИЕ: себестоимость заполнена не полностью; показатели доходности по незаполненным строкам скрыты.",
            formats["warning"],
        )
        sheet.set_row(row_index, 32)
        row_index += 2
    header_row = row_index
    for column, header in enumerate(DETAIL_HEADERS):
        sheet.write(header_row, column, header, formats["header"])
    sheet.set_row(header_row, 34)
    for source in rows:
        row_index += 1
        style = formats["text"] if source["complete"] else formats["missing"]
        sheet.write(row_index, 0, source["scope"], style)
        sheet.write(row_index, 1, source["sku"], style)
        sheet.write(row_index, 2, source["name"], style)
        sheet.write(row_index, 3, source["finish"], style)
        sheet.write_number(row_index, 4, float(source["quantity"]), formats["number"])
        sheet.write(row_index, 5, source["unit"], formats["center"])
        sheet.write_number(row_index, 6, float(source["unit_cost"]), formats["money"])
        sheet.write_number(row_index, 7, float(source["cost_total"]), formats["money"])
        sheet.write_number(row_index, 8, float(source["internal_total"]), formats["money"])
        sheet.write_number(row_index, 9, float(source["client_total"]), formats["money"])
        excel_row = row_index + 1
        if source["complete"]:
            sheet.write_formula(
                row_index,
                10,
                f"=J{excel_row}-H{excel_row}",
                formats["money"],
                float(source["profit"]),
            )
            sheet.write_formula(
                row_index,
                11,
                f'=IFERROR(K{excel_row}/H{excel_row},"")',
                formats["percent"],
                float(source["markup_percent"] / Decimal("100")),
            )
            sheet.write_formula(
                row_index,
                12,
                f'=IFERROR(K{excel_row}/J{excel_row},"")',
                formats["percent"],
                float(source["margin_percent"] / Decimal("100")),
            )
        else:
            for column in (10, 11, 12):
                sheet.write_blank(row_index, column, None, formats["missing"])
        sheet.write(row_index, 13, "OK" if source["complete"] else "НЕТ СЕБЕСТОИМОСТИ", style)

    if not rows:
        row_index += 1
        sheet.merge_range(row_index, 0, row_index, 13, "Позиции отсутствуют", formats["text"])
    else:
        total_row = row_index + 1
        first_excel = header_row + 2
        last_excel = row_index + 1
        sheet.merge_range(total_row, 0, total_row, 6, "ИТОГО", formats["total_label"])
        for column in (7, 8, 9):
            letter = chr(ord("A") + column)
            value_key = {7: "cost_total", 8: "internal_total", 9: "client_total"}[column]
            total = sum((row[value_key] for row in rows), Decimal("0"))
            sheet.write_formula(
                total_row,
                column,
                f"=SUM({letter}{first_excel}:{letter}{last_excel})",
                formats["total_money"],
                float(total),
            )
        if all(row["complete"] for row in rows):
            cost = sum((row["cost_total"] for row in rows), Decimal("0"))
            sale = sum((row["client_total"] for row in rows), Decimal("0"))
            metrics = _metrics(cost, sale, complete=True)
            excel_total = total_row + 1
            sheet.write_formula(total_row, 10, f"=J{excel_total}-H{excel_total}", formats["total_money"], float(metrics["profit"]))
            sheet.write_formula(total_row, 11, f'=IFERROR(K{excel_total}/H{excel_total},"")', formats["total_percent"], float(metrics["markup_percent"] / Decimal("100")))
            sheet.write_formula(total_row, 12, f'=IFERROR(K{excel_total}/J{excel_total},"")', formats["total_percent"], float(metrics["margin_percent"] / Decimal("100")))
        else:
            for column in (10, 11, 12):
                sheet.write_blank(total_row, column, None, formats["total_label"])
        sheet.write(total_row, 13, "НЕПОЛНЫЕ ДАННЫЕ" if any(not row["complete"] for row in rows) else "OK", formats["total_label"])
        sheet.autofilter(header_row, 0, row_index, len(DETAIL_HEADERS) - 1)
    sheet.freeze_panes(header_row + 1, 0)
    widths = [20, 16, 34, 18, 12, 9, 18, 18, 18, 18, 18, 20, 14, 23]
    for column, width in enumerate(widths):
        sheet.set_column(column, column, width)
    sheet.repeat_rows(header_row)
    sheet.print_area(0, 0, max(row_index + 1, header_row + 1), len(DETAIL_HEADERS) - 1)


def build_cost_report_xlsx(context: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties(
        {
            "title": f"Себестоимость и наценка {context['project_number']}",
            "subject": "Внутренний отчёт по себестоимости, прибыли и марже",
            "author": "Ралюма",
        }
    )
    formats = _xlsx_formats(workbook)
    summary_sheet = workbook.add_worksheet("Сводка")
    summary_sheet.hide_gridlines(2)
    summary_sheet.set_column(0, 0, 30)
    summary_sheet.set_column(1, 2, 22)
    summary_sheet.merge_range(0, 0, 0, 2, context["title"], formats["title"])
    metadata = [
        ("Счёт / проект", context["project_number"]),
        ("Заказчик", context["project"]["customer"]),
        ("Редакция", context["revision"]),
        ("Статус", "Зафиксирована" if context["status"] == "fixed" else "Черновик"),
    ]
    row = 2
    for label, value in metadata:
        summary_sheet.write(row, 0, label, formats["meta"])
        summary_sheet.merge_range(row, 1, row, 2, value, formats["text"])
        row += 1
    if context["warnings"]:
        row += 1
        summary_sheet.merge_range(row, 0, row, 2, "\n".join(context["warnings"]), formats["warning"])
        summary_sheet.set_row(row, max(36, 18 * len(context["warnings"])))
        row += 2
    summary_header = row
    for column, value in enumerate(("Показатель", "Сумма", "Комментарий")):
        summary_sheet.write(row, column, value, formats["header"])
    summary_rows = [
        ("Себестоимость", context["summary"]["cost_total"], "Частичная" if context["incomplete"] else "Полная"),
        ("Внутренняя цена", context["summary"]["internal_total"], "После внутренних коэффициентов"),
        ("Цена клиенту", context["summary"]["client_total"], "После скидок"),
    ]
    for label, value, note in summary_rows:
        row += 1
        summary_sheet.write(row, 0, label, formats["text"])
        summary_sheet.write_number(row, 1, float(value), formats["money"])
        summary_sheet.write(row, 2, note, formats["text"])
    row += 1
    summary_sheet.write(row, 0, "Прибыль", formats["total_label"])
    if context["summary"]["profit"] is not None:
        summary_sheet.write_formula(row, 1, f"=B{row}-B{row - 2}", formats["total_money"], float(context["summary"]["profit"]))
        summary_sheet.write(row, 2, "Цена клиенту − себестоимость", formats["total_label"])
    else:
        summary_sheet.write_blank(row, 1, None, formats["total_money"])
        summary_sheet.write(row, 2, "Не рассчитывается: есть незаполненные позиции", formats["total_label"])
    for label, key, formula in (
        ("Наценка на себестоимость", "markup_percent", f'=IFERROR(B{row + 1}/B{row - 2},"")'),
        ("Маржа", "margin_percent", f'=IFERROR(B{row + 1}/B{row},"")'),
    ):
        row += 1
        summary_sheet.write(row, 0, label, formats["total_label"])
        value = context["summary"][key]
        if value is not None:
            summary_sheet.write_formula(row, 1, formula, formats["total_percent"], float(value / Decimal("100")))
        else:
            summary_sheet.write_blank(row, 1, None, formats["total_percent"])
        summary_sheet.write(row, 2, "" if value is not None else "Неполные данные", formats["total_label"])
    summary_sheet.freeze_panes(summary_header + 1, 0)
    summary_sheet.set_portrait()
    summary_sheet.fit_to_pages(1, 1)
    summary_sheet.print_area(0, 0, row, 2)

    _write_detail_sheet(
        workbook,
        formats,
        "Комплектующие",
        "Конструкции и комплектующие",
        context["component_rows"],
        context,
    )
    _write_detail_sheet(
        workbook,
        formats,
        "Услуги",
        "Услуги",
        context["services"],
        context,
    )
    missing_sheet = workbook.add_worksheet("Незаполненные")
    missing_sheet.hide_gridlines(2)
    missing_sheet.set_landscape()
    missing_sheet.fit_to_pages(1, 1)
    missing_sheet.set_margins(0.35, 0.35, 0.45, 0.45)
    missing_sheet.merge_range(0, 0, 0, 3, "Незаполненные и проблемные позиции", formats["title"])
    for column, label in enumerate(("Раздел", "Артикул", "Наименование", "Причина")):
        missing_sheet.write(2, column, label, formats["header"])
    for index, item in enumerate(context["missing"], start=3):
        for column, key in enumerate(("scope", "sku", "name", "reason")):
            missing_sheet.write(index, column, item.get(key, ""), formats["missing"])
    if not context["missing"]:
        missing_sheet.merge_range(3, 0, 3, 3, "Все используемые позиции имеют себестоимость", formats["text"])
    missing_sheet.set_column(0, 0, 24)
    missing_sheet.set_column(1, 1, 18)
    missing_sheet.set_column(2, 2, 38)
    missing_sheet.set_column(3, 3, 55)
    missing_sheet.freeze_panes(3, 0)
    missing_sheet.repeat_rows(2)
    missing_sheet.print_area(0, 0, max(3, len(context["missing"]) + 2), 3)
    workbook.close()
    return output.getvalue()


def cost_report_filename(context: dict[str, Any], extension: str) -> str:
    number = str(context.get("project_number") or "project")
    revision = int(context.get("revision") or 1)
    return f"Себестоимость_и_наценка_{number}_ред_{revision}.{extension}"
