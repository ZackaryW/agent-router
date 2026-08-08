## Context

The project currently declares Python 3.14 while its newest required language and standard-library facilities are `enum.StrEnum` and `tomllib`, both available in Python 3.11. The dependency set must also resolve under the lower floor.

## Goals / Non-Goals

**Goals:**

- Align declared compatibility with the implementation’s natural Python floor.
- Prove both the base library and optional CLI under CPython 3.11.
- Keep one dependency graph valid across the supported range.

**Non-Goals:**

- Support Python 3.10 or earlier through backports or source rewrites.
- Promise compatibility with unreleased Python versions beyond what dependencies permit.

## Decisions

### Use Python 3.11 as the floor

Python 3.11 is the earliest runtime that provides the current implementation’s standard-library surface without extra dependencies. Python 3.12 or 3.13 would exclude compatible users without simplifying the code; Python 3.10 would require replacing `StrEnum` and `tomllib` or adding backports.

### Verify with a real floor interpreter

Run the complete build, Behave targets, and pytest suite with `uv --python 3.11` rather than relying only on metadata inspection. Static metadata checks alone were rejected because they cannot detect runtime or dependency incompatibility.

### Keep the existing implementation

No production source rewrite is planned. Any failure under 3.11 is treated as a compatibility defect to fix minimally rather than justification for silently raising the floor.

## Risks / Trade-offs

- [A dependency raises its Python minimum later] → Lock and test dependency resolution under Python 3.11 whenever dependencies change.
- [Only the newest interpreter is used during development] → Keep explicit floor-version verification as a repository-owned command expectation.
