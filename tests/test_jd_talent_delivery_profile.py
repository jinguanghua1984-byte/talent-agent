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


def test_build_role_profile_extracts_multimodal_video_generation_signals() -> None:
    jd_text = """
    # 腾讯游戏-多模态算法研究员/专家

    负责生成式游戏引擎、视频生成、视频预测、视频编辑和世界模型研发。
    需要熟练掌握 PyTorch，理解 Diffusion Models、GANs、VAEs、Flow-based Models。
    需要具备大规模 GPU 集群预训练、微调或后训练经验，熟悉 CLIP、LLaVA、Qwen。
    目标团队包括字节 Seedance、快手可灵、阿里通义万相、爱诗科技、生数科技和 B站。
    纯应用层 AIGC/RAG 调用经验、传统计算机视觉应用经验需要降权。
    SIGGRAPH、CVPR、ICCV、NeurIPS 一作论文优先。
    """

    profile = build_role_profile(jd_text, source_path="jd.md", role_id="tencent-games-multimodal")

    for term in ["视频生成", "世界模型", "Diffusion Models", "PyTorch", "GPU 集群", "CLIP"]:
        assert term in profile["must_have"]
    for term in ["SIGGRAPH", "CVPR", "NeurIPS"]:
        assert term in profile["nice_to_have"]
    for company in ["Seedance", "可灵", "通义万相", "爱诗科技", "生数科技", "B站"]:
        assert company in profile["company_pools"]["目标公司"]
    assert "纯应用层" in profile["exclusion_terms"]
    assert "传统计算机视觉" in profile["exclusion_terms"]
    assert "算法研究员" in profile["title_aliases"]
    assert "视频生成算法工程师" in profile["title_aliases"]


def test_build_role_profile_extracts_training_inference_data_engineering_signals() -> None:
    jd_text = """
    # 腾讯游戏训练推理数据工程研发专家/工程师

    负责生成式游戏引擎大模型分布式训练和推理系统的性能优化。
    需要熟悉 GPU 架构、CUDA 编程、算子融合优化、PyTorch FSDP、DeepSpeed、Megatron-LM。
    熟悉 vLLM、SGLang、KV Cache、动态批处理、Attention 算子定制。
    负责多模态RLHF训练与推理平台实现，熟悉 OpenRLHF。
    目标团队包括字节 Seedance、快手可灵、阿里万相、爱诗科技、生数科技和 B站。
    只有纯应用层 AIGC/RAG 调用经验需要降权。
    """

    profile = build_role_profile(jd_text, source_path="jd.md", role_id="tencent-games-ai-infra")

    for term in ["分布式训练", "FSDP", "DeepSpeed", "Megatron-LM", "vLLM", "SGLang", "CUDA", "OpenRLHF"]:
        assert term in profile["must_have"]
    for alias in ["AI Infra工程师", "大模型训练工程师", "大模型推理工程师", "RLHF工程师"]:
        assert alias in profile["title_aliases"]
    for company in ["Seedance", "可灵", "爱诗科技", "生数科技", "B站"]:
        assert company in profile["company_pools"]["目标公司"]
    assert "纯应用层" in profile["exclusion_terms"]


def test_build_role_profile_extracts_llm_product_vertical_signals_without_operations_exclusion() -> None:
    jd_text = """
    # 大模型数据策略产品经理（金融）

    负责大模型产品、模型评估、数据生产、SFT、系统指令、数据质量管控和评估流程。
    方向包括知识问答、逻辑推理、金融市场、财务分析、风险管理和合规。
    目标公司包括字节 Seed、豆包、阿里千问、腾讯混元、蚂蚁金服、阿福、灵光、百度和百川智能。
    有用户研究、社区运营或金融分析经验优先，但不把运营作为排除项。
    """

    profile = build_role_profile(jd_text, source_path="jd.md", role_id="jiukun-finance-product")

    for term in ["大模型产品", "模型评估", "SFT", "金融市场", "财务分析", "合规"]:
        assert term in profile["must_have"]
    for company in ["字节 Seed", "豆包", "阿里千问", "腾讯混元", "蚂蚁金服", "百川智能"]:
        assert company in profile["company_pools"]["目标公司"]
    for alias in ["AI产品经理", "数据策略产品经理", "产品经理", "金融产品经理"]:
        assert alias in profile["title_aliases"]
    assert "运营" not in profile["exclusion_terms"]


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
