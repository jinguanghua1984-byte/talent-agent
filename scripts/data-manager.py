#!/usr/bin/env python3
"""data-manager.py — Talent Agent 数据管理 CLI

管理 JD、候选人、Screening 结果和客户偏好的轻量级 CLI 工具。

用法:
    python scripts/data-manager.py jd create <file>
    python scripts/data-manager.py jd list
    python scripts/data-manager.py jd get <id>
    python scripts/data-manager.py candidate create <file>
    python scripts/data-manager.py candidate list [--enrichment raw|partial|enriched]
    python scripts/data-manager.py candidate get <id>
    python scripts/data-manager.py candidate update <id> <file>
    python scripts/data-manager.py candidate merge <id>
    python scripts/data-manager.py candidate dedup
    python scripts/data-manager.py screen create <jd-id> <candidate-id> <score>
    python scripts/data-manager.py screen list <jd-id>
    python scripts/data-manager.py screen update <jd-id> <candidate-id> <file>
    python scripts/data-manager.py rules get <client>
    python scripts/data-manager.py rules add-correction <client> <json-data>
    python scripts/data-manager.py validate
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date

# 尝试导入 jsonschema，如果没有则使用手动验证
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# 项目根目录（使用 CWD，支持测试时切换到临时目录）
def get_project_root():
    return os.getcwd()


# 获取 JSON Schema 文件路径
def get_schema_path(entity_type):
    """获取实体类型的 JSON Schema 文件路径。"""
    return os.path.join(get_project_root(), "schemas", f"{entity_type}.schema.json")

# 数据目录路径（延迟计算，支持 CWD 变化）
def get_data_dirs():
    root = get_project_root()
    return {
        "jds": os.path.join(root, "data", "jds"),
        "candidates": os.path.join(root, "data", "candidates"),
        "screens": os.path.join(root, "data", "screens"),
        "rules": os.path.join(root, "data", "rules"),
    }

# 有效枚举值
VALID_ENUMS = {
    "status": ["new", "screening", "interviewed", "offered", "rejected", "passed", "failed"],
    "enrichment_level": ["raw", "partial", "enriched"],
    "job_type": ["full_time", "part_time", "contract", "freelance", "intern"],
}

# 各实体必需字段
REQUIRED_FIELDS = {
    "jd": ["id", "company", "title", "created_at"],
    "candidate": ["id", "name", "created_at", "updated_at"],
    "screen": ["jd_id", "candidate_id", "score", "status", "created_at"],
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def today_iso():
    """返回当天日期 ISO 格式 (YYYY-MM-DD)。"""
    return date.today().isoformat()


def atomic_write_json(filepath, data):
    """原子写入 JSON 文件：先写 .tmp，再 os.replace()。

    Args:
        filepath: 目标文件路径
        data: 要写入的字典数据
    """
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, filepath)


def read_json(filepath):
    """读取 JSON 文件，返回字典。"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(filepath):
    """确保文件所在目录存在。"""
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)


def slugify(text, max_len=20):
    """将文本转换为 URL 友好的 slug。

    Args:
        text: 原始文本（支持中文）
        max_len: slug 最大长度

    Returns:
        小写字母、数字和连字符组成的字符串
    """
    # 提取字母数字字符
    chars = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "-", text)
    # 对中文使用拼音首字母（简化处理：直接截取）
    slug = chars.strip("-").lower()
    if not slug:
        slug = "x"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug


def generate_jd_id(data):
    """自动生成 JD ID: jd-YYYYMMDD-<slug>。"""
    dt = today_iso().replace("-", "")
    company_slug = slugify(data.get("company", "unknown"))
    title_slug = slugify(data.get("title", "job"))
    return f"jd-{dt}-{company_slug}-{title_slug}"


def generate_candidate_id():
    """自动生成候选人 ID: cand-<N>，N 为当前最大编号 +1。"""
    cand_dir = get_data_dirs()["candidates"]
    if not os.path.exists(cand_dir):
        return "cand-1"

    max_num = 0
    for fname in os.listdir(cand_dir):
        if fname.endswith(".json"):
            match = re.match(r"cand-(\d+)\.json$", fname)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

    return f"cand-{max_num + 1}"


