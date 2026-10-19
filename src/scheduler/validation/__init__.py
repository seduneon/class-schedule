"""Independent validator (SPEC L2). Plain Python only; never imports PuLP."""

from scheduler.validation import checks as _checks
from scheduler.validation.core import CHECKS, Violation, check, errors, severity_for, validate
from scheduler.validation.pins import check_pins

__all__ = [
    "CHECKS",
    "Violation",
    "_checks",
    "check",
    "check_pins",
    "errors",
    "severity_for",
    "validate",
]
