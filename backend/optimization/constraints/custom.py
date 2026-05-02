# New constraints added for capstone go here.

from optimization.constraints.base import Constraint


class PlaceholderConstraint(Constraint):
    """Stub — replace with real capstone constraints."""

    name = "placeholder"

    def apply(self, model, variables: dict, data: dict) -> None:
        pass
