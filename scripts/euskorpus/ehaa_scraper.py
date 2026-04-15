#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EHAA/BOPV Scraper - Scraper para el Boletín Oficial del País Vasco (BOPV/EHAA).

Descarga y estructura documentos legales del portal oficial:
https://www.euskadi.eus/bopv2/datos/

Uso:
    python ehaa_scraper.py --year 2024 --output data/limpios_json/
    python ehaa_scraper.py --url https://www.euskadi.eus/... --output data/limpios_json/
    python ehaa_scraper.py --help
"""

import argparse
import json
import logging
import re
import sys
import time
import unicodedata
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Instala dependencias con:  pip install requests beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ehaa_scraper")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
BASE_URL = "https://www.euskadi.eus"
BOPV_BASE = f"{BASE_URL}/bopv2/datos"
BOPV_INDEX_URL = "https://www.euskadi.eus/web01-bopvmodu/es/bopv2/datos/index.shtml"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EusKorpus-Scraper/1.0; "
        "+https://github.com/JuanHoob/data_transform)"
    ),
    "Accept-Language": "eu, es;q=0.9",
}

RATE_LIMIT_SECONDS = 1.5  # pausa entre peticiones (respeto al servidor)
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # segundos, se duplica en cada reintento

# Idiomas detectados en el portal BOPV
LANG_EU = "eu"
LANG_ES = "es"


# ---------------------------------------------------------------------------
# Utilidades HTTP
# ---------------------------------------------------------------------------

class RateLimitedSession:
    """Sesión HTTP con rate-limiting y reintentos automáticos."""

    def __init__(self, headers: Optional[Dict] = None, rate_limit: float = RATE_LIMIT_SECONDS):
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.rate_limit = rate_limit
        self._last_request: float = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET con rate-limit y reintentos."""
        # Esperar si es necesario
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=30, **kwargs)
                self._last_request = time.monotonic()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                logger.warning("Intento %d/%d fallido para %s: %s", attempt, MAX_RETRIES, url, exc)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(RETRY_BACKOFF * attempt)

        raise RuntimeError(f"No se pudo obtener {url} tras {MAX_RETRIES} intentos")


# ---------------------------------------------------------------------------
# Limpieza de texto
# ---------------------------------------------------------------------------

def normalize_unicode(text: str) -> str:
    """Normaliza unicode a NFC y elimina caracteres de control."""
    text = unicodedata.normalize("NFC", text)
    # Eliminar caracteres de control salvo saltos de línea y tabulaciones
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    return text


def clean_text(text: str) -> str:
    """Limpieza básica de texto: normalización unicode, espacios múltiples, etc."""
    if not text:
        return ""
    text = normalize_unicode(text)
    # Colapsar espacios múltiples
    text = re.sub(r" {2,}", " ", text)
    # Colapsar líneas en blanco múltiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_paragraphs(soup: BeautifulSoup, selector: str = "div.bopv-content") -> List[str]:
    """
    Extrae párrafos de texto de la página.
    Prueba selectores progresivos hasta encontrar contenido.
    """
    selectors = [selector, "article", "main", "div#contenido", "body"]
    container = None
    for sel in selectors:
        container = soup.select_one(sel)
        if container:
            break

    if not container:
        return []

    paragraphs = []
    for tag in container.find_all(["p", "li", "h1", "h2", "h3", "h4", "blockquote"]):
        text = clean_text(tag.get_text(separator=" "))
        if len(text) > 20:  # descartar fragmentos muy cortos
            paragraphs.append(text)
    return paragraphs


# ---------------------------------------------------------------------------
# Parsing de documentos BOPV
# ---------------------------------------------------------------------------

