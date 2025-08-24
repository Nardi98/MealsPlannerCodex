"""Compatibility wrapper for moved models module."""
from backend import models as _models
import sys as _sys

_sys.modules[__name__] = _models
