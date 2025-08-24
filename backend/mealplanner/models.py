"""Compatibility wrapper for the relocated ``models`` module.

Historically the models lived under a top-level ``backend`` package.
When running code from within the backend directory directly that package
name is not available which resulted in ``ModuleNotFoundError`` during
tests.  Import the module directly so it works in both layouts.
"""

import sys as _sys

# Import the ``models`` module relative to the current package to avoid
# depending on the ``backend`` package name being on ``PYTHONPATH``.
import models as _models

# Re-export for backwards compatibility so ``mealplanner.models`` behaves
# like the original module.
_sys.modules[__name__] = _models
