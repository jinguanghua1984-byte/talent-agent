"""为 maimai-scraper popup 提供本地详情任务包。"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _contact_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("contacts"), list):
        return [item for item in data["contacts"] if isinstance(item, dict)]
    raise ValueError("detail plan must contain contacts")


def build_plan_payload(plan_path: Path | str) -> dict[str, Any]:
    plan = Path(plan_path)
    data = _load_json(plan)
    contacts = _contact_items(data)
    if not contacts:
        raise ValueError("detail plan contacts is empty")
    return {
        "metadata": {
            "export_type": "maimai_detail_local_plan",
            "source_file": str(plan),
            "total_contacts": len(contacts),
        },
        "contacts": contacts,
        "totalContacts": len(contacts),
    }


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(plan_path: Path | str) -> type[BaseHTTPRequestHandler]:
    plan = Path(plan_path)

    class DetailPlanHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            try:
                if self.path.split("?", 1)[0] == "/health":
                    payload = build_plan_payload(plan)
                    _write_json(self, 200, {"ok": True, "totalContacts": payload["totalContacts"]})
                    return
                if self.path.split("?", 1)[0] == "/detail-plan.json":
                    _write_json(self, 200, build_plan_payload(plan))
                    return
                _write_json(self, 404, {"ok": False, "error": "not found"})
            except Exception as exc:
                _write_json(self, 500, {"ok": False, "error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("[maimai-detail-plan] " + (format % args) + "\n")

    return DetailPlanHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地服务 maimai-scraper 批量详情任务包")
    parser.add_argument("--plan", required=True, type=Path, help="联系人任务包 JSON")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_plan_payload(args.plan)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.plan))
    print(
        json.dumps({
            "ok": True,
            "url": f"http://{args.host}:{args.port}/detail-plan.json",
            "totalContacts": payload["totalContacts"],
            "plan": str(args.plan),
        }, ensure_ascii=False, indent=2),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
