from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from agent_router.utils.process import (
    ProcessExecutionError,
    ProcessRequest,
    ProcessRunner,
)


class GitIgnoreError(ValueError):
    """A managed Git-ignore request cannot be established safely."""


class IgnoreMode(StrEnum):
    EXACT = "exact"
    PATTERN = "pattern"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class GitIgnorePolicy:
    mode: IgnoreMode = IgnoreMode.EXACT
    pattern: str | None = None

    def __post_init__(self) -> None:
        mode = IgnoreMode(self.mode)
        object.__setattr__(self, "mode", mode)
        if mode is IgnoreMode.PATTERN:
            if self.pattern is None or self.pattern == "":
                raise ValueError("pattern ignore policy requires one pattern")
            if any(character in self.pattern for character in "\r\n\0"):
                raise ValueError("ignore pattern must be a single-line string")
        elif self.pattern is not None:
            raise ValueError(f"{mode.value} ignore policy does not accept a pattern")


@dataclass(frozen=True, slots=True)
class GitIgnorePlan:
    worktree: Path
    ignore_file: Path
    content: bytes | None
    probes: tuple[Path, ...]


def plan_gitignore(
    *,
    project_root: Path,
    target: Path,
    state_root: Path,
    policy: GitIgnorePolicy,
    runner: ProcessRunner,
) -> GitIgnorePlan | None:
    if policy.mode is IgnoreMode.NONE:
        return None
    project = Path(project_root).resolve()
    try:
        result = runner(
            ProcessRequest(argv=("git", "rev-parse", "--show-toplevel"), cwd=project)
        )
    except ProcessExecutionError as error:
        raise GitIgnoreError("Git is unavailable for managed ignore policy") from error
    if result.returncode != 0 or not result.stdout.strip():
        raise GitIgnoreError("managed ignore policy requires a containing Git worktree")
    worktree = Path(result.stdout.strip()).resolve()
    for path in (project, Path(target).resolve(), Path(state_root).resolve()):
        try:
            path.relative_to(worktree)
        except ValueError as error:
            raise GitIgnoreError("managed ignore path lies outside the Git worktree") from error
    ignore_file = worktree / ".gitignore"
    if ignore_file.is_symlink() or (ignore_file.exists() and not ignore_file.is_file()):
        raise GitIgnoreError("root .gitignore is not a writable regular file")
    try:
        existing = ignore_file.read_bytes() if ignore_file.exists() else b""
        existing.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise GitIgnoreError("root .gitignore cannot be read as UTF-8") from error

    state = Path(state_root).resolve()
    selected_target = Path(target).resolve()
    probes = (
        state / ".agent-router-ignore-probe",
        selected_target / ".agent-router-ignore-probe",
    )
    additions: list[str] = []
    if not _is_ignored(worktree, probes[0], runner):
        additions.append(_exact_rule(worktree, state))
    if not _is_ignored(worktree, probes[1], runner):
        additions.append(
            policy.pattern
            if policy.mode is IgnoreMode.PATTERN
            else _exact_rule(worktree, selected_target)
        )
    content = _append_rules(existing, additions) if additions else None
    return GitIgnorePlan(
        worktree,
        ignore_file,
        content,
        probes,
    )


def verify_gitignore(plan: GitIgnorePlan, *, runner: ProcessRunner) -> None:
    if not all(_is_ignored(plan.worktree, probe, runner) for probe in plan.probes):
        raise GitIgnoreError("planned Git ignore policy is ineffective")


def _is_ignored(worktree: Path, probe: Path, runner: ProcessRunner) -> bool:
    relative = probe.relative_to(worktree).as_posix()
    request = ProcessRequest(
        argv=("git", "check-ignore", "--no-index", "-q", "--", relative),
        cwd=worktree,
    )
    try:
        result = runner(request)
    except ProcessExecutionError as error:
        raise GitIgnoreError("Git is unavailable for ignore evaluation") from error
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise GitIgnoreError("Git could not evaluate effective ignore policy")


def _exact_rule(worktree: Path, path: Path) -> str:
    relative = path.relative_to(worktree).as_posix().rstrip("/")
    return f"/{relative}/"


def _append_rules(existing: bytes, rules: list[str]) -> bytes:
    separator = b"" if not existing or existing.endswith(b"\n") else b"\n"
    return existing + separator + "".join(f"{rule}\n" for rule in rules).encode("utf-8")
