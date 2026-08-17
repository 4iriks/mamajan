"""Editable Excel exports for production sheets and project documents."""

from __future__ import annotations

import io
import re
from typing import Any, Iterable

import xlsxwriter
from PIL import Image

from engine.office_common import (
    BRAND_DARK,
    BRAND_LIGHT,
    HEADER_GRAY,
    RED,
    WHITE,
    drawing_image_streams_for_sections,
    format_dimension,
    format_number,
    image_stream,
    load_overrides,
    override_value,
)
from engine.office_diagrams import section_diagrams
from engine.office_docx import CHECKLIST_ROWS
from engine.office_section_data import hardware_rows, profile_rows, section_summary_rows
from engine.project_documents import build_project_document_context


def _formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    border = {"border": 1, "border_color": "#4D565B"}
    return {
        "title": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 16,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "shrink": True,
                **border,
            }
        ),
        "title_compact": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 13,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "shrink": True,
                **border,
            }
        ),
        "header": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 9,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "bar": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "bold": True,
                "font_color": f"#{WHITE}",
                "bg_color": f"#{BRAND_DARK}",
                "align": "left",
                "valign": "vcenter",
                **border,
            }
        ),
        "label": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "bold": True,
                "bg_color": f"#{HEADER_GRAY}",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "cell": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "cell_bottom": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 7,
                "align": "center",
                "valign": "bottom",
                "text_wrap": True,
                **border,
            }
        ),
        "center": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "center_bold": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "note": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "italic": True,
                "font_color": "#5F696E",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "red": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 11,
                "bold": True,
                "font_color": f"#{RED}",
                "text_wrap": True,
            }
        ),
        "red_text": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "bold": True,
                "font_color": f"#{RED}",
            }
        ),
        "red_center": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 9,
                "bold": True,
                "font_color": f"#{RED}",
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "soft": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8,
                "bg_color": f"#{BRAND_LIGHT}",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "total": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 9,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                **border,
            }
        ),
        "card": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 7,
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "card_heading": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 7.3,
                "bold": True,
                "font_color": "#162D37",
            }
        ),
        "card_heading_cell": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 7.3,
                "bold": True,
                "font_color": "#162D37",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
        "card_quantity": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8.4,
                "bold": True,
                "font_color": "#000000",
            }
        ),
        "card_note": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 7,
                "italic": True,
                "font_color": "#5F696E",
            }
        ),
        "card_quantity_cell": workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 8.4,
                "bold": True,
                "align": "right",
                "valign": "vcenter",
                "text_wrap": True,
                **border,
            }
        ),
    }


def _setup_sheet(
    worksheet: xlsxwriter.worksheet.Worksheet,
    *,
    landscape: bool = True,
    paper: int = 9,
) -> None:
    worksheet.hide_gridlines(2)
    worksheet.set_paper(paper)
    if landscape:
        worksheet.set_landscape()
    else:
        worksheet.set_portrait()
    worksheet.fit_to_pages(1, 1)
    worksheet.center_horizontally()
    worksheet.set_margins(0.25, 0.25, 0.35, 0.35)
    worksheet.set_header("&C&10&BRALUMA")
    worksheet.set_footer("&L&P / &N&C&D&R&T")
    worksheet.freeze_panes(2, 0)


def _section_sheet_columns(worksheet: xlsxwriter.worksheet.Worksheet) -> None:
    widths = (9, 11, 11, 11, 9, 11, 11, 11, 9, 11, 11, 11)
    for index, width in enumerate(widths):
        worksheet.set_column(index, index, width)


def _write_section_header(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    project: object,
    section: object,
    label: str,
) -> int:
    worksheet.set_row(0, 24)
    worksheet.merge_range(
        0,
        0,
        1,
        3,
        f"ПРОЕКТ № {getattr(project, 'number', '')}",
        formats["title"],
    )
    worksheet.merge_range(
        0,
        4,
        1,
        7,
        str(getattr(section, "name", "") or "Секция"),
        formats["title"],
    )
    worksheet.merge_range(0, 8, 1, 11, label, formats["title_compact"])
    return 2


def _write_bar(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    title: str,
    *,
    last_col: int = 11,
) -> int:
    worksheet.merge_range(row, 0, row, last_col, title.upper(), formats["bar"])
    worksheet.set_row(row, 18)
    return row + 1


def _write_summary(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    section: object,
    calc: object,
) -> int:
    rows = section_summary_rows(section, calc)
    for index, (label, value) in enumerate(rows):
        line = row + index // 2
        start = 0 if index % 2 == 0 else 6
        worksheet.merge_range(line, start, line, start + 1, label, formats["label"])
        worksheet.merge_range(line, start + 2, line, start + 5, value, formats["cell"])
        worksheet.set_row(line, 20)
    return row + (len(rows) + 1) // 2


def _stream_scale(
    stream: io.BytesIO,
    max_width_px: int,
    max_height_px: int,
    *,
    allow_enlarge: bool = True,
) -> float:
    stream.seek(0)
    with Image.open(stream) as image:
        width, height = image.size
    stream.seek(0)
    if not width or not height:
        return 1
    scale = min(max_width_px / width, max_height_px / height)
    if not allow_enlarge:
        scale = min(scale, 1)
    return max(0.05, scale)


def _insert_image(
    worksheet: xlsxwriter.worksheet.Worksheet,
    row: int,
    column: int,
    stream: io.BytesIO | None,
    *,
    max_width_px: int,
    max_height_px: int,
    x_offset: int = 4,
    y_offset: int = 4,
    allow_enlarge: bool = True,
) -> None:
    if stream is None:
        return
    scale = _stream_scale(
        stream,
        max_width_px,
        max_height_px,
        allow_enlarge=allow_enlarge,
    )
    worksheet.insert_image(
        row,
        column,
        "image.png",
        {
            "image_data": stream,
            "x_scale": scale,
            "y_scale": scale,
            "x_offset": x_offset,
            "y_offset": y_offset,
            "object_position": 1,
            "description": "Изображение детали",
        },
    )


