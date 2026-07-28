"""Editable Word exports for production sheets and project documents."""

from __future__ import annotations

import io
from typing import Any, Iterable

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from engine.office_common import (
    BLACK,
    BRAND_DARK,
    HEADER_GRAY,
    RED,
    WHITE,
    format_number,
    image_stream,
    load_overrides,
    override_value,
)
from engine.office_diagrams import section_diagrams
from engine.office_section_data import (
    hardware_rows,
    profile_rows,
    section_summary_rows,
)
from engine.pdf import section_extra_components
from engine.project_documents import build_project_document_context


CHECKLIST_ROWS = [
    ("1", "Нарезка профиля по ТЗ", ""),
    ("2", "Фрезеровка профиля-замка под защелку (при наличии)", "Проверить сторону"),
    ("2", "Фрезеровка пазов в П-профиле и профиле-замке (при наличии)", ""),
    ("3", "Рассверловка боковых пристеночных профилей", "Под низкий порог снизу не сверлится"),
    ("3", "Рассверловка порога", ""),
    ("4", "Установка роликов и заглушек на стекольный профиль", ""),
    ("4", "Установка фетрового уплотнения в верхний направляющий профиль", "7×6"),
    ("4", "Установка фетрового уплотнения в профиль-ручку", "7×6 + приклеить фетр к профилю"),
    ("4", "Установка фетрового уплотнения в межстворочный профиль", "7×12 + приклеить фетр к профилю"),
    ("5", "Склеить панели по ТЗ", ""),
    ("6", "Сборка фурнитуры по ТЗ", ""),
    ("6", "Сборка дополнительной фурнитуры по накладной", ""),
    ("7", "Оклейка всех профилей пленкой «Ралюма»", ""),
    ("7", "Упаковка панелей в пузырьковую пленку и картон", ""),
]


def _set_landscape(section) -> None:
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Mm(297)
    section.page_height = Mm(210)
    section.top_margin = Mm(7)
    section.bottom_margin = Mm(7)
    section.left_margin = Mm(7)
    section.right_margin = Mm(7)


def _set_portrait(section) -> None:
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(12)
    section.bottom_margin = Mm(12)
    section.left_margin = Mm(12)
    section.right_margin = Mm(12)


