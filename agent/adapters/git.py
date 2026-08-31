from pathlib import Path
import subprocess


class GitReadError(RuntimeError):
    pass


def _run(repo_path, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitReadError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def read_git_health(
    workspace,
    expected_remote_url,
    expected_main_head,
    core6_paths,
    protected_baseline_doc="docs/protection/PROTECTED_BASELINE_SHA256.md",
):
    workspace = Path(workspace)
    if not workspace.exists():
        return {"status": "FAIL", "errors": ["WORKSPACE_MISSING"]}

    errors = []
    try:
        remote_url = _run(workspace, "remote", "get-url", "origin")
        local_main = _run(workspace, "rev-parse", "main")
        remote_line = _run(workspace, "ls-remote", "origin", "refs/heads/main")
        remote_main = remote_line.split()[0] if remote_line else ""
        dirty = bool(_run(workspace, "status", "--porcelain", "--untracked-files=all"))
    except GitReadError as exc:
        return {"status": "UNKNOWN", "errors": [f"GIT_READ_ERROR:{exc}"]}

    if remote_url != expected_remote_url:
        errors.append("REMOTE_URL_MISMATCH")
    if local_main != expected_main_head:
        errors.append("LOCAL_MAIN_MISMATCH")
    if remote_main != expected_main_head:
        errors.append("REMOTE_MAIN_MISMATCH")
    if local_main != remote_main:
        errors.append("LOCAL_REMOTE_MISMATCH")
    if dirty:
        errors.append("WORKSPACE_DIRTY")

    missing = [p for p in core6_paths if not (workspace / p).exists()]
    if missing:
        errors.append("CORE6_PATH_MISSING")
    if not (workspace / protected_baseline_doc).exists():
        errors.append("PROTECTED_BASELINE_DOC_MISSING")

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "remote_url": remote_url,
        "local_main": local_main,
        "remote_main": remote_main,
        "dirty": dirty,
        "missing_core6_paths": missing,
    }
