import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"
TESTING = REPO / "testing"
SCRIPTS = TESTING / "scripts"

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://ecommerce:ecommerce@localhost:5433/ecommerce_test"
DEFAULT_SMOKE_BASE_URL = "http://localhost:3000"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    cwd: Path = REPO
    env: dict[str, str] = field(default_factory=dict)


def tool(name: str) -> str:
    return shutil.which(name) or name


def uv_backend(*arguments: str) -> list[str]:
    return [tool("uv"), "run", "--project", str(BACKEND), "--frozen", *arguments]


def pytest_steps(name: str, *paths: str) -> list[Step]:
    command = uv_backend("pytest", "-c", str(BACKEND / "pyproject.toml"), *paths)
    env = {"TEST_DATABASE_URL": os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)}
    return [Step(name, command, env=env)]


def lint_steps() -> list[Step]:
    config = str(BACKEND / "pyproject.toml")
    return [
        Step("ruff check", uv_backend("ruff", "check", "--config", config, "backend", "testing")),
        Step(
            "ruff format",
            uv_backend("ruff", "format", "--check", "--config", config, "backend", "testing"),
        ),
        Step("import-linter", uv_backend("lint-imports"), cwd=BACKEND),
        Step("tsc", [tool("npm"), "run", "typecheck"], cwd=FRONTEND),
    ]


def nocomments_steps() -> list[Step]:
    roots = [
        "backend/src",
        "backend/migrations",
        "frontend/src",
        "frontend/vite.config.ts",
        "testing",
    ]
    return script_steps("check_no_comments", roots)


def tooling_steps() -> list[Step]:
    return pytest_steps("tooling tests", "testing/tooling")


def backend_steps() -> list[Step]:
    return pytest_steps("backend tests", "testing/backend")


def frontend_steps() -> list[Step]:
    return [Step("vitest", [tool("npm"), "test"], cwd=FRONTEND)]


def smoke_steps() -> list[Step]:
    base_url = os.environ.get("SMOKE_BASE_URL", DEFAULT_SMOKE_BASE_URL)
    return script_steps("smoke_test", ["--base-url", base_url])


def script_steps(name: str, arguments: Sequence[str]) -> list[Step]:
    return [Step(f"script {name}", [sys.executable, "-I", str(SCRIPTS / f"{name}.py"), *arguments])]


COMMANDS: dict[str, Callable[[], list[Step]]] = {
    "lint": lint_steps,
    "nocomments": nocomments_steps,
    "tooling": tooling_steps,
    "backend": backend_steps,
    "frontend": frontend_steps,
    "smoke": smoke_steps,
}

ALL_ORDER = ["lint", "nocomments", "tooling", "backend", "frontend", "smoke"]


def execute(steps: Sequence[Step]) -> int:
    for step in steps:
        print(f"\n=== {step.name} ===", flush=True)
        completed = subprocess.run(step.command, cwd=step.cwd, env={**os.environ, **step.env})
        if completed.returncode != 0:
            print(f"\nFAILED: {step.name} (exit code {completed.returncode})", flush=True)
            return completed.returncode
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="run.py", description="The single way to run checks.")
    parser.add_argument("command", choices=[*COMMANDS, "all", "script"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)

    if parsed.command == "script":
        if not parsed.arguments:
            parser.error("script needs a script name")
        steps = script_steps(parsed.arguments[0], parsed.arguments[1:])
    elif parsed.command == "all":
        steps = [step for name in ALL_ORDER for step in COMMANDS[name]()]
    else:
        steps = COMMANDS[parsed.command]()

    result = execute(steps)
    if result == 0:
        print(f"\nOK: {parsed.command}", flush=True)
    return result


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
