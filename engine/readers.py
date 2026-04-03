"""File parsers: TXT, RTF, EPUB, PDF, Markdown, OCR."""

import os
import subprocess
import tempfile

from .text import clean_pdf_text, clean_rtf_artifacts, strip_markdown


def read_file(path: str, clean_pdf: bool = True, cache_dir: str = ".tts_cache") -> str:
    """Read a file and return plain text based on extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".rtf":
        return rtf_to_text(path)
    elif ext == ".epub":
        return epub_to_text(path)
    elif ext == ".pdf":
        text = pdf_to_text(path)
        if not text.strip():
            text = ocr_pdf(path, cache_dir)
        if clean_pdf:
            text = clean_pdf_text(text)
        return text
    elif ext == ".md":
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return strip_markdown(text)
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


def rtf_to_text(path: str) -> str:
    """Read an RTF file and return stripped plain text."""
    # macOS textutil (handles cocoartf perfectly)
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", path],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            text = result.stdout.decode("utf-8", errors="replace")
            return clean_rtf_artifacts(text)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # striprtf fallback
    from striprtf.striprtf import rtf_to_text as _rtf_to_text
    with open(path, "rb") as f:
        raw = f.read()
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1")
    text = _rtf_to_text(decoded)
    text = clean_rtf_artifacts(text)
    return text.encode("utf-8", errors="replace").decode("utf-8")


def epub_to_text(path: str) -> str:
    """Extract plain text from an EPUB file, preserving chapter order."""
    import ebooklib
    from ebooklib import epub as _epub
    from bs4 import BeautifulSoup

    book = _epub.read_epub(path, options={"ignore_ncx": True})
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        chunk = soup.get_text(separator="\n")
        chunk = "\n".join(line for line in chunk.splitlines() if line.strip())
        if chunk:
            parts.append(chunk)
    text = "\n\n".join(parts)
    return text.encode("utf-8", errors="replace").decode("utf-8").strip()


def epub_metadata(path: str) -> dict:
    """Return {title, author, chapters} dict."""
    import ebooklib
    from ebooklib import epub as _epub

    book = _epub.read_epub(path, options={"ignore_ncx": True})
    title = book.get_metadata("DC", "title")
    author = book.get_metadata("DC", "creator")
    chapters = [
        item.get_name()
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
    ]
    return {
        "title": title[0][0] if title else "Unknown",
        "author": author[0][0] if author else "Unknown",
        "chapters": chapters,
    }


def pdf_to_text(path: str) -> str:
    """Extract plain text from a PDF using PyMuPDF."""
    import fitz

    doc = fitz.open(path)
    parts = []
    for page in doc:
        text = page.get_text("text")
        text = "\n".join(line for line in text.splitlines() if line.strip())
        if text:
            parts.append(text)
    doc.close()
    text = "\n\n".join(parts)
    return text.encode("utf-8", errors="replace").decode("utf-8").strip()


def pdf_metadata(path: str) -> dict:
    """Return {title, author, pages} dict."""
    import fitz

    doc = fitz.open(path)
    meta = doc.metadata or {}
    pages = doc.page_count
    doc.close()
    return {
        "title": meta.get("title") or os.path.basename(path),
        "author": meta.get("author") or "Unknown",
        "pages": pages,
    }


def ocr_pdf(path: str, cache_dir: str = ".tts_cache") -> str:
    """Run tesseract OCR on each page of a PDF and return extracted text."""
    import fitz

    conv_dir = os.path.join(cache_dir, "conversions")
    os.makedirs(conv_dir, exist_ok=True)

    text_parts = []
    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            img_fd, img_tmp = tempfile.mkstemp(suffix=".png", dir=conv_dir)
            os.close(img_fd)
            try:
                pix.save(img_tmp)
                txt_fd, txt_tmp = tempfile.mkstemp(dir=conv_dir)
                os.close(txt_fd)
                os.unlink(txt_tmp)
                res = subprocess.run(
                    ["tesseract", img_tmp, txt_tmp, "-l", "eng"],
                    capture_output=True,
                )
                out_file = txt_tmp + ".txt"
                if res.returncode == 0 and os.path.isfile(out_file):
                    with open(out_file, "r", encoding="utf-8", errors="replace") as f:
                        text_parts.append(f.read())
                    os.unlink(out_file)
            finally:
                try:
                    os.unlink(img_tmp)
                except OSError:
                    pass
    except Exception as e:
        return f"[OCR error: {e}]"
    return "\n\n".join(text_parts)
