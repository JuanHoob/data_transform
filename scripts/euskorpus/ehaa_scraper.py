#!/usr/bin/env python3
"""
EHAA/BOPV scraper for the current public HTML served by euskadi.eus.

Supported entry points:
    python -m scripts.euskorpus.ehaa_scraper --url URL --output data/limpios_json/ehaa
    python -m scripts.euskorpus.ehaa_scraper --summary-url URL --output data/limpios_json/ehaa
    python -m scripts.euskorpus.ehaa_scraper --url URL --with-parallel --dry-run

Year-scale crawling is intentionally disabled until index discovery is reliable.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

BASE_URL = "https://www.euskadi.eus"
BOPV_BASE = f"{BASE_URL}/bopv2/datos"
PARSER_VERSION = "bopv-html-v1"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EusKorpus-Scraper/1.0; "
        "+https://github.com/JuanHoob/data_transform)"
    ),
    "Accept-Language": "eu, es;q=0.9",
}

RATE_LIMIT_SECONDS = 1.5
MAX_RETRIES = 3
RETRY_BACKOFF = 2

LANG_EU = "eu"
LANG_ES = "es"
LANG_UNKNOWN = "unknown"

_BOPV_WEB_PREFIX_RE = re.compile(
    r"(?P<host>https?://(?:www\.)?euskadi\.eus)"
    r"/web01-bopv(?:modu)?/(?P<lang>es|eu)/bopv2/datos/",
    re.IGNORECASE,
)
_BOPV_DOCUMENT_RE = re.compile(
    r"/(?P<year>\d{4})/(?P<month>\d{2})/"
    r"(?P<document_id>\d{7})(?P<suffix>[ae])\.shtml(?:[?#].*)?$",
    re.IGNORECASE,
)
_BOPV_LEGACY_DOCUMENT_RE = re.compile(
    r"/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/"
    r"(?P<document_id>\d{8})\.s?html(?:[?#].*)?$",
    re.IGNORECASE,
)
_BOPV_SUMMARY_RE = re.compile(
    r"/(?P<year>\d{4})/(?P<month>\d{2})/[se]\d{2}_\d{4}\.shtml(?:[?#].*)?$",
    re.IGNORECASE,
)

_BOPV_CONTENT_CLASSES = {
    "BOPVDetalle",
    "BOPVTitulo",
    "BOPVSeccion",
    "BOPVOrden",
    "BOPVClave",
}
_BOPV_SUMMARY_CLASSES = {
    "BOPVSumarioTitulo",
    "BOPVSumarioSeccion",
    "BOPVSumarioOrden",
}
_NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "form",
    "iframe",
    ".migas",
    ".breadcrumbs",
    ".lasterbideak",
    ".busqsimpCal",
    ".prinColLeft",
    ".listaFormatos",
    ".enlaceSumario",
    ".bopvEnlacerss",
]
_NAVIGATION_PHRASES = {
    "accesibilidad",
    "buscar",
    "buscador",
    "contacto",
    "consulta",
    "consulta avanzada",
    "consulta simple",
    "euskarazko bertsioa",
    "informacion legal",
    "ir al contenido",
    "ir al sumario",
    "mapa web",
    "mi carpeta",
    "pagina de inicio",
    "politica de cookies",
    "rss",
    "sede electronica",
    "servicios",
    "solicitar una publicacion",
    "texto bilingue",
    "tramites",
    "ultimo boletin",
    "ultimo boletin rss",
    "volver arriba",
}

_SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_BASQUE_MONTHS = {
    "urtarril": 1,
    "otsail": 2,
    "martxo": 3,
    "apiril": 4,
    "maiatz": 5,
    "ekain": 6,
    "uztail": 7,
    "abuztu": 8,
    "irail": 9,
    "urri": 10,
    "azaro": 11,
    "abendu": 12,
}


@dataclass(frozen=True)
class BopvDocumentLink:
    """Document link extracted from a BOPV summary."""

    url: str
    document_id: str | None
    language: str | None
    title_hint: str | None = None
    section_hint: str | None = None


# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------


def ensure_scraper_dependencies() -> tuple[Any, Any]:
    """Import optional scraper dependencies on demand."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError(
            "Missing scraper dependencies. Install with: pip install -e '.[scraper]'"
        ) from exc
    return requests, BeautifulSoup


