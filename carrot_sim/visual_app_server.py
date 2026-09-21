from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from carrot_sim.visual_replay_frames import ReplayFrameError, load_visual_run, page_frames

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _metadata(run: dict[str, Any]) -> dict[str, Any]:
  return {k: run.get(k) for k in ("run_id", "label", "frame_count",
    "authority", "evidence_class", "rows_sha256")}


def create_visual_server(catalog: list[dict[str, Any]], host: str = "127.0.0.1",
                         port: int = 8772, optimization_dir: Path | None = None) -> ThreadingHTTPServer:
  if host not in LOOPBACK_HOSTS:
    raise ValueError("visual app server must bind to loopback")
  runs = {str(run["run_id"]): run for run in catalog}
  optimization_root = Path(optimization_dir).resolve() if optimization_dir is not None else None
  if len(runs) != len(catalog):
    raise ValueError("duplicate run_id")

  class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
      return

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
      self.send_response(status)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(payload)))
      self.send_header("Cache-Control", "no-store")
      self.send_header("X-Content-Type-Options", "nosniff")
      self.end_headers()
      if self.command != "HEAD": self.wfile.write(payload)

    def _json(self, status: int, data: Any) -> None:
      self._send(status, json.dumps(data, ensure_ascii=False, allow_nan=False,
        separators=(",", ":")).encode(), "application/json; charset=utf-8")
    def do_HEAD(self):
      self.do_GET()

    def do_GET(self):
      parsed = urlparse(self.path)
      path = unquote(parsed.path)
      if ".." in path.split("/"):
        self._json(400, {"error": "invalid path"}); return
      if path == "/healthz":
        self._json(200, {"ok": True, "read_only": True}); return
      if path == "/api/catalog":
        self._json(200, {"runs": [_metadata(run) for run in catalog]}); return
      if path in {"/api/optimization/status", "/api/optimization/report"}:
        if optimization_root is None:
          self._json(404, {"error": "optimization campaign not configured"}); return
        filename = "status.json" if path.endswith("status") else "recommendation.json"
        target = optimization_root / filename
        try:
          payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
          self._json(404, {"error": "optimization artifact not found"}); return
        self._json(200, payload); return
      if path == "/":
        html_path = Path(__file__).with_name("visual_app.html")
        if not html_path.exists():
          self._json(404, {"error": "visual UI not installed"}); return
        self._send(200, html_path.read_bytes(), "text/html; charset=utf-8"); return
      parts = path.strip("/").split("/")
      if len(parts) >= 3 and parts[:2] == ["api", "runs"]:
        run_id = parts[2]
        run = runs.get(run_id)
        if run is None:
          self._json(404, {"error": "run not found"}); return
        if len(parts) == 3:
          self._json(200, _metadata(run)); return
        if len(parts) == 4 and parts[3] == "frames":
          query = parse_qs(parsed.query, keep_blank_values=True)
          if set(query) - {"offset", "limit"}:
            self._json(400, {"error": "invalid query"}); return
          try:
            offset = int(query.get("offset", ["0"])[0])
            limit = int(query.get("limit", ["500"])[0])
            self._json(200, page_frames(run["frames"], offset, limit))
          except (ValueError, ReplayFrameError) as exc:
            self._json(400, {"error": str(exc)})
          return
      self._json(404, {"error": "not found"})

  return ThreadingHTTPServer((host, port), Handler)


def load_catalog_file(path: Path) -> list[dict[str, Any]]:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as exc:
    raise ReplayFrameError(f"cannot read catalog: {path}") from exc
  event_count = data.get("scenario_event_count")
  if isinstance(event_count, bool) or not isinstance(event_count, int) or event_count <= 0:
    raise ReplayFrameError("catalog scenario_event_count must be a positive integer")
  specs = data.get("runs")
  if not isinstance(specs, list) or not specs:
    raise ReplayFrameError("catalog runs must be a non-empty list")
  return [load_visual_run(spec) for spec in specs]


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Local-only Carrot visual simulator")
  parser.add_argument("--catalog", required=True, type=Path)
  parser.add_argument("--host", default="127.0.0.1", choices=sorted(LOOPBACK_HOSTS))
  parser.add_argument("--port", default=8772, type=int)
  args = parser.parse_args(argv)
  try:
    catalog = load_catalog_file(args.catalog)
    server = create_visual_server(catalog, args.host, args.port)
  except (ReplayFrameError, OSError, ValueError) as exc:
    parser.error(str(exc))
  print(f"Carrot visual app: http://{args.host}:{args.port}/", flush=True)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass
  finally:
    server.server_close()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
