"""MkDocs hooks for the public docs (mkdocs.yml -> hooks).

mkdocs-static-i18n builds the Spanish site by calling build() again from its
own post-build hook, with the same config and the same site_dir. The llmstxt
plugin would run in that second pass too and overwrite the English llms.txt
and llms-full.txt with empty ones, since the sections name the English pages.
So llms.txt describes the English site only, and the plugin sits out every
other language's pass.
"""


def on_pre_build(config):
    i18n = config.plugins.get("i18n")
    llmstxt = config.plugins.get("llmstxt")
    if i18n is None or llmstxt is None or i18n.is_default_language_build:
        return
    for methods in config.plugins.events.values():
        methods[:] = [m for m in methods if getattr(m, "__self__", None) is not llmstxt]
