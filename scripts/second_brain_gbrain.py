"""gbrain import/export/rebuild adapter for second-brain artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import shutil
import subprocess
import zipfile

from scripts.second_brain_models import SourceRef, append_event, build_event


def _artifact_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "docs" / "second-brain" / "cases",
        repo_root / "data" / "second-brain" / "private-cases",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(path for path in root.glob("*.md") if path.is_file()))
    return files


def export_bundle(*, repo_root: str | Path, out_path: str | Path) -> Path:
    repo = Path(repo_root)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _artifact_files(repo):
            archive.write(path, path.relative_to(repo))
    return target


def _unavailable_event(
    repo: Path,
    bundle_path: Path,
    brain_name: str,
    reason: str,
) -> dict[str, Any]:
    event = build_event(
        event_type="gbrain_unavailable",
        run_id="second-brain-import",
        client_id="global",
        jd_family="global",
        visibility="private",
        source_refs=[
            SourceRef(
                source_path=str(bundle_path),
                source_type="second_brain_bundle",
                artifact_key=brain_name,
            )
        ],
        payload={"reason": reason},
    )
    append_event(repo / "data" / "second-brain" / "events.jsonl", event)
    return event


def import_gbrain(
    *,
    repo_root: str | Path,
    bundle_path: str | Path,
    brain_name: str,
    gbrain_bin: str = "gbrain",
) -> dict[str, Any]:
    repo = Path(repo_root)
    bundle = Path(bundle_path)
    resolved = shutil.which(gbrain_bin) if "/" not in gbrain_bin else gbrain_bin
    if not resolved or not Path(resolved).exists():
        _unavailable_event(repo, bundle, brain_name, "gbrain binary not found")
        return {"status": "gbrain_unavailable", "reason": "gbrain binary not found"}
    command = [resolved, "import", str(bundle), "--brain", brain_name]
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        reason = completed.stderr.strip() or "gbrain import failed"
        _unavailable_event(repo, bundle, brain_name, reason)
        return {"status": "gbrain_unavailable", "reason": reason}
    return {"status": "imported", "stdout": completed.stdout}
