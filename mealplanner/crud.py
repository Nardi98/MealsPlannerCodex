"""Compatibility wrapper for moved CRUD module."""
from backend import crud as _crud
import sys as _sys

_sys.modules[__name__] = _crud
