from scripts.public_search import token_tracker


def test_token_tracker_exposes_main():
    assert callable(token_tracker.main)
