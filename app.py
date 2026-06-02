"""
app.py — Streamlit MF FAQ Assistant.
Continuous chat UI with session history, quick questions, and clear/new-chat actions.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mirae Asset MF FAQ",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Inject CSS inline (no external fetch) ────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
}
/* Widen main column */
.block-container { max-width: 780px !important; padding-top: 1rem !important; }

/* Header */
.app-header { text-align:center; padding: 0.5rem 0 0.25rem 0; }
.app-header h1 { font-size:1.6rem; font-weight:700; margin:0; color:#e5e5d1; }
.app-tagline { text-align:center; font-size:0.78rem; color:#6b7280; margin:0.1rem 0 0.8rem 0; }

/* ── Quick-question grid buttons ─────────────────────────────────────────────
   All buttons in the main content area get uniform height, flex-centred text,
   consistent horizontal padding, and rounded corners.
   section.main excludes the sidebar so those buttons are unaffected.          */
section.main .stButton > button {
    min-height: 72px !important;
    height: auto !important;
    width: 100% !important;
    white-space: normal !important;
    word-break: break-word !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    padding: 10px 14px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    line-height: 1.35 !important;
    border-radius: 10px !important;
    box-sizing: border-box !important;
}

/* Sidebar buttons: compact, single-line, no min-height override */
[data-testid="stSidebar"] .stButton > button {
    min-height: unset !important;
    height: auto !important;
    padding: 6px 12px !important;
    font-size: 0.82rem !important;
    white-space: nowrap !important;
    border-radius: 6px !important;
}

/* Source + timestamp caption */
.src-caption { font-size:0.75rem; color:#9ca3af; margin-top:4px; }

/* Disclaimer in sidebar */
.disc-box {
    background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px;
    padding:0.6rem 0.8rem; font-size:0.73rem; color:#6b7280; line-height:1.5;
}

/* Session history items */
.sess-item {
    background:#f3f4f6; border-radius:6px; padding:5px 10px;
    font-size:0.8rem; color:#374151; margin-bottom:4px; cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

# ── Start scheduler ONCE per process ─────────────────────────────────────────
if "scheduler_started" not in st.session_state:
    try:
        from scheduler.scheduler_init import start_scheduler
        start_scheduler()
        st.session_state["scheduler_started"] = True
    except Exception as e:
        st.session_state["scheduler_started"] = False

# ── Imports ───────────────────────────────────────────────────────────────────
from rag.pipeline import answer as rag_answer
from scheduler.scheduler_init import get_scheduler_status

# ── Constants ─────────────────────────────────────────────────────────────────
SCHEMES = [
    "Mirae Asset Large Cap Fund",
    "Mirae Asset Flexi Cap Fund",
    "Mirae Asset ELSS Tax Saver Fund",
    "Mirae Asset Mid Cap Fund",
    "Mirae Asset Liquid Fund",
]

# These are guaranteed to return great answers from our knowledge base
QUICK_QUESTIONS = [
    "Expense ratio of Mirae Asset Large Cap Fund?",
    "ELSS lock-in period?",
    "Exit load for Flexi Cap Fund?",
    "Riskometer of Mirae Asset Mid Cap Fund?",
    "Minimum SIP for Mirae Asset ELSS?",
    "How to download capital gains statement from CAMS?",
    "Benchmark of Mirae Asset Liquid Fund?",
    "Direct plan vs Regular plan difference?",
]

DISCLAIMER = (
    "Facts-only · No investment advice · Sources: AMFI, SEBI, "
    "Mirae Asset, CAMS · MF investments subject to market risks."
)

# ── Session state init ────────────────────────────────────────────────────────
def _init_state():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []          # current chat
    if "sessions" not in st.session_state:
        st.session_state["sessions"] = []          # archived sessions
    if "pending" not in st.session_state:
        st.session_state["pending"] = None         # quick-question trigger

_init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _save_current_session():
    """Archive the current chat to sessions history."""
    msgs = st.session_state["messages"]
    if not msgs:
        return
    label = msgs[0]["content"][:40] + "…" if len(msgs[0]["content"]) > 40 else msgs[0]["content"]
    st.session_state["sessions"].insert(0, {
        "label": label,
        "messages": list(msgs),
        "ts": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M"),
    })

def _format_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso or "unknown"

def _process_query(query: str):
    """Add user message, call RAG, append assistant message — no st.rerun needed."""
    query = query.strip()
    if not query:
        return

    # Append user message
    st.session_state["messages"].append({"role": "user", "content": query})

    # Call RAG
    result = rag_answer(query)
    status = result["status"]

    if status == "ok":
        content = result["answer"]
    elif status in ("pii", "opinion", "no_context"):
        content = result["answer"]
    else:
        content = result["answer"]

    st.session_state["messages"].append({
        "role": "assistant",
        "content": content,
        "meta": result,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏦 Mirae Asset MF")
    st.caption("Facts-Only FAQ Assistant")
    st.divider()

    # ── Chat actions ──────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True, key="btn_clear"):
            st.session_state["messages"] = []
            st.session_state["pending"] = None
            st.rerun()
    with col2:
        if st.button("💬 New Chat", use_container_width=True, key="btn_new"):
            _save_current_session()
            st.session_state["messages"] = []
            st.session_state["pending"] = None
            st.rerun()

    st.divider()

    # ── Scope ─────────────────────────────────────────────────────────────────
    st.markdown("**Schemes covered:**")
    for s in SCHEMES:
        st.caption(f"• {s}")

    st.divider()

    # ── Scheduler ─────────────────────────────────────────────────────────────
    st.markdown("**Corpus Refresh**")
    try:
        ss = get_scheduler_status()
        if ss["running"]:
            st.success("Scheduler ✅")
            if ss.get("next_run"):
                st.caption(f"Next: {_format_ts(ss['next_run'])}")
        else:
            st.warning("Scheduler ⚠️")
    except Exception:
        st.caption("Status unavailable")
    st.caption("12 AM · 6 AM · 12 PM · 6 PM IST")

    if st.button("🔄 Refresh Corpus", use_container_width=True, key="btn_refresh"):
        with st.spinner("Ingesting..."):
            try:
                from ingestion.ingest import run_ingestion
                s = run_ingestion(dry_run=False)
                st.success(f"{s['sources_processed']} sources, {s['total_chunks']} chunks")
            except Exception as e:
                st.error(str(e))

    st.divider()

    # ── Session history ───────────────────────────────────────────────────────
    if st.session_state["sessions"]:
        st.markdown("**Past Sessions**")
        for i, sess in enumerate(st.session_state["sessions"][:6]):
            with st.expander(f"💬 {sess['label']}", expanded=False):
                st.caption(sess["ts"])
                for m in sess["messages"]:
                    role_icon = "🧑" if m["role"] == "user" else "🏦"
                    st.markdown(f"{role_icon} {m['content'][:120]}{'…' if len(m['content']) > 120 else ''}")
                if st.button("Restore", key=f"restore_{i}"):
                    _save_current_session()
                    st.session_state["messages"] = list(sess["messages"])
                    st.rerun()
        st.divider()

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown(f'<div class="disc-box">{DISCLAIMER}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

# Header
st.markdown(
    '<div class="app-header"><h1>🏦 MF FAQ Assistant</h1></div>'
    '<p class="app-tagline">Mirae Asset Mutual Fund · Facts-only · No investment advice</p>',
    unsafe_allow_html=True,
)

# ── Quick questions (always visible at top) ────────────────────────────────────
with st.container():
    cols = st.columns(4)
    for idx, q in enumerate(QUICK_QUESTIONS):
        with cols[idx % 4]:
            if st.button(q, key=f"qq_{idx}", use_container_width=True):
                st.session_state["pending"] = q

st.divider()

# ── Process pending quick question (set before chat renders) ──────────────────
pending = st.session_state.get("pending")
if pending:
    st.session_state["pending"] = None
    with st.spinner("Searching official sources..."):
        _process_query(pending)

# ── Render chat messages ──────────────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🏦"):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            meta = msg.get("meta", {})
            status = meta.get("status", "ok")
            if status == "ok":
                url = meta.get("source_url", "")
                ts = _format_ts(meta.get("fetched_at", ""))
                parts = []
                if url:
                    parts.append(f"[Source]({url})")
                if ts:
                    parts.append(f"Updated: {ts}")
                if parts:
                    st.caption(" · ".join(parts))

# ── Empty state ───────────────────────────────────────────────────────────────
if not st.session_state["messages"]:
    st.markdown(
        "<div style='text-align:center;color:#9ca3af;padding:2rem 0;font-size:0.85rem;'>"
        "Click a question above or type below to get started.<br>"
        "<span style='font-size:0.75rem;'>expense ratio · exit load · ELSS lock-in · "
        "min SIP · riskometer · statement download</span>"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask a factual question about Mirae Asset mutual funds…")

if user_input and user_input.strip():
    with st.spinner("Searching official sources..."):
        _process_query(user_input.strip())
    st.rerun()   # only rerun needed — to render new messages cleanly

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#e5e7eb;font-size:0.68rem;margin-top:1.5rem;'>"
    "Streamlit · RAG on Pinecone (384-dim) · Gemini 2.5 Flash"
    "</div>",
    unsafe_allow_html=True,
)
