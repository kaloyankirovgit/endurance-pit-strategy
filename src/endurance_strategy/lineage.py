"""The project as two directed acyclic graphs: where data flows, and which code imports which.

The data lineage is declared here by hand. The import graph is read from the code. Both are
written to docs/LINEAGE.md by `python -m endurance_strategy.lineage`, and tests/test_lineage.py
fails if the files drift from the code or a step points at something that doesn't exist.

This is a description the tests hold to the code. It doesn't run the pipeline.
"""
from __future__ import annotations

import ast
import graphlib
import sys
from dataclasses import dataclass
from pathlib import Path

from endurance_strategy.paths import PROJECT_ROOT

PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE = "endurance_strategy"
BEGIN, END = "<!-- lineage:begin -->", "<!-- lineage:end -->"

LANES = {
    "race": "Race data",
    "traffic": "Traffic",
    "rules": "Regulation assistant",
    "evals": "Evals",
    "planned": "Planned, not built",
}


@dataclass(frozen=True)
class Asset:
    """Something stored on disk. `marker` is text that some step touching it must have in its code."""
    id: str
    label: str
    lane: str
    where: str
    committed: bool = False
    source: bool = False
    marker: str | None = None
    planned: bool = False


@dataclass(frozen=True)
class Step:
    """A piece of work. `after` is a step whose in-memory output this one takes."""
    id: str
    label: str
    lane: str
    code: tuple[str, ...] = ()
    functions: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()
    methods: str = ""
    planned: bool = False


ASSETS = (
    Asset("race_csv", "Race timing CSVs", "race", "data/raw/wec", source=True, marker="load_corpus"),
    Asset("weather_csv", "Weather CSVs", "race", "data/raw/wec_weather", source=True, marker="load_weather_corpus"),
    Asset("classification_csv", "Official classifications", "race", "data/raw/wec_classification", source=True,
          marker="CLASSIFICATION_DIR"),
    Asset("practice_csv", "Practice timing CSVs", "race", "data/raw/wec_practice", source=True, marker="PRACTICE_DIR"),
    Asset("laps", "laps.parquet", "race", "data/interim", marker="laps.parquet"),
    Asset("practice_laps", "practice_laps.parquet", "race", "data/interim", marker="practice_laps.parquet"),
    Asset("stints", "stints.parquet", "race", "data/processed", marker='"stints"'),
    Asset("pit_stops", "pit_stops.parquet", "race", "data/processed", marker='"pit_stops"'),
    Asset("classification_check", "classification_check.parquet", "race", "data/processed",
          marker="classification_check.parquet"),
    Asset("traffic_results", "Traffic results", "traffic", "reports/outputs", marker="OUTPUT_DIR"),
    Asset("regulation_pdf", "Regulation PDFs", "rules", "data/raw/regulations", source=True, marker="PdfReader"),
    Asset("regulation_chunks", "regulation_chunks.jsonl", "rules", "data/interim", marker="regulation_chunks.jsonl"),
    Asset("eval_questions", "Regulation questions", "evals", "evals/regulations", committed=True, source=True,
          marker="questions"),
    Asset("racer_questions", "Blind racer-agent questions", "evals", "evals/regulations/racer_agent", committed=True,
          marker="racer_agent"),
    Asset("retrieval_scores", "Retrieval scores", "evals", "evals/regulations/results", committed=True,
          marker="results"),
    Asset("answer_scores", "Answer scores", "evals", "evals/regulations/results", committed=True, marker="results"),
    Asset("reviewer_cases", "Planted-flaw write-ups", "evals", "evals/statistical_reviewer/cases", committed=True,
          source=True, marker="cases"),
    Asset("reviewer_scores", "Reviewer scores", "evals", "evals/statistical_reviewer/results", committed=True,
          marker="results"),
)

