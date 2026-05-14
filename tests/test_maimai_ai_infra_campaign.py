from pathlib import Path

from scripts.maimai_ai_infra_campaign import CampaignPaths, ensure_campaign


def test_campaign_paths_create_expected_layout(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"
    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")

    assert paths.root == root
    assert paths.db == root / "talent.db"
    assert paths.raw_search_dir == root / "raw" / "search"
    assert paths.contacts_dir == root / "raw" / "contacts"
    assert paths.state_dir == root / "state"
    assert paths.reports_dir == root / "reports"
    assert paths.review_dir == root / "review"
    assert paths.manifest.exists()


def test_gitignore_excludes_campaign_runtime_data():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/campaigns/" in text
