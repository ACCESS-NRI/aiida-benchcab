# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import pathlib
import sys

import aiida
import aiida.storage.sqlite_temp

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

with (pathlib.Path(__file__).parent.parent / "pyproject.toml").open("rb") as f:
    pyproject_data = tomllib.load(f)

temp_profile = aiida.storage.sqlite_temp.SqliteTempBackend.create_profile(
    "temp-profile"
)
aiida.load_profile(temp_profile, allow_switch=True)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
project = pyproject_data["project"]["name"]
author = ", ".join(author["name"] for author in pyproject_data["project"]["authors"])
copyright = f"{datetime.datetime.now().year}, {author}"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx_design",
    "sphinx_click",
    "aiida.sphinxext",
    "myst_parser",
]

# myst-parser configuration
# https://myst-parser.readthedocs.io/en/latest/configuration.html
myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence"]

# default theme configuration
# https://alabaster.readthedocs.io/en/latest/customization.html
html_theme_options = {
    "github_user": "ACCESS-NRI",
    "github_repo": "aiida-benchcab",
}
