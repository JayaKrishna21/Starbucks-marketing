"""
Sends caption + comments for one post to Gemini and asks for a structured
verdict on whether it signals demand for a gluten-free product Starbucks
doesn't currently sell.
"""
import json
import google.generativeai as genai
from . import config

_PROMPT_TEMPLATE = """You are analyzing an Instagram post and its comments about Starbucks and gluten-free food.

GOAL: Determine if this post or its comments show people asking for, wishing for, or complaining about the ABSENCE of a specific gluten-free product at Starbucks that Starbucks does not currently sell. General praise, unrelated content, or posts about gluten-free products Starbucks ALREADY sells do NOT count as a demand signal.

Respond with ONLY valid JSON, no markdown fences, no preamble, matching exactly this schema:
{{
  "demand_signal": "yes" or "no",
  "product_requested": "short name of the specific product/category requested, or null if no",
  "evidence_quote": "short paraphrase (not verbatim) of the strongest supporting line, or null if no",
  "sentiment": "frustrated" or "hopeful" or "neutral" or "excited" or "other"
}}

CAPTION:
{caption}

COMMENTS:
{comments}
"""


def _get_model():
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file or Codespaces secrets.")
    genai.configure(api_key=config.GEMINI_API_KEY)
    return genai.GenerativeModel(config.GEMINI_MODEL)


def classify_post(caption: str, comments: list) -> dict:
    model = _get_model()
    comments_block = "\n".join(f"- {c}" for c in comments) if comments else "(no comments)"

    prompt = _PROMPT_TEMPLATE.format(caption=caption or "(no caption)", comments=comments_block)

    response = model.generate_content(prompt)
    raw_text = response.text.strip()

    # Strip accidental markdown fences if the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fail safe: treat unparseable output as "no" rather than crashing the run
        result = {
            "demand_signal": "no",
            "product_requested": None,
            "evidence_quote": None,
            "sentiment": "other",
        }

    # Normalize expected keys in case the model omits one
    for key, default in [
        ("demand_signal", "no"),
        ("product_requested", None),
        ("evidence_quote", None),
        ("sentiment", "other"),
    ]:
        result.setdefault(key, default)

    return result