STEPS = (
    Step("load", "Parse and type", "race", ("io/load.py",), ("load_corpus",), reads=("race_csv",),
         libraries=("pandas",), methods="Parsing `m:ss.SSS` durations and the semicolon format"),
    Step("stint_flags", "Pit stops and stints", "race", ("reconstruct/stints.py",),
         ("add_stint_columns", "add_garage_stop_flag"), after=("load",),
         libraries=("pandas",), methods="In-lap and out-lap flags, stint numbering, garage-visit outliers"),
    Step("race_order", "Race order and gaps", "race", ("reconstruct/race_order.py",), ("add_race_order",),
         after=("stint_flags",), libraries=("duckdb",), methods="SQL window functions over lap crossings"),
    Step("weather", "Weather join", "race", ("features/weather.py", "reconstruct/race_clock.py", "io/weather.py"),
         ("join_weather", "add_lap_utc", "load_weather_corpus"), after=("race_order",), reads=("weather_csv",),
         libraries=("pandas",), methods="As-of join on UTC, with each circuit's time zone"),
    Step("clean_flags", "Clean-lap flags", "race", ("features/clean_laps.py",), ("add_clean_lap_flags",),
         after=("weather",), libraries=("pandas", "numpy"), methods="Flag and keep, never delete. Rule-based exclusions"),
    Step("write_laps", "Schema check and write", "race", ("pipeline.py", "validation/schema.py"),
         ("build_interim_laps",), after=("clean_flags",), writes=("laps",),
         libraries=("pandera", "pandas"), methods="Data contract validated on write, Parquet storage"),
    Step("practice", "Practice laps", "race", ("pipeline.py", "reconstruct/stints.py"), ("build_practice_laps",),
         reads=("practice_csv",), writes=("practice_laps",), libraries=("pandas",),
         methods="One table per session type, no clean-lap rule until one is registered"),
    Step("marts", "Stint and pit tables", "race", ("pipeline.py",), ("build_processed",), reads=("laps",),
         writes=("stints", "pit_stops"), libraries=("duckdb",), methods="SQL aggregation into analysis tables"),
    Step("classification", "Check against official results", "race", ("validation/classification.py",),
         ("compare_to_classification",), reads=("laps", "classification_csv"), writes=("classification_check",),
         libraries=("duckdb", "pandas"), methods="Reconciling a rebuilt result with an independent source"),
    Step("traffic", "Traffic association", "traffic",
         ("features/traffic.py", "models/traffic.py", "scripts/run_traffic_baseline.py",
          "scripts/run_traffic_followup.py", "scripts/run_traffic_le_mans.py"),
         ("add_traffic_exposure", "stint_residuals", "race_bootstrap"), reads=("laps",), writes=("traffic_results",),
         libraries=("pandas", "numpy"),
         methods="Within-stint comparison, cluster bootstrap over races, placebo windows, temporal holdout"),
    Step("chunk", "Cut into articles", "rules", ("rag/regulations.py",), ("build_chunks",), reads=("regulation_pdf",),
         writes=("regulation_chunks",), libraries=("pypdf",),
         methods="Chunking on document structure, with season and page metadata"),
    Step("retrieve", "Find the clause", "rules", ("rag/retrieve.py", "rag/embed.py"), ("tokenise",),
         reads=("regulation_chunks",), libraries=("fastembed", "numpy"),
         methods="BM25 (the default), embeddings, reciprocal rank fusion, season filter"),
    Step("answer", "Route, answer, check", "rules", ("rag/answer.py", "llm.py"), ("answer_question", "check_answer"),
         after=("retrieve",), methods="Routing, prompt chaining, structured output, deterministic checker, refusal"),
    Step("racer_agent", "Write blind questions", "evals",
         ("rag/racer_agent.py", "scripts/run_racer_agent.py", "llm.py"), ("select_questions", "run_canary"),
         writes=("racer_questions",),
         methods="Isolated headless agent, persona prompts, canary check, order fixed before the run"),
    Step("retrieval_eval", "Score retrieval", "evals",
         ("rag/evaluate.py", "scripts/run_retrieval_eval.py", "scripts/run_retrieval_comparison.py",
          "scripts/measure_retrieval_cost.py", "scripts/run_e019.py"),
         ("evaluate", "sign_test", "e019_decision"), after=("retrieve",),
         reads=("eval_questions", "racer_questions", "regulation_chunks"),
         writes=("retrieval_scores",), methods="recall@k, held-out sets, pre-registered paired sign test"),
    Step("answer_eval", "Score answers", "evals", ("rag/evaluate.py", "scripts/run_answer_eval.py"), ("grade_answer",),
         after=("answer",), reads=("eval_questions", "regulation_chunks"), writes=("answer_scores",),
         methods="Repeated runs, full trace logging, scoring in code against labels"),
    Step("reviewer_eval", "Score the review agent", "evals", ("evals/reviewer.py", "scripts/run_reviewer_eval.py", "llm.py"),
         ("grade_run",), reads=("reviewer_cases",), writes=("reviewer_scores",),
         methods="Planted flaws and clean controls, headless runs, exact-match scoring"),
    Step("pace", "Stint-age pace and pit loss", "planned", reads=("laps", "stints", "pit_stops"), planned=True),
    Step("simulator", "Race simulator", "planned", after=("pace",), reads=("traffic_results",), planned=True),
    Step("optimiser", "Strategy optimiser", "planned", after=("simulator",), planned=True),
    Step("simulator_tool", "Simulator as an LLM tool", "planned", after=("optimiser", "answer"), planned=True),
)

