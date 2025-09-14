# Sphinx configuration for the DQ Workbench slides (Reveal.js via sphinxjp theme)

project = 'DQ Workbench — Key Features'
author = 'DQ Workbench Team'

extensions = [
    'sphinx_revealjs',
]

templates_path = ['_templates']
exclude_patterns = ['_build']

html_static_path = ['_static', '../_static']

# Reveal.js look-and-feel (dark theme)
# Valid theme names include: black, white, league, beige, sky, night, serif, simple, solarized
revealjs_style_theme = 'moon'

# Build this single deck from index.rst
revealjs_documents = [
    (
        'index',            # source rst (without suffix)
        'index.html',       # output filename
        project,            # title
        author,             # author
        revealjs_style_theme,
    ),
]

# Reveal.js runtime options (see https://revealjs.com/config/)
revealjs_script_conf = {
    'controls': True,
    'progress': True,
    'slideNumber': True,
    'hash': True,
    'center': True,
}

# Optional: enable speaker notes if you add notes to slides
revealjs_script_plugins = [
    {
        'name': 'RevealNotes',
        'src': 'revealjs/plugin/notes/notes.js',
    }
]
