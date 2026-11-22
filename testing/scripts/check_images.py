import subprocess
import sys
from collections.abc import Mapping, Sequence

MEGABYTE = 1_000_000
BUDGETS_MB = {
    "ecommerce-frontend": 120,
    "ecommerce-backend": 500,
}


def image_size(image: str) -> int | None:
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Size}}", image],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return int(completed.stdout.strip())


def over_budget(sizes: Mapping[str, int], budgets: Mapping[str, int]) -> list[str]:
    problems = []
    for image, budget in budgets.items():
        size = sizes.get(image)
        if size is None:
            problems.append(f"{image}: image not found; build the stack first")
        elif size > budget * MEGABYTE:
            problems.append(f"{image}: {size // MEGABYTE} MB, budget {budget} MB")
    return problems


def main(argv: Sequence[str]) -> int:
    sizes = {}
    for image in BUDGETS_MB:
        size = image_size(image)
        if size is not None:
            sizes[image] = size
            print(f"{image}: {size // MEGABYTE} MB (budget {BUDGETS_MB[image]} MB)")
    problems = over_budget(sizes, BUDGETS_MB)
    for problem in problems:
        print(f"FAIL  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
