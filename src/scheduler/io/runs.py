"""Run folders (SPEC L9): one timestamped folder per solve, with metadata for reproducibility."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml

from scheduler.config import Config

DEFAULT_RUNS_DIR = Path("runs")
LATEST = "latest"
_STAMP = "%Y-%m-%d_%H-%M-%S"


def instance_name(instance: Path) -> str:
    """Folder name for a CSV instance, workbook name without extension for an .xlsx."""
    path = instance.resolve()
    return path.stem if path.is_file() else path.name


def run_dir_name(instance: Path, now: datetime) -> str:
    """``<YYYY-MM-DD_HH-MM-SS>_<instance>`` (L9)."""
    return f"{now.strftime(_STAMP)}_{instance_name(instance)}"


def new_run_dir(runs_dir: Path, instance: Path, now: datetime | None = None) -> Path:
    """Create a fresh run folder under ``runs_dir`` (suffix ``-2``, ``-3``, ... if taken)
    and point ``runs_dir/latest`` at it."""
    base = run_dir_name(instance, now or datetime.now())
    runs_dir.mkdir(parents=True, exist_ok=True)
    path, n = runs_dir / base, 1
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            n += 1
            path = runs_dir / f"{base}-{n}"
    _point_latest(runs_dir, path.name)
    return path


def _point_latest(runs_dir: Path, name: str) -> None:
    link = runs_dir / LATEST
    try:
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            return  # a real file or folder named "latest": leave it alone
        link.symlink_to(name, target_is_directory=True)
    except OSError:
        pass  # symlinks unsupported (e.g. Windows without privileges)


def input_files(instance: Path) -> list[Path]:
    """The files that make up an instance, in sorted name order."""
    if instance.is_file():
        return [instance]
    return sorted(p for p in instance.iterdir() if p.is_file() and not p.name.startswith("."))


def instance_sha256(instance: Path) -> str:
    """SHA-256 over (name, content) of every input file in sorted name order."""
    digest = hashlib.sha256()
    for path in input_files(instance):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def from_run(assignments: Path | None) -> str | None:
    """Name of the run folder a hand-off file came from (its folder holds a run.json)."""
    if assignments is None:
        return None
    folder = assignments.resolve().parent
    return folder.name if (folder / "run.json").is_file() else None


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def git_state() -> tuple[str | None, bool | None]:
    """(HEAD commit, working tree has changes) of the source checkout, or (None, None)."""
    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return None, None
    status = _git("status", "--porcelain")
    return commit, None if status is None else bool(status)


def scheduler_version() -> str | None:
    try:
        return version("class-scheduler")
    except PackageNotFoundError:
        return None


def write_config(cfg: Config, path: Path) -> Path:
    """The resolved config as YAML (loadable with ``load_config``)."""
    path.write_text(
        yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class RunRecord:
    """Metadata written to ``run.json`` (L9)."""

    command: str
    argv: list[str]
    instance: Path
    config: Path | None
    assignments: Path | None = None
    previous: Path | None = None
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    status: str = "failed"
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    from_run: str | None = field(init=False)
    hard_violations: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        # Resolve now: the hand-off may be given via runs/latest, which moves to this run.
        self.from_run = from_run(self.assignments or self.previous)

    def add_stage(
        self,
        stage: str,
        status: str,
        stats: dict[str, Any],
        errors: int = 0,
        warnings: int = 0,
        solved: bool = True,
    ) -> None:
        """Record a stage; a solved stage's error count becomes ``hard_violations``."""
        self.stages[stage] = {
            "status": status,
            **stats,
            "violations": {"error": errors, "warning": warnings},
        }
        if solved:
            self.hard_violations = errors

    def as_dict(self) -> dict[str, Any]:
        commit, dirty = git_state()
        return {
            "command": self.command,
            "argv": self.argv,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "instance": str(self.instance),
            "instance_sha256": instance_sha256(self.instance) if self.instance.exists() else None,
            "config": None if self.config is None else str(self.config),
            "assignments": None if self.assignments is None else str(self.assignments),
            "previous": None if self.previous is None else str(self.previous),
            "from_run": self.from_run,
            "scheduler_version": scheduler_version(),
            "git_commit": commit,
            "git_dirty": dirty,
            "stages": self.stages,
            "hard_violations": self.hard_violations,
        }

    def write(self, folder: Path) -> Path:
        """Stamp ``finished_at`` and write ``folder/run.json``."""
        self.finished_at = _now()
        path = folder / "run.json"
        path.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        return path
