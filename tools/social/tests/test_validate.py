import pytest

from tools.social.validate import (
    validate_linkedin_post,
    validate_reddit_post,
    validate_x_post,
    require_pending_draft,
)


def test_x_rejects_empty():
    with pytest.raises(RuntimeError, match="text is required"):
        validate_x_post({"text": "  "})


def test_x_rejects_overlong():
    with pytest.raises(RuntimeError, match="280"):
        validate_x_post({"text": "x" * 281})


def test_x_accepts_valid():
    assert validate_x_post({"text": "Hello X"}) == {"text": "Hello X"}


def test_x_rejects_media():
    with pytest.raises(RuntimeError, match="not supported"):
        validate_x_post({"text": "hi", "media_ids": ["1"]})


def test_reddit_normalizes_subreddit():
    out = validate_reddit_post(
        {"subreddit": "r/python", "title": "Hello", "text": "Body here"}
    )
    assert out["subreddit"] == "python"


def test_reddit_requires_fields():
    with pytest.raises(RuntimeError, match="title"):
        validate_reddit_post({"subreddit": "python", "text": "body"})


def test_reddit_rejects_link_post():
    with pytest.raises(RuntimeError, match="not supported"):
        validate_reddit_post(
            {"subreddit": "python", "title": "t", "text": "b", "url": "https://example.com"}
        )


def test_linkedin_rejects_org():
    with pytest.raises(RuntimeError, match="company page"):
        validate_linkedin_post(
            {"text": "hi", "author_urn": "urn:li:organization:123"}
        )


def test_linkedin_max_length():
    with pytest.raises(RuntimeError, match="3000"):
        validate_linkedin_post({"text": "a" * 3001})


def test_require_pending_draft():
    with pytest.raises(RuntimeError, match="No pending"):
        require_pending_draft(None, "X")
    assert require_pending_draft({"text": "ok"}, "X")["text"] == "ok"
