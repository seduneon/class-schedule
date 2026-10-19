"""Command-line interface (SPEC §10): check, assign, timetable, validate, report, ..."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from scheduler.config import Config, load_config
from scheduler.diagnostics import Finding, has_errors, presolve_checks
from scheduler.domain import Instance, Solution
from scheduler.io import (
    InputError,
    read_assignments,
    read_instance,
    read_solution,
    write_assignments,
    write_solution,
)
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
OutOpt = Annotated[Path, typer.Option("--out", "-o", help="Output folder.")]


def _load(instance_path: Path, config_path: Path | None) -> tuple[Instance, Config]:
    try:
        return read_instance(instance_path), load_config(config_path)
    except InputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from exc


def _print_findings(findings: Sequence[Finding]) -> None:
    if not findings:
        typer.echo("No data problems found.")
        return
    colors = {"error": typer.colors.RED, "warning": typer.colors.YELLOW, "info": None}
    for f in findings:
        typer.secho(str(f), fg=colors[f.severity])


def _print_violations(violations: Sequence[Violation]) -> None:
    if not violations:
        typer.secho("Validator: all checks passed.", fg=typer.colors.GREEN)
        return
    for v in violations:
        typer.secho(str(v), fg=typer.colors.RED if v.severity == "error" else typer.colors.YELLOW)


def _print_result(result: StageResult) -> None:
    typer.echo(f"Stage {result.stage}: {result.status.value}")
    for lv in result.lex.levels:
        typer.echo(f"  level {lv.level.key} ({lv.level.name}, {lv.level.sense}): {lv.value:.6g}")
    typer.echo(
        f"  {result.stats.get('variables', 0)} variables, {result.stats.get('constraints', 0)} "
        f"constraints, {result.stats.get('wall_time_s', 0)} s"
    )
    errors = [f for f in result.findings if f.severity != "info"]
    if errors:
        typer.echo("Diagnostics:")
        _print_findings(errors)
    if result.slacks:
        typer.echo("Non-zero slacks:")
        for s in result.slacks:
            typer.echo(f"  {s}")
    _print_violations(result.violations)


@app.command()
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
def assign(
    instance: InstanceArg,
    out: OutOpt = Path("out"),
    config: ConfigOpt = None,
    fmt: Annotated[str, typer.Option("--format", help="csv or xlsx")] = "csv",
) -> None:
    """Stage A: assign professors to sections; writes assignments.<fmt> and stage_a.json."""
    inst, cfg = _load(instance, config)
    result = run_stage_a(inst, cfg)
    _print_result(result)
    if result.solution is None:
        raise typer.Exit(1)
    path = write_assignments(result.solution.assignments, out / f"assignments.{fmt}")
    write_solution(result.solution, out / "stage_a.json")
    typer.echo(f"Wrote {path} (edit it, then run `scheduler timetable`).")


@app.command()
def timetable(
    instance: InstanceArg,
    assignments: Annotated[Path, typer.Option(help="Stage A hand-off (CSV, .xlsx or .json).")],
    out: OutOpt = Path("out"),
    config: ConfigOpt = None,
) -> None:
    """Stage B: time patterns and rooms; writes solution.json, report.xlsx, timetable.html."""
    inst, cfg = _load(instance, config)
    asg = read_assignments(assignments)
    result = run_stage_b(inst, cfg, asg)
    _print_result(result)
    if result.solution is None:
        raise typer.Exit(1)
    _write_outputs(out, inst, cfg, result.solution, result)


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
    if solution.placements is not None:
        (out / "timetable.html").write_text(render_html(inst, solution, cfg), encoding="utf-8")
    typer.echo(f"Wrote {out / 'solution.json'}, {out / 'report.xlsx'}, {out / 'timetable.html'}")


@app.command("validate")
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
def report(
    instance: InstanceArg,
    solution: Annotated[Path, typer.Argument(help="solution.json")],
    out: OutOpt = Path("out"),
    config: ConfigOpt = None,
) -> None:
    """L6: Excel workbook and HTML grid for an existing solution."""
    inst, cfg = _load(instance, config)
    _write_outputs(out, inst, cfg, read_solution(solution), None)


StageOpt = Annotated[str, typer.Option("--stage", help="A (assignment) or B (timetable).")]


def _solve_stage(
    stage: str,
    inst: Instance,
    cfg: Config,
    assignments: Path | None,
    previous: Solution | None = None,
) -> StageResult:
    if stage.upper() == "A":
        return run_stage_a(inst, cfg, previous=previous)
    if stage.upper() != "B":
        raise typer.BadParameter("stage must be A or B")
    if assignments is not None:
        asg = read_assignments(assignments)
    elif previous is not None:
        asg = previous.assignments
    else:
        raise typer.BadParameter("Stage B needs --assignments")
    return run_stage_b(inst, cfg, asg, previous=previous)


@app.command("alternatives")
def alternatives_cmd(
    instance: InstanceArg,
    stage: StageOpt = "B",
    assignments: Annotated[Path | None, typer.Option(help="Stage A hand-off (Stage B).")] = None,
    count: Annotated[
        int | None, typer.Option(help="Number of alternatives (default: config).")
    ] = None,
    out: OutOpt = Path("out"),
    config: ConfigOpt = None,
) -> None:
    """L3: solve, then list up to N near-optimal alternatives with a diff against the best."""
    inst, cfg = _load(instance, config)
    result = _solve_stage(stage, inst, cfg, assignments)
    _print_result(result)
    if result.solution is None:
        raise typer.Exit(1)
    alts = alternatives(result, cfg, count if count is not None else max(cfg.alternatives.count, 3))
    out.mkdir(parents=True, exist_ok=True)
    write_solution(result.solution, out / "best.json")
    for alt in alts:
        write_solution(alt.solution, out / f"alternative_{alt.rank}.json")
        typer.echo(
            f"#{alt.rank}: level 3 = {alt.objective:.6g} ({alt.relative_gap:.2%} below best)"
        )
        for line in alt.diff:
            typer.echo(f"    {line}")
    (out / "alternatives.json").write_text(
        json.dumps([a.as_dict() for a in alts], indent=2) + "\n", encoding="utf-8"
    )
    if not alts:
        typer.echo("No alternative within the optimality gap.")


@app.command()
def repair(
    instance: InstanceArg,
    previous: Annotated[Path, typer.Option(help="Previous solution.json.")],
    stage: StageOpt = "B",
    assignments: Annotated[
        Path | None, typer.Option(help="New Stage A hand-off (Stage B; default: previous).")
    ] = None,
    out: OutOpt = Path("out"),
    config: ConfigOpt = None,
) -> None:
    """L5: re-solve a changed instance while changing as few decisions as possible."""
    inst, cfg = _load(instance, config)
    prev = read_solution(previous)
    result = _solve_stage(stage, inst, cfg, assignments, previous=prev)
    _print_result(result)
    if result.solution is None:
        raise typer.Exit(1)
    if stage.upper() == "A":
        write_assignments(result.solution.assignments, out / "assignments.csv")
        write_solution(result.solution, out / "stage_a.json")
    else:
        _write_outputs(out, inst, cfg, result.solution, result)


@app.command()
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
    typer.echo(f"Wrote {len(inst.professors)} professors, {len(inst.sections)} sections to {out}")


@app.command()
def experiment(
    name: Annotated[str, typer.Argument(help="ablation | scaling | weights | fairness | all")],
    out: OutOpt = Path("experiments/results"),
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
        typer.echo(f"{n}: {len(rows)} rows -> {out / (n + '.csv')}")


def _under_data_private(path: Path) -> bool:
    parts = path.resolve().parts
    return any(parts[i : i + 2] == ("data", "private") for i in range(len(parts) - 1))


@app.command("convert-legacy")
def convert_legacy_cmd(
    source: Annotated[Path, typer.Argument(help="Folder with the four legacy .xlsx files.")],
    out: OutOpt = Path("data/private/legacy"),
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
    typer.echo(f"Wrote the instance to {result}; review {result / 'review.csv'} before solving.")


def main() -> None:  # pragma: no cover
    app()
