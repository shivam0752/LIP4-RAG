"""
fetcher.py — Fetch and parse content from URLs (HTML or PDF).
Supports HTTP pages and direct PDF links.
"""

import httpx
import logging
from io import BytesIO
from typing import Optional
from bs4 import BeautifulSoup
from pypdf import PdfReader
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MF-FAQ-Bot/1.0; "
        "+https://github.com/your-org/mf-faq)"
    )
}

TIMEOUT = 30  # seconds


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_url(url: str) -> Optional[str]:
    """
    Fetch content from a URL and return clean plain text.
    Detects HTML vs PDF automatically from Content-Type header.

    Args:
        url: Public URL to fetch.

    Returns:
        Extracted plain text string, or None on failure.
    """
    try:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return _parse_pdf(response.content)
        else:
            return _parse_html(response.text, url)

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _parse_html(html: str, url: str) -> str:
    """Extract meaningful text from HTML, stripping nav/footer/scripts."""
    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate tags
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    # Prefer main content blocks
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(class_="content")
        or soup.body
    )

    text = main.get_text(separator="\n") if main else soup.get_text(separator="\n")

    # Collapse excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        return "\n\n".join(pages)
    except Exception as e:
        logger.warning(f"PDF parse error: {e}")
        return ""
