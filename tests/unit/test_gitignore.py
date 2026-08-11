from __future__ import annotations

import pytest
from pathlib import Path
from pathlib import PurePosixPath

from agent_router.utils.gitignore import (
    GitIgnoreError,
    GitIgnorePolicy,
    IgnoreMode,
    plan_gitignore,
    verify_gitignore,
)
from agent_router.utils.process import ProcessExecutionError, ProcessRequest, ProcessResult
from agent_router.utils.process import run_process
from agent_router.utils.mutation import (
    DirectoryProjection,
    MutationPlan,
    RelativeWrite,
    Write,
    apply_mutation,
)


def init_repo(path: Path) -> Path:
    path.mkdir()
    result = run_process(ProcessRequest(argv=("git", "init", "--quiet"), cwd=path))
    assert result.returncode == 0, result.stderr
    return path


def test_validates_exact_pattern_and_none_ignore_policies() -> None:
    assert GitIgnorePolicy() == GitIgnorePolicy(IgnoreMode.EXACT)
    assert GitIgnorePolicy("pattern", "/.agents/skills/*/").mode is IgnoreMode.PATTERN
    assert GitIgnorePolicy("none").mode is IgnoreMode.NONE

    with pytest.raises(ValueError, match="requires one"):
        GitIgnorePolicy("pattern")
    with pytest.raises(ValueError, match="does not accept"):
        GitIgnorePolicy("exact", "*.md")
    with pytest.raises(ValueError, match="single-line"):
        GitIgnorePolicy("pattern", "one\ntwo")


def test_none_policy_bypasses_git_and_ignore_files(tmp_path: Path) -> None:
    calls: list[ProcessRequest] = []

    def runner(request: ProcessRequest) -> ProcessResult:
        calls.append(request)
        raise AssertionError("Git must not run")

    result = plan_gitignore(
        project_root=tmp_path / "missing-project",
        target=tmp_path / "outside" / "reviewer",
        state_root=tmp_path / "outside" / ".z-agent-router",
        policy=GitIgnorePolicy("none"),
        runner=runner,
    )

    assert result is None
    assert calls == []


def test_managed_policy_requires_a_containing_git_worktree(tmp_path: Path) -> None:
    requests: list[ProcessRequest] = []

    def runner(request: ProcessRequest) -> ProcessResult:
        requests.append(request)
        return ProcessResult(128, "", "not a git repository")

    with pytest.raises(GitIgnoreError, match="worktree"):
        plan_gitignore(
            project_root=tmp_path,
            target=tmp_path / ".agents" / "skills" / "reviewer",
            state_root=tmp_path / ".z-agent-router",
            policy=GitIgnorePolicy(),
            runner=runner,
        )

    assert requests == [
        ProcessRequest(argv=("git", "rev-parse", "--show-toplevel"), cwd=tmp_path)
    ]


def test_exact_policy_plans_only_missing_root_relative_rules(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("existing", encoding="utf-8")
    ignore_file = repo / ".gitignore"
    ignore_file.write_bytes(b"# keep\n")

    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy(),
        runner=run_process,
    )

    assert plan is not None
    assert plan.worktree == repo.resolve()
    assert plan.ignore_file == ignore_file
    assert plan.content == (
        b"# keep\n/.z-agent-router/\n/.agents/skills/reviewer/\n"
    )
    assert ignore_file.read_bytes() == b"# keep\n"


def test_exact_policy_reuses_effective_glob_coverage(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    ignore_file = repo / ".gitignore"
    original = b"/.agents/skills/*/\n"
    ignore_file.write_bytes(original)

    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy(),
        runner=run_process,
    )

    assert plan is not None
    assert plan.content == original + b"/.z-agent-router/\n"


def test_exact_policy_honors_an_effective_negation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    ignore_file = repo / ".gitignore"
    original = (
        b"/.z-agent-router/\n"
        b"/.agents/skills/reviewer/*\n"
        b"!/.agents/skills/reviewer/.agent-router-ignore-probe\n"
    )
    ignore_file.write_bytes(original)

    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy(),
        runner=run_process,
    )

    assert plan is not None
    assert plan.content == original + b"/.agents/skills/reviewer/\n"


