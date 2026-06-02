"""
chunker.py — Split long documents into overlapping text chunks.
Uses LangChain's RecursiveCharacterTextSplitter for semantic-aware splitting.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List

CHUNK_SIZE = 512        # characters (not tokens; fast, no tokenizer needed)
CHUNK_OVERLAP = 64      # overlap to preserve context across chunk boundaries


def split_text(text: str, metadata: dict) -> List[dict]:
    """
    Split a document's text into overlapping chunks and attach metadata.

    Args:
        text:     Full document text.
        metadata: Dict with keys like {url, scheme, category, description}.

    Returns:
        List of chunk dicts: {text, url, scheme, category, description, chunk_index}
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.split_text(text)

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if len(chunk_text) < 40:          # skip trivially short chunks
            continue
        chunks.append({
            "text": chunk_text,
            "url": metadata.get("url", ""),
            "scheme": metadata.get("scheme", "All Schemes"),
            "category": metadata.get("category", ""),
            "description": metadata.get("description", ""),
            "chunk_index": i,
        })

    return chunks