# Files that do real work but aren't a stage in the flow of data.
SUPPORT = {
    "paths.py": "Where each data folder lives",
    "lineage.py": "This file",
    "io/download.py": "Finds and fetches new race, practice, weather and classification files",
    "scripts/ingest.py": "One command: fetch anything new, check it and rebuild the tables",
    "io/regulations.py": "Fetches the regulation PDFs",
    "validation/quality.py": "Structural checks, run from the tests",
    "scripts/guard_commit.py": "Blocks commits of git-ignored files",
}

# rag.md: the LLM layer sits around the numerical system, never inside it.
NUMERICAL_MODULES = ("io", "reconstruct", "features", "validation", "models", "pipeline", "simulator", "optimiser")
LLM_MODULES = ("llm", "rag")


def code_path(relative: str, root: Path = PROJECT_ROOT) -> Path:
    if relative.startswith("scripts/"):
        return root / relative
    return root / "src" / PACKAGE / relative


def _top_level_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def _defined_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def _graph(assets: tuple[Asset, ...], steps: tuple[Step, ...]) -> dict[str, set[str]]:
    """Node -> the nodes it depends on, over both assets and steps."""
    graph: dict[str, set[str]] = {asset.id: set() for asset in assets}
    for step in steps:
        graph.setdefault(step.id, set()).update(step.after, step.reads)
        for written in step.writes:
            graph.setdefault(written, set()).add(step.id)
    return graph


def _cycle_problem(graph: dict[str, set[str]]) -> list[str]:
    try:
        graphlib.TopologicalSorter(graph).prepare()
    except graphlib.CycleError as error:
        return [f"cycle: {' -> '.join(error.args[1])}"]
    return []


