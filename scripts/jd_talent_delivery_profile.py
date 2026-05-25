from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_role_profile_v1"

CORE_TERMS = [
    "vLLM",
    "SGLang",
    "TensorRT-LLM",
    "KV Cache",
    "Prefill",
    "Decode",
    "量化",
    "CUDA",
    "GPU",
    "SLA",
    "数据质量",
    "标注平台",
    "团队管理",
    "后训练",
    "数据策略",
    "PyTorch",
    "预训练",
    "微调",
    "多模态",
    "多模态大模型",
    "视频生成",
    "视频预测",
    "视频编辑",
    "图像生成",
    "世界模型",
    "生成式游戏引擎",
    "Diffusion Models",
    "Diffusion",
    "GANs",
    "VAEs",
    "Flow-based Models",
    "CLIP",
    "LLaVA",
    "Qwen",
    "GPU 集群",
    "分布式训练",
    "数据并行",
    "模型并行",
    "流水线并行",
    "专家并行",
    "FSDP",
    "DeepSpeed",
    "Megatron-LM",
    "Megatron",
    "算子融合",
    "Attention 算子",
    "动态批处理",
    "多模态RLHF",
    "RLHF",
    "OpenRLHF",
    "训练平台",
    "推理平台",
    "推理系统",
    "性能优化",
    "显存瓶颈",
    "通信延迟",
    "负载均衡",
    "数据工程",
    "物理一致性",
    "时空一致性",
    "可交互性",
    "可编辑性",
    "SIGGRAPH",
    "CVPR",
    "ICCV",
    "NeurIPS",
]

NICE_TO_HAVE_HINTS = {"SLA", "SIGGRAPH", "CVPR", "ICCV", "NeurIPS"}

KNOWN_COMPANIES = [
    "字节",
    "字节跳动",
    "Seedance",
    "快手",
    "可灵",
    "MiniMax",
    "DeepSeek",
    "月之暗面",
    "百度",
    "阿里",
    "通义万相",
    "阿里未来实验室",
    "腾讯",
    "爱诗科技",
    "生数科技",
    "B站",
    "哔哩哔哩",
]
KNOWN_EXCLUSIONS = [
    "纯 RAG 应用",
    "纯应用层",
    "传统计算机视觉",
    "销售",
    "招聘",
    "纯前端",
    "运营",
]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = value.strip()
        if item and item not in result:
            result.append(item)
    return result


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def _contains(text: str, term: str) -> bool:
    text_folded = text.casefold()
    term_folded = term.casefold()
    return term_folded in text_folded or _compact(term) in _compact(text)


def _title_from_jd(jd_text: str, role_id: str) -> str:
    for line in jd_text.splitlines():
        text = line.strip()
        if not text:
            continue
        heading = re.sub(r"^#{1,6}\s*", "", text).strip()
        return heading or role_id
    return role_id


def _title_aliases(title: str) -> list[str]:
    aliases = [title]
    if "工程师" in title:
        aliases.extend(
            [
                title.replace("工程师", "专家"),
                title.replace("工程师", "架构师"),
            ]
        )
    if "负责人" in title:
        aliases.extend(
            [
                title.replace("负责人", "Lead"),
                title.replace("负责人", "经理"),
            ]
        )
    if "平台" in title and "平台工程师" not in title:
        aliases.append(f"{title}工程师")
    if "算法" in title:
        aliases.extend(["算法研究员", "算法专家", "多模态算法工程师", "视频生成算法工程师"])
    if "多模态" in title:
        aliases.extend(["多模态算法专家", "多模态研究员", "多模态大模型算法工程师"])
    if any(term in title for term in ["训练", "推理", "数据工程", "AI Infra"]):
        aliases.extend(
            [
                "AI Infra工程师",
                "AI Infra专家",
                "大模型训练工程师",
                "大模型训练专家",
                "大模型推理工程师",
                "大模型推理专家",
                "推理系统工程师",
                "分布式训练工程师",
                "分布式训练专家",
                "CUDA性能优化工程师",
                "RLHF工程师",
                "数据工程研发专家",
                "大模型数据工程师",
            ]
        )
    return _unique(aliases)


