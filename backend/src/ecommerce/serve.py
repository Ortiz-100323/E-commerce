import argparse
from collections.abc import Sequence

import uvicorn

APP = "ecommerce.main:create_production_app"
LOOP = "ecommerce.event_loop:new_event_loop"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ecommerce.serve", description="Run the backend without Docker."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    arguments = parser.parse_args(argv)
    uvicorn.run(
        APP,
        factory=True,
        host=arguments.host,
        port=arguments.port,
        access_log=False,
        loop=LOOP,
    )


if __name__ == "__main__":
    main()
