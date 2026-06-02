# Mirae Asset MF FAQ Assistant

This is a **facts-only** RAG-based FAQ assistant built for **Groww** users to compare and query factual details about Mirae Asset Mutual Fund schemes without receiving financial advice.

It uses a pre-curated corpus of official AMC, SEBI, and AMFI pages.

---

## Scope

| Item | Detail |
|------|--------|
| **AMC** | Mirae Asset Mutual Fund |
| **Schemes** | Large Cap · Flexi Cap · ELSS Tax Saver · Mid Cap · Liquid Fund |
| **Source corpus** | 20 official public pages (AMFI, SEBI, Mirae Asset, CAMS, KFintech) |
| **LLM** | Google Gemini 2.5 Flash |
| **Vector Store** | Pinecone (serverless, free tier) |
| **Embedding model** | `sentence-transformers/all-MiniLM-L6-v2` |

---

## Setup

### Prerequisites
- Python 3.11+
- A [Google AI Studio](https://aistudio.google.com/) API key (Gemini)
- A [Pinecone](https://www.pinecone.io/) account API key (free tier)

### 1. Clone & install

```bash
git clone <your-repo-url>
cd RAG
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY=...
#   PINECONE_API_KEY=...
#   PINECONE_INDEX_NAME=mf-faq-corpus
```

### 3. Run the ingestion pipeline (first-time setup)

```bash
# Dry run — checks fetch & chunking without writing to Pinecone
python ingestion/ingest.py --dry-run

# Full ingest — embeds and upserts all 20 sources to Pinecone
python ingestion/ingest.py
```

### 4. Launch the app

```bash
streamlit run app.py
```

---

## Architecture

```
User Query
    │
    ▼
[Guardrails] — PII & opinion checks
    │
    ▼
[Pinecone Retriever] — top-4 cosine-similar chunks
    │
    ▼
[Gemini 2.5 Flash] — facts-only, ≤3 sentences, 1 citation
    │
    ▼
[Streamlit UI] — answer card with source URL & timestamp
```

**Scheduler**: APScheduler `BackgroundScheduler` inside the Streamlit process fires at **00:00, 06:00, 12:00, 18:00 IST** daily — re-ingesting all 20 sources automatically.

---

## Project Structure

```
RAG/
├── app.py                      # Streamlit entry point
├── app_styles.css              # Custom CSS
├── requirements.txt
├── .env.example
├── README.md
├── disclaimer.txt
├── sources/
│   └── source_list.csv         # 20 curated public URLs
├── ingestion/
│   ├── ingest.py               # Main orchestrator
│   ├── fetcher.py              # HTTP fetch + HTML/PDF parse
│   ├── chunker.py              # Text chunking
│   └── pinecone_client.py      # Pinecone upsert & query
├── rag/
│   ├── pipeline.py             # End-to-end RAG chain
│   ├── retriever.py            # Pinecone search wrapper
│   ├── prompt.py               # Prompt templates
│   └── guardrails.py           # PII + opinion filters
├── scheduler/
│   ├── scheduler_init.py       # APScheduler setup
│   └── refresh_job.py          # Refresh job wrapper
├── logs/
│   └── refresh.log             # Scheduler & ingestion logs
└── samples/
    └── sample_qa.md            # 10 sample Q&As with citations
```

---

## Known Limits

1. **Dynamic content**: Some AMC pages load content via JavaScript; the `httpx` fetcher (no JS execution) may retrieve partial text. PDFs from SEBI/AMFI are fully parsed.
2. **Pinecone free tier**: Limited to 1 serverless index and ~100k vectors. Our 20-source corpus is well within limits.
3. **Gemini rate limits**: Free tier has RPM limits; under normal single-user load this is not an issue.
4. **Factsheet numbers**: Expense ratios and NAVs change monthly; the assistant reflects the last corpus refresh timestamp.
5. **Language**: English only; queries in Hindi or other languages will receive an English response or a fallback.
6. **Scope boundary**: Only Mirae Asset schemes are indexed. Questions about other AMCs will trigger a "not found in sources" response.

---

## Disclaimer

See `disclaimer.txt` for the full disclaimer text used in the UI.

---

## Deliverables Checklist

- [x] Working prototype (Streamlit app)
- [x] Source list — `sources/source_list.csv` (20 URLs)
- [x] README with setup, scope, known limits
- [x] Sample Q&A — `samples/sample_qa.md` (10 queries)
- [x] Disclaimer snippet — `disclaimer.txt`
