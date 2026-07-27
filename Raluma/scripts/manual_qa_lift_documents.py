"""Generate representative LIFT documents and render every PDF page to PNG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import fitz


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from engine.lift_calc import calculate_lift  # noqa: E402
from engine.pdf import generate_pdf, render_pdf_html, render_preview  # noqa: E402
from engine.project_documents import render_project_document_html  # noqa: E402
from schemas import SectionCreate  # noqa: E402


def _section() -> SimpleNamespace:
    values = SectionCreate(
        name="Секция 4",
        system="ЛИФТ",
        width=3043,
        height=3300,
        panels=4,
        quantity=1,
        painting_type="RAL стандарт",
        ral_color="7016 МУАР",
        lift_filling_type="СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
        lift_control_type="Пульт ДУ",
        lift_remote_1ch_qty=2,
        lift_remote_6ch_qty=1,
        lift_cable_side="Слева",
        lift_opening_type="Верх/низ глухие, сдвиг вниз",
        comments="Проверить ввод кабеля слева.\nПанели упаковать раздельно.",
    ).model_dump()
    values.update(
        id=4,
        project_id=1,
        order=4,
        document_overrides="{}",
    )
    return SimpleNamespace(**values)


def _project() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        number="LIFT-QA-001",
        customer="ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ",
        glass_status="Заказано",
        delivery_note_data=json.dumps(
            {"includeGlass": True, "places": {}},
            ensure_ascii=False,
        ),
        paint_manual_rows=json.dumps(
            [
                {
                    "article": "RL-X",
                    "name": "Нестандартная деталь ЛИФТ",
                    "color": "7016 МУАР",
                    "qty": 2,
                    "clean": 850,
                    "allowance": 900,
                }
            ],
            ensure_ascii=False,
        ),
    )


def _write_document(
    output_dir: Path,
    name: str,
    html: str,
) -> None:
    html_path = output_dir / f"{name}.html"
    pdf_path = output_dir / f"{name}.pdf"
    html_path.write_text(html, encoding="utf-8")
    try:
        pdf_path.write_bytes(generate_pdf(html))
    except ModuleNotFoundError as exc:
        if exc.name != "weasyprint":
            raise
        print(f"{name}: HTML ready; WeasyPrint is not installed")
        return

    document = fitz.open(pdf_path)
    for page_index, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(output_dir / f"{name}-page-{page_index}.png")
    print(f"{name}: {len(document)} page(s)")


def generate_documents(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    project = _project()
    section = _section()
    calc = calculate_lift(section)

    (output_dir / "production-preview.html").write_text(
        render_preview(project, section, calc),
        encoding="utf-8",
    )
    _write_document(
        output_dir,
        "production",
        render_pdf_html(project, section, calc),
    )
    for doc_type in ("paint", "glass", "delivery"):
        _write_document(
            output_dir,
            doc_type,
            render_project_document_html(
                project,
                [section],
                doc_type,
                is_pdf=True,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("C:/tmp/raluma-lift-documents"),
    )
    args = parser.parse_args()
    generate_documents(args.output)


if __name__ == "__main__":
    main()
