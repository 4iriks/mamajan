"""Render every PDF in a directory to PNG pages for visual QA."""

from __future__ import annotations

import sys
from pathlib import Path

import fitz


def main() -> None:
    directory = Path(sys.argv[1])
    for pdf_path in sorted(directory.glob("*.pdf")):
        document = fitz.open(pdf_path)
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            output = directory / f"render-{pdf_path.stem}-p{index + 1}.png"
            pixmap.save(output)
            print(output.name)


if __name__ == "__main__":
    main()
