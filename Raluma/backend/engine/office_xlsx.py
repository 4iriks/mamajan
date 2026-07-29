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
    format_number,
    image_stream,
    load_overrides,
    override_value,
)
from engine.office_diagrams import section_diagrams
from engine.office_docx import CHECKLIST_ROWS
from engine.office_section_data import hardware_rows, profile_rows, section_summary_rows
from engine.pdf import section_extra_components
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
    widths = (4, 11, 13, 17, 17, 14, 10, 10, 12, 12, 12, 12)
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
    for index, (title, data) in enumerate(diagrams):
        start_col = 0 if index % 2 == 0 else 6
        line = row + (index // 2) * 14
        worksheet.merge_range(line, start_col, line, start_col + 5, title.upper(), formats["header"])
        worksheet.merge_range(
            line + 1,
            start_col,
            line + 13,
            start_col + 5,
            "",
            formats["cell"],
        )
        for diagram_row in range(line + 1, line + 14):
            worksheet.set_row(diagram_row, 18)
        stream = io.BytesIO(data)
        _insert_image(
            worksheet,
            line + 1,
            start_col,
            stream,
            max_width_px=550,
            max_height_px=220,
            x_offset=10,
            y_offset=7,
        )
    return row + ((len(diagrams) + 1) // 2) * 14


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
                override_value(overrides, f"glass_{index}_w", format_number(glass.width_mm)),
                override_value(overrides, f"glass_{index}_h", format_number(glass.height_mm)),
                override_value(overrides, f"glass_{index}_q", glass.qty),
                format_number(glass.glass_profile_length),
            )
            for value, (first, last) in zip(values, spans, strict=True):
                worksheet.merge_range(row, first, row, last, value, formats["center"])
            worksheet.set_row(row, 20)
            row += 1
        return row

    row = _write_bar(worksheet, formats, row, "Заполнение и панели при склейке")
    spans = ((0, 0), (1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 11))
    headers = ("№", "Панель", "Заполнение", "Ширина, мм", "Высота, мм", "Склейка, мм", "Кол-во")
    row = _write_headers(worksheet, formats, row, headers, spans)
    for panel in getattr(calc, "panels", None) or []:
        values = (
            panel.panel,
            panel.role,
            panel.filling,
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_width",
                format_number(panel.width_mm),
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_height",
                format_number(panel.height_mm),
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_glued_table",
                f"{format_number(panel.glued_width_mm)} × "
                f"{format_number(panel.glued_height_mm)}",
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
    headers = ("Сечение", "Артикул", "Наименование / операция", "Длина, мм", "Кол-во", "Примечание")
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
                    "qty_field": (getattr(profile, "field_key", "") or f"profile_{index}")
                    + "_qty",
                }
            ]
        for cut_index, cut in enumerate(cuts):
            worksheet.set_row(row, 40 if cut_index == 0 else 22)
            worksheet.merge_range(row, 0, row, 1, "", formats["cell"])
            if cut_index == 0:
                source = image_stream(getattr(profile, "image", None), max_size=(650, 300))
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
            if str(getattr(profile, "article", "")).upper() != "RS3110":
                length = override_value(
                    overrides,
                    str(cut.get("length_field") or ""),
                    format_number(cut.get("length")),
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


def _write_extra_components(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    section: object,
    overrides: dict[str, Any],
) -> int:
    items = section_extra_components(section, overrides)
    if not items:
        return row
    row = _write_bar(worksheet, formats, row, "Дополнительные комплектующие")
    spans = ((0, 2), (3, 5), (6, 7), (8, 9), (10, 11))
    headers = ("Артикул", "Название", "Размер", "Кол-во", "Цвет")
    row = _write_headers(worksheet, formats, row, headers, spans)
    for item in items:
        for value, (first, last) in zip(
            (item.get("art", ""), item.get("name", ""), item.get("size", ""), item.get("qty", ""), item.get("color", "")),
            spans,
            strict=True,
        ):
            worksheet.merge_range(row, first, row, last, value, formats["cell"])
        worksheet.set_row(row, 22)
        row += 1
    return row


def _build_details_sheet(
    workbook: xlsxwriter.Workbook,
    formats: dict[str, Any],
    project: object,
    section: object,
    calc: object,
    overrides: dict[str, Any],
) -> None:
    worksheet = workbook.add_worksheet("Нарезка и комплектация")
    _setup_sheet(worksheet)
    _section_sheet_columns(worksheet)
    row = _write_section_header(
        worksheet,
        formats,
        project,
        section,
        "НАРЕЗКА И КОМПЛЕКТАЦИЯ",
    )
    row = _write_profiles(worksheet, formats, row, calc, overrides)
    row = _write_hardware(worksheet, formats, row, calc, overrides)
    row = _write_extra_components(worksheet, formats, row, section, overrides)
    if hasattr(calc, "torque") and getattr(calc, "torque", None):
        row = _write_bar(worksheet, formats, row, "Расчет привода")
        torque = calc.torque
        values = (
            ("Вес подвижных панелей", f"{format_number(torque.moving_weight_kg)} кг"),
            ("Крутящий момент", f"{format_number(torque.torque_nm)} Н·м"),
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
    _setup_sheet(worksheet)
    _section_sheet_columns(worksheet)
    worksheet.merge_range(
        0,
        0,
        1,
        11,
        f"ПРОЕКТ № {getattr(project, 'number', '')} — "
        f"{getattr(section, 'name', '')}",
        formats["title"],
    )
    row = _write_slide_checklist_block(
        worksheet,
        formats,
        2,
        section,
        overrides,
    )
    worksheet.print_area(0, 0, row, 11)


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
    labels = ("Нарезка", "Поклейка", "Упаковка", "Сборка", "Поклейка", "Комплектация", "Упаковка", "")
    for index, label in enumerate(labels):
        line = row + index % 4
        start = 0 if index < 4 else 6
        worksheet.merge_range(line, start, line, start + 1, label, formats["cell"])
        worksheet.merge_range(line, start + 2, line, start + 5, "", formats["cell"])
        worksheet.set_row(line, 22)
    return row + 4


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
    _setup_sheet(worksheet, paper=8)
    _section_sheet_columns(worksheet)
    row = _write_section_header(
        worksheet,
        formats,
        project,
        section,
        f"{system} · ПРОИЗВОДСТВЕННЫЙ ЛИСТ",
    )
    row = _write_summary(worksheet, formats, row, section, calc)
    row = _write_diagrams(worksheet, formats, row, section, calc)
    row = _write_section_glass_or_panels(worksheet, formats, row, calc, overrides)
    row = _write_profiles(worksheet, formats, row, calc, overrides)
    row = _write_hardware(worksheet, formats, row, calc, overrides)
    row = _write_extra_components(worksheet, formats, row, section, overrides)
    if hasattr(calc, "torque") and getattr(calc, "torque", None):
        row = _write_bar(worksheet, formats, row, "Расчет привода")
        torque = calc.torque
        values = (
            ("Вес подвижных панелей", f"{format_number(torque.moving_weight_kg)} кг"),
            ("Крутящий момент", f"{format_number(torque.torque_nm)} Н·м"),
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
                "lift_comments",
                getattr(section, "comments", "") or "",
            ),
            formats["cell"],
        )
        row += 5
    if system == "СЛАЙД":
        row = _write_slide_checklist_block(
            worksheet,
            formats,
            row,
            section,
            overrides,
        )
    worksheet.print_area(0, 0, max(row, 1), 11)

    workbook.close()
    return output.getvalue()


def _project_header(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    title: str,
    project: object,
) -> int:
    worksheet.merge_range(0, 0, 2, 3, title.upper(), formats["title"])
    worksheet.merge_range(0, 4, 0, 5, "Заявка", formats["label"])
    worksheet.merge_range(
        0,
        6,
        0,
        7,
        str(getattr(project, "number", "") or ""),
        formats["cell"],
    )
    worksheet.merge_range(1, 4, 1, 5, "Заказчик", formats["label"])
    worksheet.merge_range(
        1,
        6,
        1,
        7,
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
    worksheet.merge_range(
        row,
        0,
        row,
        7,
        "КРОМКИ ПОЛИРОВАННЫЕ. Печать закалки не ставить",
        formats["red"],
    )
    row += 1
    headers = ("№", "Маркировка", "Стекло", "Ширина, мм", "Высота, мм", "Кол-во", "Площадь, м²", "Примечание")
    for column, header in enumerate(headers):
        worksheet.write(row, column, header, formats["header"])
    worksheet.set_row(row, 30)
    row += 1
    for item in context["glass_rows"]:
        values = (
            item["index"],
            item["marking"],
            item["glass_type"],
            item["width"],
            item["height"],
            item["qty"],
            item["area"],
            item["note"],
        )
        for column, value in enumerate(values):
            worksheet.write(
                row,
                column,
                value,
                formats["cell"] if column in {1, 2, 7} else formats["center"],
            )
        worksheet.set_row(row, 34)
        row += 1
    worksheet.merge_range(row, 0, row, 4, "Итого", formats["total"])
    worksheet.write(row, 5, context["glass_total_qty"], formats["total"])
    worksheet.write(row, 6, context["glass_total_area"], formats["total"])
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
        candidate = f"{base[:31 - len(tail)]}{tail}"
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
        )
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
        headers = ("Артикул", "Сечение", "Кол-во", "Чистовые размеры", "С припуском 50 мм", "Общее, м.п.")
        for column, header in enumerate(headers):
            worksheet.write(row, column, header, formats["header"])
        worksheet.set_row(row, 30)
        row += 1

        for group in page["groups"]:
            rows = list(group["rows"])
            if not rows:
                continue
            start = row
            end = row + len(rows) - 1
            if end > start:
                worksheet.merge_range(start, 0, end, 0, group["article"], formats["center_bold"])
                worksheet.merge_range(start, 1, end, 1, group["name"], formats["cell_bottom"])
            else:
                worksheet.write(start, 0, group["article"], formats["center_bold"])
                worksheet.write(start, 1, group["name"], formats["cell_bottom"])
            for item in rows:
                worksheet.write(row, 2, item["qty"], formats["center"])
                worksheet.write(row, 3, item["clean"], formats["center"])
                worksheet.write(row, 4, item["allowance"], formats["center"])
                worksheet.write(row, 5, item["total_m"], formats["center"])
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
            if group.get("note"):
                worksheet.write_comment(
                    start,
                    1,
                    str(group["note"]),
                    {"author": "Raluma"},
                )
        worksheet.merge_range(row, 0, row, 1, "Итого", formats["total"])
        worksheet.write(row, 2, page["total_qty"], formats["total"])
        worksheet.write_blank(row, 3, None, formats["total"])
        worksheet.write_blank(row, 4, None, formats["total"])
        worksheet.write(row, 5, page["total_m"], formats["total"])
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
    raise ValueError("Excel export is available only for glass and paint documents")
