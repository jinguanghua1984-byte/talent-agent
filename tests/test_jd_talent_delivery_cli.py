import json
from pathlib import Path

import pytest

from scripts import jd_talent_delivery


def test_slugify_keeps_chinese_word_chars_dots_and_hyphens() -> None:
    assert jd_talent_delivery.slugify("LLM 推理/工程师.v2-候选_pool") == "LLM-推理-工程师.v2-候选_pool"
    assert jd_talent_delivery.slugify(" !@# ") == "jd"


def test_prepare_creates_output_tree_and_jd_copy(tmp_path: Path) -> None:
    jd = tmp_path / "LLM推理工程师.md"
    jd.write_text("# LLM推理工程师\n\n负责 vLLM 和 KV Cache。\n", encoding="utf-8")
    out_root = tmp_path / "output"

    result = jd_talent_delivery.prepare_workspace(
        jd_path=jd,
        output_base=out_root,
        date_text="2026-05-23",
        top_n=30,
    )

    output_dir = Path(result["output_dir"])
    assert output_dir.name.endswith("2026-05-23")
    assert (output_dir / "source" / "jd.md").read_text(encoding="utf-8-sig").startswith("# LLM推理工程师")
    assert (output_dir / "profile").exists()
    assert (output_dir / "scoring").exists()
    assert (output_dir / "reports").exists()
    assert (output_dir / "feishu").exists()
    manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["schema"] == "jd_talent_delivery_run_manifest_v1"
    assert manifest["top_n"] == 30
    assert manifest["source_jd_path"] == str(jd)
    assert manifest["output_dir"] == str(output_dir)
    assert manifest["date"] == "2026-05-23"


def test_prepare_missing_jd_path_raises_file_not_found(tmp_path: Path) -> None:
    missing_jd = tmp_path / "missing.md"

    with pytest.raises(FileNotFoundError):
        jd_talent_delivery.prepare_workspace(
            jd_path=missing_jd,
            output_base=tmp_path / "output",
            date_text="2026-05-23",
            top_n=30,
        )


def test_prepare_repeated_same_day_runs_create_independent_output_dirs(tmp_path: Path) -> None:
    jd = tmp_path / "LLM推理工程师.md"
    jd.write_text("# LLM推理工程师\n\n负责 vLLM 和 KV Cache。\n", encoding="utf-8")
    out_root = tmp_path / "output"

    first = jd_talent_delivery.prepare_workspace(
        jd_path=jd,
        output_base=out_root,
        date_text="2026-05-23",
        top_n=30,
    )
    second = jd_talent_delivery.prepare_workspace(
        jd_path=jd,
        output_base=out_root,
        date_text="2026-05-23",
        top_n=30,
    )

    first_dir = Path(first["output_dir"])
    second_dir = Path(second["output_dir"])
    assert second_dir != first_dir
    assert second_dir.name.startswith("LLM推理工程师-2026-05-23-run-")
    assert (first_dir / "source" / "jd.md").exists()
    assert (second_dir / "source" / "jd.md").exists()


def test_prepare_cli_prints_manifest_json(tmp_path: Path, capsys) -> None:
    jd = tmp_path / "算法 平台.md"
    jd.write_text("# 算法平台\n", encoding="utf-8")
    out_root = tmp_path / "output"

    exit_code = jd_talent_delivery.main(
        [
            "prepare",
            "--jd-path",
            str(jd),
            "--output-base",
            str(out_root),
            "--date",
            "2026-05-23",
            "--top-n",
            "7",
        ]
    )

    assert exit_code == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["top_n"] == 7
    assert Path(manifest["output_dir"]).name == "算法-平台-2026-05-23"


def test_prepare_cli_uses_default_output_base_and_top_n(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    jd = tmp_path / "默认JD.md"
    jd.write_text("# 默认JD\n", encoding="utf-8")

    exit_code = jd_talent_delivery.main(["prepare", "--jd-path", str(jd)])

    assert exit_code == 0
    manifest = json.loads(capsys.readouterr().out)
    output_dir = Path(manifest["output_dir"])
    assert output_dir.parts[0:2] == ("data", "output")
    assert (tmp_path / output_dir / "source" / "jd.md").exists()
    assert manifest["top_n"] == 30
