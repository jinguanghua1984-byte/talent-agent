import json
import subprocess
from pathlib import Path

import pytest

from scripts.talent_db import TalentDB
from scripts.talent_library import main


def _seed_db(path: Path) -> int:
    db = TalentDB(path)
    try:
        return db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "166812124",
                "profile_url": "https://maimai.cn/profile/detail?dstu=166812124&trackable_token=token-alice",
            },
            platform="maimai",
        )
    finally:
        db.close()


def test_detail_entry_generates_targets_from_ids(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id = _seed_db(db_path)
    out_path = tmp_path / "targets.json"

    exit_code = main([
        "detail",
        "--ids",
        str(candidate_id),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["metadata"]["entry"] == "talent-library detail"
    assert data["contacts"][0]["id"] == "166812124"
    assert data["contacts"][0]["trackable_token"] == "token-alice"


def test_detail_entry_generates_targets_from_top10_file(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id = _seed_db(db_path)
    top10_path = tmp_path / "top10.json"
    out_path = tmp_path / "targets.json"
    top10_path.write_text(
        json.dumps({"top10": [{"candidate_id": candidate_id, "name": "Alice"}]}),
        encoding="utf-8",
    )

    exit_code = main([
        "detail",
        "--top10-file",
        str(top10_path),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["metadata"]["source_file"] == str(top10_path)
    assert data["metadata"]["total_contacts"] == 1


def test_detail_entry_requires_one_target_source(tmp_path: Path):
    out_path = tmp_path / "targets.json"

    try:
        main(["detail", "--out", str(out_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("detail entry should require ids or top10 file")


def _write_capture(path: Path, contacts: list[dict]) -> None:
    path.write_text(
        json.dumps({"contacts": contacts, "metadata": {"export_type": "full"}}),
        encoding="utf-8",
    )


def _maimai_contact(**overrides):
    payload = {
        "id": 166812124,
        "name": "Alice",
        "company": "Acme",
        "position": "AI PM",
        "city": "Shanghai",
        "gender_str": 2,
        "hunting_status": 5,
        "job_preferences": {
            "regions": ["Shanghai", "Beijing"],
            "positions": ["AI Product Lead"],
            "salary": "50k-70k/月",
        },
        "detail_url": (
            "https://maimai.cn/profile/detail?dstu=166812124&"
            "trackable_token=token-alice"
        ),
        "trackable_token": "token-alice",
    }
    payload.update(overrides)
    return payload


def test_import_entry_dry_run_dedupes_contacts_without_writing_db(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    out_path = tmp_path / "import-report.md"
    _write_capture(first, [_maimai_contact()])
    _write_capture(second, [_maimai_contact(position="AI PM Updated")])

    exit_code = main([
        "import",
        "--input",
        str(first),
        "--input",
        str(second),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    db = TalentDB(db_path)
    try:
        assert exit_code == 0
        assert db.count() == 0
    finally:
        db.close()
    data = json.loads(out_path.with_suffix(".json").read_text(encoding="utf-8-sig"))
    assert data["mode"] == "dry-run"
    assert data["raw_contacts"] == 2
    assert data["unique_contacts"] == 1
    assert data["duplicates_skipped"] == 1
    assert data["result"]["created"] == 1


def test_import_entry_apply_uses_batch_ingest_with_normalized_maimai_contacts(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    capture = tmp_path / "capture.json"
    out_path = tmp_path / "import-report.md"
    _write_capture(capture, [_maimai_contact()])

    exit_code = main([
        "import",
        "--input",
        str(capture),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
        "--apply",
        "--confirm",
        "确认导入人才",
    ])

    db = TalentDB(db_path)
    try:
        candidate = db.fulltext_search("Alice")[0]
        stored = db.get(candidate.id)
        sources = db.get_sources(candidate.id)
        assert exit_code == 0
        assert db.count() == 1
        assert stored.hunting_status == "在职-看机会"
        assert json.loads(stored.expected_city) == ["Shanghai", "Beijing"]
        assert sources[0].platform == "maimai"
        assert sources[0].platform_id == "166812124"
        assert sources[0].raw_profile["maimai_contact"]["trackable_token"] == "token-alice"
    finally:
        db.close()


def test_import_entry_apply_preserves_maimai_list_raw_for_scoring(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    capture = tmp_path / "capture.json"
    out_path = tmp_path / "import-report.md"
    _write_capture(
        capture,
        [
            _maimai_contact(
                school="哈尔滨工业大学",
                edu=[
                    {
                        "school": "哈尔滨工业大学",
                        "sdegree": "硕士",
                        "hover": {"tags": "985,211,QS500,C9"},
                    }
                ],
            )
        ],
    )

    exit_code = main([
        "import",
        "--input",
        str(capture),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
        "--apply",
        "--confirm",
        "确认导入人才",
    ])

    db = TalentDB(db_path)
    try:
        candidate = db.fulltext_search("Alice")[0]
        detail = db.get_detail(candidate.id)
        assert exit_code == 0
        assert detail is not None
        assert detail.raw_data is not None
        assert detail.raw_data["maimai_list"]["school"] == "哈尔滨工业大学"
        assert detail.raw_data["maimai_list"]["edu"][0]["hover"]["tags"] == "985,211,QS500,C9"
    finally:
        db.close()


def test_import_entry_accepts_extension_capture_and_pager_export_shapes(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    passive_capture = tmp_path / "passive-capture.json"
    pager_contacts = tmp_path / "pager-contacts.json"
    passive_report = tmp_path / "passive-report.md"
    pager_report = tmp_path / "pager-report.md"
    contact = _maimai_contact()
    passive_capture.write_text(
        json.dumps(
            {
                "exportTime": "2026-05-18T00:00:00.000Z",
                "metadata": {
                    "export_type": "capture",
                    "source_pool": "passive_interception",
                },
                "contacts": [contact],
                "totalContacts": 1,
                "details": [],
                "totalDetails": 0,
                "requests": [],
            }
        ),
        encoding="utf-8",
    )
    pager_contacts.write_text(
        json.dumps(
            {
                "exportTime": "2026-05-18T00:00:00.000Z",
                "metadata": {
                    "total_pages": 1,
                    "captured_pages": 1,
                    "total_count": 1,
                    "search_params": {
                        "url": "/api/ent/v3/search/basic",
                        "method": "POST",
                        "headerNames": [],
                    },
                },
                "contacts": [contact],
                "totalContacts": 1,
            }
        ),
        encoding="utf-8",
    )

    passive_exit = main([
        "import",
        "--input",
        str(passive_capture),
        "--db",
        str(db_path),
        "--out",
        str(passive_report),
    ])
    pager_exit = main([
        "import",
        "--input",
        str(pager_contacts),
        "--db",
        str(db_path),
        "--out",
        str(pager_report),
    ])

    passive_summary = json.loads(passive_report.with_suffix(".json").read_text(encoding="utf-8-sig"))
    pager_summary = json.loads(pager_report.with_suffix(".json").read_text(encoding="utf-8-sig"))
    assert passive_exit == 0
    assert pager_exit == 0
    assert passive_summary["raw_contacts"] == 1
    assert pager_summary["raw_contacts"] == 1
    assert passive_summary["unique_contacts"] == pager_summary["unique_contacts"] == 1
    assert passive_summary["result"]["created"] == pager_summary["result"]["created"] == 1
    assert passive_summary["pre_errors"] == pager_summary["pre_errors"] == 0
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_wechat_sync_exports_markdown_and_indexes_timeline(
    tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "talent.db"
    output_dir = tmp_path / "wechat-timelines"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice Chen"}, platform="manual")
    finally:
        db.close()

    def fake_which(name):
        if name in {"wechat-cli.exe", "wechat-cli"}:
            return "wechat-cli.exe"
        return None

    def fake_run(command, check, capture_output, text, encoding):
        output_index = command.index("--output") + 1
        Path(command[output_index]).write_text(
            "## 2026-05-01 10:00:00 Alice\n你好\n\n"
            "## 2026-05-01 10:01:00 顾问\n你好，方便聊聊吗？\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("scripts.talent_library.shutil.which", fake_which)
    monkeypatch.setattr("scripts.talent_library.subprocess.run", fake_run)

    assert main(
        [
            "wechat-sync",
            "--candidate-id",
            str(candidate_id),
            "--chat-name",
            "Alice微信",
            "--start-time",
            "2026-05-01",
            "--end-time",
            "2026-05-12",
            "--db",
            str(db_path),
            "--out-dir",
            str(output_dir),
            "--wechat",
            "alice-wx",
        ]
    ) == 0

    files = list(output_dir.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "candidate_id: " + str(candidate_id) in text
    assert "chat_name: Alice微信" in text
    assert "## 2026-05-01 10:00:00 Alice" in text

    db = TalentDB(db_path)
    try:
        candidate = db.get(candidate_id)
        timelines = db.get_wechat_timelines(candidate_id)
    finally:
        db.close()

    assert candidate is not None
    assert candidate.wechat == "alice-wx"
    assert len(timelines) == 1
    assert timelines[0].chat_name == "Alice微信"
    assert timelines[0].message_count == 2


def test_wechat_sync_requires_existing_candidate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("scripts.talent_library.shutil.which", lambda name: "wechat-cli.exe")

    with pytest.raises(ValueError, match="Candidate does not exist"):
        main(
            [
                "wechat-sync",
                "--candidate-id",
                "999",
                "--chat-name",
                "张三",
                "--start-time",
                "2026-05-01",
                "--end-time",
                "2026-05-12",
                "--db",
                str(tmp_path / "talent.db"),
            ]
        )


def test_wechat_sync_reports_cli_failure(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice Chen"}, platform="manual")
    finally:
        db.close()

    def fake_run(command, check, capture_output, text, encoding):
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr="wechat database locked",
        )

    monkeypatch.setattr("scripts.talent_library.shutil.which", lambda name: "wechat-cli.exe")
    monkeypatch.setattr("scripts.talent_library.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="wechat-cli export failed"):
        main(
            [
                "wechat-sync",
                "--candidate-id",
                str(candidate_id),
                "--chat-name",
                "Alice微信",
                "--start-time",
                "2026-05-01",
                "--end-time",
                "2026-05-12",
                "--db",
                str(db_path),
                "--out-dir",
                str(tmp_path / "wechat-timelines"),
            ]
        )

    db = TalentDB(db_path)
    try:
        assert db.get_wechat_timelines(candidate_id) == []
    finally:
        db.close()
