"""RecordorAI Installer — cross-platform install + integration wizard.

Public API surface:

    from recordorai_installer import detect, plan, exec_, adapters
    from recordorai_installer.core.detect import detect_environment
    from recordorai_installer.core.plan import build_plan, Choices
    from recordorai_installer.core.exec import execute

The package has zero side-effects on import. Heavy operations live
behind explicit calls.
"""

from .version import __version__

__all__ = ["__version__"]
