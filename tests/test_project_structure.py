import subprocess
from pathlib import Path

import endurance_strategy

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_imports():
    assert endurance_strategy.__version__


def test_key_docs_exist():
    for relative_path in ["README.md", "CLAUDE.md", "docs/PROJECT_STATE.md", "docs/DECISIONS.md"]:
        assert (REPO_ROOT / relative_path).is_file(), f"missing {relative_path}"


def test_no_data_files_are_tracked_by_git():
    tracked = subprocess.run(
        ["git", "ls-files", "data/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    offenders = [path for path in tracked if not path.endswith((".gitkeep", "README.md"))]
    assert not offenders, f"data files are tracked by git: {offenders}"


def test_private_files_are_not_tracked_by_git():
    tracked = subprocess.run(
        ["git", "ls-files", "CV_work", "docs/cv", "Strategy.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    assert not tracked, f"private files are tracked by git: {tracked}"
