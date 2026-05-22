import json
from pathlib import Path

from scripts.jd_talent_delivery_profile import build_role_profile, main, render_profile_markdown


def test_build_role_profile_extracts_core_terms() -> None:
    jd_text = """
    # 大模型推理系统工程师

    负责 vLLM、SGLang、KV Cache、Prefill/Decode、量化和线上 SLA。
    需要熟悉字节、MiniMax、DeepSeek 等大模型业务场景。
    排除纯 RAG 应用和销售背景。
    """

    profile = build_role_profile(jd_text, source_path="jd.md", role_id="llm-inference")

    assert profile["schema"] == "jd_talent_delivery_role_profile_v1"
    assert profile["target_role"] == "大模型推理系统工程师"
    assert "vLLM" in profile["must_have"]
    assert "SGLang" in profile["must_have"]
    assert "KV Cache" in profile["must_have"]
    assert "SLA" in profile["nice_to_have"]
    assert "字节" in profile["company_pools"]["目标公司"]
    assert "纯 RAG 应用" in profile["exclusion_terms"]


def test_render_profile_markdown_matches_deep_dive_shape() -> None:
    profile = build_role_profile(
        "# 数据平台负责人\n负责数据质量、标注平台和团队管理。",
        source_path="jd.md",
        role_id="data-platform-lead",
    )

    markdown = render_profile_markdown(profile)

    assert markdown.startswith("# 数据平台负责人岗位深挖报告")
    for heading in [
        "## 1. 结论摘要",
        "## 2. 岗位真实问题",
        "## 3. 能力模型",
        "## 4. 候选人类型",
        "## 5. 寻访关键点",
        "## 6. 公司池与团队优先级",
        "## 7. 匹配关键词建议",
        "## 8. 排除项与风险",
    ]:
        assert heading in markdown


def test_render_profile_markdown_falls_back_to_role_id_title() -> None:
    markdown = render_profile_markdown({"role_id": "demo"})

    assert markdown.startswith("# demo岗位深挖报告")


def test_cli_writes_profile_json_and_markdown(tmp_path: Path) -> None:
    jd = tmp_path / "jd.md"
    out_json = tmp_path / "profile" / "role-profile.json"
    out_md = tmp_path / "profile" / "role-deep-dive.md"
    jd.write_text("# 大模型推理系统工程师\n负责 vLLM 和 KV Cache。", encoding="utf-8")

    code = main(
        [
            "--jd",
            str(jd),
            "--role-id",
            "llm-inference",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert code == 0
    data = json.loads(out_json.read_text(encoding="utf-8-sig"))
    assert data["role_id"] == "llm-inference"
    assert out_md.read_text(encoding="utf-8-sig").startswith("# 大模型推理系统工程师岗位深挖报告")