def _format_list(values: list[str]) -> str:
    return "、".join(values) if values else "未在 JD 中明确命中"


def build_role_profile(jd_text: str, source_path: str, role_id: str) -> dict[str, Any]:
    target_role = _title_from_jd(jd_text, role_id)
    matched_terms = [term for term in CORE_TERMS if _contains(jd_text, term)]
    must_have = [term for term in matched_terms if term not in NICE_TO_HAVE_HINTS]
    nice_to_have = [term for term in matched_terms if term in NICE_TO_HAVE_HINTS]
    companies = [company for company in KNOWN_COMPANIES if _contains(jd_text, company)]
    exclusions = [term for term in KNOWN_EXCLUSIONS if _contains(jd_text, term)]
    title_aliases = _title_aliases(target_role)

    summary_terms = _format_list(matched_terms[:6])
    company_summary = _format_list(companies)
    return {
        "schema": SCHEMA,
        "role_id": role_id,
        "source_path": source_path,
        "target_role": target_role,
        "summary": f"{target_role} 的核心画像来自 JD 中的确定性信号：{summary_terms}。",
        "real_problem": (
            f"该岗位需要围绕 {summary_terms} 解决业务落地问题，并优先从 {company_summary} "
            "等相邻业务场景中寻找有直接证据的候选人。"
        ),
        "must_have": _unique(must_have),
        "nice_to_have": _unique(nice_to_have),
        "company_pools": {"目标公司": _unique(companies)},
        "title_aliases": title_aliases,
        "exclusion_terms": _unique(exclusions),
        "risk_rules": [
            "关键能力只有泛化描述时需要人工复核",
            "仅有应用层经验且缺少岗位核心证据时降低优先级",
        ],
        "search_keywords": _unique(must_have + nice_to_have + title_aliases + companies),
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    title = str(profile.get("target_role") or profile.get("role_id") or "岗位")
    company_pools = profile.get("company_pools", {})
    target_companies = company_pools.get("目标公司", []) if isinstance(company_pools, dict) else []

    lines = [
        f"# {title}岗位深挖报告",
        "",
        f"> 来源：`{profile.get('source_path', '')}`",
        "",
        "## 1. 结论摘要",
        "",
        str(profile.get("summary", "")),
        "",
        "## 2. 岗位真实问题",
        "",
        str(profile.get("real_problem", "")),
        "",
        "## 3. 能力模型",
        "",
        f"- 必须具备：{_format_list(list(profile.get('must_have', [])))}",
        f"- 加分能力：{_format_list(list(profile.get('nice_to_have', [])))}",
        "",
        "## 4. 候选人类型",
        "",
        "- A 类：岗位标题和核心能力同时命中。",
        "- B 类：核心能力命中，但业务场景或团队边界需要复核。",
        "- C 类：有相邻经验，但证据不足，需要人工追问。",
        "",
        "## 5. 寻访关键点",
        "",
        "- 先用岗位别名确认真实职责，再用核心术语追问项目深度。",
        "- 对公司背景只作为优先级线索，不替代个人贡献证据。",
        "- 对加分项追问线上指标、团队边界和业务结果。",
        "",
        "## 6. 公司池与团队优先级",
        "",
        f"- 目标公司：{_format_list(list(target_companies))}",
        "",
        "## 7. 匹配关键词建议",
        "",
        f"- {_format_list(list(profile.get('search_keywords', [])))}",
        "",
        "## 8. 排除项与风险",
        "",
        f"- 排除项：{_format_list(list(profile.get('exclusion_terms', [])))}",
        f"- 风险规则：{_format_list(list(profile.get('risk_rules', [])))}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build JD role profile artifacts")
    parser.add_argument("--jd", required=True)
    parser.add_argument("--role-id", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    jd_path = Path(args.jd)
    jd_text = jd_path.read_text(encoding="utf-8-sig")
    profile = build_role_profile(jd_text, source_path=str(jd_path), role_id=args.role_id)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    out_md.write_text(render_profile_markdown(profile), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
