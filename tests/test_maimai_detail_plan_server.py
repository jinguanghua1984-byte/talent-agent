import json
from pathlib import Path

from scripts.maimai_detail_plan_server import build_plan_payload


def test_build_plan_payload_serves_contacts_shape(tmp_path: Path):
    plan = tmp_path / "targets.json"
    plan.write_text(
        json.dumps({
            "contacts": [
                {
                    "id": "129307963",
                    "trackable_token": "token-1",
                    "name": "候选人",
                }
            ],
            "totalContacts": 1,
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = build_plan_payload(plan)

    assert payload["contacts"][0]["id"] == "129307963"
    assert payload["totalContacts"] == 1


def test_build_plan_payload_rejects_missing_contacts(tmp_path: Path):
    plan = tmp_path / "bad.json"
    plan.write_text(json.dumps({"items": []}), encoding="utf-8")

    try:
        build_plan_payload(plan)
    except ValueError as exc:
        assert "contacts" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_plan_payload_accepts_top_level_contact_list(tmp_path: Path):
    plan = tmp_path / "targets.json"
    plan.write_text(
        json.dumps([
            {"id": "1", "trackable_token": "a"},
            {"id": "2", "trackable_token": "b"},
        ]),
        encoding="utf-8",
    )

    payload = build_plan_payload(plan)

    assert [item["id"] for item in payload["contacts"]] == ["1", "2"]
    assert payload["totalContacts"] == 2
