"""
tools.py — Tool Layer.

Thin wrappers around local capabilities that workers can call.
These are deterministic — they execute code, run shells, read files, etc.
Add new tools here as the system grows (MATLAB, CAD, search, etc.).
"""

from __future__ import annotations

import subprocess
import logging
from pathlib import Path

from config import Paths

logger = logging.getLogger(__name__)


def run_python(code: str, timeout: int = 30) -> dict:
    """
    Execute a Python snippet in an isolated subprocess.
    Returns {"stdout": ..., "stderr": ..., "returncode": ...}.
    """
    result = subprocess.run(
        ["python3", "-c", code],
        capture_output=True, text=True, timeout=timeout,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_shell(command: str, timeout: int = 30) -> dict:
    """Run an arbitrary shell command. Use carefully."""
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=timeout,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def read_file(path: str | Path) -> str:
    """Read a text file from the artifacts directory or an absolute path."""
    p = Path(path)
    if not p.is_absolute():
        p = Paths.ARTIFACTS / p
    return p.read_text()


def write_file(filename: str, content: str) -> Path:
    """Write content to a file in the artifacts directory."""
    path = Paths.ARTIFACTS / filename
    path.write_text(content)
    logger.info("[TOOL] Wrote %d bytes → %s", len(content), path)
    return path


# ── Git Keep/Revert (T-02) ────────────────────────────────────────

_PROJECT_ROOT = Paths.ROOT.parent  # ai-lab/ → project root


def git_commit_snapshot(message: str = "auto: snapshot before experiment") -> dict:
    """
    Stage all changes and commit — snapshot before an experiment runs.
    Returns {"commit_hash": ..., "success": True} or {"error": ..., "success": False}.
    """
    try:
        # Stage all tracked + untracked changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        # Check if there's anything to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(_PROJECT_ROOT), capture_output=True, timeout=10,
        )
        if status.returncode == 0:
            # Nothing staged — get current HEAD as the snapshot
            head = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=10,
            )
            commit_hash = head.stdout.strip()
            logger.info("[GIT] No changes to commit — using HEAD %s as snapshot", commit_hash)
            return {"commit_hash": commit_hash, "success": True, "was_noop": True}

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "success": False}

        # Get the short hash of the new commit
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        commit_hash = head.stdout.strip()
        logger.info("[GIT] Snapshot committed: %s — %s", commit_hash, message)
        return {"commit_hash": commit_hash, "success": True, "was_noop": False}

    except Exception as e:
        logger.error("[GIT] Snapshot failed: %s", e)
        return {"error": str(e), "success": False}


def git_revert_last() -> dict:
    """
    Revert the last commit (undo a failed experiment).
    Uses git revert --no-edit to create a new commit that undoes the changes.
    Returns {"reverted_hash": ..., "success": True} or {"error": ..., "success": False}.
    """
    try:
        # Get the hash we're about to revert
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=10,
        )
        target_hash = head.stdout.strip()

        result = subprocess.run(
            ["git", "revert", "--no-edit", "HEAD"],
            cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "success": False}

        logger.info("[GIT] Reverted commit %s", target_hash)
        return {"reverted_hash": target_hash, "success": True}

    except Exception as e:
        logger.error("[GIT] Revert failed: %s", e)
        return {"error": str(e), "success": False}


# ── Tool registry (for the worker to request tools by name) ─────
REGISTRY: dict[str, callable] = {
    "run_python": run_python,
    "run_shell": run_shell,
    "read_file": read_file,
    "write_file": write_file,
}


def dispatch(tool_name: str, **kwargs) -> dict:
    """
    Call a tool by name with keyword arguments.
    Returns a dict with at minimum {"result": ...} or {"error": ...}.
    """
    fn = REGISTRY.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}. Available: {list(REGISTRY)}"}
    try:
        result = fn(**kwargs)
        return {"result": result}
    except Exception as exc:
        logger.exception("[TOOL] %s raised: %s", tool_name, exc)
        return {"error": str(exc)}
