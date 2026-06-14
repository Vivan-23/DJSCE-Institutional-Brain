import io
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


def chunk_document(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[str]:
    """
    Character-based sliding-window chunker with token-aware overlap.
    Both chunk_size and overlap are measured in characters so the window
    boundaries are consistent with what embedding models see.
    """
    if not text.strip():
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        # Extend to the next sentence/paragraph boundary when possible
        if end < text_len:
            for sep in ("\n\n", "\n", ". ", " "):
                boundary = text.rfind(sep, start + chunk_size // 2, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward by chunk_size minus overlap
        start += max(chunk_size - overlap, 1)

    log.debug("Document chunked", total_chars=text_len, num_chunks=len(chunks))
    return chunks
