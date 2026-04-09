from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
PROJECT_TOML = ROOT / "pyproject.toml"

sys.path.insert(0, str(ROOT))

project = "APEM"
author = "APEM Contributors"
release = "0.1.0"

if PROJECT_TOML.exists():
    try:
        data = tomllib.loads(PROJECT_TOML.read_text(encoding="utf-8"))
        project = data.get("project", {}).get("name", project)
        release = data.get("project", {}).get("version", release)
    except Exception:
        pass

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autoclass_content = "both"
autodoc_typehints = "description"
add_module_names = False
python_maximum_signature_line_length = 88

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}

# Keep docs builds working in environments without solver/geospatial stacks.
autodoc_mock_imports = [
    "gurobipy",
    "pypsa",
    "geopandas",
    "shapely",
    "matplotlib",
    "matplotlib.pyplot",
    "openpyxl",
    "OMIEData",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

html_theme = "sphinx_book_theme"
html_title = project
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "show_toc_level": 2,
    "use_repository_button": False,
    "show_navbar_depth": 1,
    "max_navbar_depth": 6,
    "collapse_navbar": False,
}
