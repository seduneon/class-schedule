"""L1 diagnostics: pre-solve checks and post-solve slack explanations."""

from scheduler.diagnostics.presolve import Finding, has_errors, presolve_checks

__all__ = ["Finding", "has_errors", "presolve_checks"]