def check_lineage(assets: tuple[Asset, ...] = ASSETS, steps: tuple[Step, ...] = STEPS,
                  root: Path = PROJECT_ROOT) -> list[str]:
    """Every problem with the declared graph. Empty means it holds together and matches the code."""
    problems: list[str] = []
    asset_by_id = {asset.id: asset for asset in assets}
    step_by_id = {step.id: step for step in steps}
    if len(asset_by_id) != len(assets) or len(step_by_id) != len(steps) or set(asset_by_id) & set(step_by_id):
        problems.append("ids must be unique across assets and steps")

    writers: dict[str, list[str]] = {}
    for step in steps:
        for used in step.reads + step.writes:
            if used not in asset_by_id:
                problems.append(f"{step.id}: unknown asset {used}")
        for earlier in step.after:
            if earlier not in step_by_id:
                problems.append(f"{step.id}: unknown step {earlier}")
        for written in step.writes:
            writers.setdefault(written, []).append(step.id)
    for asset in assets:
        count = len(writers.get(asset.id, []))
        if asset.source and count:
            problems.append(f"{asset.id}: marked as a source but written by {writers[asset.id]}")
        if not asset.source and count != 1:
            problems.append(f"{asset.id}: needs exactly one step writing it, has {count}")

    problems += _cycle_problem(_graph(assets, steps))

    code_by_asset: dict[str, list[str]] = {}
    for step in steps:
        if step.planned:
            continue
        if not step.code:
            problems.append(f"{step.id}: built step with no code")
        for dependency in step.after:
            if dependency in step_by_id and step_by_id[dependency].planned:
                problems.append(f"{step.id}: built step depends on planned step {dependency}")
        missing = [relative for relative in step.code if not code_path(relative, root).is_file()]
        problems += [f"{step.id}: no such file {relative}" for relative in missing]
        if missing:
            continue
        sources = [code_path(relative, root).read_text() for relative in step.code]
        trees = [ast.parse(source) for source in sources]
        defined = set().union(*(_defined_names(tree) for tree in trees)) if trees else set()
        imported = set().union(*(_top_level_imports(tree) for tree in trees)) if trees else set()
        problems += [f"{step.id}: {name} is not defined in its files" for name in step.functions if name not in defined]
        problems += [f"{step.id}: {name} is not imported by its files" for name in step.libraries if name not in imported]
        for used in step.reads + step.writes:
            code_by_asset.setdefault(used, []).extend(sources)
    for asset in assets:
        if asset.marker and not any(asset.marker in source for source in code_by_asset.get(asset.id, [])):
            problems.append(f"{asset.id}: no step touching it has {asset.marker!r} in its code")
    return problems


def project_files(root: Path = PROJECT_ROOT) -> set[str]:
    package = root / "src" / PACKAGE
    inside = {path.relative_to(package).as_posix() for path in package.rglob("*.py") if path.name != "__init__.py"}
    scripts = {path.relative_to(root).as_posix() for path in (root / "scripts").glob("*.py")}
    return inside | scripts


def unplaced_files(steps: tuple[Step, ...] = STEPS, support: dict[str, str] = SUPPORT,
                   root: Path = PROJECT_ROOT) -> list[str]:
    """Code that appears in neither the graph nor the support list, so a new file has to be placed."""
    placed = {relative for step in steps for relative in step.code} | set(support)
    return sorted(project_files(root) - placed)


def _module_name(relative: str) -> str:
    return relative.removesuffix(".py").replace("/", ".")


def module_imports(root: Path = PROJECT_ROOT) -> dict[str, set[str]]:
    """Module -> the project modules it imports, read from the code, function-local imports included."""
    modules = {_module_name(relative): relative for relative in project_files(root)}
    graph: dict[str, set[str]] = {module: set() for module in modules}
    prefix = PACKAGE + "."
    for module, relative in modules.items():
        for node in ast.walk(ast.parse(code_path(relative, root).read_text())):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name.removeprefix(prefix) for alias in node.names if alias.name.startswith(prefix)]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    anchor = module.split(".")[:-node.level]
                    base = ".".join(anchor + ([node.module] if node.module else []))
                elif node.module == PACKAGE:
                    base = ""
                elif node.module and node.module.startswith(prefix):
                    base = node.module.removeprefix(prefix)
                else:
                    continue
                targets = [base] + [f"{base}.{alias.name}".lstrip(".") for alias in node.names]
            graph[module] |= {target for target in targets if target in modules and target != module}
    return graph


def check_imports(graph: dict[str, set[str]]) -> list[str]:
    """Import cycles, and any numerical module that reaches the LLM layer."""
    problems = _cycle_problem(graph)
    for module, imported in sorted(graph.items()):
        if module.split(".")[0] in NUMERICAL_MODULES:
            problems += [f"{module} imports {target}: the numerical code must not depend on the LLM layer"
                         for target in sorted(imported) if target.split(".")[0] in LLM_MODULES]
    return problems


def _node_id(name: str) -> str:
    return "n_" + name.replace(".", "_")


