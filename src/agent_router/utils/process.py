from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    argv: tuple[str, ...]
    cwd: Path | None = None
    environment: Mapping[str, str] | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        if not self.argv or any(not argument for argument in self.argv):
            raise ValueError("process arguments must be non-empty strings")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    def __call__(self, request: ProcessRequest) -> ProcessResult: ...


class ProcessExecutionError(RuntimeError):
    def __init__(self, message: str, request: ProcessRequest) -> None:
        super().__init__(message)
        self.request = request


def run_process(request: ProcessRequest) -> ProcessResult:
    try:
        completed = subprocess.run(
            request.argv,
            cwd=request.cwd,
            env=request.environment,
            timeout=request.timeout,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ProcessExecutionError(
            f"process timed out: {request.argv[0]}", request
        ) from error
    except OSError as error:
        raise ProcessExecutionError(
            f"process could not start: {request.argv[0]}", request
        ) from error
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)
