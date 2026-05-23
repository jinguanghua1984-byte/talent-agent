import json
import subprocess
from pathlib import Path

import pytest

from scripts import jd_talent_delivery_feishu as feishu
from scripts.jd_talent_delivery_feishu import (
    _first_sheet_id,
    _nodes_by_title,
    _resolve_lark_cli_argv,
    _stdout_json,
    _token,
    _without_dry_run,
    build_publish_manifest,
    default_runner,
    main,
    publish_output,
    validate_delivery_package,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_required_files(root: Path) -> None:
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(root / "reports" / "outreach-queue.csv", "name,email\nA,a@example.com\n")


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        joined = " ".join(argv)
        if argv == ["lark-cli", "doctor"]:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true}', "")
        if argv == ["lark-cli", "auth", "status"]:
            return subprocess.CompletedProcess(argv, 0, '{"tokenStatus":"valid","userOpenId":"ou_default_user"}', "")
        if "im +chat-search" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                '{"data":{"chats":[{"chat_id":"oc_jd_coordination","name":"JD需求协同"}]}}',
                "",
            )
        if "wiki +node-create" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +node-create" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"parent_node","obj_token":"parent_doc"}', "")
        if "drive +import" in joined and "--type docx" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "drive +import" in joined and "--type docx" in joined:
            token = "doc_" + str(len(self.calls))
            return subprocess.CompletedProcess(argv, 0, json.dumps({"obj_token": token}), "")
        if "sheets +create" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "sheets +create" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                '{"data":{"spreadsheet":{"spreadsheet_token":"sheet_token"}}}',
                "",
            )
        if "sheets +write" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "sheets +write" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"updatedRange":"A1:H2"}', "")
        if "wiki +move" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +move" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"moved_node","ready":true}', "")
        if "wiki +node-list" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                '{"items":[{"title":"Demo Role JD","obj_type":"docx"},{"title":"Demo Role outreach queue","obj_type":"sheet"}]}',
                "",
            )
        if "wiki +node-get" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node":{"title":"readback","obj_type":"docx"}}', "")
        if "docs +fetch" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"outline":[{"text":"Heading 1","level":1}]}', "")
        if "sheets +info" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                '{"data":{"sheets":{"sheets":[{"sheet_id":"sheet_1","title":"Sheet1"}]}}}',
                "",
            )
        if "sheets +read" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        "values": [
                            [
                                "candidate_id",
                                "name",
                                "company",
                                "title",
                                "score",
                                "grade",
                                "suggested_outreach_angle",
                                "profile_url",
                            ],
                            [
                                "1",
                                "A",
                                "Demo Corp",
                                "AI Lead",
                                "88",
                                "A",
                                "围绕 Demo Corp 的 AI Lead 经历确认岗位匹配深度。",
                                "https://maimai.cn/profile/detail?dstu=p1",
                            ],
                        ]
                    },
                    ensure_ascii=False,
                ),
                "",
            )
        if "im +messages-send" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"message_id":"om_demo","ok":true}', "")
        return subprocess.CompletedProcess(argv, 1, "", "unexpected command")


class ExistingChildrenRunner(FakeRunner):
    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        joined = " ".join(argv)
        if "wiki +node-list" in joined:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        "data": {
                            "nodes": [
                                {
                                    "title": "Demo Role JD",
                                    "obj_type": "docx",
                                    "obj_token": "existing_doc_jd",
                                    "node_token": "existing_node_jd",
                                },
                                {
                                    "title": "Demo Role role profile",
                                    "obj_type": "docx",
                                    "obj_token": "existing_doc_profile",
                                    "node_token": "existing_node_profile",
                                },
                                {
                                    "title": "Demo Role recommendation report",
                                    "obj_type": "docx",
                                    "obj_token": "existing_doc_recommendation",
                                    "node_token": "existing_node_recommendation",
                                },
                                {
                                    "title": "Demo Role outreach queue",
                                    "obj_type": "sheet",
                                    "obj_token": "existing_sheet",
                                    "node_token": "existing_node_sheet",
                                },
                            ]
                        }
                    }
                ),
                "",
            )
        return super().__call__(argv, cwd)


class FailingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "simulated failure")


class BadSheetReadbackRunner(FakeRunner):
    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        joined = " ".join(argv)
        if "sheets +read" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"values":[["wrong","header"],["bad","row"]]}', "")
        return super().__call__(argv, cwd)


def _safe_output_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-role-2026-05-23"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# 岗位画像\n")
    _write(root / "reports" / "talent-recommendation.md", "# 推荐报告\n")
    recommendation = {
        "read_only": True,
        "top_n": 1,
        "summary": {"total_scored": 1, "coarse_total": 1},
        "ranked": [
            {
                "candidate_id": 1,
                "name": "A",
                "score": 88,
                "grade": "A",
                "recommendation_label": "强推荐",
                "current_company": "Demo Corp",
                "current_title": "AI Lead",
                "profile_url": "https://maimai.cn/profile/detail?dstu=p1",
                "evidence": {"key_evidence": ["评分证据：Demo Corp / AI Lead"]},
            }
        ],
    }
    _write(root / "reports" / "talent-recommendation.json", json.dumps(recommendation, ensure_ascii=False))
    _write(root / "scoring" / "detailed-rank.json", json.dumps(recommendation, ensure_ascii=False))
    _write(
        root / "reports" / "quality-gates.json",
        json.dumps({"schema": "jd_talent_delivery_quality_gates_v1", "status": "passed"}, ensure_ascii=False),
    )
    _write(
        root / "reports" / "outreach-queue.csv",
        "candidate_id,name,company,title,score,grade,suggested_outreach_angle,profile_url\n"
        "1,A,Demo Corp,AI Lead,88,A,围绕 Demo Corp 的 AI Lead 经历确认岗位匹配深度。,"
        "https://maimai.cn/profile/detail?dstu=p1\n",
    )
    return root


def test_manifest_uses_doc_import_sheet_write_and_wiki_move(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )

    assert manifest["schema"] == "jd_talent_delivery_feishu_manifest_v1"
    assert manifest["wiki_space_id"] == "7642607697183001542"
    assert manifest["source_files"] == {
        "jd": "source/jd.md",
        "profile": "profile/role-deep-dive.md",
        "recommendation": "reports/talent-recommendation.md",
        "outreach": "reports/outreach-queue.csv",
    }

    serialized = json.dumps(manifest, ensure_ascii=False)
    for token in ["drive", "+import", "--type", "docx", "sheets", "+create", "+write", "wiki", "+move"]:
        assert token in serialized
    assert "lark-cli doctor" in serialized
    assert "lark-cli auth status" in serialized
    assert "wiki +node-create" in serialized
    assert "drive +import --type sheet" not in serialized
    assert "CSV is imported with drive import as sheet" not in serialized
    assert "sheets +append --file" not in serialized


