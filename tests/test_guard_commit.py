from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "guard_commit.py"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def run_guard(repo: Path, *args: str, command: str | None = None) -> subprocess.CompletedProcess:
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}) if command is not None else None
    return subprocess.run([sys.executable, str(GUARD), *args], cwd=repo, input=stdin, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("private.md\n")
    (tmp_path / "private.md").write_text("synthetic private note\n")
    (tmp_path / "code.py").write_text("x = 1\n")
    git(tmp_path, "add", ".gitignore", "code.py")
    return tmp_path


def test_clean_index_passes_both_modes(repo):
    assert run_guard(repo).returncode == 0
    assert run_guard(repo, "--claude", command="git commit -m 'msg'").returncode == 0


def test_force_added_ignored_file_blocks_git_hook(repo):
    git(repo, "add", "-f", "private.md")
    result = run_guard(repo)
    assert result.returncode == 1
    assert "private.md" in result.stderr


def test_force_added_ignored_file_blocks_claude_commit(repo):
    git(repo, "add", "-f", "private.md")
    result = run_guard(repo, "--claude", command="git add . && git commit -m 'msg'")
    assert result.returncode == 2
    assert "private.md" in result.stderr


def test_claude_hook_ignores_commands_that_are_not_commits(repo):
    git(repo, "add", "-f", "private.md")
    assert run_guard(repo, "--claude", command="git status").returncode == 0


def test_claude_hook_blocks_skipping_the_git_hook(repo):
    assert run_guard(repo, "--claude", command="git commit --no-verify -m 'msg'").returncode == 2
    assert run_guard(repo, "--claude", command="git commit -n -m 'msg'").returncode == 2
    assert run_guard(repo, "--claude", command="cd sub && git commit -anm 'msg'").returncode == 2


def test_claude_hook_ignores_commit_mentioned_in_text(repo):
    git(repo, "add", "-f", "private.md")
    command = "python3 - <<'EOF'\nnote = 'blocks a `git commit` that uses --no-verify'\nEOF"
    assert run_guard(repo, "--claude", command=command).returncode == 0
    assert run_guard(repo, "--claude", command="echo 'run git commit later'").returncode == 0


def test_claude_hook_catches_commit_after_other_commands(repo):
    git(repo, "add", "-f", "private.md")
    assert run_guard(repo, "--claude", command="git status\ngit commit -m 'msg'").returncode == 2
    assert run_guard(repo, "--claude", command="git -C . commit -m 'msg'").returncode == 2
