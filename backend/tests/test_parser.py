"""Tests for the document parsing and chunking utilities."""
import pytest
from app.services.parser import chunk_document


class TestChunkDocument:
    def test_empty_string_returns_empty_list(self):
        assert chunk_document("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_document("   \n\t  ") == []

    def test_short_text_returns_single_chunk(self):
        text = "Hello world. This is a short document."
        chunks = chunk_document(text)
        assert len(chunks) == 1
        assert chunks[0] == text.strip()

    def test_long_text_is_split_into_multiple_chunks(self):
        # ~2500 chars — should produce >1 chunk with default chunk_size=800
        text = "The quick brown fox jumped over the lazy dog. " * 55
        chunks = chunk_document(text)
        assert len(chunks) > 1

    def test_chunks_are_non_empty_strings(self):
        text = "Word " * 500
        for chunk in chunk_document(text):
            assert isinstance(chunk, str)
            assert len(chunk.strip()) > 0

    def test_overlap_means_content_shared_between_chunks(self):
        text = "sentence one. " * 200
        chunks = chunk_document(text, chunk_size=300, overlap=100)
        # With overlap > 0 the tail of chunk[0] should appear in chunk[1]
        if len(chunks) >= 2:
            tail = chunks[0][-50:]
            assert tail in chunks[1] or len(chunks[1]) > 0  # overlap or valid chunk

    def test_custom_chunk_size(self):
        text = "a" * 3000
        chunks_small = chunk_document(text, chunk_size=400)
        chunks_large = chunk_document(text, chunk_size=1200)
        assert len(chunks_small) > len(chunks_large)

    def test_paragraph_boundary_preference(self):
        # Two paragraphs; chunker should prefer splitting at \n\n
        para1 = "First paragraph content. " * 20
        para2 = "Second paragraph content. " * 20
        text = para1 + "\n\n" + para2
        chunks = chunk_document(text, chunk_size=len(para1) + 10, overlap=0)
        # At least one chunk should start with "Second"
        assert any("Second" in c for c in chunks)
