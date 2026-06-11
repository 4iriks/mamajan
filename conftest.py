import os
import sys


BACKEND_DIR = os.path.join(os.path.dirname(__file__), "Raluma", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tests.conftest import admin_headers, client, project, section  # noqa: E402,F401
