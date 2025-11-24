---
name: ecommerce-research
description: Conduct end-to-end browsing-style research on product websites, including multi-keyword investigations and structured reporting.
---

# E-Commerce Browsing Research Skill

Use this skill whenever the user asks for structured research on product or marketplace sites (search results, listings, or product detail pages), especially when multiple keywords or seed URLs are involved. It operationalizes an OODA-style loop (Observe → Orient → Decide → Act) using the available tools (`web_search`, `fetch_url`, filesystem tools, and `task`).

## Scope and Guardrails

- Stay in **public pages** only: search results, category listings, product detail pages. Do **not** log in or attempt cart/checkout actions.
- Prioritize **read-only research**: extract product signals (title, price, rating, reviews, badges, seller) and navigation cues (pagination, filters).
- Respect rate limits: keep parallelism modest (≤3 concurrent tasks) and limit each keyword to 3–5 high-quality URLs.

## Workspace Setup (mandatory before browsing)

1. Create a dedicated folder for this run:
   ```bash
   mkdir ecommerce_research_[short_topic]
   ```
2. Save the run context to `ecommerce_research_[short_topic]/context.md` with:
   - Target marketplace or site family (e.g., Amazon, AliExpress, Etsy)
   - Goal (e.g., price benchmarking, feature comparison, finding top sellers)
   - Inputs: keywords, seed URLs, regions, language, output format
   - Limits: max pages per keyword, max run time, fields to capture
3. Maintain a progress tracker file `ecommerce_research_[short_topic]/status.json` describing queued/active/done keywords and any errors.

## Single-Keyword, End-to-End Flow

1. **Plan**
   - Normalize the keyword (trim, lowercase, no duplicates).
   - Decide page types to visit: search/list pages first, then 2–3 promising detail pages.
   - Define capture schema for this keyword in `schema_[keyword].md` (fields: title, price, currency, rating, review_count, seller, shipping, badges, URL, screenshot_url if available).
2. **Discover**
   - Use `web_search` to find the best entry URLs (site-specific query like `"[keyword]" site:amazon.com` if appropriate).
   - Record chosen entry links in `sources_[keyword].md`.
3. **Observe & Orient**
   - For each chosen URL, fetch the page with `fetch_url` and briefly summarize:
     - Page type guess: listing vs. detail vs. blocker (captcha / access denied)
     - Key elements: titles, prices, review snippets, pagination cues
     - Any blockers detected (captcha text, empty content)
4. **Decide & Act**
   - Listing pages: extract top items into a table and note pagination/filters. If more depth is needed, follow 1–2 detail links.
   - Detail pages: capture the schema fields plus notable attributes (variant hints, shipping terms, discounts).
5. **Persist**
   - Save normalized results to `ecommerce_research_[short_topic]/results_[keyword].md` with a summary plus a markdown table of extracted items.
   - Note blockers or missing data in the same file under "Gaps & Issues".
6. **Checkpoint**
   - Update `status.json` for the keyword to `"done"` (or `"failed"` with reason).

## Multi-Keyword Workflow

When multiple keywords are provided, treat them as a backlog and process them incrementally.

1. **Backlog setup**
   - Store the keyword list in `keywords.md` (one per line, already normalized).
   - Seed `status.json` with entries like `{ "keyword": "wireless earbuds", "state": "queued" }`.
2. **Execution loop**
   - Pick the next `queued` keyword, mark it `active`, and run the **Single-Keyword Flow** above.
   - To speed up processing, you may spawn up to 3 concurrent `task` subagents, each handling a distinct keyword. Ensure they write to separate `results_[keyword].md` files.
3. **Aggregation**
   - After processing all keywords, read every `results_[keyword].md` and produce `summary.md` containing:
     - Overall success rate and any recurring blockers
     - Cross-keyword comparisons (price bands, common sellers, standout features)
     - Top 5 products overall with a short rationale
4. **Recovery**
   - If interrupted, resume by inspecting `status.json` and continuing with any `queued` or `failed` keywords. Avoid reprocessing `done` entries unless the user explicitly requests it.

## Report Template (for each keyword)

```
# [Keyword] — E-commerce Research

## Quick Summary
- Primary intent: [buying guide / competitor scan / pricing]
- Pages visited: [listing URLs, detail URLs]
- Notable blockers: [captcha / region lock / none]

## Extracted Items (top entries)
| Title | Price | Currency | Rating | Reviews | Seller | URL |
|-------|-------|----------|--------|---------|--------|-----|
| ...   | ...   | ...      | ...    | ...     | ...    | ... |

## Notes
- Pagination cues / filters used
- Shipping or delivery caveats
- Discount badges or coupons observed

## Gaps & Issues
- Missing fields, suspected anti-bot measures, or malformed pages
```

## Best Practices

- **Be selective**: prefer high-signal URLs from reputable domains; skip low-quality mirrors.
- **Detect blockers early**: if `fetch_url` returns empty/denied content, record it and move on rather than looping.
- **Token discipline**: keep summaries concise; store verbose extracts in the per-keyword result files, not in chat.
- **Repeatable outputs**: always write to the folder and update `status.json` so the run can be resumed or audited.

