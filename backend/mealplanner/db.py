"""Compatibility wrappers for moved database module."""
from backend import database as _database
import sys as _sys

_sys.modules[__name__] = _database
