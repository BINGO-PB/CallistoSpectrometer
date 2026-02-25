"""docs/conf.py

Sphinx configuration for the Callisto documentation.

This configuration assumes MyST Markdown as the primary markup and
enables basic API documentation for the hexagonal architecture
(`domain`, `application`, `ports`, `adapters`).

Copyright BINGO Collaboration
Last modified: 2026-02-25
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

project = "Callisto"
author = "BINGO Collaboration"
current_year = datetime.utcnow().year
copyright = f"{current_year}, BINGO Collaboration"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

autosummary_generate = True

templates_path = ["_templates"]
exclude_patterns: list[str] = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

source_suffix = {
    ".md": "markdown",
}

master_doc = "index"
