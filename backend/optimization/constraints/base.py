from abc import ABC, abstractmethod


class Constraint(ABC):
    name: str

    @abstractmethod
    def apply(self, model, variables: dict, data: dict) -> None:
        """Apply this constraint to the PuLP model."""
        ...
