"""Command-line interface (SPEC §10): check, run, assign, timetable, validate, report, ..."""

from __future__ import annotations

import functools
import json
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, TextIO

import typer
import yaml
from pydantic import ValidationError

from scheduler.config import Config, load_config
from scheduler.diagnostics import Finding, has_errors, presolve_checks
from scheduler.domain import Assignment, Instance, Solution
from scheduler.io import (
    InputError,
    RowError,
    read_assignments,
    read_instance,
    read_solution,
    write_assignments,
    write_solution,
)
from scheduler.io.runs import DEFAULT_RUNS_DIR, RunRecord, new_run_dir, write_config
from scheduler.pipeline import StageResult, alternatives, run_stage_a, run_stage_b
from scheduler.reporting import render_html, write_excel_report
from scheduler.validation import Violation, check_pins, validate

app = typer.Typer(
    help="Class scheduling optimizer: Stage A assigns professors, Stage B builds the timetable.",
    no_args_is_help=True,
    add_completion=False,
)

InstanceArg = Annotated[
    Path, typer.Argument(help="Instance folder of CSV files, or one .xlsx workbook.")
]
ConfigOpt = Annotated[
    Path | None, typer.Option("--config", "-c", help="YAML config (default: built-in defaults).")
]
OutOpt = Annotated[
    Path | None,
    typer.Option("--out", "-o", help="Output folder (default: a new folder under --runs-dir)."),
]
PlainOutOpt = Annotated[Path, typer.Option("--out", "-o", help="Output folder.")]
RunsOpt = Annotated[
    Path, typer.Option("--runs-dir", help="Parent of the timestamped run folders (L9).")
]

_LOGS: list[TextIO] = []  # log.txt of the active run folder, if any


def _say(message: str = "", fg: str | None = None, err: bool = False) -> None:
    """Print to the console and append the plain text to the active run's log.txt."""
    typer.secho(message, fg=fg, err=err)
    for log in _LOGS:
        log.write(message + "\n")


@contextmanager
def _run_folder(
    command: str,
    instance: Path,
    config: Path | None,
    cfg: Config,
    out: Path | None,
    runs_dir: Path,
    assignments: Path | None = None,
    previous: Path | None = None,
) -> Iterator[tuple[Path, RunRecord]]:
    """L9: open ``out`` (or a new run folder), log the console there, and always write
    ``config.yaml`` and ``run.json`` (status ``ok`` only if the command finishes cleanly)."""
    record = RunRecord(command, sys.argv[1:], instance, config, assignments, previous)
    folder = out if out is not None else new_run_dir(runs_dir, instance)  # moves runs/latest
    folder.mkdir(parents=True, exist_ok=True)
    write_config(cfg, folder / "config.yaml")
    ok = False
    with (folder / "log.txt").open("w", encoding="utf-8") as log:
        _LOGS.append(log)
        try:
            _say(f"Run folder: {folder}")
            yield folder, record
            ok = True
        except typer.Exit as exc:
            ok = exc.exit_code == 0
            raise
        finally:
            _LOGS.remove(log)
            record.status = "ok" if ok else "failed"
            record.write(folder)


def _record(record: RunRecord, result: StageResult) -> None:
    errors = sum(v.severity == "error" for v in result.violations)
    warnings = len(result.violations) - errors
    solved = result.solution is not None
    record.add_stage(result.stage, result.status.value, result.stats, errors, warnings, solved)


USER_ERRORS = (InputError, OSError, yaml.YAMLError, ValidationError)