def _write_diagrams(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    section: object,
    calc: object,
) -> int:
    diagrams = section_diagrams(section, calc)
    system = str(getattr(section, "system", "") or "").strip().upper()

    if system == "СЛАЙД":
        for index, (title, data) in enumerate(diagrams[:2]):
            line = row + index * 10
            worksheet.merge_range(line, 0, line, 11, title.upper(), formats["header"])
            worksheet.merge_range(line + 1, 0, line + 9, 11, "", formats["cell"])
            for diagram_row in range(line + 1, line + 10):
                worksheet.set_row(diagram_row, 16)
            _insert_image(
                worksheet,
                line + 1,
                0,
                io.BytesIO(data),
                max_width_px=790,
                max_height_px=175,
                x_offset=8,
                y_offset=4,
            )
        return row + min(len(diagrams), 2) * 10

    for index, (title, data) in enumerate(diagrams[:2]):
        start_col = index * 6
        line = row
        worksheet.merge_range(
            line, start_col, line, start_col + 5, title.upper(), formats["header"]
        )
        worksheet.merge_range(
            line + 1,
            start_col,
            line + 11,
            start_col + 5,
            "",
            formats["cell"],
        )
        for diagram_row in range(line + 1, line + 12):
            worksheet.set_row(diagram_row, 16)
        _insert_image(
            worksheet,
            line + 1,
            start_col,
            io.BytesIO(data),
            max_width_px=385,
            max_height_px=185,
            x_offset=6,
            y_offset=4,
        )

    next_row = row + 12
    if len(diagrams) > 2:
        title, data = diagrams[2]
        worksheet.merge_range(
            next_row, 0, next_row, 11, title.upper(), formats["header"]
        )
        worksheet.merge_range(next_row + 1, 0, next_row + 10, 11, "", formats["cell"])
        for diagram_row in range(next_row + 1, next_row + 11):
            worksheet.set_row(diagram_row, 16)
        _insert_image(
            worksheet,
            next_row + 1,
            0,
            io.BytesIO(data),
            max_width_px=790,
            max_height_px=165,
            x_offset=8,
            y_offset=4,
        )
        next_row += 11
    return next_row


def _write_headers(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    headers: tuple[str, ...],
    spans: tuple[tuple[int, int], ...],
) -> int:
    for header, (first, last) in zip(headers, spans, strict=True):
        if first == last:
            worksheet.write(row, first, header, formats["header"])
        else:
            worksheet.merge_range(row, first, row, last, header, formats["header"])
    worksheet.set_row(row, 28)
    return row + 1


def _write_section_glass_or_panels(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    calc: object,
    overrides: dict[str, Any],
) -> int:
    if hasattr(calc, "glass"):
        row = _write_bar(worksheet, formats, row, "Стекла")
        spans = ((0, 2), (3, 4), (5, 6), (7, 8), (9, 11))
        headers = ("Позиция", "Ширина, мм", "Высота, мм", "Кол-во, шт", "RS2021, мм")
        row = _write_headers(worksheet, formats, row, headers, spans)
        for index, glass in enumerate(calc.glass):
            if int(getattr(glass, "qty", 0) or 0) <= 0:
                continue
            values = (
                glass.position,
                override_value(
                    overrides, f"glass_{index}_w", format_dimension(glass.width_mm)
                ),
                override_value(
                    overrides, f"glass_{index}_h", format_dimension(glass.height_mm)
                ),
                override_value(overrides, f"glass_{index}_q", glass.qty),
                format_dimension(glass.glass_profile_length),
            )
            for value, (first, last) in zip(values, spans, strict=True):
                worksheet.merge_range(row, first, row, last, value, formats["center"])
            worksheet.set_row(row, 20)
            row += 1
        return row

    row = _write_bar(worksheet, formats, row, "Заполнение и панели при склейке")
    spans = ((0, 0), (1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 11))
    headers = (
        "№",
        "Панель",
        "Заполнение",
        "Ширина, мм",
        "Высота, мм",
        "Склейка, мм",
        "Кол-во",
    )
    row = _write_headers(worksheet, formats, row, headers, spans)
    for panel in getattr(calc, "panels", None) or []:
        values = (
            panel.panel,
            panel.role,
            panel.filling,
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_width",
                format_dimension(panel.width_mm),
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_height",
                format_dimension(panel.height_mm),
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_glued_table",
                f"{format_dimension(panel.glued_width_mm)} × "
                f"{format_dimension(panel.glued_height_mm)}",
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_qty",
                panel.qty,
            ),
        )
        for value, (first, last) in zip(values, spans, strict=True):
            if first == last:
                worksheet.write(row, first, value, formats["center"])
            else:
                worksheet.merge_range(row, first, row, last, value, formats["center"])
        worksheet.set_row(row, 22)
        row += 1
    return row


