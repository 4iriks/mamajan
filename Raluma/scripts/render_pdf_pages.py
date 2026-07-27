"""Render every PDF page to PNG for local visual QA."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(args.input_pdf)
    zoom = args.dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for index, page in enumerate(document, start=1):
        output = args.output_dir / f"page-{index}.png"
        page.get_pixmap(matrix=matrix, alpha=False).save(output)
        print(output)


if __name__ == "__main__":
    main()
