"""Utilities for running structured, multi-keyword e-commerce research.

The helpers in this module provide a lightweight, scriptable alternative to the
interactive agent flow. They create a repeatable workspace on disk, track
progress per keyword, and harvest search/fetch outputs into resumable markdown
artifacts. This mirrors the workflow described in the `ecommerce-research`
skill: backlog management, per-keyword result files, and an aggregated summary.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from deepagents_cli.config import COLORS, console
from deepagents_cli.tools import fetch_url, web_search


def _slugify_keyword(keyword: str) -> str:
    """Create a filesystem-friendly slug for a keyword."""

    keyword = keyword.lower().strip()
    keyword = re.sub(r"\s+", "-", keyword)
    keyword = re.sub(r"[^a-z0-9\-_]+", "", keyword)
    return keyword or "keyword"


def _normalize_keyword(keyword: str) -> str:
    """Normalize keyword text for consistent deduping and filenames."""

    return " ".join(keyword.strip().split()).lower()


def _ensure_workspace(workspace: Path) -> None:
    """Create the workspace directory and seed context/status files if missing."""

    workspace.mkdir(parents=True, exist_ok=True)

    context_path = workspace / "context.md"
    if not context_path.exists():
        timestamp = datetime.utcnow().isoformat()
        context_path.write_text(
            "\n".join(
                [
                    f"# E-commerce Research Run ({timestamp} UTC)",
                    "",  # blank
                    "## Goal",
                    "- Describe the marketplace focus and research intent.",
                    "",  # blank
                    "## Inputs",
                    "- Keywords / seed URLs / region / language",
                    "- Desired output fields (title, price, rating, seller, etc.)",
                    "",  # blank
                    "## Limits",
                    "- Max pages per keyword",
                    "- Runtime budget",
                    "",  # blank
                    "## Notes",
                    "- Add any site-specific cues or pagination hints here.",
                ]
            )
        )

    status_path = workspace / "status.json"
    if not status_path.exists():
        status_path.write_text(json.dumps({"keywords": []}, indent=2))


def _load_status(workspace: Path) -> list[dict]:
    status_path = workspace / "status.json"
    if not status_path.exists():
        return []
    try:
        data = json.loads(status_path.read_text())
        return data.get("keywords", [])
    except json.JSONDecodeError:
        return []


def _write_status(workspace: Path, entries: list[dict]) -> None:
    status_path = workspace / "status.json"
    status_path.write_text(json.dumps({"keywords": entries}, indent=2))


def _render_results_table(results: list[dict]) -> str:
    if not results:
        return "(no results captured)"

    header = "| Title | URL | Score | Excerpt |\n|------|-----|-------|---------|"
    rows = []
    for result in results:
        title = result.get("title") or "(untitled)"
        url = result.get("url") or ""
        score = result.get("score", "")
        excerpt = result.get("content") or result.get("markdown_excerpt") or ""
        rows.append(f"| {title} | {url} | {score} | {excerpt} |")
    return "\n".join([header, *rows])


def _write_result_file(
    workspace: Path,
    keyword: str,
    search_results: list[dict],
    blockers: list[str],
    pages_visited: list[str],
) -> Path:
    slug = _slugify_keyword(keyword)
    result_path = workspace / f"results_{slug}.md"

    lines: List[str] = [
        f"# {keyword.title()} — E-commerce Research",
        "",
        "## Quick Summary",
        f"- Pages visited: {', '.join(pages_visited) if pages_visited else 'none'}",
        f"- Notable blockers: {', '.join(blockers) if blockers else 'none'}",
        "",
        "## Search Results",
        _render_results_table(search_results),
        "",
        "## Gaps & Issues",
        "- " + ("; ".join(blockers) if blockers else "None noted"),
    ]

    result_path.write_text("\n".join(lines))
    return result_path


def _update_summary(workspace: Path, entries: list[dict]) -> None:
    summary_path = workspace / "summary.md"
    header = "| Keyword | State | Notes |\n|---------|-------|-------|"
    rows = []
    for entry in entries:
        keyword = entry.get("keyword", "(unknown)")
        state = entry.get("state", "queued")
        error = entry.get("error") or ""
        rows.append(f"| {keyword} | {state} | {error} |")

    summary_lines = [
        "# Multi-keyword Run Summary",
        "",
        "## Progress",
        header,
        *rows,
    ]
    summary_path.write_text("\n".join(summary_lines))


def _unique_keywords(keywords: Iterable[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for kw in keywords:
        normalized = _normalize_keyword(kw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _fetch_pages(workspace: Path, keyword: str, results: list[dict]) -> list[str]:
    pages_dir = workspace / "pages" / _slugify_keyword(keyword)
    pages_dir.mkdir(parents=True, exist_ok=True)

    stored_pages: list[str] = []
    for idx, result in enumerate(results, start=1):
        url = result.get("url")
        if not url:
            continue
        response = fetch_url(url)
        if "markdown_content" not in response:
            continue
        page_path = pages_dir / f"{idx}.md"
        page_path.write_text(response["markdown_content"])
        stored_pages.append(str(page_path))
    return stored_pages


def _prepare_entries_for_keywords(keywords: list[str], existing: list[dict]) -> list[dict]:
    existing_map = {entry.get("keyword"): entry for entry in existing}
    merged: list[dict] = []
    for keyword in keywords:
        merged.append(
            existing_map.get(
                keyword,
                {"keyword": keyword, "state": "queued", "error": None},
            )
        )
    return merged


def run_ecommerce_research(
    keywords: Iterable[str],
    workspace: Path,
    *,
    max_results: int = 5,
    fetch_pages: bool = False,
    site: str | None = None,
    resume: bool = False,
) -> Path:
    """Run multi-keyword research and persist artifacts to a workspace.

    Returns:
        Path to the workspace directory.
    """

    keyword_list = _unique_keywords(keywords)
    if not keyword_list:
        raise ValueError("At least one keyword is required")

    _ensure_workspace(workspace)

    existing_entries = _load_status(workspace)
    entries = _prepare_entries_for_keywords(keyword_list, existing_entries)
    _write_status(workspace, entries)

    for entry in entries:
        keyword = entry["keyword"]
        if entry.get("state") == "done" and resume:
            console.print(
                f"[green]✓[/green] Skipping '{keyword}' (already done, resume enabled)",
                style=COLORS["dim"],
            )
            continue

        entry["state"] = "active"
        entry["error"] = None
        _write_status(workspace, entries)

        query = f"{keyword} site:{site}" if site else keyword
        search_response = web_search(query, max_results=max_results)

        blockers: list[str] = []
        search_results = search_response.get("results") or []
        if search_response.get("error"):
            blockers.append(str(search_response["error"]))
        pages_visited = [res.get("url", "") for res in search_results if res.get("url")]

        if fetch_pages and search_results:
            stored_paths = _fetch_pages(workspace, keyword, search_results)
            if stored_paths:
                blockers.append(f"Stored {len(stored_paths)} fetched pages for review")

        _write_result_file(workspace, keyword, search_results, blockers, pages_visited)

        entry["state"] = "done"
        _write_status(workspace, entries)

    _update_summary(workspace, entries)
    return workspace


def run_cli_ecommerce_research(
    keywords: Iterable[str],
    workspace: Path,
    *,
    max_results: int = 5,
    fetch_pages: bool = False,
    site: str | None = None,
    resume: bool = False,
) -> None:
    """Wrapper for CLI to run research with friendly console output."""

    normalized = _unique_keywords(keywords)
    console.print(
        f"[bold]{len(normalized)} keyword(s) provided. Initializing workspace...[/bold]",
        style=COLORS["primary"],
    )
    workspace = run_ecommerce_research(
        normalized,
        workspace,
        max_results=max_results,
        fetch_pages=fetch_pages,
        site=site,
        resume=resume,
    )
    console.print(f"[green]✓[/green] Workspace ready at {workspace}")
    console.print(
        f"[dim]Status file:[/dim] {workspace / 'status.json'}\n"
        f"[dim]Summary file:[/dim] {workspace / 'summary.md'}",
        style=COLORS["dim"],
    )