def test_manifest_rejects_sensitive_paths(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(root / "reports" / "outreach-queue.csv", "database\nraw/search/unit-1.json\n")

    with pytest.raises(ValueError, match="sensitive marker"):
        build_publish_manifest(root, jd_title="Demo", wiki_space_id="7642607697183001542", dry_run=True)


def test_manifest_rejects_tracking_tokens_in_publish_sources(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(
        root / "reports" / "outreach-queue.csv",
        "profile_url\nhttps://maimai.cn/profile/detail?dstu=p1&trackable_token=secret\n",
    )

    with pytest.raises(ValueError, match="sensitive marker"):
        build_publish_manifest(root, jd_title="Demo", wiki_space_id="7642607697183001542", dry_run=True)


def test_parent_create_respects_dry_run_flag(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    dry_manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )
    live_manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=False,
    )

    dry_parent = next(step["argv"] for step in dry_manifest["publish_steps"] if "+node-create" in step["argv"])
    live_parent = next(step["argv"] for step in live_manifest["publish_steps"] if "+node-create" in step["argv"])
    assert "--dry-run" in dry_parent
    assert "--dry-run" not in live_parent


def test_manifest_rejects_sensitive_title_from_final_manifest_check(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    with pytest.raises(ValueError, match="sensitive marker"):
        build_publish_manifest(root, jd_title="talent.db", wiki_space_id="7642607697183001542", dry_run=True)


def test_normal_database_content_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\nExperience with vector database systems is preferred.\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(
        root / "reports" / "talent-recommendation.md",
        "# Recommendations\nCandidate has database systems background.\n",
    )
    _write(root / "reports" / "outreach-queue.csv", "name,notes\nA,vector database systems\n")

    manifest = build_publish_manifest(
        root,
        jd_title="Database Platform Engineer",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )

    assert manifest["jd_title"] == "Database Platform Engineer"


def test_main_writes_utf8_sig_manifest_and_creates_parent_dir(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)
    manifest_out = root / "feishu" / "publish-manifest.json"

    code = main(
        [
            "--output-root",
            str(root),
            "--jd-title",
            "Demo JD",
            "--manifest-out",
            str(manifest_out),
            "--dry-run",
        ]
    )

    assert code == 0
    assert manifest_out.read_bytes().startswith(b"\xef\xbb\xbf")
    stored = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    assert stored["schema"] == "jd_talent_delivery_feishu_manifest_v1"
    assert stored["wiki_space_id"] == "7642607697183001542"


def test_publish_output_runs_preflight_dry_run_then_real_publish(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = FakeRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
    )

    assert result["status"] == "published"
    assert result["parent_node_token"] == "parent_node"
    assert (root / "feishu" / "publish-results.json").exists()
    assert (root / "feishu" / "dry-run-results.json").exists()
    assert (root / "feishu" / "im-notification-message.txt").exists()
    assert (root / "feishu" / "im-notification-results.json").exists()
    assert result["notification"]["status"] == "sent"
    assert result["notification"]["target_type"] == "chat_name"
    assert result["notification"]["target_name"] == "JD需求协同"
    assert result["notification"]["target_id"] == "oc_jd_coordination"

    dry_run_results = json.loads((root / "feishu" / "dry-run-results.json").read_text(encoding="utf-8-sig"))
    assert dry_run_results["schema"] == "jd_talent_delivery_feishu_dry_run_results_v1"
    assert all("--dry-run" in item["argv"] for item in dry_run_results["results"])
    assert result["readback"]["wiki_children"]["items"][0]["title"] == "Demo Role JD"
    assert len(result["readback"]["doc_outlines"]) == 3
    assert result["readback"]["sheet_previews"][0]["values"][0] == [
        "candidate_id",
        "name",
        "company",
        "title",
        "score",
        "grade",
        "suggested_outreach_angle",
        "profile_url",
    ]

    calls = [" ".join(call) for call in runner.calls]
    assert calls[0] == "lark-cli doctor"
    assert calls[1] == "lark-cli auth status"
    assert any("wiki +node-create" in call and "--dry-run" in call for call in calls)
    assert any("drive +import" in call and "--type docx" in call and "--dry-run" in call for call in calls)
    assert not any("drive +import" in call and "--type sheet" in call for call in calls)
    assert any("sheets +create" in call and "--dry-run" in call for call in calls)
    assert any("sheets +write" in call and "--values" in call for call in calls)
    assert any("wiki +move" in call and "--target-parent-token parent_node" in call for call in calls)
    assert any("wiki +node-list --as user --space-id 7642607697183001542 --parent-node-token parent_node --page-size 50 --format json" in call for call in calls)
    assert any("wiki +node-get --as user --token doc_" in call and "--obj-type docx --space-id 7642607697183001542 --format json" in call for call in calls)
    assert any("docs +fetch --as user --api-version v2 --doc doc_" in call and "--format json --scope outline --max-depth 3" in call for call in calls)
    assert any("sheets +info --as user --spreadsheet-token sheet_token" in call for call in calls)
    assert any("sheets +read --as user --spreadsheet-token sheet_token --sheet-id sheet_1 --range A1:Z5" in call for call in calls)
    assert any("im +chat-search --as user --query JD需求协同" in call for call in calls)
    assert any("im +messages-send --as user" in call and "--chat-id oc_jd_coordination" in call for call in calls)

    send_call = next(call for call in runner.calls if call[:3] == ["lark-cli", "im", "+messages-send"])
    sent_message = send_call[send_call.index("--text") + 1]
    stored_message = (root / "feishu" / "im-notification-message.txt").read_text(encoding="utf-8-sig")
    assert sent_message == stored_message
    for token in ["任务执行结果", "成果物清单", "Wiki目录", "推荐报告摘要"]:
        assert token in sent_message

    write_call = next(call for call in runner.calls if call[:3] == ["lark-cli", "sheets", "+write"] and "--dry-run" not in call)
    values = json.loads(write_call[write_call.index("--values") + 1])
    assert values[1][6] == "围绕 Demo Corp 的 AI Lead 经历确认岗位匹配深度。"


def test_publish_output_reuses_existing_parent_node_without_creating_parent(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = FakeRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
        parent_node_token="existing_parent",
    )

    assert result["status"] == "published"
    assert result["parent_node_token"] == "existing_parent"
    calls = [" ".join(call) for call in runner.calls]
    assert not any("wiki +node-create" in call for call in calls)
    assert any(
        "wiki +node-list --as user --space-id 7642607697183001542 --parent-node-token existing_parent --page-size 50 --format json"
        in call
        for call in calls
    )
    assert any("wiki +move" in call and "--target-parent-token existing_parent" in call for call in calls)


def test_publish_output_reuses_existing_children_without_duplicate_imports(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = ExistingChildrenRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
        parent_node_token="existing_parent",
    )

    assert result["status"] == "published"
    assert [item["reused_existing"] for item in result["published"]] == [True, True, True, True]
    assert [item["obj_token"] for item in result["published"]] == [
        "existing_doc_jd",
        "existing_doc_profile",
        "existing_doc_recommendation",
        "existing_sheet",
    ]
    assert (root / "feishu" / "publish-results.json").exists()
    calls = [" ".join(call) for call in runner.calls]
    assert not any("drive +import" in call for call in calls)
    assert not any("wiki +move" in call for call in calls)
    assert any("docs +fetch --as user --api-version v2 --doc existing_doc_jd" in call for call in calls)
    assert any("sheets +info --as user --spreadsheet-token existing_sheet" in call for call in calls)
    assert any("sheets +write --as user --spreadsheet-token existing_sheet" in call for call in calls)
    assert any("sheets +read --as user --spreadsheet-token existing_sheet --sheet-id sheet_1 --range A1:Z5" in call for call in calls)


def test_validate_delivery_package_blocks_bad_quality_gate(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    _write(
        root / "reports" / "quality-gates.json",
        json.dumps(
            {
                "schema": "jd_talent_delivery_quality_gates_v1",
                "status": "blocked",
                "critical_issues": ["top_n_all_low_confidence"],
            },
            ensure_ascii=False,
        ),
    )

    result = validate_delivery_package(root)

    assert result["status"] == "blocked"
    assert "quality_gate_blocked:top_n_all_low_confidence" in result["critical_issues"]


def test_publish_output_blocks_invalid_package_before_lark_calls(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    _write(root / "reports" / "outreach-queue.csv", "candidate_id,name\n1,A\n")
    runner = FakeRunner()

    with pytest.raises(ValueError, match="delivery package is not publishable"):
        publish_output(
            output_root=root,
            jd_title="Demo Role",
            wiki_space_id="7642607697183001542",
            runner=runner,
        )

    assert runner.calls == []


def test_publish_output_blocks_sheet_readback_mismatch(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)

    with pytest.raises(ValueError, match="sheet readback mismatch"):
        publish_output(
            output_root=root,
            jd_title="Demo Role",
            wiki_space_id="7642607697183001542",
            runner=BadSheetReadbackRunner(),
        )


def test_completion_notification_template_contains_required_sections(tmp_path: Path) -> None:
    text = feishu.build_completion_notification_text(
        jd_title="Demo Role",
        publish_result={"status": "published", "package_quality": {"status": "passed", "outreach_rows": 30}},
        report_summary={
            "top_n": 30,
            "coarse_total": 13332,
            "total_scored": 125,
            "grade_counts": {"A": 2, "B": 20, "C": 8, "淘汰": 0},
            "confidence_note": "JD 正文待补充，本轮为低置信优先深审名单。",
        },
        links={
            "wiki": "https://sq8org1v4k6.feishu.cn/wiki/wiki_node",
            "jd": "https://sq8org1v4k6.feishu.cn/docx/doc_jd",
            "profile": "https://sq8org1v4k6.feishu.cn/docx/doc_profile",
            "recommendation": "https://sq8org1v4k6.feishu.cn/docx/doc_report",
            "outreach": "https://sq8org1v4k6.feishu.cn/sheets/sheet_token",
        },
    )

    for token in [
        "任务执行结果",
        "成果物清单",
        "Wiki目录",
        "推荐报告摘要",
        "Top30：A=2/B=20/C=8/淘汰=0",
        "https://sq8org1v4k6.feishu.cn/wiki/wiki_node",
    ]:
        assert token in text


def test_publish_output_can_send_notification_to_explicit_chat(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = FakeRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
        notify_chat_id="oc_demo",
    )

    assert result["notification"]["target_type"] == "chat_id"
    assert result["notification"]["target_id"] == "oc_demo"
    calls = [" ".join(call) for call in runner.calls]
    assert any("im +messages-send --as user" in call and "--chat-id oc_demo" in call for call in calls)


def test_preview_values_supports_current_sheets_read_shape() -> None:
    assert feishu._preview_values({"data": {"valueRange": {"values": [["a"], ["b"]]}}}) == [
        ["a"],
        ["b"],
    ]


def test_preview_values_normalizes_url_cells() -> None:
    preview = {
        "data": {
            "valueRange": {
                "values": [
                    [
                        [
                            {
                                "type": "url",
                                "text": "https://maimai.cn/profile/detail?dstu=p1",
                                "link": "https://maimai.cn/profile/detail?dstu=p1",
                            }
                        ]
                    ]
                ]
            }
        }
    }

    assert feishu._preview_values(preview) == [["https://maimai.cn/profile/detail?dstu=p1"]]


def test_preview_values_normalizes_multi_segment_rich_text_cells() -> None:
    preview = {
        "data": {
            "valueRange": {
                "values": [
                    [
                        [
                            {"type": "text", "text": "成果展示："},
                            {
                                "type": "url",
                                "text": "https://ai.fe",
                                "link": "https://ai.fe",
                            },
                            {"type": "text", "text": "..."},
                        ]
                    ]
                ]
            }
        }
    }

    assert feishu._preview_values(preview) == [["成果展示：https://ai.fe..."]]


def test_sheet_readback_allows_trailing_blank_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "queue.csv"
    _write(csv_path, "a,b\n1,2\n")

    feishu._assert_sheet_readback_matches(
        csv_path,
        {"data": {"valueRange": {"values": [["a", "b", ""], [1, 2, ""]]}}},
    )


def test_publish_output_raises_when_command_fails(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)

    with pytest.raises(RuntimeError, match="command failed"):
        publish_output(
            output_root=root,
            jd_title="Demo Role",
            wiki_space_id="7642607697183001542",
            runner=FailingRunner(),
        )


def test_without_dry_run_removes_only_trailing_generated_flag() -> None:
    argv = ["lark-cli", "wiki", "+node-create", "--title", "--dry-run", "--dry-run"]

    assert _without_dry_run(argv) == ["lark-cli", "wiki", "+node-create", "--title", "--dry-run"]


def test_without_dry_run_preserves_middle_dry_run_value_when_no_trailing_flag() -> None:
    argv = ["lark-cli", "wiki", "+node-create", "--title", "--dry-run", "--space-id", "space"]

    assert _without_dry_run(argv) == argv
    assert _without_dry_run(argv) is not argv


def test_stdout_json_wraps_non_json_stdout_in_value_error() -> None:
    with pytest.raises(ValueError, match="command stdout is not valid JSON"):
        _stdout_json({"stdout": "not json output that should be summarized"})


def test_stdout_json_accepts_prefixed_cli_text_before_json() -> None:
    assert _stdout_json({"stdout": 'Found 5 node(s)\n{"data":{"ok":true}}'}) == {"data": {"ok": True}}


def test_stdout_json_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="command stdout JSON must be an object"):
        _stdout_json({"stdout": '["not", "object"]'})


def test_token_reads_nested_data_dict() -> None:
    assert _token({"data": {"node_token": "nested"}}, "node_token") == "nested"


def test_token_reads_deep_nested_normalized_keys() -> None:
    assert _token({"data": {"items": [{"node": {"wikiToken": "deep"}}]}}, "wiki_token") == "deep"


def test_nodes_by_title_reads_real_node_list_shape() -> None:
    nodes = _nodes_by_title(
        {
            "data": {
                "nodes": [
                    {"title": "A", "obj_token": "a"},
                    {"title": "B", "obj_token": "b"},
                ]
            }
        }
    )

    assert nodes["A"]["obj_token"] == "a"
    assert nodes["B"]["obj_token"] == "b"


def test_first_sheet_id_reads_sheets_info_shape() -> None:
    assert (
        _first_sheet_id({"data": {"sheets": {"sheets": [{"sheet_id": "OVWwfA", "title": "Sheet1"}]}}})
        == "OVWwfA"
    )


def test_resolve_lark_cli_argv_prefers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CLI", r"C:\tools\lark-cli.cmd")

    assert _resolve_lark_cli_argv(["lark-cli", "doctor"]) == [r"C:\tools\lark-cli.cmd", "doctor"]
    assert _resolve_lark_cli_argv(["node", "run.js"]) == ["node", "run.js"]


def test_resolve_lark_cli_argv_uses_cmd_shim_before_other_names(monkeypatch) -> None:
    monkeypatch.delenv("LARK_CLI", raising=False)
    checked: list[str] = []

    def fake_which(name: str) -> str | None:
        checked.append(name)
        return r"C:\npm\lark-cli.cmd" if name == "lark-cli.cmd" else None

    monkeypatch.setattr(feishu.shutil, "which", fake_which)

    assert _resolve_lark_cli_argv(["lark-cli", "auth", "status"]) == [
        r"C:\npm\lark-cli.cmd",
        "auth",
        "status",
    ]
    assert checked == ["lark-cli.cmd"]


def test_resolve_lark_cli_argv_uses_direct_node_for_sheet_json_payloads(monkeypatch) -> None:
    monkeypatch.setattr(
        feishu,
        "_resolve_direct_node_lark_cli_argv",
        lambda argv: ["node.exe", "run.js", *argv[1:]],
    )

    assert _resolve_lark_cli_argv(["lark-cli", "sheets", "+write", "--values", "[[\"中文\"]]"]) == [
        "node.exe",
        "run.js",
        "sheets",
        "+write",
        "--values",
        "[[\"中文\"]]",
    ]


def test_resolve_lark_cli_argv_uses_direct_node_for_im_text(monkeypatch) -> None:
    monkeypatch.setattr(
        feishu,
        "_resolve_direct_node_lark_cli_argv",
        lambda argv: ["node.exe", "run.js", *argv[1:]],
    )

    assert _resolve_lark_cli_argv(
        ["lark-cli", "im", "+messages-send", "--as", "user", "--user-id", "ou_demo", "--text", "中文\n消息"]
    ) == [
        "node.exe",
        "run.js",
        "im",
        "+messages-send",
        "--as",
        "user",
        "--user-id",
        "ou_demo",
        "--text",
        "中文\n消息",
    ]


def test_default_runner_passes_resolved_argv_to_subprocess(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CLI", r"C:\tools\lark-cli.cmd")
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(feishu.subprocess, "run", fake_run)

    completed = default_runner(["lark-cli", "doctor"], cwd="demo")

    assert completed.args == [r"C:\tools\lark-cli.cmd", "doctor"]
    assert seen["argv"] == [r"C:\tools\lark-cli.cmd", "doctor"]
    assert seen["kwargs"] == {
        "cwd": "demo",
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "capture_output": True,
        "check": False,
    }


def test_main_help_mentions_publish_entry(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--publish" in help_text
    assert "--no-notify" in help_text
    assert "--notify-user-id" in help_text


def test_main_publish_invokes_publish_output(tmp_path: Path, monkeypatch) -> None:
    root = _safe_output_root(tmp_path)
    calls: list[tuple[str, str, str, str | None, bool, str | None, str | None]] = []

    def fake_publish_output(
        output_root,
        jd_title,
        wiki_space_id,
        parent_node_token=None,
        notify=True,
        notify_user_id=None,
        notify_chat_id=None,
    ):
        calls.append((str(output_root), jd_title, wiki_space_id, parent_node_token, notify, notify_user_id, notify_chat_id))
        return {"status": "published"}

    monkeypatch.setattr(feishu, "publish_output", fake_publish_output)

    code = main(["--output-root", str(root), "--jd-title", "Demo Role", "--publish"])

    assert code == 0
    assert calls == [(str(root), "Demo Role", "7642607697183001542", None, True, None, None)]


def test_main_publish_passes_parent_node_token(tmp_path: Path, monkeypatch) -> None:
    root = _safe_output_root(tmp_path)
    calls: list[tuple[str, str, str, str | None, bool, str | None, str | None]] = []

    def fake_publish_output(
        output_root,
        jd_title,
        wiki_space_id,
        parent_node_token=None,
        notify=True,
        notify_user_id=None,
        notify_chat_id=None,
    ):
        calls.append((str(output_root), jd_title, wiki_space_id, parent_node_token, notify, notify_user_id, notify_chat_id))
        return {"status": "published"}

    monkeypatch.setattr(feishu, "publish_output", fake_publish_output)

    code = main(
        [
            "--output-root",
            str(root),
            "--jd-title",
            "Demo Role",
            "--parent-node-token",
            "existing_parent",
            "--publish",
        ]
    )

    assert code == 0
    assert calls == [(str(root), "Demo Role", "7642607697183001542", "existing_parent", True, None, None)]


def test_main_publish_passes_notification_flags(tmp_path: Path, monkeypatch) -> None:
    root = _safe_output_root(tmp_path)
    calls: list[tuple[bool, str | None, str | None]] = []

    def fake_publish_output(
        output_root,
        jd_title,
        wiki_space_id,
        parent_node_token=None,
        notify=True,
        notify_user_id=None,
        notify_chat_id=None,
    ):
        calls.append((notify, notify_user_id, notify_chat_id))
        return {"status": "published"}

    monkeypatch.setattr(feishu, "publish_output", fake_publish_output)

    code = main(
        [
            "--output-root",
            str(root),
            "--jd-title",
            "Demo Role",
            "--publish",
            "--no-notify",
            "--notify-user-id",
            "ou_target",
        ]
    )

    assert code == 0
    assert calls == [(False, "ou_target", None)]
