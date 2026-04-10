#!/usr/bin/env python3
"""
Token Tracker - 轻量级 OTLP HTTP 接收器

接收 Claude Code 的 OTEL 遥测数据，提取 token 消耗并写入 JSONL 文件。
纯 Python stdlib 实现，零外部依赖。

用法:
    python scripts/token-tracker.py [--port 4318] [--output data/token-tracker/tokens.jsonl]

环境变量（Claude Code 侧）:
    CLAUDE_CODE_ENABLE_TELEMETRY=1
    OTEL_LOGS_EXPORTER=otlp
    OTEL_EXPORTER_OTLP_PROTOCOL=http/json
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

DEFAULT_PORT = 4318
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "token-tracker", "tokens.jsonl")


class OTLPHandler(BaseHTTPRequestHandler):
    """处理 OTLP HTTP/JSON 请求，提取 token 数据写入 JSONL"""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        if self.path == "/v1/logs":
            self._process_logs(data)
        # /v1/metrics 和 /v1/traces 返回 200 但不处理

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def _process_logs(self, data):
        """从 OTLP logs 中提取 claude_code.api_request 事件的 token 数据"""
        for resource_log in data.get("resourceLogs", []):
            for scope_log in resource_log.get("scopeLogs", []):
                for record in scope_log.get("logRecords", []):
                    attrs = self._parse_attributes(record.get("attributes", []))

                    if attrs.get("event.name") == "api_request":
                        entry = {
                            "timestamp": record.get("timeUnixNano", ""),
                            "prompt_id": attrs.get("prompt.id", ""),
                            "input_tokens": int(attrs.get("input_tokens", 0)),
                            "output_tokens": int(attrs.get("output_tokens", 0)),
                            "cache_read_tokens": int(attrs.get("cache_read_tokens", 0)),
                            "cache_creation_tokens": int(attrs.get("cache_creation_tokens", 0)),
                            "cost_usd": float(attrs.get("cost_usd", 0)),
                            "model": attrs.get("model", ""),
                        }
                        self._write_entry(entry)

    @staticmethod
    def _parse_attributes(attrs_list):
        """将 OTLP 属性列表解析为字典"""
        result = {}
        for attr in attrs_list:
            key = attr.get("key", "")
            value = attr.get("value", {})
            for vtype in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if vtype in value:
                    result[key] = value[vtype]
                    break
        return result

    def _write_entry(self, entry):
        """追加写入 JSONL 文件"""
        output_path = self.server.output_path
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_message(self, format, *args):
        """抑制 HTTP 请求日志"""
        pass


def main():
    port = DEFAULT_PORT
    output = DEFAULT_OUTPUT

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ("--help", "-h"):
            print(f"用法: {sys.argv[0]} [--port 4318] [--output path/to/tokens.jsonl]")
            sys.exit(0)
        else:
            i += 1

    server = HTTPServer(("0.0.0.0", port), OTLPHandler)
    server.output_path = os.path.abspath(output)

    print(f"Token Tracker 已启动 :{port}")
    print(f"输出文件: {server.output_path}")
    print("按 Ctrl+C 停止")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
