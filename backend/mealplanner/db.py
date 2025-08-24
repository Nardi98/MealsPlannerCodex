"""Compatibility wrapper for the relocated ``database`` module.

The original project structure exposed the database utilities from a
top-level ``backend`` package.  When running the tests inside the backend
directory, that package name no longer exists on ``PYTHONPATH`` which led
to ``ModuleNotFoundError: No module named 'backend'`` during imports.

Import the module using a direct import so it works regardless of whether
the code is executed from the repository root or from within the backend
directory.
"""

import sys as _sys

# Import the ``database`` module relative to the current package.  This
# avoids relying on the presence of a top-level ``backend`` package name.
import database as _database

# Re-export the ``database`` module under ``mealplanner.db`` for backwards
# compatibility with existing imports.
_sys.modules[__name__] = _database
