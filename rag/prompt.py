"""
prompt.py — System and user prompt templates for Gemini 2.5 Flash.
Strict fact-only, citation-required, ≤3-sentence constraint.
"""

SYSTEM_PROMPT = """You are a Mutual Fund Facts Assistant for Mirae Asset Mutual Fund schemes.

STRICT RULES — follow every rule without exception:
1. Answer ONLY from the provided context chunks. Do NOT use any external knowledge.
2. Keep every answer to a MAXIMUM of 3 sentences.
3. End EVERY answer with exactly one citation in this format:
   Source: <URL from context>
4. Do NOT compute, estimate, or compare returns or performance figures.
5. Do NOT give investment advice, recommendations, or opinions.
6. If the context does not contain a clear answer, respond with:
   "I couldn't find this information in the official sources. Please check the official AMFI website: https://www.amfiindia.com"
7. Never make up information. Stick strictly to the context.
8. Append "Last updated from sources: {fetched_at}" at the end of every answer.

Tone: factual, concise, helpful."""


def build_user_prompt(query: str, context_chunks: list[dict]) -> str:
    """
    Build the user-turn prompt with retrieved context injected.

    Args:
        query:          User's question.
        context_chunks: List of dicts from pinecone_client.query_index().

    Returns:
        Formatted prompt string for the LLM.
    """
    if not context_chunks:
        context_block = "No relevant context found."
    else:
        parts = []
        for i, chunk in enumerate(context_chunks, 1):
            parts.append(
                f"[Chunk {i}] (Source URL: {chunk['url']})\n{chunk['text']}"
            )
        context_block = "\n\n---\n\n".join(parts)

    return f"""CONTEXT (from official public sources):
{context_block}

USER QUESTION:
{query}

Provide a factual answer in ≤3 sentences using ONLY the context above. \
End with: Source: <URL from the most relevant chunk>"""


def build_system_prompt(fetched_at: str = "unknown") -> str:
    """Return system prompt with fetched_at timestamp filled in."""
    return SYSTEM_PROMPT.format(fetched_at=fetched_at)