def _write_profiles(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    calc: object,
    overrides: dict[str, Any],
) -> int:
    row = _write_bar(worksheet, formats, row, "Нарезка профилей")
    spans = ((0, 1), (2, 3), (4, 6), (7, 8), (9, 9), (10, 11))
    headers = (
        "Сечение",
        "Артикул",
        "Наименование / операция",
        "Длина, мм",
        "Кол-во",
        "Примечание",
    )
    row = _write_headers(worksheet, formats, row, headers, spans)

    for index, profile in enumerate(profile_rows(calc)):
        cuts = list(getattr(profile, "display_cuts", None) or [])
        if not cuts:
            cuts = [
                {
                    "length": getattr(profile, "length_mm", 0),
                    "qty": getattr(profile, "qty", 0),
                    "length_field": getattr(profile, "field_key", "")
                    or f"profile_{index}_length",
                    "qty_field": (
                        getattr(profile, "field_key", "") or f"profile_{index}"
                    )
                    + "_qty",
                }
            ]
        for cut_index, cut in enumerate(cuts):
            worksheet.set_row(row, 40 if cut_index == 0 else 22)
            worksheet.merge_range(row, 0, row, 1, "", formats["cell"])
            if cut_index == 0:
                source = image_stream(
                    getattr(profile, "image", None), max_size=(650, 300)
                )
                _insert_image(
                    worksheet,
                    row,
                    0,
                    source,
                    max_width_px=115,
                    max_height_px=46,
                    allow_enlarge=False,
                )
                worksheet.merge_range(
                    row,
                    2,
                    row,
                    3,
                    str(getattr(profile, "article", "") or ""),
                    formats["center_bold"],
                )
                worksheet.merge_range(
                    row,
                    4,
                    row,
                    6,
                    str(getattr(profile, "name", "") or ""),
                    formats["cell"],
                )
                worksheet.merge_range(
                    row,
                    10,
                    row,
                    11,
                    str(getattr(profile, "note", "") or ""),
                    formats["note"],
                )
            else:
                worksheet.merge_range(row, 2, row, 3, "", formats["cell"])
                worksheet.merge_range(row, 4, row, 6, "", formats["cell"])
                worksheet.merge_range(row, 10, row, 11, "", formats["cell"])
            length = ""
            if str(getattr(profile, "article", "")).upper() not in {
                "RS1005",
                "RS3110",
            }:
                length = override_value(
                    overrides,
                    str(cut.get("length_field") or ""),
                    format_dimension(cut.get("length")),
                )
            quantity = override_value(
                overrides,
                str(cut.get("qty_field") or ""),
                cut.get("qty", 0),
            )
            worksheet.merge_range(row, 7, row, 8, length, formats["center_bold"])
            worksheet.write(row, 9, quantity, formats["center_bold"])
            row += 1
    return row


def _write_hardware(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    calc: object,
    overrides: dict[str, Any],
) -> int:
    row = _write_bar(worksheet, formats, row, "Фурнитура и крепеж")
    spans = ((0, 1), (2, 3), (4, 6), (7, 7), (8, 8), (9, 11))
    headers = ("Изображение", "Артикул", "Наименование", "Кол-во", "Ед.", "Примечание")
    row = _write_headers(worksheet, formats, row, headers, spans)
    for article, name, value, unit, image, field_key, note in hardware_rows(calc):
        worksheet.set_row(row, 42)
        worksheet.merge_range(row, 0, row, 1, "", formats["cell"])
        _insert_image(
            worksheet,
            row,
            0,
            image_stream(image, max_size=(550, 300)),
            max_width_px=115,
            max_height_px=48,
            allow_enlarge=False,
        )
        worksheet.merge_range(row, 2, row, 3, article, formats["center_bold"])
        worksheet.merge_range(row, 4, row, 6, name, formats["cell"])
        worksheet.write(
            row,
            7,
            override_value(overrides, field_key, format_number(value)),
            formats["center_bold"],
        )
        worksheet.write(row, 8, unit, formats["center"])
        worksheet.merge_range(row, 9, row, 11, note, formats["note"])
        row += 1
    return row


def _write_compact_cards(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    title: str,
    cards: list[tuple[io.BytesIO | None, str, str, str]],
) -> int:
    if not cards:
        return row
    row = _write_bar(worksheet, formats, row, title)
    for offset in range(0, len(cards), 3):
        for column in range(3):
            start = column * 4
            index = offset + column
            worksheet.write(row, start, "", formats["cell"])
            if index >= len(cards):
                worksheet.merge_range(
                    row, start + 1, row, start + 3, "", formats["cell"]
                )
                continue
            image, heading, quantity, note = cards[index]
            worksheet.merge_range(row, start + 1, row, start + 2, "", formats["card"])
            if note:
                worksheet.write_rich_string(
                    row,
                    start + 1,
                    formats["card_heading"],
                    heading,
                    "\n",
                    formats["card_note"],
                    note,
                    formats["card"],
                )
            else:
                worksheet.write(
                    row,
                    start + 1,
                    heading,
                    formats["card_heading_cell"],
                )
            worksheet.write(row, start + 3, quantity, formats["card_quantity_cell"])
            _insert_image(
                worksheet,
                row,
                start,
                image,
                max_width_px=68,
                max_height_px=43,
                x_offset=2,
                y_offset=2,
                allow_enlarge=False,
            )
        worksheet.set_row(row, 62)
        row += 1
    return row


def _write_compact_profiles(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    calc: object,
    overrides: dict[str, Any],
) -> int:
    cards: list[tuple[io.BytesIO | None, str, str, str]] = []
    for index, profile in enumerate(profile_rows(calc)):
        cuts = list(getattr(profile, "display_cuts", None) or [])
        if not cuts:
            key = getattr(profile, "field_key", "") or f"profile_{index}"
            cuts = [
                {
                    "length": getattr(profile, "length_mm", 0),
                    "qty": getattr(profile, "qty", 0),
                    "length_field": f"{key}_length",
                    "qty_field": f"{key}_qty",
                }
            ]
        values: list[str] = []
        for cut in cuts:
            quantity = override_value(
                overrides,
                str(cut.get("qty_field") or ""),
                cut.get("qty", 0),
            )
            if str(getattr(profile, "article", "")).upper() in {
                "RS1005",
                "RS3110",
            }:
                values.append(f"{quantity} шт")
            else:
                length = override_value(
                    overrides,
                    str(cut.get("length_field") or ""),
                    format_dimension(cut.get("length")),
                )
                values.append(f"{length} мм {quantity} шт")
        heading = f"{getattr(profile, 'article', '')} · {getattr(profile, 'name', '')}"
        quantity = "; ".join(values)
        note = str(getattr(profile, "note", "") or "")
        cards.append(
            (
                image_stream(getattr(profile, "image", None), max_size=(600, 260)),
                heading,
                quantity,
                note,
            )
        )
    return _write_compact_cards(
        worksheet,
        formats,
        row,
        "Нарезка профилей",
        cards,
    )


