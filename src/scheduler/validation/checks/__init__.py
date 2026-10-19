"""One check module per constraint ID; importing this package registers them all."""

from scheduler.validation.checks import (
    a01,
    a02,
    a03,
    a04,
    a05,
    a06,
    a07,
    a08,
    a09,
    b01,
    b02,
    b03,
    b04,
    b05,
    b06,
    b07,
    b08,
    b09,
    b10,
    b11,
    b12,
    b13,
)

__all__ = [
    "a01", "a02", "a03", "a04", "a05", "a06", "a07", "a08", "a09",
    "b01", "b02", "b03", "b04", "b05", "b06", "b07", "b08", "b09", "b10", "b11", "b12", "b13",
]  # fmt: skip
