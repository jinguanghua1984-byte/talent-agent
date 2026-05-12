import json
from pathlib import Path

from scripts.maimai_ai_infra_search_runner import patch_search_body


def _template_body():
    return {
        "sid": "sid-1",
        "sessionid": "session-1",
        "data_version": "dv",
        "highlight_exp": "1",
        "search": {
            "query": "old",
            "search_query": "old",
            "positions": "",
            "allcompanies": "一线互联网公司",
            "degrees": "2,3",
            "worktimes": "",
            "age": "",
            "query_relation": 0,
            "paginationParam": {"page": 1, "size": 30},
            "page": 0,
            "size": 30,
            "sid": "sid-search",
            "sessionid": "session-search",
            "data_version": "4.1",
            "highlight_exp": 1,
        },
    }


def _batch():
    return {
        "batch_id": "tier1-bytedance-precision-001",
        "company": "字节跳动",
        "position": "大模型训练",
        "query": '"Seed" "训练框架"',
        "query_relation": 0,
        "page_size": 30,
    }


def test_patch_search_body_preserves_session_fields_and_patches_verified_fields():
    patched = patch_search_body(_template_body(), _batch(), page=2)

    assert patched["sid"] == "sid-1"
    assert patched["sessionid"] == "session-1"
    assert patched["data_version"] == "dv"
    assert patched["highlight_exp"] == "1"
    assert patched["search"]["query"] == '"Seed" "训练框架"'
    assert patched["search"]["search_query"] == '"Seed" "训练框架"'
    assert patched["search"]["paginationParam"]["page"] == 2
    assert patched["search"]["paginationParam"]["size"] == 30
    assert patched["search"]["page"] == 1
    assert patched["search"]["size"] == 30
    assert patched["search"]["positions"] == ""
    assert patched["search"]["allcompanies"] == "一线互联网公司"
    assert patched["search"]["degrees"] == "2,3"
    assert patched["search"]["sid"] == "sid-search"
    assert patched["search"]["sessionid"] == "session-search"
    assert patched["search"]["data_version"] == "4.1"
    assert patched["search"]["highlight_exp"] == 1


def test_patch_search_body_rejects_incompatible_template():
    try:
        patch_search_body({"search": []}, _batch(), page=1)
    except ValueError as exc:
        assert "search must be an object" in str(exc)
    else:
        raise AssertionError("invalid template should fail")


def test_runner_dry_run_template_only_outputs_patched_body(tmp_path: Path):
    plan_path = tmp_path / "plan.json"
    template_path = tmp_path / "template.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({"run_id": "smoke", "batches": [_batch()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    template_path.write_text(json.dumps(_template_body(), ensure_ascii=False), encoding="utf-8")

    from scripts.maimai_ai_infra_search_runner import main

    assert main([
        "--plan",
        str(plan_path),
        "--template",
        str(template_path),
        "--out",
        str(out_path),
        "--dry-run-template-only",
    ]) == 0

    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["status"] == "dry-run-template-only"
    assert data["batches"][0]["patched_pages"][0]["body"]["search"]["paginationParam"]["page"] == 1
    assert data["contacts"] == []
