"""
ingest.py — Main ingestion orchestrator.
Reads knowledge/*.txt files (pre-curated from official sources).
Each file contains a 'Source: <url>' header used as the citation URL.
Embeds chunks and upserts to Pinecone. Updates source_list.csv timestamps.
"""

import os
import sys
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from ingestion.chunker import split_text
from ingestion.pinecone_client import upsert_chunks, get_or_create_index

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "refresh.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
# Patch stdout handler to survive Windows cp1252 consoles
for h in logging.root.handlers:
    if isinstance(h, logging.StreamHandler) and hasattr(h.stream, 'reconfigure'):
        try:
            h.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = ROOT / "knowledge"
SOURCE_CSV = ROOT / "sources" / "source_list.csv"

# Map knowledge filenames → source URL + metadata
KNOWLEDGE_META = {
    "elss_guide.txt":           {"url": "https://www.amfiindia.com/investor-corner/knowledge-center/elss.html",              "scheme": "ELSS", "category": "amfi_education", "description": "AMFI ELSS guide"},
    "sip_guide.txt":            {"url": "https://www.amfiindia.com/investor-corner/knowledge-center/sip-faqs.html",           "scheme": "All Schemes", "category": "amfi_education", "description": "AMFI SIP FAQs"},
    "mirae_large_cap.txt":      {"url": "https://miraeassetmf.co.in/schemes/equity/mirae-asset-large-cap-fund",              "scheme": "Large Cap", "category": "amc_product", "description": "Mirae Asset Large Cap Fund"},
    "mirae_flexi_cap.txt":      {"url": "https://miraeassetmf.co.in/schemes/equity/mirae-asset-flexi-cap-fund",              "scheme": "Flexi Cap", "category": "amc_product", "description": "Mirae Asset Flexi Cap Fund"},
    "mirae_elss.txt":           {"url": "https://miraeassetmf.co.in/schemes/equity/mirae-asset-elss-tax-saver-fund",         "scheme": "ELSS", "category": "amc_product", "description": "Mirae Asset ELSS Tax Saver Fund"},
    "mirae_mid_cap.txt":        {"url": "https://miraeassetmf.co.in/schemes/equity/mirae-asset-mid-cap-fund",                "scheme": "Mid Cap", "category": "amc_product", "description": "Mirae Asset Mid Cap Fund"},
    "mirae_liquid_fund.txt":    {"url": "https://miraeassetmf.co.in/schemes/debt/mirae-asset-liquid-fund",                   "scheme": "Liquid", "category": "amc_product", "description": "Mirae Asset Liquid Fund"},
    "riskometer_sebi.txt":      {"url": "https://www.sebi.gov.in/legal/circulars/oct-2020/product-labeling-in-mutual-funds-risk-o-meter_47909.html", "scheme": "All Schemes", "category": "sebi_circular", "description": "SEBI Riskometer circular"},
    "expense_ratio_sebi.txt":   {"url": "https://www.sebi.gov.in/legal/circulars/sep-2012/rationalization-of-total-expense-ratio-ter-charged-by-mutual-funds_23689.html", "scheme": "All Schemes", "category": "sebi_circular", "description": "SEBI TER circular"},
    "cams_statement_guide.txt": {"url": "https://www.camsonline.com/Investors/Statements/Capital-Gain-Loss-Statement",       "scheme": "All Schemes", "category": "cams_statement", "description": "CAMS capital gains statement guide"},
    "account_statement_guide.txt": {"url": "https://www.amfiindia.com/investor-corner/knowledge-center/common-account-statement.html", "scheme": "All Schemes", "category": "amfi_education", "description": "CAS download guide"},
    "mf_general_faqs.txt":      {"url": "https://www.amfiindia.com/investor-corner/knowledge-center/mutual-fund-faqs.html",  "scheme": "All Schemes", "category": "amfi_education", "description": "MF general FAQs"},
    "sebi_categorization.txt":  {"url": "https://www.sebi.gov.in/legal/circulars/may-2021/categorization-and-rationalization-of-mutual-fund-schemes_50060.html", "scheme": "All Schemes", "category": "sebi_circular", "description": "SEBI scheme categorization"},
}


def run_ingestion(dry_run: bool = False) -> dict:
    """
    Full ingestion pipeline: read local knowledge files → chunk → embed → upsert.

    Args:
        dry_run: If True, chunk without writing to Pinecone.

    Returns:
        Summary dict with counts and timestamp.
    """
    started_at = datetime.now(timezone.utc)
    fetched_at = started_at.isoformat()

    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Ingestion started at {fetched_at}")

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(f"Knowledge directory not found: {KNOWLEDGE_DIR}")

    knowledge_files = list(KNOWLEDGE_DIR.glob("*.txt"))
    logger.info(f"Found {len(knowledge_files)} knowledge files in {KNOWLEDGE_DIR}")

    if not dry_run:
        get_or_create_index()

    total_chunks = 0
    total_vectors = 0
    processed = 0

    for kfile in knowledge_files:
        fname = kfile.name
        meta_override = KNOWLEDGE_META.get(fname, {})

        # Read text content
        text = kfile.read_text(encoding="utf-8")

        # Extract Source URL from first line if present
        source_url = meta_override.get("url", "")
        if not source_url:
            match = re.match(r"Source:\s*(https?://\S+)", text)
            if match:
                source_url = match.group(1)

        metadata = {
            "url": source_url,
            "scheme": meta_override.get("scheme", "All Schemes"),
            "category": meta_override.get("category", "knowledge"),
            "description": meta_override.get("description", fname),
        }

        chunks = split_text(text, metadata)
        total_chunks += len(chunks)
        logger.info(f"  → {len(chunks)} chunks from {fname} (source: {source_url})")

        if not dry_run and chunks:
            upserted = upsert_chunks(chunks, fetched_at)
            total_vectors += upserted

        processed += 1

    summary = {
        "started_at": fetched_at,
        "sources_processed": processed,
        "failed_urls": 0,
        "total_chunks": total_chunks,
        "total_vectors_upserted": total_vectors,
        "dry_run": dry_run,
    }

    logger.info(f"Ingestion complete: {summary}")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MF FAQ ingestion pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Chunk without writing to Pinecone")
    args = parser.parse_args()
    run_ingestion(dry_run=args.dry_run)
