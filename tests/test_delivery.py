import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from offscroll.delivery import export_site, public_lanes, render_page, safe_link
from offscroll.ranking import DigestError
from offscroll.web import app, database


@pytest.fixture
def lanes():
    return {
        "hackernews": [
            {
                "lane_rank": 1,
                "title": "<script>bad()</script>",
                "url": "javascript:alert(1)",
                "discussion_url": "https://news.ycombinator.com/item?id=1",
                "domain": "example.org",
                "why_here": "A source story.",
                "summary": "PRIVATE GEMINI OUTPUT",
                "summary_label": "AI-generated summary",
                "also_covered_by": [
                    {
                        "source": "wikipedia",
                        "title": "Context",
                        "url": "https://en.wikipedia.org/wiki/Test",
                    }
                ],
            }
        ],
        "wikipedia": [],
        "youtube": [
            {
                "lane_rank": 1,
                "video_id": "AAAAAAAAAAA",
                "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                "title": "API TITLE",
                "views": 999,
                "thumbnails": {"default": "https://i.ytimg.com/example.jpg"},
                "category": "science",
                "final_score": 5,
            }
        ],
    }


def test_public_projection_excludes_expiring_and_region_restricted_data(lanes):
    projected = public_lanes(lanes)
    assert set(projected["youtube"][0]) == {"lane_rank", "video_id", "url"}
    serialized = json.dumps(projected)
    assert all(
        value not in serialized
        for value in ("API TITLE", "PRIVATE GEMINI", "thumbnails", "final_score")
    )
    assert projected["hackernews"][0]["url"] is None
    assert projected["hackernews"][0]["summary_label"] == "Source context"


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,bad", "https://user:pass@example.org", None]
)
def test_dangerous_links_are_rejected(url):
    assert safe_link(url) is None


def test_page_escapes_source_text_has_finite_sections_and_no_trackers(lanes):
    html = render_page(public_lanes(lanes), date="16 November 2026")
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "javascript:" not in html and "i.ytimg.com" not in html
    assert "PRIVATE GEMINI" not in html and "API TITLE" not in html
    assert (
        "That&#39;s everything for this week" in html or "That's everything for this week" in html
    )
    assert "Skip to the digest" in html and "youtube-heading" in html
    assert "<iframe" not in html and "autoplay" not in html.split("<footer>")[0]
    assert "Content-Security-Policy" in html


def test_export_writes_public_html_json_and_local_assets(monkeypatch, tmp_path, lanes):
    monkeypatch.setattr("offscroll.delivery.read_digest", lambda _: lanes)
    output = tmp_path / "site"
    page = export_site(Mock(), output)
    assert page.exists()
    assert json.loads((output / "digest.json").read_text())["lanes"] == public_lanes(lanes)
    assert (output / "youtube-logo.png").exists() and (output / ".nojekyll").exists()
    export_site(Mock(), output)  # Rebuilding the same directory is supported.
    (output / "unrelated.txt").write_text("keep")
    with pytest.raises(DigestError):
        export_site(Mock(), output)
    assert (output / "unrelated.txt").read_text() == "keep"
    symlink = tmp_path / "link"
    symlink.symlink_to(output, target_is_directory=True)
    with pytest.raises(DigestError):
        export_site(Mock(), symlink)


def test_read_only_http_routes_and_safe_errors(monkeypatch, lanes):
    engine = Mock()
    app.dependency_overrides[database] = lambda: engine
    reader = Mock(return_value=lanes)
    monkeypatch.setattr("offscroll.web.read_digest", reader)
    try:
        with TestClient(app) as client:
            page = client.get("/")
            assert page.status_code == 200 and "set-cookie" not in page.headers
            assert "PRIVATE GEMINI" not in page.text
            assert client.get("/static/style.css").status_code == 200
            assert client.get("/api/digests/latest").json() == public_lanes(lanes)
            assert client.get("/api/digests/2026-W46").status_code == 200
            reader.assert_called_with(engine, week="2026-W46", purge=False)
            assert client.post("/api/digests/latest").status_code == 405
            reader.side_effect = DigestError("No digest")
            assert client.get("/").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_health_checks_database(monkeypatch):
    engine = Mock()
    connection = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=connection)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    app.dependency_overrides[database] = lambda: engine
    try:
        with TestClient(app) as client:
            assert client.get("/healthz").json() == {"status": "ok"}
            connection.execute.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_web_database_failure_is_generic_and_does_not_expose_details(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    def unavailable():
        raise SQLAlchemyError("PRIVATE DATABASE DIAGNOSTIC")

    monkeypatch.setattr("offscroll.web.load_settings", unavailable)
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable."}
        assert "PRIVATE" not in response.text


def test_brand_asset_is_the_unmodified_official_full_logo(lanes):
    import hashlib

    from offscroll.delivery import PACKAGE

    logo = PACKAGE / "static" / "youtube-logo.png"
    assert hashlib.sha256(logo.read_bytes()).hexdigest() == (
        "9d9674fdc18083dad15563ef34773ec5337db21aa4ce75c45977a894784d728f"
    )
    html = render_page(public_lanes(lanes), date="16 November 2026")
    assert 'src="youtube-logo.png" alt="YouTube" height="48"' in html