def _make_soup(html: str) -> Any:
    _, beautiful_soup = ensure_scraper_dependencies()
    return beautiful_soup(html, "lxml")


class RateLimitedSession:
    """HTTP session with a small delay and retry loop."""

    def __init__(
        self, headers: dict[str, str] | None = None, rate_limit: float = RATE_LIMIT_SECONDS
    ):
        self.requests, _ = ensure_scraper_dependencies()
        self.session = self.requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.rate_limit = rate_limit
        self._last_request: float = 0.0

    def get(self, url: str, **kwargs: Any) -> Any:
        """Run GET with rate limiting and retries."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=30, **kwargs)
                self._last_request = time.monotonic()
                response.raise_for_status()
                if not response.encoding:
                    response.encoding = response.apparent_encoding
                return response
            except self.requests.RequestException as exc:
                logger.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, exc)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(RETRY_BACKOFF * attempt)

        raise RuntimeError(f"Could not fetch {url} after {MAX_RETRIES} attempts")


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalize_bopv_url(url: str) -> str:
    """
    Return a stable BOPV URL accepted by the current public site.

    The BOPV serves equivalent pages both under `/bopv2/datos/` and under
    `/web01-bopv/{es,eu}/bopv2/datos/`. The canonical form used by this scraper
    is the shorter `/bopv2/datos/` URL.
    """
    normalized = clean_text(url)
    if normalized.startswith("//"):
        normalized = f"https:{normalized}"
    elif normalized.startswith("/"):
        normalized = urljoin(BASE_URL, normalized)

    normalized = normalized.replace("\r", "").replace("\n", "")
    normalized = _BOPV_WEB_PREFIX_RE.sub(r"\g<host>/bopv2/datos/", normalized)
    return normalized


def is_bopv_summary_url(url: str) -> bool:
    """Return True for BOPV summary URLs such as `s24_0210.shtml`."""
    normalized = normalize_bopv_url(url)
    return bool(_BOPV_SUMMARY_RE.search(normalized)) or normalized.endswith(
        ("/Ultimo.shtml", "/Azkena.shtml")
    )


def is_bopv_document_url(url: str) -> bool:
    """Return True for real BOPV document URLs."""
    normalized = normalize_bopv_url(url)
    return bool(_BOPV_DOCUMENT_RE.search(normalized) or _BOPV_LEGACY_DOCUMENT_RE.search(normalized))


def infer_bopv_language_from_url(url: str) -> str | None:
    """Infer BOPV language from the modern `a/e` suffix or path language."""
    normalized = normalize_bopv_url(url)
    match = _BOPV_DOCUMENT_RE.search(normalized)
    if match:
        suffix = match.group("suffix").lower()
        if suffix == "a":
            return LANG_ES
        if suffix == "e":
            return LANG_EU

    if "/es/" in url:
        return LANG_ES
    if "/eu/" in url:
        return LANG_EU
    return None


def get_parallel_language_url(url: str) -> str | None:
    """Build the parallel Spanish/Basque URL when the BOPV suffix allows it."""
    normalized = normalize_bopv_url(url)
    match = _BOPV_DOCUMENT_RE.search(normalized)
    if not match:
        return None

    suffix = match.group("suffix").lower()
    next_suffix = "e" if suffix == "a" else "a"
    return f"{normalized[: match.start('suffix')]}{next_suffix}{normalized[match.end('suffix') :]}"


def _extract_document_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized = normalize_bopv_url(url)
    match = _BOPV_DOCUMENT_RE.search(normalized) or _BOPV_LEGACY_DOCUMENT_RE.search(normalized)
    return match.group("document_id") if match else None


# ---------------------------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------------------------


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC and remove control characters except newlines/tabs."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")


def clean_text(text: str) -> str:
    """Basic text cleanup for BOPV HTML fragments."""
    if not text:
        return ""
    text = normalize_unicode(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _normalized_phrase(text: str) -> str:
    text = _strip_accents(clean_text(text)).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tag_text(tag: Any) -> str:
    return clean_text(tag.get_text(separator=" ", strip=True)) if tag else ""


def _tag_classes(tag: Any) -> list[str]:
    classes = tag.get("class", []) if tag else []
    if isinstance(classes, str):
        return [classes]
    return list(classes)


def _has_any_class(tag: Any, names: Iterable[str]) -> bool:
    wanted = set(names)
    return any(cls in wanted for cls in _tag_classes(tag))


# ---------------------------------------------------------------------------
# Main-content extraction
# ---------------------------------------------------------------------------


def _remove_noise_nodes(root: Any) -> None:
    for selector in _NOISE_SELECTORS:
        for node in root.select(selector):
            node.decompose()


def extract_main_content_node(soup: Any) -> Any:
    """
    Return the BOPV document/summary container, avoiding site navigation.

    The real pages keep the useful content in `div.colCentralinterior` nested
    under `div.prinColCenter`, with semantic BOPV classes inside.
    """
    _remove_noise_nodes(soup)

    marker = soup.select_one(
        ".BOPVDetalle, .BOPVTitulo, .BOPVSeccion, .BOPVOrden, "
        ".BOPVSumarioTitulo, .BOPVSumarioSeccion"
    )
    if marker:
        for parent in [marker, *list(marker.parents)]:
            classes = set(_tag_classes(parent))
            if {"colCentralinterior", "prinColCenter"} & classes:
                return parent
        return marker.parent or marker

    main = soup.find("main")
    if main:
        return main

    legacy = soup.select_one("div.bopv-content, article, div#contenido")
    if legacy:
        return legacy

    body = soup.find("body")
    return body or soup


def _is_legal_short_text(text: str) -> bool:
    normalized = _normalized_phrase(text)
    if len(text) >= 20:
        return True
    return bool(
        re.match(
            r"^(base|articulo|art|primero|segundo|tercero|cuarto|quinto|"
            r"lehenengoa|bigarrena|\d+|[ivx]+|resuelvo|ebazten dut)\b",
            normalized,
        )
        or ".-" in normalized
        or ".–" in text
    )


def _is_navigation_text(text: str) -> bool:
    normalized = _normalized_phrase(text)
    if normalized in _NAVIGATION_PHRASES:
        return True
    return any(
        normalized == phrase or normalized.startswith(f"{phrase} ")
        for phrase in _NAVIGATION_PHRASES
    )


def extract_paragraphs(soup: Any, selector: str | None = None) -> list[str]:
    """
    Extract clean paragraph texts from a BOPV document.

    This function intentionally returns plain strings for compatibility with
    earlier tests and downstream processors. `parse_bopv_document` wraps them in
    paragraph objects with index/language metadata.
    """
    if selector:
        container = soup.select_one(selector)
    else:
        container = None
    container = container or extract_main_content_node(soup)
    if not container:
        return []

    preferred_tags = container.select(".BOPVTitulo, .BOPVClave, .BOPVDetalle")
    if not preferred_tags:
        preferred_tags = container.find_all(["p", "li", "h1", "h2", "h3", "h4", "blockquote"])

    paragraphs: list[str] = []
    previous: str | None = None
    for tag in preferred_tags:
        text = _tag_text(tag)
        if not text:
            continue
        if _is_navigation_text(text):
            continue
        if not _is_legal_short_text(text):
            continue
        if text == previous:
            continue
        paragraphs.append(text)
        previous = text
    return paragraphs


# ---------------------------------------------------------------------------
# Summary parsing
# ---------------------------------------------------------------------------


def parse_bopv_summary(html: str, base_url: str) -> list[BopvDocumentLink]:
    """Extract ordered document links from a real BOPV summary page."""
    soup = _make_soup(html)
    container = extract_main_content_node(soup)
    current_section: str | None = None
    links: list[BopvDocumentLink] = []
    seen: set[str] = set()

    for tag in container.find_all(["h4", "a"], recursive=True):
        if tag.name == "h4" and _has_any_class(tag, {"BOPVSumarioSeccion"}):
            current_section = _tag_text(tag) or current_section
            continue

        if tag.name != "a" or not tag.get("href"):
            continue

        full_url = normalize_bopv_url(urljoin(base_url, tag["href"]))
        if not is_bopv_document_url(full_url) or full_url in seen:
            continue

        seen.add(full_url)
        links.append(
            BopvDocumentLink(
                url=full_url,
                document_id=_extract_document_id_from_url(full_url),
                language=infer_bopv_language_from_url(full_url),
                title_hint=_tag_text(tag) or None,
                section_hint=current_section,
            )
        )

    return links


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------


def parse_bopv_document(
    html: str, source_url: str | None = None, language: str | None = None
) -> dict[str, Any]:
    """Parse a BOPV/EHAA document page into a stable JSON structure."""
    soup = _make_soup(html)
    normalized_url = normalize_bopv_url(source_url) if source_url else None
    main = extract_main_content_node(soup)

    paragraph_texts = extract_paragraphs(soup)
    document_language = (
        infer_bopv_language_from_url(normalized_url or "")
        or language
        or _extract_html_language(soup)
        or _detect_language_from_text(paragraph_texts)
        or LANG_UNKNOWN
    )

    date_published, date_raw = _extract_date_info(soup, normalized_url)
    document_id = _extract_document_id_from_url(normalized_url) or _extract_document_id_from_html(
        soup, date_published
    )
    raw_classes = _detect_raw_bopv_classes(main)

    document: dict[str, Any] = {
        "source": "EHAA/BOPV",
        "source_url": normalized_url,
        "url": normalized_url,
        "document_id": document_id,
        "language": document_language,
        "parallel_url": get_parallel_language_url(normalized_url) if normalized_url else None,
        "title": _extract_title(soup, main),
        "date_published": date_published,
        "section": _extract_section(soup),
        "bopv_number": _extract_bopv_number(soup, normalized_url),
        "order": _extract_order(soup),
        "paragraphs": [
            {"index": index, "text": text, "language": document_language}
            for index, text in enumerate(paragraph_texts)
        ],
        "metadata": {
            "parser_version": PARSER_VERSION,
            "scraped_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "raw_classes_detected": raw_classes,
            "paragraph_count": len(paragraph_texts),
        },
    }
    if date_raw and date_raw != date_published:
        document["date_published_raw"] = date_raw

    return document


def _detect_raw_bopv_classes(node: Any) -> list[str]:
    classes: set[str] = set()
    for tag in node.find_all(True):
        for class_name in _tag_classes(tag):
            if class_name.startswith("BOPV"):
                classes.add(class_name)
    return sorted(classes)


def _extract_title(soup: Any, main: Any) -> str:
    for selector in [".BOPVTitulo", "h1"]:
        tag = main.select_one(selector) or soup.select_one(selector)
        text = _tag_text(tag)
        if text and not _is_navigation_text(text):
            return text

    title = _tag_text(soup.find("title"))
    if title and not re.fullmatch(r"BOPV\s+\d{4}[-/]\d{2}[-/]\d{2}", title, re.IGNORECASE):
        return title
    return ""


def _extract_html_language(soup: Any) -> str | None:
    html = soup.find("html")
    lang = (html.get("lang") if html else None) or ""
    lang = lang.lower()
    if lang.startswith("es"):
        return LANG_ES
    if lang.startswith("eu"):
        return LANG_EU
    return None


def _detect_language_from_text(paragraphs: list[str]) -> str | None:
    if not paragraphs:
        return None
    try:
        from scripts.euskorpus.lang_detect import detect_language

        result = detect_language(" ".join(paragraphs[:5]))
        language = result.get("language")
        return language if language in {LANG_ES, LANG_EU} else None
    except Exception:
        return None


def _extract_date_info(soup: Any, url: str | None) -> tuple[str | None, str | None]:
    candidates: list[str] = []

    for meta in soup.find_all("meta"):
        name = meta.get("name", "") or meta.get("property", "")
        if "date" in name.lower() and meta.get("content"):
            candidates.append(str(meta["content"]))

    for selector in [".tituGeneral", ".BOPVDetalle", "time", "h2", "p", "span"]:
        for tag in soup.select(selector)[:20]:
            text = _tag_text(tag)
            if text:
                candidates.append(text)

    if url:
        candidates.append(url)

    for candidate in candidates:
        parsed = _parse_date_string(candidate)
        if parsed:
            return parsed, candidate

    raw = next((candidate for candidate in candidates if _looks_like_date(candidate)), None)
    return None, raw


def _extract_date(soup: Any, url: str) -> str | None:
    """Compatibility wrapper returning only the normalized date."""
    return _extract_date_info(soup, url)[0]


def _looks_like_date(text: str) -> bool:
    normalized = _strip_accents(text.lower())
    return bool(
        re.search(r"\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}", normalized)
        or re.search(r"\d{4}ko\s+[a-z]+(?:aren|ren)\s+\d{1,2}a?", normalized)
        or re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}", normalized)
    )


def _parse_date_string(text: str) -> str | None:
    text = clean_text(text)
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y%m%d"]:
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    normalized = _strip_accents(text.lower())

    match = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", normalized)
    if match:
        day, month_name, year = match.groups()
        month = _SPANISH_MONTHS.get(month_name)
        if month:
            return f"{int(year):04d}-{month:02d}-{int(day):02d}"

    match = re.search(r"\b(\d{4})ko\s+([a-z]+?)(?:aren|ren)\s+(\d{1,2})a?\b", normalized)
    if match:
        year, month_name, day = match.groups()
        month = _BASQUE_MONTHS.get(month_name)
        if month:
            return f"{int(year):04d}-{month:02d}-{int(day):02d}"

    match = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", normalized)
    if match:
        day, month, year = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    return None


def _extract_section(soup: Any) -> str | None:
    tag = soup.select_one(".BOPVSeccion")
    text = _tag_text(tag)
    if text:
        return text

    for tag in soup.find_all(["h2", "h3", "h4"], limit=30):
        text = _tag_text(tag)
        if re.match(r"^[IVX]+\s*[-–]\s*.+", text, re.IGNORECASE):
            return text
    return None


def _extract_bopv_number(soup: Any, url: str | None) -> str | None:
    if url:
        legacy_match = _BOPV_LEGACY_DOCUMENT_RE.search(normalize_bopv_url(url))
        if legacy_match:
            return legacy_match.group("document_id")

    candidates = [_tag_text(tag) for tag in soup.select(".tituGeneral")[:5]]
    candidates.extend(_tag_text(tag) for tag in soup.find_all(["h2", "span", "p"], limit=40))

    for text in candidates:
        normalized = _strip_accents(text.lower())
        match = re.search(r"\bn\s*\.?\s*[ºo]?\s*(\d+)\b", normalized)
        if match:
            return match.group(1)
        match = re.search(r"\b(\d+)\.\s*zk\.", normalized)
        if match:
            return match.group(1)

    if url:
        summary_match = _BOPV_SUMMARY_RE.search(normalize_bopv_url(url))
        if summary_match:
            summary_file = normalize_bopv_url(url).rsplit("/", 1)[-1]
            match = re.search(r"_(\d{4})\.shtml", summary_file)
            if match:
                return str(int(match.group(1)))
    return None


def _extract_order(soup: Any) -> str | None:
    tag = soup.select_one(".BOPVOrden")
    text = _tag_text(tag)
    if text:
        return text

    hidden = soup.find("input", {"id": "bopvNumOrden"}) or soup.find(
        "input", {"name": "bopvNumOrden"}
    )
    value = hidden.get("value") if hidden else None
    if value:
        return str(value)[-5:].lstrip("0") or str(value)
    return None


def _extract_document_id_from_html(soup: Any, date_published: str | None) -> str | None:
    hidden = soup.find("input", {"id": "bopvNumOrden"}) or soup.find(
        "input", {"name": "bopvNumOrden"}
    )
    value = str(hidden.get("value", "")) if hidden else ""
    if re.fullmatch(r"\d{10}", value):
        return f"{value[2:4]}{value[-5:]}"

    order = _extract_order(soup)
    if date_published and order and order.isdigit():
        return f"{date_published[2:4]}{int(order):05d}"
    return None


# ---------------------------------------------------------------------------
# Scraping and output
# ---------------------------------------------------------------------------


def scrape_document(url: str, session: RateLimitedSession) -> dict[str, Any] | None:
    """Download and parse one BOPV document."""
    try:
        normalized_url = normalize_bopv_url(url)
        response = session.get(normalized_url)
        return parse_bopv_document(response.text, normalized_url)
    except session.requests.RequestException as exc:
        logger.warning("Error downloading %s: %s", url, exc)
        return None


def _expand_parallel_urls(urls: list[str], with_parallel: bool) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for url in urls:
        for candidate in [url, get_parallel_language_url(url) if with_parallel else None]:
            if candidate and candidate not in seen:
                ordered.append(candidate)
                seen.add(candidate)
    return ordered


def scrape_url(
    url: str,
    output_dir: Path,
    session: RateLimitedSession | None = None,
    *,
    with_parallel: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Scrape one document URL, optionally including its ES/EU parallel."""
    if session is None:
        session = RateLimitedSession()

    saved_files: list[Path] = []
    for candidate_url in _expand_parallel_urls([normalize_bopv_url(url)], with_parallel):
        document = scrape_document(candidate_url, session)
        if not document or not document["paragraphs"]:
            logger.error("Could not extract content from %s", candidate_url)
            continue

        out_path = output_dir / build_output_filename(document)
        if dry_run:
            print(f"DRY-RUN document {candidate_url} -> {out_path}")
            continue

        output_dir.mkdir(parents=True, exist_ok=True)
        _save_json(document, out_path)
        saved_files.append(out_path)
        logger.info("Saved: %s (%d paragraphs)", out_path, len(document["paragraphs"]))

    return saved_files


