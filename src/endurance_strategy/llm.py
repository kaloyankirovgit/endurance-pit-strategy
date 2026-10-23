from __future__ import annotations

import json
import subprocess


class ClaudeCallError(RuntimeError):
    pass


def claude_json(prompt: str, system_prompt: str, schema: dict, workdir: str, timeout_s: int = 600) -> dict:
    """One headless Claude Code call with no tools and a fixed JSON schema for the answer.

    Run from an empty `workdir` so no project instructions or memory load. Returns the
    structured answer plus the model names, so every logged answer says what produced it.
    """
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--system-prompt", system_prompt,
            "--tools", "",
            "--json-schema", json.dumps(schema),
            "--output-format", "json",
            "--no-session-persistence",
        ],
        cwd=workdir, capture_output=True, text=True, timeout=timeout_s,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ClaudeCallError(f"no JSON from claude -p: {result.stderr[:500]}") from error
    if payload.get("is_error") or "structured_output" not in payload:
        raise ClaudeCallError(str(payload.get("result"))[:500])
    return {"output": payload["structured_output"], "models": sorted(payload.get("modelUsage", {}))}
