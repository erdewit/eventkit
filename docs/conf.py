extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',
    ]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = 'eventkit'
copyright = '2021, Ewald de Wit'
author = 'Ewald de Wit'

__version__ = None
exec(open('../eventkit/version.py').read())
version = '.'.join(__version__.split('.')[:2])
release = __version__

language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = False
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'canonical_url': 'https://eventkit.readthedocs.io',
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    # Toc options
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}
github_url = 'https://github.com/erdewit/eventkit'

autoclass_content = 'both'
autodoc_member_order = "bysource"
autodoc_default_flags = [
    'members',
    'undoc-members',
    ]