def scrape_summary_url(
    summary_url: str,
    output_dir: Path,
    session: RateLimitedSession | None = None,
    *,
    with_parallel: bool = False,
    dry_run: bool = False,
    max_docs: int | None = None,
) -> list[Path]:
    """Download a BOPV summary and process the linked documents."""
    if session is None:
        session = RateLimitedSession()

    normalized_summary_url = normalize_bopv_url(summary_url)
    response = session.get(normalized_summary_url)
    links = parse_bopv_summary(response.text, normalized_summary_url)
    urls = [link.url for link in links]
    if max_docs:
        urls = urls[:max_docs]

    saved_files: list[Path] = []
    for document_url in _expand_parallel_urls(urls, with_parallel):
        saved_files.extend(
            scrape_url(
                document_url,
                output_dir,
                session,
                with_parallel=False,
                dry_run=dry_run,
            )
        )
    return saved_files


def scrape_year(*_: Any, **__: Any) -> list[Path]:
    """Year scraping is intentionally disabled for this PR."""
    raise NotImplementedError(
        "Year scraping is currently disabled until BOPV index discovery is implemented safely."
    )


def build_output_filename(document: dict[str, Any]) -> str:
    """Build a stable filename for one parsed BOPV document."""
    date_part = document.get("date_published") or "unknown-date"
    document_id = document.get("document_id") or document.get("order") or "unknown-id"
    language = document.get("language") or LANG_UNKNOWN
    safe_id = re.sub(r"[^\w-]", "_", str(document_id))
    safe_language = re.sub(r"[^\w-]", "_", str(language))
    return f"ehaa_bopv_{date_part}_{safe_id}_{safe_language}.json"


