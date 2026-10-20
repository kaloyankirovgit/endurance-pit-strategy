#!/usr/bin/env python3
"""Block a commit that would include a git-ignored file.

Used twice: as the git pre-commit hook (any commit, from any tool) and as a
Claude Code PreToolUse hook (`--claude`), which reads the tool call from stdin.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


def ignored_files_in_index() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--ignored", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


GIT_COMMIT = re.compile(r"(?:^|[;&|(\n])\s*git\s+(?:-C\s+\S+\s+)*commit\b([^;&|\n]*)")
SKIPS_HOOK = re.compile(r"(?:^|\s)(?:--no-verify|-n|-[a-zA-Z]*n[a-zA-Z]*)(?=\s|$)")


def check_claude_command(command: str) -> str | None:
    commits = [match.group(1) for match in GIT_COMMIT.finditer(command)]
    if not commits:
        return None
    if any(SKIPS_HOOK.search(args) for args in commits):
        return "Commits must not skip the pre-commit check (--no-verify)."
    offenders = ignored_files_in_index()
    if offenders:
        return f"These git-ignored files are staged or tracked and must not be committed: {offenders}"
    return None


def main(argv: list[str]) -> int:
    if "--claude" in argv:
        tool_call = json.load(sys.stdin)
        reason = check_claude_command(tool_call.get("tool_input", {}).get("command", ""))
        if reason:
            print(reason, file=sys.stderr)
            return 2
        return 0

    offenders = ignored_files_in_index()
    if offenders:
        print("Commit blocked. These git-ignored files are staged or tracked:", file=sys.stderr)
        for path in offenders:
            print(f"  {path}", file=sys.stderr)
        print("Unstage them with: git restore --staged <path>", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
