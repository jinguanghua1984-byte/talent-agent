"""Redaction and safety checks for second-brain public/private case pages."""

from __future__ import annotations

from hashlib import sha256
import re

SENSITIVE_MARKERS = [
    "cookie",
    "access_token",
    "access-token",
    "access token",
    "authorization",
    "trackable_token",
    "profile_url",
    "raw_profile",
    "raw_payload",
]

CONTACT_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(微信|手机号|电话|邮箱)"),
]


def _fingerprint(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:4]


def redact_candidate_name(name: str) -> str:
    return f"候选人#{_fingerprint(name)}"


def redact_company_name(name: str) -> str:
    return f"公司#{_fingerprint(name)}"


def _contains_marker(content: str) -> str | None:
    lowered = content.lower()
    for marker in SENSITIVE_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def assert_public_case_safe(
    content: str,
    *,
    candidate_names: list[str],
    company_names: list[str],
) -> None:
    marker = _contains_marker(content)
    if marker:
        raise ValueError(f"public case contains sensitive marker: {marker}")
    for name in candidate_names:
        if name and name in content:
            raise ValueError("public case contains blocked candidate text")
    for company_name in company_names:
        if company_name and company_name in content:
            raise ValueError("public case contains blocked candidate text")
    for pattern in CONTACT_PATTERNS:
        if pattern.search(content):
            raise ValueError("public case contains contact-like data")


def assert_private_case_safe(content: str) -> None:
    marker = _contains_marker(content)
    if marker:
        raise ValueError(f"private case contains sensitive marker: {marker}")
    for pattern in CONTACT_PATTERNS:
        if pattern.search(content):
            raise ValueError("private case contains contact-like data")