def parse_bopv_document(html: str, url: str, language: str = LANG_ES) -> Dict[str, Any]:
    """
    Parsea un documento BOPV y devuelve un dict estructurado.

    Estructura de salida::

        {
          "url": str,
          "language": "eu" | "es",
          "scraped_at": ISO-8601,
          "title": str,
          "date_published": str | null,    # YYYY-MM-DD
          "section": str | null,
          "paragraphs": [str, ...],
          "metadata": {...}
        }
    """
    soup = BeautifulSoup(html, "lxml")

    # Título
    title_tag = (
        soup.find("h1")
        or soup.find("title")
    )
    title = clean_text(title_tag.get_text()) if title_tag else ""

    # Fecha de publicación (formato BOPV: dd/mm/yyyy o yyyy/mm/dd en URL)
    date_published = _extract_date(soup, url)

    # Sección (e.g. "I - DISPOSICIONES GENERALES")
    section = _extract_section(soup)

    # Párrafos
    paragraphs = extract_paragraphs(soup)

    # Número de BOPV
    bopv_number = _extract_bopv_number(soup, url)

    return {
        "url": url,
        "language": language,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "title": title,
        "date_published": date_published,
        "section": section,
        "bopv_number": bopv_number,
        "paragraphs": paragraphs,
        "metadata": {
            "source": "EHAA/BOPV",
            "base_url": BASE_URL,
            "paragraph_count": len(paragraphs),
        },
    }


def _extract_date(soup: BeautifulSoup, url: str) -> Optional[str]:
    """Intenta extraer la fecha de publicación del documento."""
    # 1) Meta tag
    for meta in soup.find_all("meta"):
        name = meta.get("name", "") or meta.get("property", "")
        if "date" in name.lower():
            content = meta.get("content", "")
            parsed = _parse_date_string(content)
            if parsed:
                return parsed

    # 2) URL pattern: /datos/YYYY/MM/DD/
    url_date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if url_date_match:
        y, m, d = url_date_match.groups()
        return f"{y}-{m}-{d}"

    # 3) Texto visible
    date_pattern = re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b")
    for tag in soup.find_all(["time", "span", "p"], limit=30):
        text = tag.get_text()
        m = date_pattern.search(text)
        if m:
            day, month, year = m.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

    return None


