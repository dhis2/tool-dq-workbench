# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'dq-workbench'
copyright = '2025, University of Oslo'
author = 'Jason P. Pickering'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']

# -- Options for LaTeX/PDF output -------------------------------------------
# Improve code-block rendering in PDFs by enabling line wrapping for verbatim.
latex_elements = {
    # Wrap long lines in verbatim/code blocks to avoid overflow
    'sphinxsetup': 'verbatimwrapslines=true, verbatimforcewraps=true, verbatimmaxoverfull=0',
}
