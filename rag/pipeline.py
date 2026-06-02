"""
pipeline.py — End-to-end RAG pipeline for the MF FAQ assistant.
Orchestrates: guardrails → retrieval → prompt build → Gemini 2.5 Flash → output.
"""

import os
import logging
from typing import Dict, Any

import google.generativeai as genai
from dotenv import load_dotenv

from rag.guardrails import run_guardrails
from rag.retriever import retrieve, get_latest_fetch_time
from rag.prompt import build_system_prompt, build_user_prompt

load_dotenv()
logger = logging.getLogger(__name__)

# ── Gemini setup ──────────────────────────────────────────────────────────────
_gemini_configured = False


def _configure_gemini():
    global _gemini_configured
    if not _gemini_configured:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        genai.configure(api_key=api_key)
        _gemini_configured = True


def _get_model():
    _configure_gemini()
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,        # low temp for factual, deterministic answers
            max_output_tokens=512,
        ),
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

def answer(query: str) -> Dict[str, Any]:
    """
    Process a user query through the full RAG pipeline.

    Returns a dict with:
        status:       "ok" | "pii" | "opinion" | "no_context" | "error"
        answer:       Answer text (or refusal message)
        source_url:   Primary citation URL (or None)
        fetched_at:   Source timestamp string
        chunks_used:  Number of context chunks retrieved
    """
    query = query.strip()

    # ── 1. Guardrails ─────────────────────────────────────────────────────────
    guard_status, guard_message = run_guardrails(query)

    if guard_status != "ok":
        return {
            "status": guard_status,
            "answer": guard_message,
            "source_url": None,
            "fetched_at": None,
            "chunks_used": 0,
        }

    # ── 2. Retrieve context ───────────────────────────────────────────────────
    try:
        chunks = retrieve(query, top_k=4)
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return {
            "status": "error",
            "answer": (
                "⚠️ The knowledge base is currently unavailable. "
                "Please try again in a moment."
            ),
            "source_url": None,
            "fetched_at": None,
            "chunks_used": 0,
        }

    fetched_at = get_latest_fetch_time(chunks)

    if not chunks:
        return {
            "status": "no_context",
            "answer": (
                "I couldn't find this information in the official sources. "
                "Please check: [amfiindia.com](https://www.amfiindia.com)"
            ),
            "source_url": "https://www.amfiindia.com",
            "fetched_at": fetched_at,
            "chunks_used": 0,
        }

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(query=query, context_chunks=chunks)

    # ── 4. Generate answer via Gemini 2.5 Flash ───────────────────────────────
    try:
        model = _get_model()
        chat = model.start_chat(history=[
            {"role": "user", "parts": [system_prompt]},
            {"role": "model", "parts": ["Understood. I will follow all rules strictly."]},
        ])
        response = chat.send_message(user_prompt)
        answer_text = response.text.strip()
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        return {
            "status": "error",
            "answer": (
                "⚠️ The AI service is temporarily unavailable. Please try again shortly."
            ),
            "source_url": None,
            "fetched_at": fetched_at,
            "chunks_used": len(chunks),
        }

    # ── 5. Extract primary source URL ─────────────────────────────────────────
    # Best-match chunk is index 0 (highest cosine similarity)
    primary_url = chunks[0]["url"] if chunks else None

    return {
        "status": "ok",
        "answer": answer_text,
        "source_url": primary_url,
        "fetched_at": fetched_at,
        "chunks_used": len(chunks),
    }
