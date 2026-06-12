import zipfile
from pathlib import Path

from scripts.second_brain_gbrain import export_bundle, import_gbrain
from scripts.second_brain_models import load_jsonl


def test_export_bundle_includes_public_and_private_cases(tmp_path: Path) -> None:
    (tmp_path / "docs" / "second-brain" / "cases").mkdir(parents=True)
    (tmp_path / "data" / "second-brain" / "private-cases").mkdir(parents=True)
    (tmp_path / "docs" / "second-brain" / "cases" / "public.md").write_text(
        "public",
        encoding="utf-8",
    )
    (tmp_path / "data" / "second-brain" / "private-cases" / "private.md").write_text(
        "private",
        encoding="utf-8",
    )

    bundle = export_bundle(repo_root=tmp_path, out_path=tmp_path / "bundle.zip")

    with zipfile.ZipFile(bundle) as archive:
        assert sorted(archive.namelist()) == [
            "data/second-brain/private-cases/private.md",
            "docs/second-brain/cases/public.md",
        ]


def test_export_source_tree_includes_public_cases_and_events_without_private_cases(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs" / "second-brain" / "cases").mkdir(parents=True)
    (tmp_path / "data" / "second-brain").mkdir(parents=True)
    (tmp_path / "data" / "second-brain" / "private-cases").mkdir(parents=True)
    (tmp_path / "docs" / "second-brain" / "cases" / "public.md").write_text(
        "# Public Case\n\nEvidence only.\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "second-brain" / "private-cases" / "private.md").write_text(
        "# Private Case\n\n张三\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "second-brain" / "events.jsonl").write_text(
        '{"event_type":"batch_feedback_summarized","visibility":"public"}\n',
        encoding="utf-8",
    )

    from scripts.second_brain_gbrain import export_source_tree

    out_dir = export_source_tree(repo_root=tmp_path, out_dir=tmp_path / "brain")

    assert (out_dir / "cases" / "public.md").exists()
    assert (out_dir / "events" / "events.jsonl").exists()
    assert not (out_dir / "private-cases").exists()


def test_import_gbrain_records_unavailable_when_binary_missing(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("docs/second-brain/cases/public.md", "public")

    result = import_gbrain(
        repo_root=tmp_path,
        bundle_path=bundle,
        brain_name="talent-agent-local",
        gbrain_bin="/no/such/gbrain",
    )

    assert result["status"] == "gbrain_unavailable"
    events = load_jsonl(tmp_path / "data" / "second-brain" / "events.jsonl")
    assert events[-1]["event_type"] == "gbrain_unavailable"
