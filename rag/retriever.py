"""
retriever.py — Thin wrapper around pinecone_client.query_index().
Provides the retrieval step for the RAG pipeline.
"""

from ingestion.pinecone_client import query_index
from typing import List, Dict, Any


def retrieve(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Retrieve top-k relevant chunks for a user query.

    Args:
        query:  User's question string.
        top_k:  Number of chunks to retrieve (default 4).

    Returns:
        List of match dicts: {text, url, scheme, score, fetched_at}
    """
    return query_index(query_text=query, top_k=top_k)


def get_latest_fetch_time(chunks: List[Dict[str, Any]]) -> str:
    """
    Extract the most recent fetched_at timestamp from retrieved chunks.
    Used for 'Last updated from sources:' display in answers.
    """
    timestamps = [c.get("fetched_at", "") for c in chunks if c.get("fetched_at")]
    if not timestamps:
        return "unknown"
    return max(timestamps)  # ISO strings sort lexicographically
