from types import ModuleType

import pytest


def test_all_runs_every_check_in_ci_order(runner: ModuleType) -> None:
    assert runner.ALL_ORDER == ["lint", "nocomments", "tooling", "backend", "frontend", "smoke"]
    assert set(runner.ALL_ORDER) <= set(runner.COMMANDS)


def test_each_command_has_at_least_one_step(runner: ModuleType) -> None:
    for name in runner.ALL_ORDER:
        assert runner.COMMANDS[name](), name


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
