"""搜索结果 → candidate schema 格式转换。

搜索结果 JSON 存储平台原始字段，评分 pipeline 需要规范化字段。
此模块提供独立的转换函数，不依赖 adapter 模块。
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def convert_boss_search_result(item: dict) -> dict:
    """将 Boss 搜索结果 item 转换为 candidate schema 格式。

    输入: data/boss-search/search-*.json 中的单个 item (原始 API 格式)
    输出: 符合 candidate.schema.json 的 dict
    """
    result: dict[str, Any] = {}

    result["name"] = item.get("name", "")

    gender = item.get("gender")
    if gender == 1:
        result["gender"] = "男"
    elif gender == 2:
        result["gender"] = "女"

    result["city"] = item.get("city", "")

    degree = item.get("highestDegreeName")
    if degree:
        edu_map = {"大专": "大专", "本科": "本科", "硕士": "硕士",
                    "博士": "博士", "MBA": "硕士", "EMBA": "硕士"}
        result["education"] = edu_map.get(degree, degree)

    work_year = item.get("workYear")
    if work_year:
        m = re.search(r"(\d+)", str(work_year))
        if m:
            result["work_years"] = int(m.group(1))

    active_desc = item.get("activeDesc")
    if active_desc:
        result["active_state"] = active_desc

    salary = item.get("salary")
    if salary:
        result["expected_salary"] = salary

    # 当前职位: workEduDesc.name = "公司名·部门·职位名"
    work_edu = item.get("workEduDesc") or {}
    work_edu_name = work_edu.get("name", "")
    if work_edu_name:
        parts = work_edu_name.split("·")
        if len(parts) >= 2:
            result["current_company"] = parts[0]
            result["current_title"] = parts[-1]
        else:
            result["current_title"] = work_edu_name

    expect = item.get("expect") or {}
    expect_name = expect.get("name", "").strip()
    if expect_name:
        result["expected_title"] = expect_name

    label_list = item.get("labelMatchList") or []
    skill_tags = [tag["markWord"] for tag in label_list if tag.get("markWord")]
    if skill_tags:
        result["skill_tags"] = skill_tags

    # 工作经历: works[].name = "职位·公司" 或 "公司·职位"
    works = item.get("works") or []
    if works:
        experiences = []
        for w in works:
            w_name = w.get("name", "")
            parts = w_name.split("·")
            if len(parts) >= 2:
                w_title, w_company = parts[0], parts[-1]
            else:
                w_title, w_company = w_name, ""
            experiences.append({
                "period": "",
                "company": w_company,
                "title": w_title,
                "description": "",
            })
        if experiences:
            result["work_experience"] = experiences

    school = item.get("eduSchool", "")
    major = item.get("eduMajor", "")
    if school or major:
        result["education_experience"] = [{
            "period": "", "school": school, "major": major, "description": ""
        }]

    geek_desc = item.get("geekDesc") or {}
    desc_text = geek_desc.get("name", "")
    if desc_text:
        result["_desc_raw"] = desc_text

    lid_tag = item.get("lidTag")
    if lid_tag:
        result["_lid_tag"] = lid_tag

    encrypt_id = item.get("encryptGeekId", "")
    if encrypt_id:
        result["_source"] = {
            "channel": "boss",
            "platform_id": encrypt_id,
            "url": f"https://www.zhipin.com/web/geek/{encrypt_id}",
        }
        result["id"] = f"boss-{encrypt_id[:16]}"

    return result


def batch_convert(items: list[dict], source: str) -> list[dict]:
    """批量转换搜索结果。"""
    converters = {
        "boss": convert_boss_search_result,
    }
    converter = converters.get(source)
    if not converter:
        raise ValueError(f"不支持的数据来源: {source!r}，支持: {list(converters.keys())}")
    return [converter(item) for item in items]
