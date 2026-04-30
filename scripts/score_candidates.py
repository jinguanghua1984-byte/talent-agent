"""[LEGACY] 对 Boss 搜索结果进行评分排序

已被 score_pipeline.py 替代。保留用于回归基线对比。
新项目请使用: python -m scripts.score_pipeline run --jd-id <id> --source boss --search-keyword <keyword>
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 搜索意图关键词
SEARCH_INTENT = "企业级agent"
INTENT_KEYWORDS = [
    "agent", "智能体", "ai agent", "llm agent", "大模型应用",
    "企业级", "enterprise", "ai应用", "ai平台", "ai产品",
    "rpa", "workflow", "copilot", "ai工程", "ai落地",
    "多模态", "nlp", "自然语言", "对话系统", "知识图谱",
    "rag", "向量数据库", "prompt engineering", "langchain",
    "autogen", "crewai", "dify", "coze", "fastgpt",
    "大模型", "gpt", "glm", " Claude", "gemini",
    "agentic", "tool use", "function calling",
    "ai架构", "机器学习", "深度学习",
]

# 高权重关键词（直接与 agent 相关）
HIGH_WEIGHT_KEYWORDS = [
    "agent", "智能体", "agentic", "ai agent", "llm agent",
    "langchain", "autogen", "crewai", "dify", "coze", "fastgpt",
    "rag", "function calling", "tool use", "copilot",
    "企业级", "enterprise", "ai平台", "ai工程", "ai落地",
]

# 中等权重关键词（AI 相关但非 agent 核心）
MED_WEIGHT_KEYWORDS = [
    "大模型", "llm", "gpt", "glm", "多模态",
    "nlp", "自然语言", "对话系统", "知识图谱",
    "prompt", "ai应用", "ai产品", "ai架构",
    "机器学习", "深度学习", "embedding",
]

# 低权重关键词（泛技术背景）
LOW_WEIGHT_KEYWORDS = [
    "python", "java", "go", "typescript", "react",
    "微服务", "分布式", "kubernetes", "docker",
    "全栈", "后端", "前端", "架构师",
]

# 名企加分
TOP_COMPANIES = [
    "阿里巴巴", "阿里", "字节跳动", "字节", "腾讯",
    "百度", "美团", "京东", "拼多多", "网易",
    "小米", "华为", "滴滴", "快手",
    "微软", "google", "amazon", "meta", "apple",
    "openai", "anthropic", "智谱", "百川", "月之暗面",
    "minimax", "零一万物", "商汤", "旷视",
]

# 学历评分
EDU_SCORES = {
    "博士": 15,
    "硕士": 12,
    "mba": 12,
    "emba": 12,
    "本科": 8,
    "大专": 4,
}

# 工作年限评分
def work_year_score(years_str):
    if not years_str:
        return 5
    m = re.search(r"(\d+)", years_str)
    if not m:
        return 5
    years = int(m.group(1))
    if years >= 10:
        return 10
    elif years >= 7:
        return 8
    elif years >= 5:
        return 7
    elif years >= 3:
        return 5
    else:
        return 3

# 薪资评分（薪资越高说明市场认可度越高，间接反映能力）
def salary_score(low, high):
    if not low or not high:
        return 3
    avg = (low + high) / 2
    if avg >= 80:
        return 10
    elif avg >= 60:
        return 8
    elif avg >= 40:
        return 6
    elif avg >= 25:
        return 4
    else:
        return 2

# 活跃度评分
def active_score(desc):
    if not desc:
        return 3
    if "今日" in desc or "刚刚" in desc:
        return 10
    elif "本周" in desc:
        return 8
    elif "近" in desc or "2周" in desc or "3日" in desc:
        return 6
    else:
        return 3


def score_candidate(item: dict) -> dict:
    """对单个候选人评分，返回评分明细"""
    scores = {}

    # === 维度 1: 职位匹配度 (0-30) ===
    pos_score = 0
    expect_name = (item.get("expect") or {}).get("name", "").lower()
    lid_tag = (item.get("lidTag") or "").lower()
    desc = (item.get("geekDesc") or {}).get("name", "").lower()

    # lidTag 是平台标签，权重高
    tag_text = f"{expect_name} {lid_tag} {desc}"

    # 统计关键词命中
    high_hits = sum(1 for kw in HIGH_WEIGHT_KEYWORDS if kw in tag_text)
    med_hits = sum(1 for kw in MED_WEIGHT_KEYWORDS if kw in tag_text)
    low_hits = sum(1 for kw in LOW_WEIGHT_KEYWORDS if kw in tag_text)

    # 职位匹配度 = 标签直接相关 + 描述关键词密度
    direct_match = 0
    if any(kw in lid_tag for kw in ["agent", "智能体", "ai"]):
        direct_match = 15
    elif any(kw in lid_tag for kw in ["产品", "算法", "架构", "nlp", "大模型", "llm"]):
        direct_match = 10
    elif any(kw in expect_name for kw in ["agent", "智能体", "ai"]):
        direct_match = 12

    keyword_density = min(15, high_hits * 3 + med_hits * 1.5 + low_hits * 0.5)
    pos_score = min(30, direct_match + keyword_density)
    scores["职位匹配度"] = round(pos_score, 1)

    # === 维度 2: 技能重叠度 (0-25) ===
    skill_score = 0
    # 从描述中提取技能关键词
    skill_hits = high_hits + med_hits
    # 额外检查 works 中的公司
    works = item.get("works", [])
    work_companies = " ".join(
        (w.get("name", "") or "").lower() for w in works
    )
    # 检查是否有 AI 公司经历
    ai_companies = [
        "智谱", "百川", "月之暗面", "minimax", "零一万物",
        "商汤", "旷视", "openai", "anthropic", "dify", "coze",
        "langchain", "autogen", "rasa",
    ]
    ai_company_hits = sum(1 for c in ai_companies if c in work_companies.lower())

    skill_score = min(25, skill_hits * 2 + ai_company_hits * 5)
    scores["技能重叠度"] = round(skill_score, 1)

    # === 维度 3: 行业经验 (0-20) ===
    industry_score = 0
    # 名企经历加分
    all_company_text = work_companies
    top_company_hits = sum(1 for c in TOP_COMPANIES if c.lower() in all_company_text)
    industry_score += min(10, top_company_hits * 3)
    # AI/大模型行业经历
    industry_score += min(10, ai_company_hits * 5 + high_hits * 1)
    scores["行业经验"] = round(min(20, industry_score), 1)

    # === 维度 4: 学历背景 (0-15) ===
    edu = (item.get("highestDegreeName") or "").lower()
    edu_score = EDU_SCORES.get(edu, 5)
    # 名校加分
    school = (item.get("eduSchool") or "").lower()
    top_schools = [
        "清华", "北大", "北京大", "浙江大", "复旦", "上海交",
        "中科大", "中国科学院", "南京大", "哈工大", "华中科技",
        "武汉大", "中山大", "西安交", "同济", "北航", "北理",
        "cmu", "mit", "stanford", "berkeley", "cambridge", "oxford",
    ]
    school_bonus = sum(3 for s in top_schools if s in school)
    scores["学历背景"] = round(min(15, edu_score + school_bonus), 1)

    # === 维度 5: 意向匹配 (0-10) ===
    intent_score = 0
    # 工作年限
    wy = item.get("workYear", "")
    intent_score += work_year_score(wy) * 0.3  # 最多 3 分
    # 薪资期望
    intent_score += salary_score(item.get("lowSalary"), item.get("hightSalary")) * 0.3  # 最多 3 分
    # 活跃度
    intent_score += active_score(item.get("activeDesc")) * 0.4  # 最多 4 分
    scores["意向匹配"] = round(min(10, intent_score), 1)

    total = sum(scores.values())
    scores["总分"] = round(total, 1)

    return scores


def main():
    data_file = Path("data/boss-search/search-企业级agent.json")
    if not data_file.exists():
        print(json.dumps({"status": "error", "message": f"文件不存在: {data_file}"}))
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    print(f"开始评分，共 {len(items)} 条记录...", file=sys.stderr)

    results = []
    for i, item in enumerate(items):
        scores = score_candidate(item)
        results.append({
            "rank": 0,
            "name": item.get("name", ""),
            "gender": "男" if item.get("gender") == 1 else "女" if item.get("gender") == 2 else "未知",
            "city": item.get("city", ""),
            "workYear": item.get("workYear", ""),
            "salary": item.get("salary", ""),
            "education": item.get("highestDegreeName", ""),
            "school": item.get("eduSchool", ""),
            "major": item.get("eduMajor", ""),
            "activeDesc": item.get("activeDesc", ""),
            "lidTag": item.get("lidTag", ""),
            "expect": (item.get("expect") or {}).get("name", "").strip(),
            "current_work": (item.get("workEduDesc") or {}).get("name", "").strip(),
            "desc": ((item.get("geekDesc") or {}).get("name", "") or "")[:200],
            "encryptGeekId": item.get("encryptGeekId", ""),
            "scores": scores,
            "raw": item,
        })

    # 按总分排序
    results.sort(key=lambda x: x["scores"]["总分"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    # 输出
    output = {
        "status": "ok",
        "data": {
            "query": data.get("query", ""),
            "total": len(results),
            "scored_at": __import__("datetime").datetime.now().isoformat(),
            "candidates": results,
        }
    }

    # 写入结果文件
    output_file = Path("data/boss-search/scored-企业级agent.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"评分完成，结果已写入 {output_file}", file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
