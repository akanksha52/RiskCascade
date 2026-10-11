
"""Multi-source news ingestion with explicit evidence-quality labels."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re

from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qs


import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

FEEDS = {
    "Financial News": (
        "https://news.google.com/rss/search?"
        "q=financial+markets+corporate+risk+when:7d"
        "&hl=en-US&gl=US&ceid=US:en"
    ),
    "Supply Chain and Cyber Risk": (
        "https://news.google.com/rss/search?"
        "q=company+supply+chain+disruption+OR+cyberattack+when:7d"
        "&hl=en-US&gl=US&ceid=US:en"
    ),
    "SEC Current 8-K Filings": (
        "https://www.sec.gov/cgi-bin/browse-edgar?"
        "action=getcurrent&type=8-K&company=&dateb=&owner=include"
        "&count=40&output=atom"
    ),
}

HEADERS = {
    "User-Agent": "RiskCascadePrototype/0.2 research contact: YOUR_EMAIL@example.com"
}
TIMEOUT_SECONDS = 15
MIN_FULL_TEXT_CHARS = 500
MIN_SUMMARY_CHARS = 80


def clean_html(value):
    if not value:
        return ""
    soup = BeautifulSoup(unescape(value), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _published_at(entry):
    value = entry.get("published") or entry.get("updated")
    if value:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            pass

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        from calendar import timegm
        from datetime import datetime as dt_datetime
        try:
            return dt_datetime.fromtimestamp(
                timegm(parsed), timezone.utc
            ).isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    return None


def _normalize_url(url):
    if not url:
        return ""
    parts = urlsplit(url.strip())
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/") or "/",
        parts.query,
        "",
    ))


def resolve_article_url(url):
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT_SECONDS,
            allow_redirects=True, stream=True,
        )
        resolved = response.url
        response.close()
        if resolved and "news.google.com" not in urlsplit(resolved).netloc:
            return resolved
    except requests.RequestException:
        pass
    return url


def extract_article(url):
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            return {
                "article_text": "",
                "content_status": "unsupported_content_type",
                "extraction_error": f"Unsupported content type: {content_type}",
            }

        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        ) or ""
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) >= MIN_FULL_TEXT_CHARS:
            return {
                "article_text": text,
                "content_status": "full_text",
                "extraction_error": None,
            }

        return {
            "article_text": "",
            "content_status": "summary_only",
            "extraction_error": "Full article text unavailable or too short",
        }

    except requests.RequestException as exc:
        return {
            "article_text": "",
            "content_status": "fetch_failed",
            "extraction_error": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "article_text": "",
            "content_status": "extraction_failed",
            "extraction_error": f"{type(exc).__name__}: {exc}",
        }



def _extract_sec_document(url):
    """Fetch one SEC HTML document and return readable text."""
    response = requests.get(
        url, headers=HEADERS, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()

    text = "\n".join(
        line.strip()
        for line in soup.get_text("\n").splitlines()
        if line.strip()
    )
    return re.sub(r"\s+", " ", text).strip()


def extract_sec_filing(index_url):
    """
    Extract an SEC filing's primary HTML document and meaningful exhibits.
    Returns full text only when substantive document text is available.
    """
    try:
        response = requests.get(
            index_url, headers=HEADERS, timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        candidates = []

        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href:
                continue

            # SEC inline-XBRL viewer links use ?doc=/Archives/...
            query = parse_qs(urlsplit(href).query)
            document_path = query.get("doc", [None])[0]
            if document_path:
                href = document_path

            absolute_url = urljoin(index_url, href)
            path = urlsplit(absolute_url).path.lower()

            if not path.endswith((".htm", ".html")):
                continue
            if "-index.htm" in path or path.endswith("index.html"):
                continue
            if "/ix?" in absolute_url.lower():
                continue

            row = link.find_parent("tr")
            row_text = (
                row.get_text(" ", strip=True) if row else link.get_text(" ", strip=True)
            )
            filename = path.rsplit("/", 1)[-1]

            if not any(
                item["url"] == absolute_url for item in candidates
            ):
                candidates.append({
                    "url": absolute_url,
                    "filename": filename,
                    "row_text": row_text,
                })

        if not candidates:
            return {
                "article_text": "",
                "content_status": "extraction_failed",
                "extraction_error": "No HTML filing documents found on SEC index",
            }

        # Prefer the document explicitly identified as the 8-K.
        primary = next(
            (
                item for item in candidates
                if re.search(r"\b8-K\b", item["row_text"], re.I)
                and not re.search(r"EX-?99|EXHIBIT", item["row_text"], re.I)
            ),
            candidates[0],
        )

        primary_text = _extract_sec_document(primary["url"])

        if len(primary_text) < MIN_FULL_TEXT_CHARS:
            return {
                "article_text": "",
                "content_status": "extraction_failed",
                "extraction_error": (
                    f"Primary filing text too short ({len(primary_text)} characters)"
                ),
            }

        sections = [
            f"[Primary filing: {primary['filename']}]\n{primary_text}"
        ]
        used_urls = {primary["url"]}
        exhibit_count = 0

        # Add up to two substantive exhibits when available.
        for item in candidates:
            if item["url"] in used_urls:
                continue

            is_exhibit = (
                re.search(r"EX-?99|EXHIBIT", item["row_text"], re.I)
                or re.search(r"ex99|exhibit", item["filename"], re.I)
            )
            if not is_exhibit:
                continue

            try:
                exhibit_text = _extract_sec_document(item["url"])
            except requests.RequestException:
                continue

            # Skip index-like stubs and placeholder documents.
            if len(exhibit_text) < MIN_FULL_TEXT_CHARS:
                continue

            sections.append(
                f"[Exhibit: {item['filename']}]\n{exhibit_text}"
            )
            used_urls.add(item["url"])
            exhibit_count += 1

            if exhibit_count >= 2:
                break

        return {
            "article_text": "\n\n".join(sections),
            "content_status": "full_text",
            "extraction_error": None,
        }

    except requests.RequestException as exc:
        return {
            "article_text": "",
            "content_status": "fetch_failed",
            "extraction_error": f"{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "article_text": "",
            "content_status": "extraction_failed",
            "extraction_error": f"{type(exc).__name__}: {exc}",
        }



def _source_name(entry, fallback):
    source = entry.get("source")
    if isinstance(source, dict):
        return source.get("title") or fallback
    return fallback



def fetch_news(max_per_feed=20, fetch_full_text=False):
    """Fetch feeds and return normalized articles with evidence metadata."""
    articles = []
    errors = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for feed_name, feed_url in FEEDS.items():
        try:
            parsed = feedparser.parse(
                feed_url, request_headers=HEADERS
            )

            if parsed.bozo and not parsed.entries:
                errors.append(
                    f"{feed_name}: {parsed.bozo_exception}"
                )
                continue

            if not parsed.entries:
                errors.append(f"{feed_name}: no entries returned")
                continue

            for entry in parsed.entries[:max_per_feed]:
                link = entry.get("link", "").strip()
                title = clean_html(entry.get("title", ""))

                if not link or not title:
                    continue

                summary = clean_html(
                    entry.get("summary", "")
                    or entry.get("description", "")
                )

                # Initialize all values before optional extraction.
                article_text = ""
                extraction_error = None
                publisher_url = link
                content_status = "not_requested"

                if fetch_full_text:
                    if "SEC" in feed_name:
                        # SEC feed links point to filing index pages.
                        extracted = extract_sec_filing(link)
                    else:
                        publisher_url = resolve_article_url(link)
                        extracted = extract_article(publisher_url)

                    article_text = (
                        extracted.get("article_text") or ""
                    ).strip()
                    content_status = extracted.get(
                        "content_status", "extraction_failed"
                    )
                    extraction_error = extracted.get(
                        "extraction_error"
                    )

                # Classify the best text actually available.
                if len(article_text) >= MIN_FULL_TEXT_CHARS:
                    evidence_quality = "full_text"
                    body = article_text

                elif len(summary) >= MIN_SUMMARY_CHARS:
                    evidence_quality = "summary_only"
                    body = summary

                else:
                    evidence_quality = "headline_only"
                    body = ""

                # Avoid repeating the title if it already starts the body.
                if body and body.casefold().startswith(title.casefold()):
                    text = body
                elif body:
                    text = f"{title}\n\n{body}"
                else:
                    text = title

                # If retrieval was attempted but no full text was obtained,
                # preserve the extractor's retrieval status.
                if (
                    fetch_full_text
                    and evidence_quality != "full_text"
                    and content_status == "full_text"
                ):
                    content_status = "summary_only"

                articles.append({
                    "article_id": entry.get("id") or link,
                    "feed": feed_name,
                    "title": title,
                    "summary": summary,
                    "article_text": article_text,
                    "text": text,
                    "content_status": content_status,
                    "evidence_quality": evidence_quality,
                    "extraction_error": extraction_error,
                    "url": publisher_url,
                    "rss_url": link,
                    "published_at": _published_at(entry),
                    "source": _source_name(entry, feed_name),
                    "retrieved_at": retrieved_at,
                    "source_type": (
                        "regulatory_filing"
                        if "SEC" in feed_name else "news_feed"
                    ),
                })

        except Exception as exc:
            errors.append(
                f"{feed_name}: {type(exc).__name__}: {exc}"
            )

    # Deduplicate by normalized URL and then title.
    unique = {}
    seen_titles = set()

    for article in articles:
        key = _normalize_url(
            article["url"] or article["rss_url"]
        )
        title_key = re.sub(
            r"\W+", " ", article["title"].casefold()
        ).strip()

        if key in unique or (
            title_key and title_key in seen_titles
        ):
            continue

        unique[key or title_key] = article

        if title_key:
            seen_titles.add(title_key)

    return {
        "articles": list(unique.values()),
        "errors": errors,
        "retrieved_at": retrieved_at,
        "source_count": len(FEEDS),
    }
