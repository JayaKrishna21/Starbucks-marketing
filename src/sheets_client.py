"""
Google Sheets I/O.

Sheet layout expected:
  raw_log tab columns:    post_id | url | timestamp | demand_signal | product_requested | evidence_quote | sentiment | caption_snippet
  top_requested tab cols: product_requested | mention_count | sentiment_summary | last_seen
"""
import json
import gspread
from google.oauth2.service_account import Credentials
from collections import Counter, defaultdict
from . import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def _load_credentials():
    """
    GOOGLE_SERVICE_ACCOUNT_JSON can be EITHER:
    - a file path to the downloaded service account JSON, OR
    - the raw JSON content itself (handy for Codespaces secrets, where
      pasting a file isn't practical - paste the whole JSON as the secret's
      value instead and this will detect and parse it directly)
    """
    raw = config.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if raw.startswith("{"):
        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(raw, scopes=SCOPES)


def _get_sheet():
    if not config.GOOGLE_SERVICE_ACCOUNT_JSON or not config.GOOGLE_SHEET_ID:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID must be set "
            "(via .env locally, or Codespaces secrets in the cloud)"
        )
    creds = _load_credentials()
    gc = gspread.authorize(creds)
    return gc.open_by_key(config.GOOGLE_SHEET_ID)


def _get_or_create_tab(sheet, title: str, header: list):
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=len(header))
        ws.append_row(header)
    return ws


def get_existing_post_ids() -> set:
    """
    Reads the raw_log tab and returns the set of post_ids already logged,
    so we never reprocess or duplicate a post on a later run.
    """
    sheet = _get_sheet()
    ws = _get_or_create_tab(
        sheet,
        config.RAW_LOG_TAB,
        ["post_id", "url", "timestamp", "demand_signal", "product_requested",
         "evidence_quote", "sentiment", "caption_snippet", "commenters"],
    )
    records = ws.get_all_records()
    return {str(r["post_id"]) for r in records if r.get("post_id")}


def append_raw_log(rows: list):
    """
    rows: list of dicts with keys matching the raw_log header.
    Appends every processed post (yes AND no) for auditability.
    """
    if not rows:
        return
    sheet = _get_sheet()
    ws = _get_or_create_tab(
        sheet,
        config.RAW_LOG_TAB,
        ["post_id", "url", "timestamp", "demand_signal", "product_requested",
         "evidence_quote", "sentiment", "caption_snippet", "commenters"],
    )
    values = [
        [
            r.get("post_id", ""),
            r.get("url", ""),
            r.get("timestamp", ""),
            r.get("demand_signal", ""),
            r.get("product_requested", ""),
            r.get("evidence_quote", ""),
            r.get("sentiment", ""),
            (r.get("caption", "") or "")[:200],
            ", ".join(r.get("commenter_usernames", []) or []),
        ]
        for r in rows
    ]
    ws.append_rows(values, value_input_option="RAW")


def write_rollup(yes_rows: list):
    """
    Rebuilds the top_requested tab from scratch using ONLY demand_signal == 'yes' rows.
    Groups by product_requested, counts mentions, summarizes sentiment mix.
    """
    sheet = _get_sheet()
    ws = _get_or_create_tab(
        sheet, config.ROLLUP_TAB,
        ["product_requested", "mention_count", "sentiment_summary", "last_seen"],
    )

    counts = Counter()
    sentiments = defaultdict(Counter)
    last_seen = {}

    for r in yes_rows:
        product = (r.get("product_requested") or "unspecified").strip().lower()
        counts[product] += 1
        sentiments[product][r.get("sentiment", "unknown")] += 1
        ts = r.get("timestamp", "")
        if ts and (product not in last_seen or ts > last_seen[product]):
            last_seen[product] = ts

    # Rebuild sheet contents (small dataset, simplest to overwrite rollup each run)
    header = ["product_requested", "mention_count", "sentiment_summary", "last_seen"]
    rows_out = [header]
    for product, count in counts.most_common():
        sentiment_summary = ", ".join(f"{s}:{n}" for s, n in sentiments[product].most_common())
        rows_out.append([product, count, sentiment_summary, last_seen.get(product, "")])

    ws.clear()
    ws.update(rows_out, value_input_option="RAW")