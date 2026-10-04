"""Local API server for development: serves the functions in `api/` the way Vercel will.

    python -m dev.api_server [--port 8787]

Vite forwards /api to it (vite.config.ts), so `pnpm dev` and this server together are the whole
app on one machine. It lives outside `api/` so Vercel never deploys it.
"""

from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer

from dotenv import load_dotenv

from agent.console import use_utf8_output
from agent.web import ApiRequest, ApiResponse, Handle, error_response, make_handler
from api import item, report, reveal, topics

ROUTES: dict[str, Handle] = {
    "/api/topics": topics.handle,
    "/api/item": item.handle,
    "/api/reveal": reveal.handle,
    "/api/report": report.handle,
}
DEFAULT_PORT = 8787


def dispatch(request: ApiRequest) -> ApiResponse:
    handle = ROUTES.get(request.path.rstrip("/"))
    if handle is None:
        return error_response(404, f"No API route {request.path}.")
    return handle(request)


def main(argv: list[str] | None = None) -> None:
    use_utf8_output()
    parser = argparse.ArgumentParser(prog="python -m dev.api_server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    load_dotenv(".env")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(dispatch))
    print(f"API on http://127.0.0.1:{args.port} ({', '.join(ROUTES)}). Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
