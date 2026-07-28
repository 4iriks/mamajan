"""Generate representative Office documents for visual QA."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SECRET_KEY", "local-office-qa-key")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/raluma-office-qa.db")

from main import app  # noqa: E402


SLIDE_SECTION = {
    "name": "Секция 1",
    "system": "СЛАЙД",
    "width": 4850,
    "height": 2780,
    "panels": 6,
    "quantity": 2,
    "rails": 5,
    "slide_rows": 2,
    "threshold": "Накладной окраш",
    "painting_type": "RAL нестандарт",
    "ral_color": "7016 МУАР",
    "glass_type": "10ММ БРОНЗА В МАССЕ",
    "first_panels": "В центре",
    "inter_glass_profile": "Алюминиевый RS2061",
    "profile_left_wall": True,
    "profile_right_wall": True,
    "profile_left_handle_bar": True,
    "profile_right_handle_bar": True,
    "handle_left": "Ручка-кноб RS3014",
    "handle_right": "Ручка-кноб RS3014",
    "central_handle_left": "Ручка-кноб RS3014",
    "central_handle_right": "Ручка-кноб RS3014",
    "comments": (
        "Проверить цвет перед запуском. Комплектовать секции отдельно "
        "и приложить маркировку."
    ),
    "extra_components": json.dumps(
        [
            {
                "article": "EXTRA-1",
                "name": "Дополнительный уголок по ТЗ",
                "color": "RAL 7016",
                "size": "120",
                "qty": "4",
            }
        ],
        ensure_ascii=False,
    ),
}

LIFT_SECTION = {
    "name": "Секция 2",
    "order": 2,
    "system": "ЛИФТ",
    "width": 3043,
    "height": 3300,
    "panels": 4,
    "quantity": 1,
    "painting_type": "RAL стандарт",
    "ral_color": "9003 ГЛЯНЦЕВЫЙ",
    "lift_filling_type": "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
    "lift_control_type": "Пульт ДУ",
    "lift_remote_1ch_qty": 2,
    "lift_remote_6ch_qty": 1,
    "lift_cable_side": "Слева",
    "lift_opening_type": "Верх/низ глухие, сдвиг вниз",
    "comments": "Перед упаковкой проверить ход каждой панели и привод.",
}

PROJECT = {
    "number": "QA-OFFICE-2026",
    "customer": "ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ",
    "paint_manual_rows": json.dumps(
        [
            {
                "color": "RAL 7016 МУАР",
                "article": "MAN-7016",
                "name": "Ручная деталь с нестандартной обработкой",
                "qty": 2,
                "clean": 1450,
                "allowance": 1500,
                "totalM": 3.0,
                "note": "Проверить образец цвета",
            },
            {
                "color": "RAL 9003 ГЛЯНЦЕВЫЙ",
                "article": "MAN-9003",
                "name": "Дополнительная ручка",
                "qty": 1,
                "clean": 600,
                "allowance": 650,
                "totalM": 0.65,
            },
        ],
        ensure_ascii=False,
    ),
}


def _download(client: TestClient, path: str, payload: dict, target: Path) -> None:
    response = client.post(path, json=payload)
    response.raise_for_status()
    target.write_bytes(response.content)
    print(f"{target.name}: {len(response.content)} bytes")


def main() -> None:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "office-qa")
    output_dir.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as client:
        for file_format in ("docx", "xlsx"):
            _download(
                client,
                f"/api/projects/local/sections/{file_format}",
                {"project": PROJECT, "section": SLIDE_SECTION},
                output_dir / f"01-slide-production-sheet.{file_format}",
            )
            _download(
                client,
                f"/api/projects/local/sections/{file_format}",
                {"project": PROJECT, "section": LIFT_SECTION},
                output_dir / f"02-lift-production-sheet.{file_format}",
            )
            _download(
                client,
                f"/api/projects/local/documents/glass/{file_format}",
                {
                    "project": PROJECT,
                    "sections": [SLIDE_SECTION, LIFT_SECTION],
                },
                output_dir / f"03-glass-order.{file_format}",
            )
            _download(
                client,
                f"/api/projects/local/documents/paint/{file_format}",
                {
                    "project": PROJECT,
                    "sections": [SLIDE_SECTION, LIFT_SECTION],
                },
                output_dir / f"04-paint-request.{file_format}",
            )


if __name__ == "__main__":
    main()
