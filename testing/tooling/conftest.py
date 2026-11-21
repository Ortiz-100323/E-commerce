import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TESTING_DIR = Path(__file__).resolve().parent.parent


def load_module(relative_path: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TESTING_DIR / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def no_comments() -> ModuleType:
    return load_module("scripts/check_no_comments.py", "check_no_comments")


@pytest.fixture(scope="session")
def runner() -> ModuleType:
    return load_module("run.py", "testing_runner")
