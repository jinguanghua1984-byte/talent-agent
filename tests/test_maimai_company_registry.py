import json
from pathlib import Path

import pytest

from scripts.maimai_company_registry import (
    CompanyProductMapping,
    expand_company_pool_terms,
    load_company_product_registry,
    resolve_company_product_term,
)


def _registry_path(tmp_path: Path) -> Path:
    path = tmp_path / "company-product-registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "term": "字节 DMC",
                        "canonical_company": "字节跳动",
                        "company_aliases": ["字节", "ByteDance"],
                        "org_product_terms": ["DMC", "Data Management Center", "数据管理中心"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                    {
                        "term": "阿里千问",
                        "canonical_company": "阿里巴巴",
                        "company_aliases": ["阿里", "阿里云", "Alibaba"],
                        "org_product_terms": ["通义千问", "通义", "Qwen", "千问"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                    {
                        "term": "百度千帆",
                        "canonical_company": "百度",
                        "company_aliases": ["百度", "Baidu"],
                        "org_product_terms": ["千帆", "文心", "ERNIE"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_resolve_company_product_term_maps_shorthand(tmp_path: Path) -> None:
    registry = load_company_product_registry(_registry_path(tmp_path))

    mapping = resolve_company_product_term("字节 dmc", registry)

    assert mapping == CompanyProductMapping(
        term="字节 DMC",
        canonical_company="字节跳动",
        company_aliases=["字节", "ByteDance"],
        org_product_terms=["DMC", "Data Management Center", "数据管理中心"],
        preferred_search_mode="hybrid",
        confidence="curated",
    )


def test_expand_company_pool_terms_keeps_unknown_terms_as_query_only(tmp_path: Path) -> None:
    registry = load_company_product_registry(_registry_path(tmp_path))

    expanded = expand_company_pool_terms(["字节 DMC", "未知团队"], registry)

    assert expanded[0]["raw_term"] == "字节 DMC"
    assert expanded[0]["canonical_company"] == "字节跳动"
    assert expanded[0]["org_product_terms"] == ["DMC", "Data Management Center", "数据管理中心"]
    assert expanded[1]["raw_term"] == "未知团队"
    assert expanded[1]["canonical_company"] == ""
    assert expanded[1]["preferred_search_mode"] == "query_only"


def test_load_company_product_registry_rejects_duplicate_terms(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {"term": "字节 DMC", "canonical_company": "字节跳动"},
                    {"term": "字节 dmc", "canonical_company": "字节跳动"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate company product term"):
        load_company_product_registry(path)
