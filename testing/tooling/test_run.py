from types import ModuleType

import pytest


def test_all_runs_every_check_in_ci_order(runner: ModuleType) -> None:
    assert runner.ALL_ORDER == ["lint", "nocomments", "tooling", "backend", "frontend", "smoke"]
    assert set(runner.ALL_ORDER) <= set(runner.COMMANDS)


def test_each_command_has_at_least_one_step(runner: ModuleType) -> None:
    for name in runner.ALL_ORDER:
        assert runner.COMMANDS[name](), name


def test_lint_runs_every_static_check(runner: ModuleType) -> None:
    names = [step.name for step in runner.COMMANDS["lint"]()]
    assert names == [
        "ruff check",
        "ruff format",
        "import-linter",
        "mypy",
        "tsc",
        "prettier",
        "script check_no_raw_html",
    ]


def test_backend_tests_enforce_domain_and_application_coverage(runner: ModuleType) -> None:
    command = runner.COMMANDS["backend"]()[0].command
    assert "--cov=ecommerce.catalog.domain" in command
    assert "--cov=ecommerce.catalog.application" in command
    assert "--cov=ecommerce.shared_kernel.domain" in command
    assert "--cov-fail-under=95" in command


def test_unknown_command_is_rejected(runner: ModuleType) -> None:
    with pytest.raises(SystemExit) as raised:
        runner.main(["nope"])
    assert raised.value.code == 2


def test_script_command_runs_the_named_script_isolated(runner: ModuleType) -> None:
    steps = runner.script_steps("smoke_test", ["--base-url", "http://x"])
    assert len(steps) == 1
    command = steps[0].command
    assert command[1] == "-I"
    assert command[2].endswith("smoke_test.py")
    assert command[3:] == ["--base-url", "http://x"]


def test_frontend_tests_enforce_coverage(runner: ModuleType) -> None:
    command = runner.COMMANDS["frontend"]()[0].command
    assert command[-2:] == ["run", "test:coverage"]


def test_the_docker_checks_run_on_the_host_and_stay_out_of_all(runner: ModuleType) -> None:
    assert {"containers", "images"} <= set(runner.COMMANDS)
    assert {"containers", "images"}.isdisjoint(runner.ALL_ORDER)
