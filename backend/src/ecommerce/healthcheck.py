import sys
import urllib.error
import urllib.request
from collections.abc import Sequence

DEFAULT_URL = "http://127.0.0.1:8000/api/v1/health"
TIMEOUT_SECONDS = 3


def main(argv: Sequence[str]) -> int:
    url = argv[0] if argv else DEFAULT_URL
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return 0 if response.status == 200 else 1
    except (urllib.error.URLError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
