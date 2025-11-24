import json
import sys
from pathlib import Path

import pytest


# Ensure local packages are importable without installation
REPO_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists()
)
sys.path.insert(0, str(REPO_ROOT / "libs" / "deepagents-cli"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "deepagents"))

from deepagents_cli import ecommerce_research


def _fake_search_response():
    return {
        "results": [
            {
                "title": "Product A",
                "url": "https://example.com/a",
                "content": "Affordable price and solid reviews",
                "score": 0.9,
            },
            {
                "title": "Product B",
                "url": "https://example.com/b",
                "content": "Premium option",
                "score": 0.8,
            },
        ]
    }


def test_run_ecommerce_research_creates_workspace_and_results(monkeypatch, tmp_path):
    def fake_search(query, max_results=5, topic="general", include_raw_content=False):  # noqa: ARG001
        return _fake_search_response()

    def fake_fetch(url, timeout=30):  # noqa: ARG001
        return {
            "url": url,
            "markdown_content": "# Sample Page\nPrice: $10\nRating: 4.5",
            "status_code": 200,
            "content_length": 32,
        }

    monkeypatch.setattr(ecommerce_research, "web_search", fake_search)
    monkeypatch.setattr(ecommerce_research, "fetch_url", fake_fetch)

    workspace = tmp_path / "workspace"
    ecommerce_research.run_ecommerce_research(
        ["Wireless Earbuds"], workspace, max_results=2, fetch_pages=True
    )

    assert (workspace / "context.md").exists()
    assert (workspace / "status.json").exists()
    assert (workspace / "summary.md").exists()

    result_file = workspace / "results_wireless-earbuds.md"
    assert result_file.exists()
    assert "Wireless Earbuds" in result_file.read_text()

    stored_page = workspace / "pages" / "wireless-earbuds" / "1.md"
    assert stored_page.exists()

    status = json.loads((workspace / "status.json").read_text())
    assert status["keywords"][0]["state"] == "done"


def test_run_ecommerce_research_respects_resume(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_search(query, max_results=5, topic="general", include_raw_content=False):  # noqa: ARG001
        calls.append(query)
        return _fake_search_response()

    monkeypatch.setattr(ecommerce_research, "web_search", fake_search)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "context.md").write_text("context")
    (workspace / "status.json").write_text(
        json.dumps({"keywords": [{"keyword": "wireless earbuds", "state": "done"}]})
    )

    ecommerce_research.run_ecommerce_research(
        ["wireless earbuds"], workspace, max_results=1, resume=True
    )

    # Should not trigger new searches when resuming completed keywords
    assert calls == []
    status = json.loads((workspace / "status.json").read_text())
    assert status["keywords"][0]["state"] == "done"
