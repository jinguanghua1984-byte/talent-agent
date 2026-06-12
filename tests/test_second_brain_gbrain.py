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
