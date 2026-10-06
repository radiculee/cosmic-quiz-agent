"""Local API server for development: serves the WSGI apps in `api/` the way Vercel will.

    python -m dev.api_server [--port 8787]

Vite forwards /api to it (vite.config.ts), so `pnpm dev` and this server together are the whole
app on one machine. Each route is the same `app` object Vercel loads from that file, served by
the standard library's `wsgiref` with a thread per request (a live run streams for about 20
seconds). It lives outside `api/` so Vercel never deploys it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from dotenv import load_dotenv

from agent.console import use_utf8_output
from api import item, report, research, reveal, topics

ROUTES: dict[str, WSGIApplication] = {
    "/api/topics": topics.app,
    "/api/item": item.app,
    "/api/reveal": reveal.app,
    "/api/report": report.app,
    "/api/research": research.app,
}
DEFAULT_PORT = 8787


def dispatch(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    """Send each request to the app for its path, as Vercel routes `api/<name>.py`."""
    path = str(environ.get("PATH_INFO", "")).rstrip("/")
    app = ROUTES.get(path)
    if app is None:
        body = json.dumps({"error": f"No API route {path}."}).encode("utf-8")
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]
    return app(environ, start_response)


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    """One short line per request instead of the default access log."""

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        sys.stderr.write(f"{self.command} {self.path} -> {code}\n")


def main(argv: list[str] | None = None) -> None:
    use_utf8_output()
    parser = argparse.ArgumentParser(prog="python -m dev.api_server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    load_dotenv(".env")
    server = make_server(
        "127.0.0.1",
        args.port,
        dispatch,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    )
    print(f"API on http://127.0.0.1:{args.port} ({', '.join(ROUTES)}). Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
