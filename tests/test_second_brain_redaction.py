import pytest

from scripts.second_brain_redaction import (
    assert_private_case_safe,
    assert_public_case_safe,
    redact_candidate_name,
    redact_company_name,
)


def test_public_case_blocks_candidate_name_and_company() -> None:
    content = "候选人张三，目前在腾讯，反馈是不认可。"

    with pytest.raises(ValueError, match="public case contains blocked candidate text"):
        assert_public_case_safe(content, candidate_names=["张三"], company_names=["腾讯"])


def test_public_case_blocks_profile_url_and_token_marker() -> None:
    content = "profile_url=https://maimai.cn/detail?dstu=1&trackable_token=secret"

    with pytest.raises(ValueError, match="public case contains sensitive marker"):
        assert_public_case_safe(content, candidate_names=[], company_names=[])


def test_private_case_allows_name_and_company_but_blocks_contact() -> None:
    content = "张三 当前公司 腾讯 手机号 13800000000"

    with pytest.raises(ValueError, match="private case contains contact-like data"):
        assert_private_case_safe(content)


def test_redaction_helpers_are_stable() -> None:
    assert redact_candidate_name("张三") == "候选人#1d84"
    assert redact_company_name("腾讯") == "公司#5387"
