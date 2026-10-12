"""Windows adapter for the canonical DOCX renderer (console LO waits for export).

Use an isolated task-local or bundled LibreOffice, never a running desktop profile.
All layout/rasterization remains in the canonical render_docx.py.
"""
import argparse
import importlib.util
from pathlib import Path
import sys

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--renderer", required=True)
parser.add_argument("--libreoffice", required=True)
args, remaining = parser.parse_known_args()
binary = Path(args.libreoffice).resolve(strict=True)
spec = importlib.util.spec_from_file_location("canonical_docx_renderer", args.renderer)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._resolve_soffice = lambda: str(binary)
sys.argv = [args.renderer, *remaining]
module.main()