def _user_errors[**P](command: Callable[P, None]) -> Callable[P, None]:
    """Report bad or missing input files in one red line (exit code 2), not a traceback."""

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            command(*args, **kwargs)
        except USER_ERRORS as exc:
            _say(f"Error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from exc

    return wrapper


def _load(instance_path: Path, config_path: Path | None) -> tuple[Instance, Config]:
    try:
        cfg = load_config(config_path)
    except ValueError as exc:  # also pydantic ValidationError
        raise InputError([RowError(str(config_path), None, str(exc))]) from exc
    return read_instance(instance_path), cfg


def _print_findings(findings: Sequence[Finding]) -> None:
    if not findings:
        _say("No data problems found.")
        return
    colors = {"error": typer.colors.RED, "warning": typer.colors.YELLOW, "info": None}
    for f in findings:
        _say(str(f), fg=colors[f.severity])


def _print_violations(violations: Sequence[Violation]) -> None:
    if not violations:
        _say("Validator: all checks passed.", fg=typer.colors.GREEN)
        return
    for v in violations:
        _say(str(v), fg=typer.colors.RED if v.severity == "error" else typer.colors.YELLOW)


def _print_result(result: StageResult) -> None:
    _say(f"Stage {result.stage}: {result.status.value}")
    for lv in result.lex.levels:
        _say(f"  level {lv.level.key} ({lv.level.name}, {lv.level.sense}): {lv.value:.6g}")
    _say(
        f"  {result.stats.get('variables', 0)} variables, {result.stats.get('constraints', 0)} "
        f"constraints, {result.stats.get('wall_time_s', 0)} s"
    )
    errors = [f for f in result.findings if f.severity != "info"]
    if errors:
        _say("Diagnostics:")
        _print_findings(errors)
    if result.slacks:
        _say("Non-zero slacks:")
        for s in result.slacks:
            _say(f"  {s}")
    if result.solution is None:
        _say("No solution, so nothing was validated.", fg=typer.colors.RED)
        return
    _print_violations(result.violations)


@app.command()
@_user_errors
def check(
    instance: InstanceArg,
    config: ConfigOpt = None,
    assignments: Annotated[
        Path | None, typer.Option(help="Stage A hand-off file to check for Stage B.")
    ] = None,
) -> None:
    """L1 pre-solve diagnostics. Exit code 1 if any error is found."""
    inst, cfg = _load(instance, config)
    asg = read_assignments(assignments) if assignments else None
    findings = presolve_checks(inst, cfg, asg)
    _print_findings(findings)
    if has_errors(findings):
        raise typer.Exit(1)


@app.command()
@_user_errors
def run(
    instance: InstanceArg,
    config: ConfigOpt = None,
    assignments: Annotated[
        Path | None,
        typer.Option(
            help="Edited Stage A hand-off: skip Stage A and use this (CSV, .xlsx, .json)."
        ),
    ] = None,
    out: OutOpt = None,
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """L9: check → Stage A → Stage B in one step, all results in a new run folder."""
    inst, cfg = _load(instance, config)
    asg = read_assignments(assignments) if assignments else None
    with _run_folder("run", instance, config, cfg, out, runs_dir, assignments) as (folder, rec):
        findings = presolve_checks(inst, cfg, asg)
        (folder / "check.txt").write_text(
            "".join(f"{f}\n" for f in findings) or "No data problems found.\n", encoding="utf-8"
        )
        _say(_findings_summary(findings))
        if asg is None:
            asg = _assign(inst, cfg, folder, rec, "csv")
        _timetable(inst, cfg, asg, folder, rec)
        n = rec.hard_violations or 0
        _say(
            f"Result: {n} hard violation(s); see the violations sheet in report.xlsx."
            if n
            else "Result: no hard violations.",
            fg=typer.colors.YELLOW if n else typer.colors.GREEN,
        )


def _findings_summary(findings: Sequence[Finding]) -> str:
    counts = {sev: sum(f.severity == sev for f in findings) for sev in ("error", "warning")}
    return f"Check: {counts['error']} error(s), {counts['warning']} warning(s) (see check.txt)."


def _assign(
    inst: Instance, cfg: Config, out: Path, rec: RunRecord, fmt: str
) -> tuple[Assignment, ...]:
    result = run_stage_a(inst, cfg)
    _print_result(result)
    _record(rec, result)
    if result.solution is None:
        raise typer.Exit(1)
    path = write_assignments(result.solution.assignments, out / f"assignments.{fmt}")
    write_solution(result.solution, out / "stage_a.json")
    _say(
        f"Wrote {path} (edit it, then run `scheduler timetable` or `scheduler run --assignments`)."
    )
    return result.solution.assignments


def _timetable(
    inst: Instance, cfg: Config, asg: Sequence[Assignment], out: Path, rec: RunRecord
) -> None:
    result = run_stage_b(inst, cfg, asg)
    _print_result(result)
    _record(rec, result)
    if result.solution is None:
        raise typer.Exit(1)
    _write_outputs(out, inst, cfg, result.solution, result)


@app.command()
@_user_errors
def assign(
    instance: InstanceArg,
    out: OutOpt = None,
    config: ConfigOpt = None,
    fmt: Annotated[str, typer.Option("--format", help="csv or xlsx")] = "csv",
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """Stage A: assign professors to sections; writes assignments.<fmt> and stage_a.json."""
    inst, cfg = _load(instance, config)
    with _run_folder("assign", instance, config, cfg, out, runs_dir) as (folder, rec):
        _assign(inst, cfg, folder, rec, fmt)


@app.command()
@_user_errors
def timetable(
    instance: InstanceArg,
    assignments: Annotated[Path, typer.Option(help="Stage A hand-off (CSV, .xlsx or .json).")],
    out: OutOpt = None,
    config: ConfigOpt = None,
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """Stage B: time patterns and rooms; writes solution.json, report.xlsx, timetable.html."""
    inst, cfg = _load(instance, config)
    asg = read_assignments(assignments)
    with _run_folder("timetable", instance, config, cfg, out, runs_dir, assignments) as (
        folder,
        rec,
    ):
        _timetable(inst, cfg, asg, folder, rec)


def _write_outputs(
    out: Path, inst: Instance, cfg: Config, solution: Solution, result: StageResult | None
) -> None:
    write_solution(solution, out / "solution.json")
    write_excel_report(
        out / "report.xlsx",
        inst,
        solution,
        cfg,
        violations=result.violations if result else validate(inst, solution, cfg),
        slacks=result.slacks if result else (),
        findings=result.findings if result else (),
        stats=result.stats if result else None,
    )
    written = [out / "solution.json", out / "report.xlsx"]
    if solution.placements is not None:
        (out / "timetable.html").write_text(render_html(inst, solution, cfg), encoding="utf-8")
        written.append(out / "timetable.html")
    _say("Wrote " + ", ".join(str(p) for p in written))


@app.command("validate")
@_user_errors
def validate_cmd(
    instance: InstanceArg,
    solution: Annotated[Path, typer.Argument(help="solution.json, or an assignments CSV/xlsx.")],
    config: ConfigOpt = None,
) -> None:
    """L2: check a (possibly hand-edited) solution. Exit code 1 if any hard rule is broken."""
    inst, cfg = _load(instance, config)
    sol = (
        read_solution(solution)
        if solution.suffix.lower() == ".json"
        else Solution(read_assignments(solution))
    )
    violations = validate(inst, sol, cfg) + check_pins(inst, sol)
    _print_violations(violations)
    if any(v.severity == "error" for v in violations):
        raise typer.Exit(1)


@app.command()
@_user_errors
def report(
    instance: InstanceArg,
    solution: Annotated[Path, typer.Argument(help="solution.json")],
    out: OutOpt = None,
    config: ConfigOpt = None,
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """L6: Excel workbook and HTML grid for an existing solution."""
    inst, cfg = _load(instance, config)
    sol = read_solution(solution)
    with _run_folder("report", instance, config, cfg, out, runs_dir, previous=solution) as (
        folder,
        _,
    ):
        _write_outputs(folder, inst, cfg, sol, None)


StageOpt = Annotated[str, typer.Option("--stage", help="A (assignment) or B (timetable).")]


def _check_stage(stage: str, assignments: Path | None, previous: Path | None = None) -> None:
    if stage.upper() not in ("A", "B"):
        raise typer.BadParameter("stage must be A or B", param_hint="--stage")
    if stage.upper() == "B" and assignments is None and previous is None:
        raise typer.BadParameter("Stage B needs --assignments", param_hint="--assignments")


def _solve_stage(
    stage: str,
    inst: Instance,
    cfg: Config,
    assignments: Path | None,
    previous: Solution | None = None,
) -> StageResult:
    if stage.upper() == "A":
        return run_stage_a(inst, cfg, previous=previous)
    if assignments is not None:
        asg = read_assignments(assignments)
    else:
        assert previous is not None  # _check_stage
        asg = previous.assignments
    return run_stage_b(inst, cfg, asg, previous=previous)


@app.command("alternatives")
@_user_errors
def alternatives_cmd(
    instance: InstanceArg,
    stage: StageOpt = "B",
    assignments: Annotated[Path | None, typer.Option(help="Stage A hand-off (Stage B).")] = None,
    count: Annotated[
        int | None, typer.Option(help="Number of alternatives (default: config).")
    ] = None,
    out: OutOpt = None,
    config: ConfigOpt = None,
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """L3: solve, then list up to N near-optimal alternatives with a diff against the best."""
    _check_stage(stage, assignments)
    inst, cfg = _load(instance, config)
    with _run_folder("alternatives", instance, config, cfg, out, runs_dir, assignments) as (
        folder,
        rec,
    ):
        result = _solve_stage(stage, inst, cfg, assignments)
        _print_result(result)
        _record(rec, result)
        if result.solution is None:
            raise typer.Exit(1)
        n = count if count is not None else max(cfg.alternatives.count, 3)
        alts = alternatives(result, cfg, n)
        write_solution(result.solution, folder / "best.json")
        for alt in alts:
            write_solution(alt.solution, folder / f"alternative_{alt.rank}.json")
            _say(f"#{alt.rank}: level 3 = {alt.objective:.6g} ({alt.relative_gap:.2%} below best)")
            for line in alt.diff:
                _say(f"    {line}")
        (folder / "alternatives.json").write_text(
            json.dumps([a.as_dict() for a in alts], indent=2) + "\n", encoding="utf-8"
        )
        if not alts:
            _say("No alternative within the optimality gap.")


@app.command()
@_user_errors
def repair(
    instance: InstanceArg,
    previous: Annotated[Path, typer.Option(help="Previous solution.json.")],
    stage: StageOpt = "B",
    assignments: Annotated[
        Path | None, typer.Option(help="New Stage A hand-off (Stage B; default: previous).")
    ] = None,
    out: OutOpt = None,
    config: ConfigOpt = None,
    runs_dir: RunsOpt = DEFAULT_RUNS_DIR,
) -> None:
    """L5: re-solve a changed instance while changing as few decisions as possible."""
    _check_stage(stage, assignments, previous)
    inst, cfg = _load(instance, config)
    prev = read_solution(previous)
    with _run_folder("repair", instance, config, cfg, out, runs_dir, assignments, previous) as (
        folder,
        rec,
    ):
        result = _solve_stage(stage, inst, cfg, assignments, previous=prev)
        _print_result(result)
        _record(rec, result)
        if result.solution is None:
            raise typer.Exit(1)
        if stage.upper() == "A":
            write_assignments(result.solution.assignments, folder / "assignments.csv")
            write_solution(result.solution, folder / "stage_a.json")
        else:
            _write_outputs(folder, inst, cfg, result.solution, result)


@app.command()
@_user_errors
def generate(
    out: Annotated[Path, typer.Argument(help="Folder to write the CSV instance to.")],
    professors: int = 6,
    courses: int = 6,
    seed: int = 0,
    load_tightness: float = 0.8,
    correlation: float = 0.5,
) -> None:
    """L8: write a seeded synthetic instance."""
    from scheduler.generate import GeneratorSpec, generate_instance
    from scheduler.io import write_instance

    spec = GeneratorSpec(
        n_professors=professors,
        n_courses=courses,
        seed=seed,
        load_tightness=load_tightness,
        preference_correlation=correlation,
    )
    inst = generate_instance(spec)
    write_instance(inst, out)
    _say(f"Wrote {len(inst.professors)} professors, {len(inst.sections)} sections to {out}")


@app.command()
@_user_errors
def experiment(
    name: Annotated[str, typer.Argument(help="ablation | scaling | weights | fairness | all")],
    out: PlainOutOpt = Path("experiments/results"),
    seeds: Annotated[int, typer.Option(help="Number of seeds (0..n-1).")] = 3,
    config: ConfigOpt = None,
) -> None:
    """M10: run an experiment on generated instances; writes <name>.csv."""
    import pandas as pd

    from scheduler.experiment import EXPERIMENTS

    cfg = load_config(config)
    names = list(EXPERIMENTS) if name == "all" else [name]
    for n in names:
        if n not in EXPERIMENTS:
            raise typer.BadParameter(f"unknown experiment {n!r}; choose from {sorted(EXPERIMENTS)}")
        rows = EXPERIMENTS[n](cfg, list(range(seeds)))
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out / f"{n}.csv", index=False)
        _say(f"{n}: {len(rows)} rows -> {out / (n + '.csv')}")


def _under_data_private(path: Path) -> bool:
    parts = path.resolve().parts
    return any(parts[i : i + 2] == ("data", "private") for i in range(len(parts) - 1))


@app.command("convert-legacy")
@_user_errors
def convert_legacy_cmd(
    source: Annotated[Path, typer.Argument(help="Folder with the four legacy .xlsx files.")],
    out: PlainOutOpt = Path("data/private/legacy"),
    add_offering: Annotated[
        list[str] | None,
        typer.Option(help="Extra sections COURSE:TYPE:N:CAP, e.g. MATH161:R:8:57 (repeatable)."),
    ] = None,
    anonymize: Annotated[
        bool, typer.Option(help="Rename professors P01.. and drop comments (SPEC §8.1).")
    ] = False,
) -> None:
    """SPEC §8.1: convert the previous capstone's wide Excel files into the §8 tables."""
    from scheduler.io.legacy import ExtraOffering, convert_legacy, write_legacy

    if not anonymize and not _under_data_private(out):
        raise typer.BadParameter(
            "real data may only be written under data/private/ (or use --anonymize)",
            param_hint="--out",
        )
    try:
        extra = tuple(ExtraOffering.parse(x) for x in add_offering or [])
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--add-offering") from exc
    result = write_legacy(convert_legacy(source, extra, anonymize), out)
    _say(f"Wrote the instance to {result}; review {result / 'review.csv'} before solving.")


def main() -> None:  # pragma: no cover
    app()