def _write_compact_hardware(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    calc: object,
    overrides: dict[str, Any],
) -> int:
    cards: list[tuple[io.BytesIO | None, str, str, str]] = []
    for article, name, value, unit, image, field_key, note in hardware_rows(calc):
        quantity = override_value(overrides, field_key, format_number(value))
        cards.append(
            (
                image_stream(image, max_size=(500, 260)),
                f"{article} · {name}",
                f"{quantity} {unit}".strip(),
                note,
            )
        )
    return _write_compact_cards(
        worksheet,
        formats,
        row,
        "Фурнитура и крепеж",
        cards,
    )


def _build_details_sheet(
    workbook: xlsxwriter.Workbook,
    formats: dict[str, Any],
    project: object,
    section: object,
    calc: object,
    overrides: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet("Нарезка и комплектация")
    _setup_sheet(worksheet, landscape=False)
    _section_sheet_columns(worksheet)
    row = _write_section_header(
        worksheet,
        formats,
        project,
        section,
        "НАРЕЗКА И КОМПЛЕКТАЦИЯ",
    )
    row = _write_compact_profiles(worksheet, formats, row, calc, overrides)
    row = _write_compact_hardware(worksheet, formats, row, calc, overrides)
    if hasattr(calc, "torque") and getattr(calc, "torque", None):
        row = _write_bar(worksheet, formats, row, "Расчет привода")
        torque = calc.torque
        values = (
            (
                "Вес подвижных панелей",
                f"{format_dimension(torque.moving_weight_kg)} кг",
            ),
            (
                "Крутящий момент",
                f"{format_dimension(torque.torque_nm)} Н·м",
            ),
            ("Количество приводов", f"{torque.drive_count} шт"),
        )
        for column, (label, value) in enumerate(values):
            first = column * 4
            worksheet.merge_range(row, first, row, first + 3, label, formats["label"])
            worksheet.merge_range(
                row + 1,
                first,
                row + 1,
                first + 3,
                value,
                formats["center_bold"],
            )
        row += 2
    row = _write_bar(worksheet, formats, row, "Примечания и особые отметки")
    worksheet.merge_range(
        row,
        0,
        row + 4,
        11,
        override_value(
            overrides,
            "lift_comments" if hasattr(calc, "torque") else "section_comments",
            getattr(section, "comments", "") or "",
        ),
        formats["cell"],
    )
    worksheet.print_area(0, 0, row + 4, 11)


def _build_slide_checklist_sheet(
    workbook: xlsxwriter.Workbook,
    formats: dict[str, Any],
    project: object,
    section: object,
    overrides: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet("Чек-лист")
    _setup_sheet(worksheet, landscape=False)
    _section_sheet_columns(worksheet)
    worksheet.merge_range(
        0,
        0,
        1,
        11,
        f"ПРОЕКТ № {getattr(project, 'number', '')} — {getattr(section, 'name', '')}",
        formats["title"],
    )
    row = _write_slide_checklist_block(
        worksheet,
        formats,
        2,
        section,
        overrides,
    )
    drawings = drawing_image_streams_for_sections([section])
    if drawings:
        row = _write_bar(worksheet, formats, row, "Чертежи ручек")
        for index, (name, stream) in enumerate(drawings):
            start_col = index * 6
            worksheet.merge_range(
                row,
                start_col,
                row + 8,
                start_col + 5,
                "",
                formats["cell"],
            )
            _insert_image(
                worksheet,
                row,
                start_col,
                stream,
                max_width_px=300,
                max_height_px=155,
                x_offset=12,
                y_offset=5,
                allow_enlarge=False,
            )
            label = "Ручка-кноб" if name == "knob" else "Ручка-скоба 600 мм"
            worksheet.merge_range(
                row + 9,
                start_col,
                row + 9,
                start_col + 5,
                label,
                formats["center_bold"],
            )
        row += 10
    worksheet.print_area(0, 0, row - 1, 11)


def _write_slide_checklist_block(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    section: object,
    overrides: dict[str, Any],
) -> int:
    row = _write_bar(worksheet, formats, row, "Чек-лист")
    spans = ((0, 0), (1, 1), (2, 6), (7, 10), (11, 11))
    headers = ("№ п/п", "Отм. пр-ва", "Действие", "Примечание", "Отм. ОТК")
    row = _write_headers(worksheet, formats, row, headers, spans)
    for number, action, note in CHECKLIST_ROWS:
        values = (number, "☐", action, note, "☐")
        for value, (first, last) in zip(values, spans, strict=True):
            if first == last:
                worksheet.write(row, first, value, formats["center"])
            else:
                worksheet.merge_range(row, first, row, last, value, formats["cell"])
        worksheet.set_row(row, 24)
        row += 1
    row = _write_bar(
        worksheet,
        formats,
        row,
        "Примечания и особые отметки при производстве или проверке ОТК",
    )
    worksheet.merge_range(
        row,
        0,
        row + 7,
        11,
        override_value(
            overrides,
            "section_comments",
            getattr(section, "comments", "") or "",
        ),
        formats["cell"],
    )
    row += 8
    row = _write_bar(worksheet, formats, row, "Ответственные за заказ на производстве")
    labels = (
        "Нарезка",
        "Поклейка",
        "Упаковка",
        "Сборка",
        "Поклейка",
        "Комплектация",
        "Упаковка",
        "",
    )
    for index, label in enumerate(labels):
        line = row + index % 4
        start = 0 if index < 4 else 6
        worksheet.write(line, start, index + 1, formats["center"])
        worksheet.merge_range(line, start + 1, line, start + 2, label, formats["cell"])
        worksheet.merge_range(line, start + 3, line, start + 5, "", formats["cell"])
        worksheet.set_row(line, 22)
    row += 4

    worksheet.merge_range(
        row,
        0,
        row,
        7,
        'Дата фото профиля и панелей   "____"  ______________  202___ г.',
        formats["cell"],
    )
    worksheet.merge_range(row, 8, row, 11, "Ответственный", formats["center"])
    worksheet.set_row(row, 24)
    row += 1
    worksheet.merge_range(
        row,
        0,
        row,
        7,
        'Дата фото фурнитуры           "____"  ______________  202___ г.',
        formats["cell"],
    )
    worksheet.merge_range(row, 8, row, 11, "", formats["cell"])
    worksheet.set_row(row, 24)
    row += 1
    worksheet.merge_range(row, 0, row, 7, "", formats["cell"])
    worksheet.merge_range(row, 8, row, 11, "подпись", formats["center"])
    worksheet.set_row(row, 18)
    row += 1
    worksheet.merge_range(row, 0, row, 7, "", formats["cell"])
    worksheet.merge_range(row, 8, row, 11, "", formats["cell"])
    worksheet.set_row(row, 24)
    row += 1
    worksheet.merge_range(row, 0, row, 7, "", formats["cell"])
    worksheet.merge_range(row, 8, row, 11, "расшифровка", formats["center"])
    worksheet.set_row(row, 18)
    return row + 1


def build_section_xlsx(project: object, section: object, calc: object) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties(
        {
            "title": "Производственный лист",
            "subject": f"{getattr(project, 'number', '')} / {getattr(section, 'name', '')}",
            "company": "Raluma",
        }
    )
    formats = _formats(workbook)
    overrides = load_overrides(section)
    system = str(getattr(section, "system", "") or "").strip().upper()

    worksheet = workbook.add_worksheet("Производственный лист")
    _setup_sheet(worksheet, landscape=False, paper=9)
    _section_sheet_columns(worksheet)
    row = _write_section_header(
        worksheet,
        formats,
        project,
        section,
        f"{system} · ПРОИЗВОДСТВЕННЫЙ ЛИСТ",
    )
    for warning_text in getattr(calc, "warnings", []) or []:
        worksheet.merge_range(
            row,
            0,
            row,
            11,
            str(warning_text),
            formats["red_center"],
        )
        worksheet.set_row(row, 28)
        row += 1
    row = _write_summary(worksheet, formats, row, section, calc)
    row = _write_diagrams(worksheet, formats, row, section, calc)
    row = _write_section_glass_or_panels(worksheet, formats, row, calc, overrides)
    if system == "СЛАЙД":
        row = _write_compact_profiles(worksheet, formats, row, calc, overrides)
        row = _write_compact_hardware(worksheet, formats, row, calc, overrides)
    worksheet.print_area(0, 0, max(row - 1, 1), 11)

    if system == "ЛИФТ":
        _build_details_sheet(workbook, formats, project, section, calc, overrides)
    else:
        _build_slide_checklist_sheet(workbook, formats, project, section, overrides)

    workbook.close()
    return output.getvalue()


def _project_header(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    title: str,
    project: object,
    *,
    last_col: int = 7,
) -> int:
    info_start = max(3, last_col - 3)
    worksheet.merge_range(0, 0, 2, info_start - 1, title.upper(), formats["title"])
    worksheet.write(0, info_start, "Заявка", formats["label"])
    worksheet.merge_range(
        0,
        info_start + 1,
        0,
        last_col,
        str(getattr(project, "number", "") or ""),
        formats["cell"],
    )
    worksheet.write(1, info_start, "Заказчик", formats["label"])
    worksheet.merge_range(
        1,
        info_start + 1,
        1,
        last_col,
        str(getattr(project, "customer", "") or ""),
        formats["cell"],
    )
    return 3


def _build_glass_xlsx(context: dict) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    formats = _formats(workbook)
    worksheet = workbook.add_worksheet("Заказ стекла")
    _setup_sheet(worksheet, landscape=False)
    widths = (5, 16, 24, 12, 12, 9, 12, 18)
    for index, width in enumerate(widths):
        worksheet.set_column(index, index, width)
    row = _project_header(
        worksheet,
        formats,
        "Заказ стекла",
        context["project"],
    )
    for warning in context.get("document_warnings", []):
        worksheet.merge_range(row, 0, row, 7, warning, formats["red_center"])
        worksheet.set_row(row, 26)
        row += 1
    worksheet.merge_range(
        row,
        0,
        row,
        7,
        "КРОМКИ ПОЛИРОВАННЫЕ. Печать закалки не ставить",
        formats["red"],
    )
    row += 1
    headers = (
        "№",
        "Маркировка",
        "Стекло",
        "Ширина, мм",
        "Высота, мм",
        "Кол-во",
        "Площадь, м²",
        "Примечание",
    )
    for column, header in enumerate(headers):
        worksheet.write(row, column, header, formats["header"])
    worksheet.set_row(row, 30)
    row += 1
    data_start_row = row
    for item in context["glass_rows"]:
        values = (
            item["index"],
            item["marking"],
            item["glass_type"],
            item["width"],
            item["height"],
            item["qty"],
            item["note"],
        )
        for column, value in enumerate(values[:6]):
            worksheet.write(
                row,
                column,
                value,
                formats["cell"] if column in {1, 2, 7} else formats["center"],
            )
        excel_row = row + 1
        worksheet.write_formula(
            row,
            6,
            f"=ROUND(D{excel_row}*E{excel_row}*F{excel_row}/1000000,3)",
            formats["center"],
            item["area"],
        )
        worksheet.write(row, 7, item["note"], formats["cell"])
        worksheet.set_row(row, 34)
        row += 1
    worksheet.merge_range(row, 0, row, 4, "Итого", formats["total"])
    first_excel_row = data_start_row + 1
    last_excel_row = row
    if row > data_start_row:
        worksheet.write_formula(
            row,
            5,
            f"=SUM(F{first_excel_row}:F{last_excel_row})",
            formats["total"],
            context["glass_total_qty"],
        )
        worksheet.write_formula(
            row,
            6,
            f"=ROUND(SUM(G{first_excel_row}:G{last_excel_row}),3)",
            formats["total"],
            context["glass_total_area"],
        )
    else:
        worksheet.write_number(row, 5, 0, formats["total"])
        worksheet.write_number(row, 6, 0, formats["total"])
    worksheet.write_blank(row, 7, None, formats["total"])
    row += 2
    worksheet.merge_range(
        row,
        0,
        row + 3,
        7,
        "ОБРАЩАЮ ВНИМАНИЕ НА ПОВЫШЕННОЕ КАЧЕСТВО ИЗДЕЛИЙ\n"
        "Т.К. ФИРМА ИЗГОТАВЛИВАЕТ БЕЗРАМНОЕ ОСТЕКЛЕНИЕ\n"
        "ПЕРЕКОС ДИАГОНАЛИ НЕ ДОЛЖЕН ПРЕВЫШАТЬ 1-2ММ\n"
        "ГАБАРИТЫ СТЕКЛА НЕ ДОЛЖНЫ ПРЕВЫШАТЬ 2ММ",
        formats["red"],
    )
    worksheet.print_area(0, 0, row + 3, 7)
    workbook.close()
    return output.getvalue()


def _safe_sheet_name(value: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", str(value or "Без цвета")).strip()[:31]
    base = base or "Без цвета"
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        tail = f" {suffix}"
        candidate = f"{base[: 31 - len(tail)]}{tail}"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def _build_paint_xlsx(context: dict) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    formats = _formats(workbook)
    pages = context["paint_pages"]
    if not pages:
        pages = [
            {
                "color": "Без цвета",
                "groups": [],
                "total_qty": 0,
                "total_m": 0,
            }
        ]
    used_names: set[str] = set()
    for page in pages:
        worksheet = workbook.add_worksheet(_safe_sheet_name(page["color"], used_names))
        _setup_sheet(worksheet, landscape=False)
        worksheet.fit_to_pages(1, 1)
        widths = (14, 24, 10, 17, 17, 14)
        for index, width in enumerate(widths):
            worksheet.set_column(index, index, width)
        row = _project_header(
            worksheet,
            formats,
            "Заявка на покраску",
            context["project"],
            last_col=5,
        )
        for warning in context.get("document_warnings", []):
            worksheet.merge_range(row, 0, row, 5, warning, formats["red_center"])
            worksheet.set_row(row, 26)
            row += 1
        worksheet.merge_range(
            row,
            0,
            row,
            5,
            f"ЦВЕТ: {page['color']}",
            formats["red_center"],
        )
        row += 1
        worksheet.merge_range(
            row,
            0,
            row,
            5,
            "В СЧЕТЕ УКАЗАТЬ НОМЕР ЗАЯВКИ И ЦВЕТ ПРОФИЛЯ",
            formats["red_center"],
        )
        row += 1
        headers = (
            "Артикул",
            "Сечение",
            "Кол-во",
            "Чистовые размеры",
            "С припуском 50 мм",
            "Общее, м.п.",
        )
        for column, header in enumerate(headers):
            worksheet.write(row, column, header, formats["header"])
        worksheet.set_row(row, 30)
        row += 1

        data_start_row = row
        for group in page["groups"]:
            rows = list(group["rows"])
            if not rows:
                continue
            start = row
            end = row + len(rows) - 1
            if end > start:
                worksheet.merge_range(
                    start, 0, end, 0, group["article"], formats["center_bold"]
                )
                worksheet.merge_range(start, 1, end, 1, "", formats["cell_bottom"])
            else:
                worksheet.write(start, 0, group["article"], formats["center_bold"])
                worksheet.write(start, 1, "", formats["cell_bottom"])
            note = str(group.get("note") or "").strip()
            if note:
                worksheet.write_rich_string(
                    start,
                    1,
                    str(group["name"]),
                    "\n",
                    formats["red_text"],
                    note,
                    formats["cell_bottom"],
                )
            else:
                worksheet.write(start, 1, group["name"], formats["cell_bottom"])
            for item in rows:
                worksheet.write(row, 2, item["qty"], formats["center"])
                worksheet.write(row, 3, item["clean"], formats["center"])
                worksheet.write(row, 4, item["allowance"], formats["center"])
                excel_row = row + 1
                worksheet.write_formula(
                    row,
                    5,
                    f"=ROUND(C{excel_row}*E{excel_row}/1000,1)",
                    formats["center"],
                    item["total_m"],
                )
                worksheet.set_row(row, 58)
                row += 1
            source = image_stream(
                group.get("image"),
                group.get("image_data"),
                max_size=(760, 480),
            )
            _insert_image(
                worksheet,
                start,
                1,
                source,
                max_width_px=135,
                max_height_px=max(38, len(rows) * 70 - 28),
                x_offset=12,
                y_offset=3,
                allow_enlarge=False,
            )
        worksheet.merge_range(row, 0, row, 1, "Итого", formats["total"])
        first_excel_row = data_start_row + 1
        last_excel_row = row
        if row > data_start_row:
            worksheet.write_formula(
                row,
                2,
                f"=SUM(C{first_excel_row}:C{last_excel_row})",
                formats["total"],
                page["total_qty"],
            )
        else:
            worksheet.write_number(row, 2, 0, formats["total"])
        worksheet.write_blank(row, 3, None, formats["total"])
        worksheet.write_blank(row, 4, None, formats["total"])
        if row > data_start_row:
            worksheet.write_formula(
                row,
                5,
                f"=ROUND(SUM(F{first_excel_row}:F{last_excel_row}),1)",
                formats["total"],
                page["total_m"],
            )
        else:
            worksheet.write_number(row, 5, 0, formats["total"])
        worksheet.print_area(0, 0, row, 5)
    workbook.close()
    return output.getvalue()


def _build_hardware_order_xlsx(context: dict) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    formats = _formats(workbook)
    pages = context["hardware_order_pages"]
    if not pages:
        pages = [{"system": "Фурнитура", "rows": [], "warning": ""}]

    used_names: set[str] = set()
    for page in pages:
        worksheet = workbook.add_worksheet(
            _safe_sheet_name(page["system"] or "Фурнитура", used_names)
        )
        _setup_sheet(worksheet, landscape=False)
        worksheet.set_header("")
        worksheet.fit_to_pages(1, 1)
        widths = (12, 18, 34, 16, 16, 9, 14, 12)
        for column, width in enumerate(widths):
            worksheet.set_column(column, column, width)

        project = context["project"]
        project_number = str(
            getattr(project, "invoice_number", None)
            or getattr(project, "order_number", None)
            or getattr(project, "number", None)
            or ""
        )
        worksheet.merge_range(
            0,
            0,
            0,
            7,
            f"НАРЯД-ЗАКАЗ НА ФУРНИТУРУ — {project_number}",
            formats["title"],
        )
        worksheet.set_row(0, 22)
        worksheet.merge_range(
            1,
            0,
            1,
            7,
            page["system"] or "БЕЗ СИСТЕМЫ",
            formats["bar"],
        )
        worksheet.set_row(1, 18)
        row = 2
        if not used_names or len(used_names) == 1:
            for warning in context.get("document_warnings", []):
                worksheet.merge_range(
                    row,
                    0,
                    row,
                    7,
                    warning,
                    formats["red_center"],
                )
                worksheet.set_row(row, 24)
                row += 1
        if page.get("warning"):
            worksheet.merge_range(
                row,
                0,
                row,
                7,
                page["warning"],
                formats["red_center"],
            )
            worksheet.set_row(row, 24)
            row += 1
        headers = (
            "Артикул",
            "Эскиз",
            "Название",
            "Цвет",
            "Размер",
            "Этап",
            "Кол-во\n(общее в проекте)",
            "Единицы измерения",
        )
        header_row = row
        for column, header in enumerate(headers):
            worksheet.write(row, column, header, formats["header"])
        worksheet.set_row(row, 24)
        worksheet.repeat_rows(0, row)
        worksheet.freeze_panes(row + 1, 0)
        row += 1

        for row_data in page["rows"]:
            worksheet.write(row, 0, row_data["article"], formats["center_bold"])
            worksheet.write_blank(row, 1, None, formats["center"])
            worksheet.write(row, 2, row_data["name"], formats["cell"])
            worksheet.write(row, 3, row_data.get("color") or "—", formats["cell"])
            worksheet.write(row, 4, row_data.get("size") or "—", formats["cell"])
            worksheet.write(row, 5, row_data["stage_text"], formats["center_bold"])
            worksheet.write_number(row, 6, row_data["qty"], formats["center_bold"])
            worksheet.write(row, 7, row_data["unit"], formats["center"])
            worksheet.set_row(row, 28)
            _insert_image(
                worksheet,
                row,
                1,
                image_stream(row_data.get("image"), max_size=(700, 420)),
                max_width_px=92,
                max_height_px=25,
                x_offset=4,
                y_offset=2,
                allow_enlarge=False,
            )
            row += 1
        if not page["rows"]:
            worksheet.merge_range(
                row,
                0,
                row + 1,
                7,
                "Позиции не найдены",
                formats["center"],
            )
            row += 2

        worksheet.autofilter(header_row, 0, max(header_row, row - 1), 7)
        worksheet.print_area(0, 0, max(header_row, row - 1), 7)

    workbook.close()
    return output.getvalue()


def _build_delivery_xlsx(context: dict) -> bytes:
    """Build the editable, image-free delivery note on a single worksheet."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    project = context["project"]
    delivery = context["delivery"]
    project_number = str(
        getattr(project, "invoice_number", None)
        or getattr(project, "order_number", None)
        or getattr(project, "number", None)
        or ""
    )
    workbook.set_properties(
        {
            "title": f"Накладная {project_number}",
            "subject": "Комплектность отгрузки",
            "company": "Raluma",
        }
    )
    formats = _formats(workbook)
    border = {"border": 1, "border_color": "#4D565B"}
    detail = workbook.add_format(
        {
            "font_name": "Arial",
            "font_size": 9,
            "valign": "vcenter",
            "text_wrap": True,
            **border,
        }
    )
    detail_bold = workbook.add_format(
        {
            "font_name": "Arial",
            "font_size": 9,
            "bold": True,
            "valign": "vcenter",
            "text_wrap": True,
            **border,
        }
    )
    quantity = workbook.add_format(
        {
            "font_name": "Arial",
            "font_size": 9,
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "num_format": "0.###",
            **border,
        }
    )
    signature = workbook.add_format(
        {
            "font_name": "Arial",
            "font_size": 9,
            "valign": "bottom",
            "text_wrap": True,
        }
    )

    worksheet = workbook.add_worksheet("Накладная")
    _setup_sheet(worksheet, landscape=False, paper=9)
    worksheet.set_header("")
    worksheet.set_footer("&LНакладная&CСтраница &P из &N&R&D")
    worksheet.set_margins(0.3, 0.3, 0.35, 0.4)
    for column, width in enumerate((6, 14, 22, 55, 13, 14)):
        worksheet.set_column(column, column, width)

    worksheet.merge_range(
        0,
        0,
        0,
        5,
        f"НАКЛАДНАЯ № {project_number}",
        formats["title"],
    )
    worksheet.set_row(0, 28)
    worksheet.merge_range(
        1,
        0,
        1,
        2,
        "Исполнитель: ООО «ПРОЗРАЧНЫЕ РЕШЕНИЯ»",
        detail_bold,
    )
    worksheet.merge_range(
        1,
        3,
        1,
        5,
        f"Дата: {delivery.get('dateText', '')}",
        detail_bold,
    )

    detail_rows = (
        ("Заказчик", str(getattr(project, "customer", "") or "")),
        ("Примечание", str(delivery.get("note") or "")),
        ("Контактное лицо", str(delivery.get("contact") or "")),
        ("Доставка, разгрузка и монтаж", str(delivery.get("delivery") or "")),
    )
    row = 2
    for label, value in detail_rows:
        worksheet.merge_range(row, 0, row, 1, label, formats["label"])
        worksheet.merge_range(row, 2, row, 5, value, detail)
        worksheet.set_row(row, 21 if value else 18)
        row += 1

    for warning in context.get("document_warnings", []):
        worksheet.merge_range(row, 0, row, 5, warning, formats["red_center"])
        worksheet.set_row(row, 26)
        row += 1

    stages = int(delivery.get("productionStages") or 1)
    current_stage = int(delivery.get("currentStage") or 1)
    stage_text = "Одна отгрузка" if stages == 1 else f"Этап {current_stage} из {stages}"
    worksheet.merge_range(row, 0, row, 5, stage_text, formats["bar"])
    worksheet.set_row(row, 19)
    row += 1

    headers = (
        "№",
        "Раздел",
        "Артикул / маркировка",
        "Наименование, размеры и примечания",
        "Количество",
        "Кол-во мест",
    )
    header_row = row
    for column, header in enumerate(headers):
        worksheet.write(row, column, header, formats["header"])
    worksheet.set_row(row, 30)
    worksheet.repeat_rows(0, row)
    worksheet.freeze_panes(row + 1, 0)
    row += 1
    data_start_row = row
    item_number = 1

    def write_item(
        section_name: str,
        article: str,
        name: str,
        details_text: str,
        qty: object,
        places: object,
    ) -> None:
        nonlocal row, item_number
        try:
            numeric_qty = float(qty or 0)
        except (TypeError, ValueError):
            numeric_qty = 0.0
        worksheet.write_number(row, 0, item_number, formats["center"])
        worksheet.write(row, 1, section_name, formats["center"])
        worksheet.write(row, 2, article, formats["center_bold"])
        text = name if not details_text else f"{name}\n{details_text}"
        worksheet.write(row, 3, text, detail_bold if name else detail)
        worksheet.write_number(row, 4, numeric_qty, quantity)
        worksheet.write(row, 5, str(places or ""), formats["center"])
        worksheet.set_row(row, max(24, 16 * (text.count("\n") + 1)))
        item_number += 1
        row += 1

    for item in context.get("delivery_item1_rows") or []:
        if item.get("kind") == "construction":
            dimensions = []
            for dimension in item.get("dimensions") or []:
                value = f"{dimension.get('size', '')} — {dimension.get('qty', 0)} шт."
                threshold = str(dimension.get("threshold") or "")
                if threshold and item.get("threshold") == "Пороги согласно ТЗ":
                    value += f" — {threshold}"
                dimensions.append(value)
            meta = ", ".join(
                value
                for value in (
                    str(item.get("profile_set_name") or ""),
                    str(item.get("color") or ""),
                    str(item.get("threshold") or ""),
                )
                if value
            )
            details_text = "\n".join(filter(None, (meta, *dimensions)))
            write_item(
                "Конструкция",
                "",
                str(item.get("name") or ""),
                details_text,
                item.get("qty"),
                item.get("places"),
            )
            continue

        glass_rows = item.get("rows") or []
        for glass_index, glass in enumerate(glass_rows):
            if glass.get("width") is None or glass.get("height") is None:
                size = "Размеры согласно ТЗ"
            else:
                size = f"{glass.get('width')} × {glass.get('height')} мм"
            note = str(glass.get("note") or "")
            details_text = "\n".join(
                filter(None, (size, note, str(item.get("color") or "")))
            )
            write_item(
                "Стекло",
                str(glass.get("marking") or ""),
                str(glass.get("glass_type") or item.get("name") or ""),
                details_text,
                glass.get("qty"),
                item.get("places") if glass_index == 0 else "",
            )

    for item in context.get("delivery_item2_rows") or []:
        details_text = "\n".join(
            filter(
                None,
                (
                    f"Цвет: {item.get('color')}" if item.get("color") else "",
                    f"Размер: {item.get('size')}" if item.get("size") else "",
                    f"Единица: {item.get('unit')}" if item.get("unit") else "",
                    f"Этап: {item.get('stage')}" if item.get("stage") else "",
                    str(item.get("note") or ""),
                ),
            )
        )
        write_item(
            "Фурнитура",
            str(item.get("article") or ""),
            str(item.get("name") or ""),
            details_text,
            item.get("qty"),
            item.get("places"),
        )

    for item in context.get("delivery_project_extra_rows") or []:
        details_text = "\n".join(
            filter(
                None,
                (
                    f"Цвет: {item.get('color')}" if item.get("color") else "",
                    f"Размер: {item.get('size')}" if item.get("size") else "",
                    f"Единица: {item.get('unit')}" if item.get("unit") else "",
                    f"Этап: {item.get('stage')}" if item.get("stage") else "",
                ),
            )
        )
        write_item(
            "Доп. комплектующие проекта",
            str(item.get("article") or ""),
            str(item.get("name") or ""),
            details_text,
            item.get("qty"),
            item.get("places"),
        )

    if row == data_start_row:
        worksheet.merge_range(row, 0, row, 3, "Позиции для отгрузки не найдены", detail)
        worksheet.write_number(row, 4, 0, quantity)
        worksheet.write_blank(row, 5, None, formats["center"])
        row += 1

    # Quantities have different units (шт., м, компл.); a shared numeric total
    # would be misleading, so the document intentionally has no total row.
    row += 1

    worksheet.merge_range(
        row,
        0,
        row,
        5,
        "Изделия и комплектацию принял. Претензий по качеству и количеству не имею.",
        signature,
    )
    worksheet.set_row(row, 24)
    row += 2
    worksheet.merge_range(
        row,
        0,
        row,
        2,
        "Исполнитель: __________________ / __________________",
        signature,
    )
    worksheet.merge_range(
        row, 3, row, 5, "Заказчик: __________________ / __________________", signature
    )
    worksheet.set_row(row, 30)

    worksheet.autofilter(header_row, 0, max(header_row, row - 4), 5)
    worksheet.print_area(0, 0, row, 5)
    workbook.close()
    return output.getvalue()


def build_project_xlsx(
    project: object,
    sections: Iterable[object],
    doc_type: str,
) -> bytes:
    context = build_project_document_context(project, sections, doc_type)
    if doc_type == "glass":
        return _build_glass_xlsx(context)
    if doc_type == "paint":
        return _build_paint_xlsx(context)
    if doc_type == "hardware_order":
        return _build_hardware_order_xlsx(context)
    if doc_type == "delivery":
        return _build_delivery_xlsx(context)
    raise ValueError(
        "Excel export is available only for glass, paint, hardware order and delivery documents"
    )
