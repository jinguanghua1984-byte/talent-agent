from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_OPERATOR_ACTION = (
    "处理平台验证/登录/安全页面后，回到人才银行页面，不刷新页面，再运行恢复命令。"
)
IDENTITIES = {"bot", "user"}
SENSITIVE_KEYWORDS = (
    "secret",
    "password",
    "session",
    "sessionid",
    "access[_-]token",
    "client[_-]secret",
    "app[_-]secret",
    "api[-_]key",
    "cookie",
    "token",
)
SENSITIVE_KEYWORD_PATTERN = "|".join(SENSITIVE_KEYWORDS)
SENSITIVE_VALUE_PATTERN = r'"[^"]*"|\'[^\']*\'|[^\s&,;]+'
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\bauthorization\s*[:=]\s*(?:basic|bearer)\s+[^\s,;]+"),
    re.compile(rf"(?i)\b(?:{SENSITIVE_KEYWORD_PATTERN})\b\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s&,;]+)"),
    re.compile(rf"(?i)--authorization\b(?:\s*=\s*|\s+)(?:(?:basic|bearer)\s+)?(?:{SENSITIVE_VALUE_PATTERN})"),
    re.compile(rf"(?i)--(?:{SENSITIVE_KEYWORD_PATTERN})\b(?:\s*=\s*|\s+)(?:{SENSITIVE_VALUE_PATTERN})"),
]


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


def _safe_value(value: Any) -> str:
    text = _string_value(value)
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("<redacted-sensitive-value>", text)
    return text


def build_message_text(event: dict[str, Any]) -> str:
    completed = _safe_value(event.get("completed") or 0)
    total = _safe_value(event.get("total") or 0)
    operator_action = _safe_value(event.get("operator_action")) or DEFAULT_OPERATOR_ACTION

    return "\n".join(
        [
            f"Campaign ID：{_safe_value(event.get('campaign_id'))}",
            f"中断阶段：{_safe_value(event.get('blocked_stage'))}",
            f"原因：{_safe_value(event.get('reason'))}",
            f"进度：{completed}/{total}",
            f"证据文件：{_safe_value(event.get('evidence_file'))}",
            f"操作要求：{operator_action}",
            f"恢复命令：{_safe_value(event.get('resume_command'))}",
        ]
    )


def build_send_argv(
    identity: str,
    chat_id: str,
    user_id: str,
    text: str,
    idempotency_key: str,
    dry_run: bool,
) -> list[str]:
    identity = (identity or "").strip()
    chat_id = (chat_id or "").strip()
    user_id = (user_id or "").strip()
    if identity not in IDENTITIES:
        raise ValueError("identity must be bot or user")
    if bool(chat_id) == bool(user_id):
        raise ValueError("exactly one of chat_id or user_id is required")

    argv = ["lark-cli", "im", "+messages-send", "--as", identity]
    if chat_id:
        argv.extend(["--chat-id", chat_id])
    else:
        argv.extend(["--user-id", user_id])
    argv.extend(["--text", text, "--idempotency-key", idempotency_key])
    if dry_run:
        argv.append("--dry-run")
    return argv


def resolve_lark_cli_argv(argv: list[str]) -> list[str]:
    if not argv or argv[0] != "lark-cli":
        return argv

    configured = (os.environ.get("LARK_CLI") or "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["lark-cli.cmd", "lark-cli.exe", "lark-cli", "lark-cli.ps1"])

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, *argv[1:]]

    raise FileNotFoundError("lark-cli executable not found; install @larksuite/cli or set LARK_CLI")


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("event JSON must be an object")
    return data


def build_idempotency_key(event: dict[str, Any]) -> str:
    event_id = _string_value(event.get("blocked_event_id")) or _string_value(event.get("event_id"))
    if event_id:
        raw_key = "-".join(
            [
                _string_value(event.get("campaign_id")) or "campaign",
                _string_value(event.get("blocked_stage")) or "stage",
                event_id,
            ]
        )
    else:
        raw_key = "-".join(
            [
                _string_value(event.get("campaign_id")) or "campaign",
                _string_value(event.get("blocked_stage")) or "stage",
                _string_value(event.get("reason")) or "reason",
            ]
        )
    key = re.sub(r"[^0-9A-Za-z_.-]+", "-", raw_key).strip("-")
    return key or "campaign-notification"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="发送 campaign 中断飞书 IM 通知")
    parser.add_argument("--event", required=True)
    parser.add_argument("--identity", choices=sorted(IDENTITIES), required=True)
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        event = load_json(args.event)
        text = build_message_text(event)
        idempotency_key = build_idempotency_key(event)
        try:
            cmd = build_send_argv(
                identity=args.identity,
                chat_id=args.chat_id,
                user_id=args.user_id,
                text=text,
                idempotency_key=idempotency_key,
                dry_run=args.dry_run,
            )
        except ValueError as exc:
            parser.error(str(exc))

        if args.dry_run:
            print(
                json.dumps(
                    {"argv": cmd, "text": text, "idempotency_key": idempotency_key},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        completed = subprocess.run(resolve_lark_cli_argv(cmd), check=False, text=True, capture_output=True)
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        return completed.returncode
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
