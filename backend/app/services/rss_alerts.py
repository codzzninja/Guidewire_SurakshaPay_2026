"""Real RSS feeds for social / government-style disruption signals (Phase 2)."""

import asyncio
import re
from typing import Any

import feedparser

from app.config import settings
from app.services.errors import IntegrationError


def _parse_feed_sync(url: str) -> feedparser.FeedParserDict:
    return feedparser.parse(url)


def _scan_items(feed: feedparser.FeedParserDict, limit: int = 40) -> list[str]:
    texts: list[str] = []
    for entry in feed.entries[:limit]:
        t = (getattr(entry, "title", "") or "") + " " + (getattr(entry, "summary", "") or "")
        texts.append(t)
    return texts


async def fetch_social_rss_signals() -> dict[str, Any]:
    """
    Fetch a public RSS feed and detect keywords for curfew / closures.
    Default feed: ReliefWeb India (real HTTP, real entries).
    """
    url = settings.government_rss_url.strip()
    if not url:
        if settings.allow_mocks:
            return {
                "curfew_social": False,
                "traffic_zone_closure": False,
                "source": "skipped",
                "matches": [],
            }
        raise IntegrationError(
            "Set GOVERNMENT_RSS_URL in .env for real social disruption signals.",
            "rss",
        )

    try:
        feed = await asyncio.to_thread(_parse_feed_sync, url)
    except Exception as e:
        raise IntegrationError(f"RSS fetch failed: {e}", "rss") from e

    if not feed.entries:
        return {
            "curfew_social": False,
            "traffic_zone_closure": False,
            "source": "rss",
            "feed_title": getattr(feed.feed, "title", "") or url,
            "matches": [],
            "note": "no_entries_in_feed",
        }

    texts = _scan_items(feed)
    blob = " ".join(texts).lower()

    curfew_kw = r"(curfew|section\s*144|lockdown|prohibitory|ban\s+orders)"
    closure_kw = r"(closure|bandh|strike|road\s+block|diversion|shutdown|suspension\s+of\s+traffic)"

    curfew = bool(re.search(curfew_kw, blob, re.I))
    closure = bool(re.search(closure_kw, blob, re.I))

    matches: list[str] = []
    if curfew:
        matches.append("curfew_pattern")
    if closure:
        matches.append("closure_pattern")

    return {
        "curfew_social": curfew,
        "traffic_zone_closure": closure,
        "source": "rss",
        "feed_title": getattr(feed.feed, "title", "") or url,
        "matches": matches,
    }
