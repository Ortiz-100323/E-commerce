import ast
import sys
from pathlib import Path

import pytest

import ecommerce

SOURCE = Path(ecommerce.__file__).resolve().parent
ALLOWED_PROJECT_PREFIXES = ("ecommerce.shared_kernel.domain",)


def domain_packages() -> list[Path]:
    return sorted(path for path in SOURCE.glob("*/domain") if path.is_dir())


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def is_allowed(module: str, own_domain: str) -> bool:
    if module.split(".")[0] in sys.stdlib_module_names:
        return True
    return module.startswith((own_domain, *ALLOWED_PROJECT_PREFIXES))


def test_the_catalog_domain_exists() -> None:
    assert SOURCE / "catalog" / "domain" in domain_packages()


@pytest.mark.parametrize("package", domain_packages(), ids=lambda path: path.parent.name)
def test_a_domain_imports_only_the_standard_library_and_the_shared_kernel_domain(
    package: Path,
) -> None:
    own_domain = f"ecommerce.{package.parent.name}.domain"
    offenders = [
        f"{path.name}: {module}"
        for path in sorted(package.rglob("*.py"))
        for module in imported_modules(path)
        if not is_allowed(module, own_domain)
    ]
    assert offenders == []
