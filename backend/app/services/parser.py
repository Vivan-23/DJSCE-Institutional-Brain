import io
import re
import structlog
from typing import List

log = structlog.get_logger()


def parse_pdf(file_content: bytes) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_content))
    pages = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            pages.append(extracted)
    return "\n".join(pages)


def parse_docx(file_content: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(file_content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _window(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Sliding window for a single oversize paragraph, cut at sentence/word boundaries."""
    chunks: List[str] = []
    start, text_len = 0, len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            for sep in ("\n", ". ", " "):
                boundary = text.rfind(sep, start + chunk_size // 2, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= text_len:
            break
        start = max(end - overlap, start + 1)  # step from where this chunk really ended
    return chunks


def _title_line(text: str) -> str:
    """The document's title: first short line that is not a bracketed banner, else ''."""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not line.startswith("[") and len(line) <= 120:
            return line
    return ""


def chunk_document(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[str]:
    """
    Paragraph-aware chunker. Whole paragraphs (a Q&A pair, a list, a clause) are packed
    into chunks of up to ``chunk_size`` characters, so a question is never separated from
    its answer; only a paragraph longer than the limit falls back to a sliding window with
    ``overlap``. Every chunk after the first is prefixed with the document's title line,
    so an excerpt still says which document (department, policy) it belongs to.
    """
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_window(para, chunk_size, overlap))
        elif not current:
            current = para
        elif len(current) + 2 + len(para) <= chunk_size:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)

    title = _title_line(text)
    if title:
        chunks = [chunks[0]] + [c if c.startswith(title) else f"{title}\n{c}" for c in chunks[1:]]

    log.debug("Document chunked", total_chars=len(text), num_chunks=len(chunks))
    return chunks
