import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ecommerce.healthcheck import main


class Health(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self) -> None:
        self.send_response(type(self).status)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def server() -> Iterator[HTTPServer]:
    httpd = HTTPServer(("127.0.0.1", 0), Health)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def url(httpd: HTTPServer) -> str:
    host, port = httpd.server_address[0], httpd.server_address[1]
    return f"http://{host!s}:{port}/api/v1/health"


def test_a_healthy_answer_exits_with_zero(server: HTTPServer) -> None:
    Health.status = 200

    assert main([url(server)]) == 0


def test_an_unhealthy_answer_exits_with_one(server: HTTPServer) -> None:
    Health.status = 503

    assert main([url(server)]) == 1


def test_an_unreachable_server_exits_with_one() -> None:
    assert main(["http://127.0.0.1:1/api/v1/health"]) == 1