def _parse_date_string(text: str) -> Optional[str]:
    """Parsea texto de fecha a formato YYYY-MM-DD."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y%m%d"]
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_section(soup: BeautifulSoup) -> Optional[str]:
    """Extrae la sección del boletín (I, II, III...) si existe."""
    for tag in soup.find_all(["h2", "h3", "div", "span"], limit=20):
        text = tag.get_text(strip=True)
        if re.match(r"^[IVX]+\s*[-–]\s*.+", text, re.IGNORECASE):
            return clean_text(text)
    return None


def _extract_bopv_number(soup: BeautifulSoup, url: str) -> Optional[str]:
    """Extrae el número de BOPV del contenido o URL."""
    # De la URL: .../datos/2024/01/15/00001234.shtml
    num_match = re.search(r"/(\d{8})\.s?html?", url)
    if num_match:
        return num_match.group(1)

    for tag in soup.find_all(["span", "p", "div"], limit=30):
        text = tag.get_text(strip=True)
        m = re.search(r"N[uú]m(?:ero)?[.\s]*:?\s*(\d+)", text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Índice de números de BOPV
# ---------------------------------------------------------------------------

def iter_bopv_urls_for_year(
    year: int, session: RateLimitedSession
) -> Generator[Dict[str, str], None, None]:
    """
    Genera pares {"url_es": ..., "url_eu": ...} para cada entrada del BOPV
    publicada en `year`.
    """
    index_url = f"{BOPV_BASE}/{year}/"
    logger.info("Obteniendo índice de %d desde %s", year, index_url)

    try:
        resp = session.get(index_url)
    except requests.RequestException as exc:
        logger.error("No se pudo obtener el índice para %d: %s", year, exc)
        return

    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.find_all("a", href=True)

    doc_pattern = re.compile(r"\d{8}\.s?html?$", re.IGNORECASE)

    seen: set = set()
    for link in links:
        href = link["href"]
        full_url = urljoin(index_url, href)
        if doc_pattern.search(full_url) and full_url not in seen:
            seen.add(full_url)
            # Intentar construir la URL en euskera (cambio /es/ -> /eu/)
            eu_url = full_url.replace("/es/", "/eu/") if "/es/" in full_url else full_url
            yield {"url_es": full_url, "url_eu": eu_url}


# ---------------------------------------------------------------------------
# Scraper principal
# ---------------------------------------------------------------------------

def scrape_document(url: str, language: str, session: RateLimitedSession) -> Optional[Dict[str, Any]]:
    """Descarga y parsea un documento BOPV."""
    try:
        resp = session.get(url)
        return parse_bopv_document(resp.text, url, language)
    except requests.RequestException as exc:
        logger.warning("Error descargando %s: %s", url, exc)
        return None


def scrape_year(
    year: int,
    output_dir: Path,
    languages: List[str],
    session: Optional[RateLimitedSession] = None,
    max_docs: Optional[int] = None,
) -> List[Path]:
    """
    Scrapea todos los documentos de un año y los guarda como JSON.

    Returns:
        Lista de rutas a los archivos JSON generados.
    """
    if session is None:
        session = RateLimitedSession()

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files: List[Path] = []
    count = 0

    for entry in iter_bopv_urls_for_year(year, session):
        if max_docs and count >= max_docs:
            break

        for lang in languages:
            url = entry.get(f"url_{lang}", entry["url_es"])
            doc = scrape_document(url, lang, session)
            if doc and doc["paragraphs"]:
                filename = _build_filename(doc, lang)
                out_path = output_dir / filename
                _save_json(doc, out_path)
                saved_files.append(out_path)
                logger.info("Guardado: %s (%d párrafos)", out_path.name, len(doc["paragraphs"]))
            else:
                logger.debug("Sin contenido para %s [%s]", url, lang)

        count += 1

    logger.info("Total documentos procesados: %d → %d archivos guardados", count, len(saved_files))
    return saved_files


def scrape_url(url: str, output_dir: Path, session: Optional[RateLimitedSession] = None) -> Optional[Path]:
    """Scrapea una URL única y la guarda como JSON."""
    if session is None:
        session = RateLimitedSession()
    output_dir.mkdir(parents=True, exist_ok=True)

    lang = LANG_EU if "/eu/" in url else LANG_ES
    doc = scrape_document(url, lang, session)
    if not doc or not doc["paragraphs"]:
        logger.error("No se pudo extraer contenido de %s", url)
        return None

    filename = _build_filename(doc, lang)
    out_path = output_dir / filename
    _save_json(doc, out_path)
    logger.info("Guardado: %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Utilidades de salida
# ---------------------------------------------------------------------------

def _build_filename(doc: Dict[str, Any], lang: str) -> str:
    """Construye un nombre de archivo seguro para el documento."""
    date_part = doc.get("date_published") or "unknown-date"
    num_part = doc.get("bopv_number") or re.sub(r"[^\w]", "_", doc["url"][-20:])
    return f"bopv_{date_part}_{num_part}_{lang}.json"


def _save_json(data: Dict[str, Any], path: Path) -> None:
    """Serializa a JSON con indentación."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ehaa_scraper",
        description="Scraper para el BOPV/EHAA (Boletín Oficial del País Vasco).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--year", type=int, metavar="YYYY", help="Año a scrapear (ej: 2024)")
    group.add_argument("--url", metavar="URL", help="URL directa de un documento BOPV")

    parser.add_argument(
        "--output",
        metavar="DIR",
        default="data/limpios_json/ehaa",
        help="Directorio de salida para los JSON (default: data/limpios_json/ehaa)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        choices=["es", "eu"],
        default=["eu", "es"],
        help="Idiomas a descargar (default: eu es)",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        metavar="N",
        default=None,
        help="Máximo de documentos a procesar (para pruebas)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        metavar="SECS",
        default=RATE_LIMIT_SECONDS,
        help=f"Segundos entre peticiones (default: {RATE_LIMIT_SECONDS})",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging detallado")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    session = RateLimitedSession(rate_limit=args.rate_limit)
    output_dir = Path(args.output)

    if args.url:
        result = scrape_url(args.url, output_dir, session)
        return 0 if result else 1

    if args.year:
        files = scrape_year(
            year=args.year,
            output_dir=output_dir,
            languages=args.languages,
            session=session,
            max_docs=args.max_docs,
        )
        return 0 if files else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
