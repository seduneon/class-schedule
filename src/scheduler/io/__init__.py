"""Input/output: readers, schemas and writers (SPEC §8). pandas is allowed here."""

from scheduler.io.readers import (
    InputError,
    RowError,
    build_instance,
    load_tables,
    read_assignments,
    read_instance,
    read_solution,
    solution_from_dict,
)
from scheduler.io.writers import (
    instance_tables,
    solution_to_dict,
    write_assignments,
    write_instance,
    write_solution,
)

__all__ = [
    "InputError",
    "RowError",
    "build_instance",
    "instance_tables",
    "load_tables",
    "read_assignments",
    "read_instance",
    "read_solution",
    "solution_from_dict",
    "solution_to_dict",
    "write_assignments",
    "write_instance",
    "write_solution",
]
