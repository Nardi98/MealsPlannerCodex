"""Compatibility wrapper for the relocated CRUD utilities.

As with the other compatibility modules, importing ``crud`` via the old
``backend`` package name fails when the backend directory is executed
directly. Import the module without the package prefix so it works in
both scenarios.
"""

import sys as _sys

# Import the ``crud`` module directly to avoid dependence on a ``backend``
# package existing on the ``PYTHONPATH``.
import crud as _crud

# Re-export under ``mealplanner.crud`` for backwards compatibility.
_sys.modules[__name__] = _crud
