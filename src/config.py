import os
from dotenv import load_dotenv

load_dotenv()

# --- Secrets (loaded from .env locally, or injected directly as env vars
#     by GitHub Codespaces secrets in the cloud - os.getenv covers both) ---
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# --- Hashtags to intersect (post must contain ALL of these) ---
HASHTAGS = ["starbucks", "glutenfree"]

# --- Apify actor IDs (official actors owned/maintained by Apify itself, not third parties) ---
HASHTAG_SCRAPER_ACTOR = "apify/instagram-hashtag-scraper"
COMMENTS_SCRAPER_ACTOR = "apify/instagram-comment-scraper"

# --- Volume caps (keep costs predictable) ---
POSTS_PER_HASHTAG = 100        # pulled per hashtag, BEFORE intersection
MAX_COMMENTS_PER_POST = 50     # comments pulled per matched post

# --- Date filter (reference only; the hashtag actor has no date input - see README) ---
DAYS_BACK = 365

# --- Google Sheet tab names ---
RAW_LOG_TAB = "raw_log"        # every post processed, yes and no
ROLLUP_TAB = "top_requested"   # aggregated, yes-only

# --- Gemini model ---
GEMINI_MODEL = "gemini-2.0-flash"