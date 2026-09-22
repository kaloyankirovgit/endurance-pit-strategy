"""Layer 0 smoke tests.

These check that the repository's scaffolding holds together: the package
imports, and the documentation files the working agreement depends on exist.
They are deliberately thin -- there is no logic to test yet.

Their real job is to make the test suite and CI runnable from day one, so that
the first substantive test has somewhere to go.
"""

from pathlib import Path

import endurance_strategy

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_imports():
    assert endurance_strategy.__version__


def test_context_files_exist():
    """Files that CLAUDE.md instructs every session to rely on."""
    for relative_path in [
        "CLAUDE.md",
        "Strategy.md",
        "README.md",
        "docs/PROJECT_STATE.md",
        "docs/DECISIONS.md",
        "docs/EXPERIMENT_LOG.md",
        "docs/DATA_DICTIONARY.md",
    ]:
        assert (REPO_ROOT / relative_path).is_file(), f"missing {relative_path}"


def test_no_data_files_are_tracked_by_git():
    """The licensing constraint, as a test.

    FIA WEC timing data may not be redistributed. Nothing under data/ is ever
    committed -- .gitignore is the primary defence and this is the alarm.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "data/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    offenders = [path for path in tracked if not path.endswith((".gitkeep", "README.md"))]
    assert not offenders, f"data files are tracked by git: {offenders}"
