from __future__ import annotations

from dataclasses import replace

from endurance_strategy.lineage import (
    ASSETS,
    END,
    PROJECT_ROOT,
    STEPS,
    Asset,
    Step,
    check_imports,
    check_lineage,
    lineage_mermaid,
    module_imports,
    render_document,
    render_readme_block,
    unplaced_files,
)


def with_step(step_id: str, **changes) -> tuple[Step, ...]:
    return tuple(replace(step, **changes) if step.id == step_id else step for step in STEPS)


def test_declared_lineage_matches_the_code():
    assert check_lineage() == []


def test_every_python_file_is_placed():
    assert unplaced_files() == []


def test_real_imports_keep_the_llm_layer_out_of_the_numerical_code():
    assert check_imports(module_imports()) == []


def test_committed_lineage_document_is_up_to_date():
    assert (PROJECT_ROOT / "docs" / "LINEAGE.md").read_text() == render_document()


def test_readme_diagram_is_up_to_date():
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert render_readme_block() in readme and END in readme


def test_a_cycle_is_reported():
    steps = with_step("load", after=("clean_flags",))
    assert any(problem.startswith("cycle") for problem in check_lineage(steps=steps))


def test_an_unknown_asset_is_reported():
    problems = check_lineage(steps=with_step("marts", reads=("no_such_table",)))
    assert "marts: unknown asset no_such_table" in problems


def test_a_missing_file_is_reported():
    problems = check_lineage(steps=with_step("load", code=("io/gone.py",)))
    assert "load: no such file io/gone.py" in problems


def test_a_function_that_does_not_exist_is_reported():
    problems = check_lineage(steps=with_step("load", functions=("not_a_function",)))
    assert "load: not_a_function is not defined in its files" in problems


def test_a_library_the_step_does_not_import_is_reported():
    problems = check_lineage(steps=with_step("load", libraries=("xgboost",)))
    assert "load: xgboost is not imported by its files" in problems


def test_a_table_with_no_writer_is_reported():
    orphan = ASSETS + (Asset("orphan", "Orphan", "race", "data/interim"),)
    assert "orphan: needs exactly one step writing it, has 0" in check_lineage(assets=orphan)


def test_a_renamed_file_is_caught_by_its_marker():
    assets = tuple(replace(a, marker="renamed.parquet") if a.id == "laps" else a for a in ASSETS)
    assert any(problem.startswith("laps: no step touching it") for problem in check_lineage(assets=assets))


def test_a_built_step_cannot_rest_on_a_planned_one():
    problems = check_lineage(steps=with_step("marts", after=("simulator",)))
    assert "marts: built step depends on planned step simulator" in problems


def test_a_new_file_must_be_placed():
    steps = tuple(step for step in STEPS if step.id != "chunk")
    assert "rag/regulations.py" in unplaced_files(steps=steps)


def test_numerical_code_importing_the_llm_is_reported():
    problems = check_imports({"models.traffic": {"llm"}, "llm": set()})
    assert problems == ["models.traffic imports llm: the numerical code must not depend on the LLM layer"]


def test_a_future_simulator_is_covered_by_the_boundary():
    assert check_imports({"simulator.core": {"rag.answer"}, "rag.answer": set()})


def test_the_llm_layer_may_import_numerical_code():
    assert check_imports({"rag.answer": {"models.traffic"}, "models.traffic": set()}) == []


def test_an_import_cycle_is_reported():
    assert any(problem.startswith("cycle") for problem in check_imports({"a": {"b"}, "b": {"a"}}))


def test_function_local_imports_are_seen():
    assert "io.download" in module_imports()["validation.classification"]


def test_planned_steps_are_drawn_as_planned():
    assert 'n_simulator["Race simulator"]:::planned' in lineage_mermaid()
