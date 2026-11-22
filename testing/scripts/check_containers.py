import subprocess
import sys
from collections.abc import Mapping, Sequence

ROOT_UID = "0"

type Process = tuple[str, str]


def docker(*arguments: str) -> str:
    completed = subprocess.run(["docker", *arguments], capture_output=True, text=True, check=True)
    return completed.stdout


def process_users(top_output: str) -> list[Process]:
    processes = []
    for line in top_output.splitlines()[1:]:
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            processes.append((parts[0], parts[2].strip()))
    return processes


def root_processes(processes: Mapping[str, Sequence[Process]]) -> list[str]:
    return [
        f"{container}: {command}"
        for container, found in processes.items()
        for uid, command in found
        if uid == ROOT_UID
    ]


def running_containers() -> dict[str, list[Process]]:
    identifiers = docker("compose", "ps", "--quiet").split()
    found = {}
    for identifier in identifiers:
        name = docker("inspect", "--format", "{{.Name}}", identifier).strip().lstrip("/")
        found[name] = process_users(docker("top", identifier, "-eo", "uid,pid,comm"))
    return found


def main(argv: Sequence[str]) -> int:
    containers = running_containers()
    if not containers:
        print("FAIL  no running containers; start the stack first")
        return 1
    for name, processes in sorted(containers.items()):
        users = sorted({uid for uid, _ in processes})
        print(f"{name}: user ids {', '.join(users)}")
    offenders = root_processes(containers)
    for offender in offenders:
        print(f"FAIL  runs as root: {offender}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
