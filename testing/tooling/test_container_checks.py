from types import ModuleType

import pytest

TOP_OUTPUT = """UID                 PID                 COMMAND
70                  4121                postgres
70                  4121                postgres
"""


def test_reads_the_user_of_every_process(check_containers: ModuleType) -> None:
    assert check_containers.process_users(TOP_OUTPUT) == [("70", "postgres"), ("70", "postgres")]


def test_flags_a_container_with_a_root_process(check_containers: ModuleType) -> None:
    processes = {
        "ecommerce-db-1": [("70", "postgres")],
        "ecommerce-frontend-1": [("101", "nginx"), ("0", "nginx")],
    }

    assert check_containers.root_processes(processes) == ["ecommerce-frontend-1: nginx"]


def test_a_stack_without_root_passes(check_containers: ModuleType) -> None:
    assert check_containers.root_processes({"ecommerce-backend-1": [("999", "uvicorn")]}) == []


def test_reports_images_over_their_budget(check_images: ModuleType) -> None:
    sizes = {"ecommerce-frontend": 90_000_000, "ecommerce-backend": 510_000_000}

    assert check_images.over_budget(
        sizes, {"ecommerce-frontend": 120, "ecommerce-backend": 500}
    ) == ["ecommerce-backend: 510 MB, budget 500 MB"]


def test_a_missing_image_is_reported(check_images: ModuleType) -> None:
    assert check_images.over_budget({}, {"ecommerce-backend": 500}) == [
        "ecommerce-backend: image not found; build the stack first"
    ]


@pytest.mark.parametrize("size", [0, 120_000_000])
def test_an_image_within_budget_passes(check_images: ModuleType, size: int) -> None:
    assert check_images.over_budget({"ecommerce-frontend": size}, {"ecommerce-frontend": 120}) == []