def list_json_files(directory):
    """列出目录中所有 .json 文件（不含 .tmp）。"""
    if not os.path.exists(directory):
        return []
    return [
        f for f in os.listdir(directory)
        if f.endswith(".json") and not f.endswith(".tmp")
    ]


# ---------------------------------------------------------------------------
# JD 命令
# ---------------------------------------------------------------------------

def cmd_jd_create(args):
    """从 JSON 文件创建 JD。"""
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
        return 1

    data = read_json(filepath)

    # 自动生成 ID
    if "id" not in data:
        data["id"] = generate_jd_id(data)

    jd_id = data["id"]
    jd_path = os.path.join(get_data_dirs()["jds"], f"{jd_id}.json")

    if os.path.exists(jd_path):
        print(f"错误: JD 已存在: {jd_id}", file=sys.stderr)
        return 1

    # 自动设置时间戳
    data["created_at"] = today_iso()

    ensure_dir(jd_path)
    atomic_write_json(jd_path, data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_jd_list(args):
    """列出所有 JD。"""
    results = []
    for fname in list_json_files(get_data_dirs()["jds"]):
        filepath = os.path.join(get_data_dirs()["jds"], fname)
        results.append(read_json(filepath))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_jd_get(args):
    """获取单个 JD。"""
    jd_path = os.path.join(get_data_dirs()["jds"], f"{args.id}.json")
    if not os.path.exists(jd_path):
        print(f"错误: JD 不存在: {args.id}", file=sys.stderr)
        return 1

    data = read_json(jd_path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Candidate 命令
# ---------------------------------------------------------------------------

def cmd_candidate_create(args):
    """从 JSON 文件创建候选人。"""
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
        return 1

    data = read_json(filepath)

    # 自动生成 ID
    if "id" not in data:
        data["id"] = generate_candidate_id()

    cand_id = data["id"]
    cand_path = os.path.join(get_data_dirs()["candidates"], f"{cand_id}.json")

    if os.path.exists(cand_path):
        print(f"错误: 候选人已存在: {cand_id}", file=sys.stderr)
        return 1

    # 自动设置时间戳
    today = today_iso()
    data["created_at"] = today
    data["updated_at"] = today

    ensure_dir(cand_path)
    atomic_write_json(cand_path, data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_list(args):
    """列出候选人，可选按 enrichment_level 过滤。"""
    results = []
    for fname in list_json_files(get_data_dirs()["candidates"]):
        filepath = os.path.join(get_data_dirs()["candidates"], fname)
        cand = read_json(filepath)

        # 按 enrichment_level 过滤
        if args.enrichment:
            if cand.get("enrichment_level") != args.enrichment:
                continue

        results.append(cand)

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_get(args):
    """获取单个候选人。"""
    cand_path = os.path.join(get_data_dirs()["candidates"], f"{args.id}.json")
    if not os.path.exists(cand_path):
        print(f"错误: 候选人不存在: {args.id}", file=sys.stderr)
        return 1

    data = read_json(cand_path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_update(args):
    """更新候选人信息（合并，保留已有字段）。"""
    cand_path = os.path.join(get_data_dirs()["candidates"], f"{args.id}.json")
    if not os.path.exists(cand_path):
        print(f"错误: 候选人不存在: {args.id}", file=sys.stderr)
        return 1

    update_file = args.file
    if not os.path.exists(update_file):
        print(f"错误: 文件不存在: {update_file}", file=sys.stderr)
        return 1

    existing = read_json(cand_path)
    update_data = read_json(update_file)

    # 合并：update_data 的值覆盖 existing
    merged = {**existing, **update_data}
    merged["updated_at"] = today_iso()

    atomic_write_json(cand_path, merged)
    print(json.dumps(merged, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_merge(args):
    """合并候选人的多源信息。

    - 合并 sources 列表（去重）
    - 更新 enrichment_level 为最高级别
    """
    cand_path = os.path.join(get_data_dirs()["candidates"], f"{args.id}.json")
    if not os.path.exists(cand_path):
        print(f"错误: 候选人不存在: {args.id}", file=sys.stderr)
        return 1

    cand = read_json(cand_path)

    # sources 去重（按 type+url）
    sources = cand.get("sources", [])
    seen = set()
    unique_sources = []
    for src in sources:
        key = (src.get("type", ""), src.get("url", ""))
        if key not in seen:
            seen.add(key)
            unique_sources.append(src)
    cand["sources"] = unique_sources

    # enrichment_level 取最高
    level_order = {"raw": 0, "partial": 1, "enriched": 2}
    current_level = cand.get("enrichment_level", "raw")
    # 从 sources 中推断最高级别
    for src in cand.get("sources", []):
        src_level = src.get("enrichment_level", "raw")
        if level_order.get(src_level, 0) > level_order.get(current_level, 0):
            current_level = src_level
    cand["enrichment_level"] = current_level
    cand["updated_at"] = today_iso()

    atomic_write_json(cand_path, cand)
    print(json.dumps(cand, ensure_ascii=False, indent=2))
    return 0


def cmd_candidate_dedup(args):
    """按 name + current_company 查找重复候选人。"""
    groups = defaultdict(list)

    for fname in list_json_files(get_data_dirs()["candidates"]):
        filepath = os.path.join(get_data_dirs()["candidates"], fname)
        cand = read_json(filepath)
        key = (cand.get("name", ""), cand.get("current_company", ""))
        groups[key].append(cand)

    # 只保留有重复的组（2个以上）
    duplicates = []
    for key, cands in sorted(groups.items()):
        if len(cands) > 1:
            duplicates.append({
                "key": {"name": key[0], "current_company": key[1]},
                "candidates": cands,
            })

    print(json.dumps(duplicates, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Screen 命令
# ---------------------------------------------------------------------------

def screen_filename(jd_id, candidate_id):
    """生成 screening 文件名（双下划线分隔）。"""
    return f"{jd_id}__{candidate_id}.json"


def cmd_screen_create(args):
    """创建 screening 结果。"""
    jd_id = args.jd_id
    candidate_id = args.candidate_id
    score = int(args.score)

    screen_path = os.path.join(
        get_data_dirs()["screens"],
        screen_filename(jd_id, candidate_id),
    )

    data = {
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "score": score,
        "status": "new",
        "created_at": today_iso(),
    }

    ensure_dir(screen_path)
    atomic_write_json(screen_path, data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_screen_list(args):
    """列出某个 JD 下的所有 screening 结果。"""
    jd_id = args.jd_id
    results = []

    for fname in list_json_files(get_data_dirs()["screens"]):
        if fname.startswith(f"{jd_id}__"):
            filepath = os.path.join(get_data_dirs()["screens"], fname)
            results.append(read_json(filepath))

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_screen_update(args):
    """更新 screening 结果。"""
    screen_path = os.path.join(
        get_data_dirs()["screens"],
        screen_filename(args.jd_id, args.candidate_id),
    )

    if not os.path.exists(screen_path):
        print(
            f"错误: Screening 不存在: {args.jd_id}/{args.candidate_id}",
            file=sys.stderr,
        )
        return 1

    update_file = args.file
    if not os.path.exists(update_file):
        print(f"错误: 文件不存在: {update_file}", file=sys.stderr)
        return 1

    existing = read_json(screen_path)
    update_data = read_json(update_file)

    merged = {**existing, **update_data}
    atomic_write_json(screen_path, merged)
    print(json.dumps(merged, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Rules 命令
# ---------------------------------------------------------------------------

def _get_rules_file():
    """获取规则文件路径。"""
    return os.path.join(get_data_dirs()["rules"], "preferences.json")


def _load_rules():
    """加载规则文件，不存在则返回空结构。"""
    rules_file = _get_rules_file()
    if os.path.exists(rules_file):
        return read_json(rules_file)
    return {"clients": {}}


def _save_rules(rules):
    """原子写入规则文件。"""
    rules_file = _get_rules_file()
    ensure_dir(rules_file)
    atomic_write_json(rules_file, rules)


def cmd_rules_get(args):
    """获取客户偏好设置。"""
    rules = _load_rules()
    client = args.client
    client_data = rules.get("clients", {}).get(client, {})
    print(json.dumps(client_data, ensure_ascii=False, indent=2))
    return 0


def cmd_rules_add_correction(args):
    """为客户添加修正记录。"""
    client = args.client
    correction_data = json.loads(args.json_data)

    rules = _load_rules()
    if "clients" not in rules:
        rules["clients"] = {}
    if client not in rules["clients"]:
        rules["clients"][client] = {"corrections": []}
    if "corrections" not in rules["clients"][client]:
        rules["clients"][client]["corrections"] = []

    correction_data["added_at"] = today_iso()
    rules["clients"][client]["corrections"].append(correction_data)

    _save_rules(rules)
    print(json.dumps(rules["clients"][client], ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Validate 命令
# ---------------------------------------------------------------------------

def _validate_date(value):
    """验证日期格式是否为 YYYY-MM-DD。"""
    if not isinstance(value, str):
        return False
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value))


def _validate_entity(entity_type, filepath):
    """验证单个实体的完整性。

    Returns:
        错误信息列表，空列表表示验证通过。
    """
    errors = []

    try:
        data = read_json(filepath)
    except (json.JSONDecodeError, OSError) as e:
        return [f"JSON 解析失败: {filepath}: {e}"]

    fname = os.path.basename(filepath)

    if HAS_JSONSCHEMA:
        # 使用 JSON Schema 验证
        schema_path = get_schema_path(entity_type)
        if os.path.exists(schema_path):
            try:
                schema = read_json(schema_path)
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.ValidationError as e:
                errors.append(f"{fname}: {e.message}")
            except jsonschema.SchemaError as e:
                errors.append(f"{fname}: Schema 错误: {e}")
        else:
            errors.append(f"{fname}: Schema 文件不存在: {schema_path}")
            # 回退到基本验证
            return _validate_entity_basic(entity_type, filepath, fname, data)
    else:
        # 手动验证（兼容模式）
        errors.extend(_validate_entity_basic(entity_type, filepath, fname, data))

    return errors


def _validate_entity_basic(entity_type, filepath, fname, data):
    """手动验证单个实体的基本字段。"""
    errors = []

    # 检查必需字段
    required = REQUIRED_FIELDS.get(entity_type, [])
    for field in required:
        if field not in data:
            errors.append(f"{fname}: 缺少必需字段 '{field}'")

    # 检查枚举值
    for field, valid_values in VALID_ENUMS.items():
        if field in data and data[field] not in valid_values:
            errors.append(
                f"{fname}: '{field}' 值 '{data[field]}' 无效，"
                f"有效值: {valid_values}"
            )

    # 检查日期格式
    for date_field in ["created_at", "updated_at"]:
        if date_field in data and not _validate_date(data[date_field]):
            errors.append(f"{fname}: '{date_field}' 日期格式无效，应为 YYYY-MM-DD")

    return errors


def cmd_validate(args):
    """验证所有数据文件的完整性。"""
    all_errors = []

    # 验证 JD
    for fname in list_json_files(get_data_dirs()["jds"]):
        filepath = os.path.join(get_data_dirs()["jds"], fname)
        all_errors.extend(_validate_entity("jd", filepath))

    # 验证 Candidate
    for fname in list_json_files(get_data_dirs()["candidates"]):
        filepath = os.path.join(get_data_dirs()["candidates"], fname)
        all_errors.extend(_validate_entity("candidate", filepath))

    # 验证 Screen
    for fname in list_json_files(get_data_dirs()["screens"]):
        filepath = os.path.join(get_data_dirs()["screens"], fname)
        all_errors.extend(_validate_entity("screen", filepath))

    if all_errors:
        for err in all_errors:
            print(f"错误: {err}", file=sys.stderr)
        return 1

    print("验证通过: 所有数据文件格式正确")
    return 0


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def build_parser():
    """构建 argparse CLI 解析器。"""
    parser = argparse.ArgumentParser(
        description="Talent Agent 数据管理 CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- JD ---
    jd_parser = subparsers.add_parser("jd", help="JD 管理")
    jd_sub = jd_parser.add_subparsers(dest="action")

    jd_create = jd_sub.add_parser("create", help="从 JSON 文件创建 JD")
    jd_create.add_argument("file", help="JD JSON 文件路径")

    jd_sub.add_parser("list", help="列出所有 JD")

    jd_get = jd_sub.add_parser("get", help="获取单个 JD")
    jd_get.add_argument("id", help="JD ID")

    # --- Candidate ---
    cand_parser = subparsers.add_parser("candidate", help="候选人管理")
    cand_sub = cand_parser.add_subparsers(dest="action")

    cand_create = cand_sub.add_parser("create", help="从 JSON 文件创建候选人")
    cand_create.add_argument("file", help="候选人 JSON 文件路径")

    cand_list = cand_sub.add_parser("list", help="列出候选人")
    cand_list.add_argument(
        "--enrichment",
        choices=["raw", "partial", "enriched"],
        default=None,
        help="按 enrichment_level 过滤",
    )

    cand_get = cand_sub.add_parser("get", help="获取单个候选人")
    cand_get.add_argument("id", help="候选人 ID")

    cand_update = cand_sub.add_parser("update", help="更新候选人")
    cand_update.add_argument("id", help="候选人 ID")
    cand_update.add_argument("file", help="更新数据 JSON 文件路径")

    cand_merge = cand_sub.add_parser("merge", help="合并候选人多源信息")
    cand_merge.add_argument("id", help="候选人 ID")

    cand_sub.add_parser("dedup", help="查找重复候选人")

    # --- Screen ---
    screen_parser = subparsers.add_parser("screen", help="Screening 管理")
    screen_sub = screen_parser.add_subparsers(dest="action")

    screen_create = screen_sub.add_parser("create", help="创建 screening 结果")
    screen_create.add_argument("jd_id", help="JD ID")
    screen_create.add_argument("candidate_id", help="候选人 ID")
    screen_create.add_argument("score", help="评分")

    screen_list = screen_sub.add_parser("list", help="列出 JD 下的 screening")
    screen_list.add_argument("jd_id", help="JD ID")

    screen_update = screen_sub.add_parser("update", help="更新 screening 结果")
    screen_update.add_argument("jd_id", help="JD ID")
    screen_update.add_argument("candidate_id", help="候选人 ID")
    screen_update.add_argument("file", help="更新数据 JSON 文件路径")

    # --- Rules ---
    rules_parser = subparsers.add_parser("rules", help="客户偏好规则")
    rules_sub = rules_parser.add_subparsers(dest="action")

    rules_get = rules_sub.add_parser("get", help="获取客户偏好")
    rules_get.add_argument("client", help="客户标识")

    rules_add = rules_sub.add_parser("add-correction", help="添加修正记录")
    rules_add.add_argument("client", help="客户标识")
    rules_add.add_argument("json_data", help="修正数据 (JSON 字符串)")

    # --- Validate ---
    subparsers.add_parser("validate", help="验证所有数据文件")

    return parser


def main():
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "jd":
        handler = {
            "create": cmd_jd_create,
            "list": cmd_jd_list,
            "get": cmd_jd_get,
        }.get(args.action)
    elif args.command == "candidate":
        handler = {
            "create": cmd_candidate_create,
            "list": cmd_candidate_list,
            "get": cmd_candidate_get,
            "update": cmd_candidate_update,
            "merge": cmd_candidate_merge,
            "dedup": cmd_candidate_dedup,
        }.get(args.action)
    elif args.command == "screen":
        handler = {
            "create": cmd_screen_create,
            "list": cmd_screen_list,
            "update": cmd_screen_update,
        }.get(args.action)
    elif args.command == "rules":
        handler = {
            "get": cmd_rules_get,
            "add-correction": cmd_rules_add_correction,
        }.get(args.action)
    elif args.command == "validate":
        handler = cmd_validate
    else:
        handler = None

    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