def _set_cell_shading(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def _set_cell_margins(cell, top=60, start=80, bottom=60, end=80) -> None:
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_repeat_header(row) -> None:
    properties = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    properties.append(repeat)


def _prevent_row_split(row) -> None:
    properties = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    properties.append(cant_split)


def _set_cell_text(
    cell,
    value: Any,
    *,
    bold: bool = False,
    size: float = 8,
    color: str = BLACK,
    align: WD_ALIGN_PARAGRAPH | None = None,
) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run(str(value if value is not None else ""))
    run.bold = bold
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_margins(cell)


def _style_table(table, header_rows: int = 1) -> None:
    table.style = "Table Grid"
    table.autofit = True
    for row_index, row in enumerate(table.rows):
        _prevent_row_split(row)
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        if row_index < header_rows:
            _set_repeat_header(row)
            for cell in row.cells:
                _set_cell_shading(cell, HEADER_GRAY)
                for run in cell.paragraphs[0].runs:
                    run.bold = True


def _configure_document(document: Document, *, landscape: bool) -> None:
    if landscape:
        _set_landscape(document.sections[0])
    else:
        _set_portrait(document.sections[0])
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(8)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.space_before = Pt(0)


def _add_bar(document: Document, text: str) -> None:
    table = document.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    _set_cell_text(cell, text.upper(), bold=True, size=9, color=WHITE)
    _set_cell_shading(cell, BRAND_DARK)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def _add_header(document: Document, project: object, section: object, label: str) -> None:
    table = document.add_table(rows=1, cols=3)
    values = (
        f"ПРОЕКТ № {getattr(project, 'number', '')}",
        str(getattr(section, "name", "") or "Секция"),
        label,
    )
    for index, value in enumerate(values):
        _set_cell_text(
            table.cell(0, index),
            value,
            bold=True,
            size=10,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    table.style = "Table Grid"


def _add_picture(cell, data: bytes | io.BytesIO | None, width_mm: float) -> None:
    if not data:
        return
    stream = data if isinstance(data, io.BytesIO) else io.BytesIO(data)
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(0)
    try:
        paragraph.add_run().add_picture(stream, width=Mm(width_mm))
    except Exception:
        return


def _add_summary(document: Document, section: object, calc: object) -> None:
    rows = section_summary_rows(section, calc)
    columns = 2
    table = document.add_table(rows=ceil_div(len(rows), columns), cols=4)
    for index, (label, value) in enumerate(rows):
        row = index // columns
        pair = index % columns
        _set_cell_text(table.cell(row, pair * 2), label, bold=True, size=7.5)
        _set_cell_text(table.cell(row, pair * 2 + 1), value, size=8)
        _set_cell_shading(table.cell(row, pair * 2), HEADER_GRAY)
    table.style = "Table Grid"


def ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor


def _add_diagrams(document: Document, section: object, calc: object) -> None:
    diagrams = section_diagrams(section, calc)
    first = diagrams[:2]
    table = document.add_table(rows=1, cols=len(first))
    for index, (title, data) in enumerate(first):
        cell = table.cell(0, index)
        _set_cell_text(
            cell,
            title,
            bold=True,
            size=8,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
        paragraph = cell.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(
            io.BytesIO(data),
            width=Mm(128 if len(first) == 2 else 255),
        )
    table.style = "Table Grid"

    for title, data in diagrams[2:]:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(title.upper())
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(8)
        picture = document.add_paragraph()
        picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture.add_run().add_picture(io.BytesIO(data), width=Mm(255))


def _add_slide_glass(document: Document, calc: object, overrides: dict[str, Any]) -> None:
    _add_bar(document, "Стекла")
    table = document.add_table(rows=1, cols=5)
    headers = ("Позиция", "Ширина, мм", "Высота, мм", "Кол-во, шт", "RS2021, мм")
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for index, glass in enumerate(getattr(calc, "glass", None) or []):
        if int(getattr(glass, "qty", 0) or 0) <= 0:
            continue
        row = table.add_row()
        values = (
            glass.position,
            override_value(overrides, f"glass_{index}_w", format_number(glass.width_mm)),
            override_value(overrides, f"glass_{index}_h", format_number(glass.height_mm)),
            override_value(overrides, f"glass_{index}_q", glass.qty),
            format_number(glass.glass_profile_length),
        )
        for column, value in enumerate(values):
            _set_cell_text(
                row.cells[column],
                value,
                align=WD_ALIGN_PARAGRAPH.CENTER if column else None,
            )
    _style_table(table)


def _add_lift_panels(document: Document, calc: object, overrides: dict[str, Any]) -> None:
    _add_bar(document, "Заполнение и панели при склейке")
    table = document.add_table(rows=1, cols=7)
    headers = (
        "№",
        "Панель",
        "Заполнение",
        "Ширина, мм",
        "Высота, мм",
        "Склейка, мм",
        "Кол-во",
    )
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for panel in getattr(calc, "panels", None) or []:
        row = table.add_row()
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
                f"{format_number(panel.glued_width_mm)} × {format_number(panel.glued_height_mm)}",
            ),
            override_value(
                overrides,
                f"lift_panel_{panel.panel}_qty",
                panel.qty,
            ),
        )
        for column, value in enumerate(values):
            _set_cell_text(
                row.cells[column],
                value,
                align=WD_ALIGN_PARAGRAPH.CENTER if column != 2 else None,
            )
    _style_table(table)


def _add_profiles(document: Document, calc: object, overrides: dict[str, Any]) -> None:
    _add_bar(document, "Нарезка профилей")
    table = document.add_table(rows=1, cols=6)
    headers = ("Сечение", "Артикул", "Наименование / операция", "Длина, мм", "Кол-во", "Примечание")
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    for index, profile in enumerate(profile_rows(calc)):
        cuts = list(getattr(profile, "display_cuts", None) or [])
        if not cuts:
            cuts = [
                {
                    "length": getattr(profile, "length_mm", 0),
                    "qty": getattr(profile, "qty", 0),
                    "length_field": getattr(profile, "field_key", "") or f"profile_{index}_length",
                    "qty_field": (getattr(profile, "field_key", "") or f"profile_{index}") + "_qty",
                }
            ]
        for cut_index, cut in enumerate(cuts):
            row = table.add_row()
            if cut_index == 0:
                _add_picture(
                    row.cells[0],
                    image_stream(getattr(profile, "image", None), max_size=(600, 260)),
                    23,
                )
                _set_cell_text(row.cells[1], getattr(profile, "article", ""), bold=True)
                _set_cell_text(row.cells[2], getattr(profile, "name", ""))
                _set_cell_text(row.cells[5], getattr(profile, "note", ""), size=7)
            length = ""
            if str(getattr(profile, "article", "")).upper() != "RS3110":
                length = override_value(
                    overrides,
                    str(cut.get("length_field") or ""),
                    format_number(cut.get("length")),
                )
            qty = override_value(
                overrides,
                str(cut.get("qty_field") or ""),
                cut.get("qty", 0),
            )
            _set_cell_text(row.cells[3], length, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(row.cells[4], qty, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style_table(table)


def _add_hardware(document: Document, calc: object, overrides: dict[str, Any]) -> None:
    _add_bar(document, "Фурнитура и крепеж")
    table = document.add_table(rows=1, cols=6)
    headers = ("Изображение", "Артикул", "Наименование", "Кол-во", "Ед.", "Примечание")
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for article, name, value, unit, image, field_key, note in hardware_rows(calc):
        row = table.add_row()
        _add_picture(row.cells[0], image_stream(image, max_size=(500, 260)), 20)
        _set_cell_text(row.cells[1], article, bold=True)
        _set_cell_text(row.cells[2], name)
        _set_cell_text(
            row.cells[3],
            override_value(overrides, field_key, format_number(value)),
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
        _set_cell_text(row.cells[4], unit, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(row.cells[5], note, size=7)
    _style_table(table)


def _add_extra_components(document: Document, section: object, overrides: dict[str, Any]) -> None:
    rows = section_extra_components(section, overrides)
    if not rows:
        return
    _add_bar(document, "Дополнительные комплектующие")
    table = document.add_table(rows=1, cols=5)
    headers = ("Артикул", "Название", "Размер", "Кол-во", "Цвет")
    for index, header in enumerate(headers):
        _set_cell_text(table.cell(0, index), header, bold=True)
    for item in rows:
        row = table.add_row()
        for index, key in enumerate(("art", "name", "size", "qty", "color")):
            _set_cell_text(row.cells[index], item.get(key, ""))
    _style_table(table)


def _add_slide_checklist(
    document: Document,
    project: object,
    section: object,
    overrides: dict[str, Any],
) -> None:
    document.add_page_break()
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(
        f"ПРОЕКТ № {getattr(project, 'number', '')} — "
        f"{getattr(section, 'name', '')}"
    )
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(15)
    table = document.add_table(rows=1, cols=5)
    headers = ("№ п/п", "Отм. пр-ва", "Действие", "Примечание", "Отм. ОТК")
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for number, action, note in CHECKLIST_ROWS:
        row = table.add_row()
        values = (number, "☐", action, note, "☐")
        for index, value in enumerate(values):
            _set_cell_text(
                row.cells[index],
                value,
                size=8,
                align=WD_ALIGN_PARAGRAPH.CENTER if index in {0, 1, 4} else None,
            )
    _style_table(table)
    _add_bar(document, "Примечания и особые отметки при производстве или проверке ОТК")
    comments_table = document.add_table(rows=1, cols=1)
    comments = override_value(overrides, "section_comments", getattr(section, "comments", "") or "")
    _set_cell_text(comments_table.cell(0, 0), comments, bold=True, size=11)
    comments_table.rows[0].height = Mm(38)
    comments_table.style = "Table Grid"

    _add_bar(document, "Ответственные за заказ на производстве")
    people = document.add_table(rows=4, cols=4)
    labels = ("Нарезка", "Поклейка", "Упаковка", "Сборка", "Поклейка", "Комплектация", "Упаковка", "")
    for index, label in enumerate(labels):
        row, pair = divmod(index, 2)
        _set_cell_text(people.cell(row, pair * 2), label)
        _set_cell_text(people.cell(row, pair * 2 + 1), "")
    people.style = "Table Grid"


def build_section_docx(project: object, section: object, calc: object) -> bytes:
    document = Document()
    _configure_document(document, landscape=True)
    system = str(getattr(section, "system", "") or "").strip().upper()
    label = "ЛИФТ · ПРОИЗВОДСТВЕННЫЙ ЛИСТ" if system == "ЛИФТ" else "СЛАЙД · ПРОИЗВОДСТВЕННЫЙ ЛИСТ"
    overrides = load_overrides(section)
    _add_header(document, project, section, label)
    _add_summary(document, section, calc)
    _add_diagrams(document, section, calc)
    if system == "ЛИФТ":
        _add_lift_panels(document, calc, overrides)
        document.add_page_break()
        _add_header(document, project, section, "ЛИФТ · НАРЕЗКА И КОМПЛЕКТАЦИЯ")
    else:
        _add_slide_glass(document, calc, overrides)
    _add_profiles(document, calc, overrides)
    _add_hardware(document, calc, overrides)
    _add_extra_components(document, section, overrides)

    if system == "ЛИФТ":
        if getattr(calc, "torque", None):
            _add_bar(document, "Расчет привода")
            torque = calc.torque
            table = document.add_table(rows=2, cols=3)
            values = (
                ("Вес подвижных панелей", f"{format_number(torque.moving_weight_kg)} кг"),
                ("Крутящий момент", f"{format_number(torque.torque_nm)} Н·м"),
                ("Количество приводов", f"{torque.drive_count} шт"),
            )
            for index, (label_text, value) in enumerate(values):
                _set_cell_text(table.cell(0, index), label_text, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
                _set_cell_text(table.cell(1, index), value, bold=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
            table.style = "Table Grid"
        _add_bar(document, "Примечания и особые отметки")
        notes = document.add_table(rows=1, cols=1)
        _set_cell_text(
            notes.cell(0, 0),
            override_value(overrides, "lift_comments", getattr(section, "comments", "") or ""),
            bold=True,
            size=10,
        )
        notes.rows[0].height = Mm(30)
        notes.style = "Table Grid"
    else:
        _add_slide_checklist(document, project, section, overrides)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _project_header(document: Document, title: str, project: object) -> None:
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).merge(table.cell(1, 0))
    _set_cell_text(table.cell(0, 0), title.upper(), bold=True, size=20)
    _set_cell_text(table.cell(0, 1), "Заявка", bold=True, size=8)
    table.cell(0, 1).add_paragraph(str(getattr(project, "number", "") or ""))
    _set_cell_text(table.cell(1, 1), f"Заказчик: {getattr(project, 'customer', '')}", size=8)
    table.style = "Table Grid"


def _build_glass_docx(context: dict) -> bytes:
    document = Document()
    _configure_document(document, landscape=False)
    _project_header(document, "Заказ стекла", context["project"])
    paragraph = document.add_paragraph()
    run = paragraph.add_run("КРОМКИ ПОЛИРОВАННЫЕ. Печать закалки не ставить")
    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string(RED)

    table = document.add_table(rows=1, cols=8)
    headers = ("№", "Маркировка", "Стекло", "Ширина, мм", "Высота, мм", "Кол-во", "Площадь, м²", "Примечание")
    for index, header in enumerate(headers):
        _set_cell_text(
            table.cell(0, index),
            header,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for row_data in context["glass_rows"]:
        row = table.add_row()
        values = (
            row_data["index"],
            row_data["marking"],
            row_data["glass_type"],
            row_data["width"],
            row_data["height"],
            row_data["qty"],
            f"{row_data['area']:.3f}",
            row_data["note"],
        )
        for index, value in enumerate(values):
            _set_cell_text(
                row.cells[index],
                value,
                size=7.5,
                align=WD_ALIGN_PARAGRAPH.CENTER if index != 2 else None,
            )
    total = table.add_row()
    total.cells[0].merge(total.cells[4])
    _set_cell_text(total.cells[0], "Итого", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    _set_cell_text(total.cells[5], context["glass_total_qty"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(total.cells[6], f"{context['glass_total_area']:.3f}", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style_table(table)

    quality = document.add_paragraph()
    quality.paragraph_format.space_before = Pt(8)
    quality_run = quality.add_run(
        "ОБРАЩАЮ ВНИМАНИЕ НА ПОВЫШЕННОЕ КАЧЕСТВО ИЗДЕЛИЙ\n"
        "Т.К. ФИРМА ИЗГОТАВЛИВАЕТ БЕЗРАМНОЕ ОСТЕКЛЕНИЕ\n"
        "ПЕРЕКОС ДИАГОНАЛИ НЕ ДОЛЖЕН ПРЕВЫШАТЬ 1-2ММ\n"
        "ГАБАРИТЫ СТЕКЛА НЕ ДОЛЖНЫ ПРЕВЫШАТЬ 2ММ"
    )
    quality_run.bold = True
    quality_run.font.name = "Arial"
    quality_run.font.size = Pt(10)
    quality_run.font.color.rgb = RGBColor.from_string(RED)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _build_paint_docx(context: dict) -> bytes:
    document = Document()
    _configure_document(document, landscape=False)
    pages = context["paint_pages"]
    if not pages:
        _project_header(document, "Заявка на покраску", context["project"])
        document.add_paragraph("В проекте нет окрашиваемых профилей.")
    for page_index, page in enumerate(pages):
        if page_index:
            document.add_page_break()
        _project_header(document, "Заявка на покраску", context["project"])
        color = document.add_paragraph()
        color.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = color.add_run(f"Цвет: {page['color']}")
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor.from_string(RED)
        warning = document.add_paragraph()
        warning.alignment = WD_ALIGN_PARAGRAPH.CENTER
        warning_run = warning.add_run("В СЧЕТЕ УКАЗАТЬ НОМЕР ЗАЯВКИ И ЦВЕТ ПРОФИЛЯ")
        warning_run.bold = True
        warning_run.font.name = "Arial"
        warning_run.font.size = Pt(9)
        warning_run.font.color.rgb = RGBColor.from_string(RED)

        table = document.add_table(rows=1, cols=6)
        headers = ("Артикул", "Сечение", "Кол-во", "Чистовые размеры", "С припуском 50 мм", "Общее, м.п.")
        for index, header in enumerate(headers):
            _set_cell_text(
                table.cell(0, index),
                header,
                bold=True,
                align=WD_ALIGN_PARAGRAPH.CENTER,
            )
        for group in page["groups"]:
            start = len(table.rows)
            for row_data in group["rows"]:
                row = table.add_row()
                _set_cell_text(row.cells[0], group["article"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
                _set_cell_text(row.cells[1], group["name"], size=7.5)
                _set_cell_text(row.cells[2], row_data["qty"], align=WD_ALIGN_PARAGRAPH.CENTER)
                _set_cell_text(row.cells[3], format_number(row_data["clean"]), align=WD_ALIGN_PARAGRAPH.CENTER)
                _set_cell_text(row.cells[4], format_number(row_data["allowance"]), align=WD_ALIGN_PARAGRAPH.CENTER)
                _set_cell_text(row.cells[5], f"{row_data['total_m']:.1f}".replace(".", ","), align=WD_ALIGN_PARAGRAPH.CENTER)
            end = len(table.rows) - 1
            article_cell = table.cell(start, 0)
            image_cell = table.cell(start, 1)
            if end > start:
                article_cell = article_cell.merge(table.cell(end, 0))
                image_cell = image_cell.merge(table.cell(end, 1))
            _set_cell_text(article_cell, group["article"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(image_cell, group["name"], size=7.5, align=WD_ALIGN_PARAGRAPH.CENTER)
            if group.get("note"):
                note = image_cell.add_paragraph(str(group["note"]))
                note.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in note.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor.from_string(RED)
                    run.font.size = Pt(8)
            source = image_stream(
                group.get("image"),
                group.get("image_data"),
                max_size=(700, 450),
            )
            _add_picture(image_cell, source, 37)

        total = table.add_row()
        total.cells[0].merge(total.cells[1])
        _set_cell_text(total.cells[0], "Итого", bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell_text(total.cells[2], page["total_qty"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(total.cells[5], f"{page['total_m']:.1f}".replace(".", ","), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _style_table(table)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def build_project_docx(
    project: object,
    sections: Iterable[object],
    doc_type: str,
) -> bytes:
    context = build_project_document_context(project, sections, doc_type)
    if doc_type == "glass":
        return _build_glass_docx(context)
    if doc_type == "paint":
        return _build_paint_docx(context)
    raise ValueError("Word export is available only for glass and paint documents")
