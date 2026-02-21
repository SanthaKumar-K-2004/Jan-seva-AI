"""
Jan-Seva AI — Gazette Scraper (Full OCR)
Downloads PDF circulars from government gazette sites.
Pipeline: PDF → PyMuPDF Text → If poor text → Tesseract OCR → Chunk → Embed
Uses pytesseract for scanned PDFs and PyMuPDF for text-native PDFs.
"""

import os
import re
import tempfile
from datetime import datetime
from typing import Optional

from app.services.scraper.base_scraper import BaseScraper
from app.utils.logger import logger


class GazetteScraper(BaseScraper):
    """
    Gazette & PDF Scraper — Full OCR Pipeline.
    Flow: Download PDF → PyMuPDF text extraction → If result is sparse →
          Render pages to images → Tesseract OCR → Chunk with overlap → Embed
    """

    # Minimum chars that must be extracted before OCR fallback triggers
    MIN_TEXT_THRESHOLD = 100

    async def scrape(self, source: dict) -> dict:
        """Scrape a gazette URL for PDF links, download, and process with OCR."""
        result = {
            "source": source["name"],
            "source_url": source["url"],
            "status": "started",
            "schemes_found": 0,
            "pdfs_processed": 0,
            "ocr_used": 0,
        }

        try:
            # Step 1: Fetch the gazette page
            soup = self.fetch_html(source["url"])

            # Step 2: Find all PDF links
            pdf_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.lower().endswith(".pdf"):
                    full_url = href if href.startswith("http") else \
                        f"{source['url'].rstrip('/')}/{href.lstrip('/')}"
                    if full_url not in pdf_links:
                        pdf_links.append(full_url)

            logger.info(f"📄 Found {len(pdf_links)} PDFs on {source['name']}")

            # Step 3: Process each PDF (limit 15 per run for rate limiting)
            for pdf_url in pdf_links[:15]:
                try:
                    text, used_ocr = self._extract_text(pdf_url)
                    if not text:
                        continue

                    result["pdfs_processed"] += 1
                    if used_ocr:
                        result["ocr_used"] += 1

                    if self.contains_scheme_keywords(text):
                        # Smart chunking with overlap
                        chunks = self.chunk_text(text, chunk_size=500, overlap=50)

                        if chunks:
                            scheme_name = self._extract_scheme_name(text)

                            if scheme_name:
                                scheme_data = {
                                    "name": scheme_name,
                                    "slug": self.generate_slug(scheme_name),
                                    "description": chunks[0][:500] if chunks else "",
                                    "source_url": pdf_url,
                                    "source_type": "gazette",
                                    "state": self._detect_state(source),
                                    "ministry": source.get("name", ""),
                                }
                                scheme_id = self.upsert_scheme(scheme_data)
                            else:
                                scheme_id = None

                            stored = self.create_and_store_embeddings(
                                chunks, scheme_id, pdf_url, source["name"]
                            )
                            if stored > 0:
                                result["schemes_found"] += 1

                except Exception as e:
                    logger.warning(f"Failed to process PDF {pdf_url}: {e}")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            logger.error(f"Gazette scraper failed for {source['name']}: {e}")

        self.log_scraper_run(
            source["url"], result["status"],
            result["schemes_found"], result.get("pdfs_processed", 0),
        )
        return result

    def _extract_text(self, pdf_url: str) -> tuple[str, bool]:
        """
        Download PDF and extract text.
        Returns (text, used_ocr) tuple.
        Strategy: PyMuPDF first → if poor text → Tesseract OCR
        """
        response = self.fetch_page(pdf_url)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        try:
            # ─── Strategy 1: PyMuPDF native text extraction ───
            text = self._pymupdf_extract(temp_path)

            if text and len(text.strip()) >= self.MIN_TEXT_THRESHOLD:
                return text, False

            # ─── Strategy 2: Tesseract OCR (for scanned PDFs) ───
            logger.info(f"🔍 PyMuPDF yielded only {len(text.strip())} chars, switching to OCR...")
            ocr_text = self._tesseract_ocr(temp_path)

            if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                return ocr_text, True

            # Return whatever we got
            return text or ocr_text or "", bool(ocr_text)

        finally:
            os.unlink(temp_path)

    def _pymupdf_extract(self, pdf_path: str) -> str:
        """Extract text using PyMuPDF (works for text-native PDFs)."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            text_parts = []

            for page in doc:
                # Try standard text extraction
                text = page.get_text()
                if text and len(text.strip()) > 20:
                    text_parts.append(text)
                else:
                    # Try text blocks (catches more structured text)
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        if block[6] == 0:  # Text block (not image)
                            text_parts.append(block[4])

            doc.close()
            return "\n".join(text_parts).strip()

        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")
            return ""

    def _tesseract_ocr(self, pdf_path: str) -> str:
        """
        OCR pipeline: PDF → Images → Tesseract → Text.
        Uses PyMuPDF to render pages as images, then pytesseract for OCR.
        """
        try:
            import fitz  # PyMuPDF for rendering
            import pytesseract
            from PIL import Image
            import io

            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc):
                # Render page to high-res image (300 DPI)
                mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Run Tesseract OCR
                # Support English + Hindi + Tamil
                try:
                    ocr_text = pytesseract.image_to_string(
                        image,
                        lang="eng+hin+tam",
                        config="--psm 6"  # Assume uniform block of text
                    )
                except Exception:
                    # Fallback to English only
                    ocr_text = pytesseract.image_to_string(
                        image,
                        lang="eng",
                        config="--psm 6"
                    )

                if ocr_text and len(ocr_text.strip()) > 20:
                    text_parts.append(ocr_text)

                # Limit to first 20 pages for performance
                if page_num >= 19:
                    break

            doc.close()
            return "\n".join(text_parts).strip()

        except ImportError as e:
            logger.error(f"OCR dependencies missing (install pytesseract & Pillow): {e}")
            return ""
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return ""

    def _extract_scheme_name(self, text: str) -> Optional[str]:
        """Extract scheme name from gazette text using regex patterns."""
        patterns = [
            r"(?:scheme|yojana|programme|mission|abhiyan)\s*[-:–]\s*[\"']?(.+?)[\"']?(?:\n|\.)",
            r"(?:notification|order|circular|resolution)\s+(?:regarding|for|on)\s+[\"']?(.+?)[\"']?(?:\n|\.)",
            r'"([^"]+(?:scheme|yojana|programme|mission)[^"]*)"',
            r"'([^']+(?:scheme|yojana|programme|mission)[^']*)'",
            r"(?:launch|announce|introduce)\w*\s+(?:the\s+)?(.+?(?:scheme|yojana|programme|mission))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:2000], re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up
                name = re.sub(r"\s+", " ", name)
                if 8 <= len(name) <= 150:
                    return name

        return None

    def _detect_state(self, source: dict) -> str:
        """Detect state from source metadata."""
        name = source.get("name", "").lower()
        state_map = {
            "tamil": "Tamil Nadu", "tn ": "Tamil Nadu",
            "kerala": "Kerala",
            "andhra": "Andhra Pradesh", "ap ": "Andhra Pradesh",
            "karnataka": "Karnataka",
            "maharashtra": "Maharashtra", "mh ": "Maharashtra",
            "uttar": "Uttar Pradesh", "up ": "Uttar Pradesh",
            "rajasthan": "Rajasthan",
        }
        for key, state in state_map.items():
            if key in name:
                return state
        return "Central"


# --- Singleton ---
_gazette_scraper: GazetteScraper | None = None


def get_gazette_scraper() -> GazetteScraper:
    global _gazette_scraper
    if _gazette_scraper is None:
        _gazette_scraper = GazetteScraper()
    return _gazette_scraper