def _build_filename(document: dict[str, Any], lang: str | None = None) -> str:
    """Backward-compatible filename helper kept for existing callers."""
    legacy_document = dict(document)
    if lang and "language" not in legacy_document:
        legacy_document["language"] = lang
    if "document_id" not in legacy_document:
        legacy_document["document_id"] = legacy_document.get("bopv_number")
    return build_output_filename(legacy_document)


def _save_json(data: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ehaa_scraper",
        description="Scraper for BOPV/EHAA real HTML pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", metavar="URL", help="Direct BOPV document URL")
    group.add_argument("--summary-url", metavar="URL", help="BOPV summary URL")
    group.add_argument("--year", type=int, metavar="YYYY", help="Disabled: year scraping")

    parser.add_argument(
        "--output",
        metavar="DIR",
        default="data/limpios_json/ehaa",
        help="Output directory for JSON files (default: data/limpios_json/ehaa)",
    )
    parser.add_argument(
        "--with-parallel",
        action="store_true",
        help="Also process the parallel ES/EU document when the URL pattern allows it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse, but print planned outputs without writing files",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        metavar="N",
        default=None,
        help="Maximum summary documents to process (useful for smoke tests)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        metavar="SECS",
        default=RATE_LIMIT_SECONDS,
        help=f"Seconds between requests (default: {RATE_LIMIT_SECONDS})",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.year:
        parser.error(
            "Year scraping is currently disabled until BOPV index discovery is implemented safely."
        )

    session = RateLimitedSession(rate_limit=args.rate_limit)
    output_dir = Path(args.output)

    if args.url:
        results = scrape_url(
            args.url,
            output_dir,
            session,
            with_parallel=args.with_parallel,
            dry_run=args.dry_run,
        )
        return 0 if results or args.dry_run else 1

    if args.summary_url:
        results = scrape_summary_url(
            args.summary_url,
            output_dir,
            session,
            with_parallel=args.with_parallel,
            dry_run=args.dry_run,
            max_docs=args.max_docs,
        )
        return 0 if results or args.dry_run else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
