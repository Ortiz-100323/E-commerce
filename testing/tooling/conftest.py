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


@pytest.fixture(scope="session")
def check_docs() -> ModuleType:
    return load_module("scripts/check_docs.py", "check_docs")


@pytest.fixture(scope="session")
def no_raw_html() -> ModuleType:
    return load_module("scripts/check_no_raw_html.py", "check_no_raw_html")


@pytest.fixture(scope="session")
def smoke_test() -> ModuleType:
    return load_module("scripts/smoke_test.py", "smoke_test")


@pytest.fixture(scope="session")
def profile_csv() -> ModuleType:
    return load_module("scripts/profile_csv.py", "profile_csv")


@pytest.fixture(scope="session")
def simulate_import() -> ModuleType:
    return load_module("scripts/simulate_import.py", "simulate_import")


@pytest.fixture(scope="session")
def redact_images() -> ModuleType:
    return load_module("scripts/redact_images.py", "redact_images")


@pytest.fixture(scope="session")
def check_containers() -> ModuleType:
    return load_module("scripts/check_containers.py", "check_containers")


@pytest.fixture(scope="session")
def check_images() -> ModuleType:
    return load_module("scripts/check_images.py", "check_images")
