"""Unpaid public-feed scrapers for Discovery (no paid Trends/TikTok APIs)."""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

FetchFn = Callable[[str, float], bytes]

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
USER_AGENT = "HermesOS/1.0 (+https://hermestudios.com; unpaid discovery RSS)"

# Public Atom feeds — no API keys. TikTok has no unpaid official feed; News RSS
# tagged TikTok is the documented substitute.
YOUTUBE_FEEDS = (
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCbfYPyITQ-7l4upoX8nvctg",  # Two Minute Papers
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCZHmQk67mSJgfCCTn7xBfew",  # Fireship
)
REDDIT_URL = "https://www.reddit.com/r/MachineLearning/hot.json?limit=8"
NEWS_TIKTOK_URL = (
    "https://news.google.com/rss/search?q=TikTok+Shorts+AI&hl=en-US&gl=US&ceid=US:en"
)
NEWS_TRENDS_URL = (
    "https://news.google.com/rss/search?q=YouTube+Shorts+AI+agents&hl=en-US&gl=US&ceid=US:en"
)


def scrape_timeout() -> float:
    raw = (os.environ.get("HERMES_SCRAPE_TIMEOUT") or "2.0").strip()
    try:
        return max(0.2, min(float(raw), 8.0))
    except ValueError:
        return 2.0


def _default_fetch(url: str, timeout: float) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/json, */*"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — operator-chosen public RSS hosts
        return resp.read(400_000)


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return " ".join(el.text.split())


def parse_rss_or_atom(payload: bytes) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []
    items: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = _text(entry.find("atom:title", ATOM_NS))
        link_el = entry.find("atom:link", ATOM_NS)
        href = (link_el.get("href") if link_el is not None else "") or ""
        published_el = entry.find("atom:published", ATOM_NS)
        if published_el is None:
            published_el = entry.find("atom:updated", ATOM_NS)
        published = _text(published_el)
        if title:
            items.append({"title": title, "url": href, "published": published})
    for item in root.findall(".//item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        published_el = item.find("pubDate")
        if published_el is None:
            published_el = item.find("published")
        published = _text(published_el)
        if title:
            items.append({"title": title, "url": link, "published": published})
    return items[:12]


def parse_reddit(payload: bytes) -> list[dict[str, str]]:
    import json

    try:
        body = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    children = ((body.get("data") or {}).get("children")) or []
    items: list[dict[str, str]] = []
    for child in children:
        data = child.get("data") or {}
        title = str(data.get("title") or "").strip()
        if not title:
            continue
        permalink = str(data.get("permalink") or "")
        url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else str(data.get("url") or "")
        items.append(
            {
                "title": title,
                "url": url,
                "published": str(data.get("created_utc") or ""),
                "ups": str(data.get("ups") or "0"),
            }
        )
    return items[:12]


def _score(title: str, *, ups: int = 0) -> int:
    blob = title.lower()
    bump = 50
    for token, pts in (("ai", 18), ("agent", 12), ("llm", 10), ("short", 8), ("tiktok", 6), ("youtube", 6)):
        if token in blob:
            bump += pts
    bump += min(20, ups // 50)
    return max(40, min(99, bump))


def _stable_id(source: str, title: str) -> str:
    digest = hashlib.sha256(f"{source}:{title}".encode("utf-8")).hexdigest()[:16]
    return f"scan-{source.lower()}-{digest}"


def _ingest_feed(
    *,
    source: str,
    url: str,
    kind: str,
    fetch: FetchFn,
    timeout: float,
) -> dict[str, Any]:
    try:
        raw = fetch(url, timeout)
        parsed = parse_reddit(raw) if kind == "reddit" else parse_rss_or_atom(raw)
        rows = []
        for index, item in enumerate(parsed):
            title = item["title"]
            ups = int(item.get("ups") or 0) if str(item.get("ups") or "").isdigit() else 0
            rows.append(
                {
                    "id": _stable_id(source, title),
                    "title": title[:180],
                    "score": _score(title, ups=ups),
                    "source": source,
                    "rank": index + 1,
                    "payload": {"url": item.get("url"), "published": item.get("published"), "feed": url},
                }
            )
        return {"source": source, "ok": True, "count": len(rows), "items": rows, "url": url}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "source": source,
            "ok": False,
            "count": 0,
            "items": [],
            "url": url,
            "error": exc.__class__.__name__,
        }


def scan_public_feeds(*, fetch: FetchFn | None = None, query: str | None = None) -> dict[str, Any]:
    """Pull YouTube Atom, Reddit JSON, and News RSS (TikTok/Trends stand-ins)."""
    getter = fetch or _default_fetch
    timeout = scrape_timeout()
    q = (query or "").strip()
    youtube_urls = list(YOUTUBE_FEEDS)
    if q:
        youtube_urls = [f"https://www.youtube.com/feeds/videos.xml?search_query={quote_plus(q)}"]
    feeds: list[dict[str, Any]] = []
    for url in youtube_urls[:2]:
        feeds.append(_ingest_feed(source="YouTube", url=url, kind="atom", fetch=getter, timeout=timeout))
    reddit_url = REDDIT_URL
    if q:
        reddit_url = f"https://www.reddit.com/search.json?q={quote_plus(q)}&limit=8&sort=hot"
    feeds.append(_ingest_feed(source="Reddit", url=reddit_url, kind="reddit", fetch=getter, timeout=timeout))
    tiktok_url = NEWS_TIKTOK_URL
    if q:
        tiktok_url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(f"TikTok {q}")
            + "&hl=en-US&gl=US&ceid=US:en"
        )
    feeds.append(_ingest_feed(source="TikTok", url=tiktok_url, kind="rss", fetch=getter, timeout=timeout))
    feeds.append(_ingest_feed(source="News", url=NEWS_TRENDS_URL, kind="rss", fetch=getter, timeout=timeout))
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for feed in feeds:
        for row in feed.get("items") or []:
            key = str(row.get("id"))
            if key in seen:
                continue
            seen.add(key)
            items.append(row)
    items.sort(key=lambda r: int(r.get("score") or 0), reverse=True)
    for index, row in enumerate(items):
        row["rank"] = index + 1
    live = sum(1 for f in feeds if f.get("ok"))
    return {
        "ok": live > 0,
        "mode": "live" if live else "dry_run",
        "paid": False,
        "note": "YouTube Atom + Reddit JSON + Google News RSS. No TikTok official API (unpaid).",
        "feeds": [{k: v for k, v in f.items() if k != "items"} for f in feeds],
        "items": items[:24],
        "count": min(len(items), 24),
        "live_feeds": live,
    }
