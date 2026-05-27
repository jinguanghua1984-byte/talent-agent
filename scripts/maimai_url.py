from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


MAIMAI_TRACKING_QUERY_KEYS = {
    "trackable_token",
    "trackableToken",
    "trackable",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "show_tip",
}


def sanitize_maimai_profile_url(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if "maimai.cn" not in parsed.netloc:
        return text
    query = parse_qsl(parsed.query, keep_blank_values=True)
    dstu = next((item for key, item in query if key == "dstu" and item), "")
    if parsed.path.rstrip("/") == "/profile/detail" and dstu:
        return f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}?dstu={dstu}"
    safe_query = [
        (key, item)
        for key, item in query
        if key not in MAIMAI_TRACKING_QUERY_KEYS
    ]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(safe_query),
            "",
        )
    )


def build_openable_maimai_profile_url(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if "maimai.cn" not in parsed.netloc:
        return text
    query = parse_qsl(parsed.query, keep_blank_values=True)
    dstu = next((item for key, item in query if key == "dstu" and item), "")
    trackable_token = next(
        (
            item
            for key, item in query
            if key in {"trackable_token", "trackableToken", "trackable"} and item
        ),
        "",
    )
    if parsed.path.rstrip("/") != "/profile/detail" or not dstu:
        return sanitize_maimai_profile_url(text)
    safe_query = [("dstu", dstu)]
    if trackable_token:
        safe_query.append(("trackable_token", trackable_token))
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path,
            "",
            urlencode(safe_query),
            "",
        )
    )


def is_openable_maimai_profile_url(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if "maimai.cn" not in parsed.netloc or parsed.path.rstrip("/") != "/profile/detail":
        return False
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return bool(query.get("dstu") and query.get("trackable_token"))