def test_verifies_an_effective_explicit_pattern(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy("pattern", "/.agents/skills/*/"),
        runner=run_process,
    )
    assert plan is not None and plan.content is not None
    plan.ignore_file.write_bytes(plan.content)

    verify_gitignore(plan, runner=run_process)


@pytest.mark.parametrize("pattern", ["*.txt", "!/.agents/skills/reviewer/"])
def test_rejects_an_ineffective_or_negated_explicit_pattern(
    tmp_path: Path, pattern: str
) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy("pattern", pattern),
        runner=run_process,
    )
    assert plan is not None and plan.content is not None
    plan.ignore_file.write_bytes(plan.content)

    with pytest.raises(GitIgnoreError, match="ineffective"):
        verify_gitignore(plan, runner=run_process)


def test_failed_git_verification_rolls_back_ignore_and_projection(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    (target / "old.txt").write_bytes(b"old")
    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy("pattern", "*.txt"),
        runner=run_process,
    )
    assert plan is not None and plan.content is not None

    with pytest.raises(GitIgnoreError, match="ineffective"):
        apply_mutation(
            MutationPlan(
                writes=(Write(plan.ignore_file, plan.content),),
                projections=(
                    DirectoryProjection(
                        target,
                        (RelativeWrite(PurePosixPath("SKILL.md"), b"new"),),
                    ),
                ),
                before_projection_swap=(
                    lambda: verify_gitignore(plan, runner=run_process),
                ),
            )
        )

    assert not plan.ignore_file.exists()
    assert (target / "old.txt").read_bytes() == b"old"
    assert not (target / "SKILL.md").exists()


def test_reuses_nested_coverage_for_a_forced_tracked_target(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    skill_root = repo / ".agents" / "skills"
    target = skill_root / "reviewer"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_bytes(b"tracked")
    (skill_root / ".gitignore").write_bytes(b"reviewer/\n")
    added = run_process(
        ProcessRequest(
            argv=("git", "add", "-f", ".agents/skills/reviewer/SKILL.md"),
            cwd=repo,
        )
    )
    assert added.returncode == 0, added.stderr

    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy(),
        runner=run_process,
    )

    assert plan is not None
    assert plan.content == b"/.z-agent-router/\n"


def test_preserves_existing_ignore_bytes_before_appending_rules(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    target = repo / ".agents" / "skills" / "reviewer"
    target.mkdir(parents=True)
    ignore_file = repo / ".gitignore"
    original = b"# windows line\r\n# no final newline"
    ignore_file.write_bytes(original)

    plan = plan_gitignore(
        project_root=repo,
        target=target,
        state_root=repo / ".z-agent-router",
        policy=GitIgnorePolicy(),
        runner=run_process,
    )

    assert plan is not None and plan.content is not None
    assert plan.content.startswith(original + b"\n")
    assert plan.content.removeprefix(original + b"\n") == (
        b"/.z-agent-router/\n/.agents/skills/reviewer/\n"
    )


def test_rejects_managed_paths_outside_the_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    with pytest.raises(GitIgnoreError, match="outside"):
        plan_gitignore(
            project_root=repo,
            target=tmp_path / "outside" / "reviewer",
            state_root=repo / ".z-agent-router",
            policy=GitIgnorePolicy(),
            runner=run_process,
        )


def test_reports_an_unavailable_git_executable(tmp_path: Path) -> None:
    def runner(request: ProcessRequest) -> ProcessResult:
        raise ProcessExecutionError("missing", request)

    with pytest.raises(GitIgnoreError, match="unavailable"):
        plan_gitignore(
            project_root=tmp_path,
            target=tmp_path / ".agents" / "skills" / "reviewer",
            state_root=tmp_path / ".z-agent-router",
            policy=GitIgnorePolicy(),
            runner=runner,
        )


def test_rejects_an_unexpected_check_ignore_status(tmp_path: Path) -> None:
    calls = 0

    def runner(request: ProcessRequest) -> ProcessResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProcessResult(0, f"{tmp_path}\n", "")
        return ProcessResult(2, "", "unexpected")

    with pytest.raises(GitIgnoreError, match="evaluate"):
        plan_gitignore(
            project_root=tmp_path,
            target=tmp_path / ".agents" / "skills" / "reviewer",
            state_root=tmp_path / ".z-agent-router",
            policy=GitIgnorePolicy(),
            runner=runner,
        )
