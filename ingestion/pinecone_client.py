"""
pinecone_client.py — Pinecone index management and upsert helpers.
Uses the Pinecone serverless (free-tier) index for storing MF FAQ embeddings.
"""

import os
import logging
import hashlib
from typing import List, Dict, Any

from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "mf-faq-corpus")
EMBED_MODEL = "all-MiniLM-L6-v2"          # 384-dim, runs locally
EMBED_DIM = 384
BATCH_SIZE = 100                           # Pinecone upsert batch size
CLOUD = "aws"
REGION = "us-east-1"                       # Free tier region

# ── Singleton model (loaded once) ─────────────────────────────────────────────
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info(f"Loading embedding model: {EMBED_MODEL}")
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _get_client() -> Pinecone:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable is not set.")
    return Pinecone(api_key=api_key)


def get_or_create_index():
    """Create the Pinecone index if it doesn't exist; return the Index object."""
    pc = _get_client()
    existing = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME not in existing:
        logger.info(f"Creating Pinecone index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )
    else:
        logger.info(f"Using existing Pinecone index: {INDEX_NAME}")

    return pc.Index(INDEX_NAME)


def chunk_id(chunk: Dict[str, Any]) -> str:
    """
    Deterministic vector ID based on URL + chunk_index.
    Allows safe re-ingestion (upsert overwrites stale vectors).
    """
    raw = f"{chunk['url']}::{chunk['chunk_index']}"
    return hashlib.md5(raw.encode()).hexdigest()


def upsert_chunks(chunks: List[Dict[str, Any]], fetched_at: str) -> int:
    """
    Embed and upsert chunks into Pinecone.

    Args:
        chunks:     List of chunk dicts from chunker.py.
        fetched_at: ISO timestamp string for the current ingestion run.

    Returns:
        Number of vectors upserted.
    """
    if not chunks:
        return 0

    index = get_or_create_index()
    embedder = _get_embedder()

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    vectors = []
    for chunk, embedding in zip(chunks, embeddings):
        vectors.append({
            "id": chunk_id(chunk),
            "values": embedding.tolist(),
            "metadata": {
                "text": chunk["text"],
                "url": chunk["url"],
                "scheme": chunk["scheme"],
                "category": chunk["category"],
                "description": chunk["description"],
                "fetched_at": fetched_at,
            },
        })

    # Upsert in batches
    total = 0
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i: i + BATCH_SIZE]
        index.upsert(vectors=batch)
        total += len(batch)
        logger.info(f"Upserted batch {i // BATCH_SIZE + 1} ({len(batch)} vectors)")

    return total


def query_index(query_text: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Embed a query and retrieve top-k matching chunks with metadata.

    Args:
        query_text: User's question string.
        top_k:      Number of results to return.

    Returns:
        List of match dicts with keys: text, url, scheme, score.
    """
    index = get_or_create_index()
    embedder = _get_embedder()

    query_vec = embedder.encode([query_text], normalize_embeddings=True)[0].tolist()

    results = index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
    )

    matches = []
    for match in results.matches:
        meta = match.metadata or {}
        matches.append({
            "text": meta.get("text", ""),
            "url": meta.get("url", ""),
            "scheme": meta.get("scheme", ""),
            "score": round(match.score, 4),
            "fetched_at": meta.get("fetched_at", ""),
        })

    return matches
