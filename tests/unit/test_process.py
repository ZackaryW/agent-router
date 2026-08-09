from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError

import pytest

from agent_router.utils.process import (
    ProcessExecutionError,
    ProcessRequest,
    run_process,
)


def test_run_process_captures_output_and_uses_environment_and_cwd(tmp_path) -> None:
    request = ProcessRequest(
        argv=(
            sys.executable,
            "-c",
            "import os; from pathlib import Path; "
            "print(os.environ['AGENT_ROUTER_TEST']); "
            "print(Path.cwd()); print('problem', file=__import__('sys').stderr)",
        ),
        cwd=tmp_path,
        environment={"AGENT_ROUTER_TEST": "isolated"},
        timeout=5,
    )

    result = run_process(request)

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["isolated", str(tmp_path)]
    assert result.stderr.strip() == "problem"
    with pytest.raises(FrozenInstanceError):
        request.timeout = 1  # type: ignore[misc]


def test_run_process_wraps_missing_executable() -> None:
    request = ProcessRequest(argv=("agent-router-definitely-missing",))

    with pytest.raises(ProcessExecutionError, match="could not start") as raised:
        run_process(request)

    assert raised.value.request == request


def test_run_process_wraps_timeout() -> None:
    request = ProcessRequest(
        argv=(sys.executable, "-c", "import time; time.sleep(2)"),
        timeout=0.01,
    )

    with pytest.raises(ProcessExecutionError, match="timed out") as raised:
        run_process(request)

    assert raised.value.request == request
