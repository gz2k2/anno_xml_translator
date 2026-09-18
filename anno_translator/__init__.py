"""Anno XML Translator package.

Exposes the version constant so tooling (and PyInstaller) can resolve the
package without importing the GUI layer.
"""

from anno_translator.version import APP_VERSION

__all__ = ["APP_VERSION"]
