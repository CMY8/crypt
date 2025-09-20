"""Minimal HTTP endpoint exposing dashboard data."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Tuple

DashboardPayload = Dict[str, object]
StateProvider = Callable[[], DashboardPayload]


def _make_handler(state_provider: StateProvider) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler contract)
            if self.path not in {'/api/dashboard', '/api/dashboard/'}:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            payload = state_provider()
            body = json.dumps(payload).encode('utf-8')
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003 (shadow builtins)
            return

    return DashboardHandler


def serve_dashboard_api(
    state_provider: StateProvider,
    host: str = '127.0.0.1',
    port: int = 8000,
) -> Tuple[ThreadingHTTPServer, threading.Thread]:
    """Start the dashboard API in a background thread."""
    handler = _make_handler(state_provider)
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


__all__ = ['serve_dashboard_api']