def lineage_mermaid(assets: tuple[Asset, ...] = ASSETS, steps: tuple[Step, ...] = STEPS) -> str:
    lines = ["flowchart LR"]
    for lane, title in LANES.items():
        lines.append(f'  subgraph {lane}["{title}"]')
        for asset in assets:
            if asset.lane == lane:
                style = "planned" if asset.planned else "committed" if asset.committed else "local"
                lines.append(f'    {_node_id(asset.id)}[("{asset.label}")]:::{style}')
        for step in steps:
            if step.lane == lane:
                lines.append(f'    {_node_id(step.id)}["{step.label}"]' + (":::planned" if step.planned else ""))
        lines.append("  end")
    for step in steps:
        target = _node_id(step.id)
        lines += [f"  {_node_id(earlier)} --> {target}" for earlier in step.after]
        lines += [f"  {_node_id(read)} --> {target}" for read in step.reads]
        lines += [f"  {target} --> {_node_id(written)}" for written in step.writes]
    lines += ["  classDef local stroke-dasharray:5 4", "  classDef committed stroke-width:2px",
              "  classDef planned stroke-dasharray:2 3,opacity:0.6"]
    return "\n".join(lines)


def imports_mermaid(graph: dict[str, set[str]]) -> str:
    lines = ["flowchart LR"]
    groups: dict[str, list[str]] = {}
    for module in sorted(graph):
        groups.setdefault(module.split(".")[0] if "." in module else "top level", []).append(module)
    for index, (group, modules) in enumerate(sorted(groups.items())):
        lines.append(f'  subgraph g{index}["{group}"]')
        lines += [f'    {_node_id(module)}["{module.split(".")[-1]}"]' for module in modules]
        lines.append("  end")
    lines += [f"  {_node_id(module)} --> {_node_id(target)}"
              for module in sorted(graph) for target in sorted(graph[module])]
    return "\n".join(lines)


def _fence(diagram: str) -> str:
    return f"```mermaid\n{diagram}\n```"


def render_document(root: Path = PROJECT_ROOT) -> str:
    rows = ["| Step | Files | Libraries | Methods |", "|---|---|---|---|"]
    for step in STEPS:
        if not step.planned:
            files = "<br>".join(f"`{relative}`" for relative in step.code)
            rows.append(f"| {step.label} | {files} | {', '.join(step.libraries) or 'standard library'} | {step.methods} |")
    support = "\n".join(f"- `{relative}`: {purpose}" for relative, purpose in SUPPORT.items())
    return f"""# Lineage

Generated by `python -m endurance_strategy.lineage`. Don't edit this file by hand: `tests/test_lineage.py` fails if it differs from the generator.

## Where the data goes

Cylinders are stored files and rectangles are steps. A dashed cylinder stays on the laptop because the source data can't be redistributed. A thick cylinder is committed to Git. The faint boxes aren't built yet.

{_fence(lineage_mermaid())}

The graph is declared in `src/endurance_strategy/lineage.py`. The tests check that it has no cycles, that every file and function it names exists, that every library it lists is imported by that step's files, and that every Python file in the project is placed in it. They can't prove every arrow is right.

It doesn't run anything. The pipeline is one command that takes under 20 seconds on a laptop, so there's nothing yet for a scheduler to do (D-028).

## What each step uses

{chr(10).join(rows)}

Files that do real work but aren't a stage in the flow:

{support}

## Which code imports which

Read from the code, so it can't be out of date.

{_fence(imports_mermaid(module_imports(root)))}

The import graph must have no cycles. No numerical module (`{'`, `'.join(NUMERICAL_MODULES)}`) may import the LLM layer (`{'`, `'.join(LLM_MODULES)}`). That rule comes from `.claude/rules/rag.md`: the LLM explains the numbers and never computes them.
"""


def render_readme_block() -> str:
    return f"{BEGIN}\n{_fence(lineage_mermaid())}\n{END}"


def replace_block(text: str, block: str) -> str:
    start, end = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + block + text[end:]


def main() -> int:
    problems = check_lineage() + [f"unplaced: {path}" for path in unplaced_files()] + check_imports(module_imports())
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    (PROJECT_ROOT / "docs" / "LINEAGE.md").write_text(render_document())
    readme = PROJECT_ROOT / "README.md"
    readme.write_text(replace_block(readme.read_text(), render_readme_block()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
