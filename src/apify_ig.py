"""
Handles all Apify calls:
1. Scrape posts for each hashtag separately
2. Intersect results on post ID -> posts that used BOTH hashtags
3. Pull comments for only the matched posts
"""
from apify_client import ApifyClient
from . import config


def _get_client():
    if not config.APIFY_API_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN is not set. Add it to your .env file.")
    return ApifyClient(config.APIFY_API_TOKEN)


def scrape_hashtag(client: ApifyClient, hashtag: str, limit: int = None):
    """
    Run the official apify/instagram-hashtag-scraper for a single hashtag.
    Returns a list of post dicts (raw actor output).

    Note: this actor's input schema is just hashtags / resultsType / resultsLimit -
    it does NOT support a date-filter input field, so DAYS_BACK in config.py is
    aspirational only here (see README limitations). If you need a hard date
    cutoff, filter `timestamp` on the results after the fact instead.
    """
    limit = limit or config.POSTS_PER_HASHTAG

    run_input = {
        "hashtags": [hashtag],
        "resultsType": "posts",
        "resultsLimit": limit,
    }

    run = client.actor(config.HASHTAG_SCRAPER_ACTOR).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    return items


def normalize_post(raw_post: dict) -> dict:
    """
    Different actor versions use slightly different field names.
    This pulls out the fields we actually need, with fallbacks.
    """
    post_id = raw_post.get("id") or raw_post.get("shortCode") or raw_post.get("postId")
    url = raw_post.get("url") or raw_post.get("postUrl") or raw_post.get("displayUrl")
    caption = raw_post.get("caption") or raw_post.get("text") or ""
    timestamp = raw_post.get("timestamp") or raw_post.get("takenAt") or ""

    return {
        "post_id": post_id,
        "url": url,
        "caption": caption,
        "timestamp": timestamp,
    }


def get_posts_with_both_hashtags(hashtags: list = None) -> list:
    """
    Scrapes each hashtag separately, then returns only posts whose ID
    appears in every hashtag's result set (i.e. the post used all tags).
    """
    hashtags = hashtags or config.HASHTAGS
    client = _get_client()

    result_sets = []
    normalized_by_id = {}

    for tag in hashtags:
        raw_items = scrape_hashtag(client, tag)
        normalized = [normalize_post(p) for p in raw_items]
        normalized = [p for p in normalized if p["post_id"]]  # drop anything unparseable

        ids = set()
        for p in normalized:
            ids.add(p["post_id"])
            normalized_by_id[p["post_id"]] = p  # last write wins, fields are the same either way

        result_sets.append(ids)

    if not result_sets:
        return []

    matched_ids = set.intersection(*result_sets)
    return [normalized_by_id[pid] for pid in matched_ids]


def scrape_comments(client: ApifyClient, post_url: str, limit: int = None) -> list:
    """
    Pull comments for a single post URL.
    Returns a list of dicts: {"text": ..., "username": ...}
    """
    limit = limit or config.MAX_COMMENTS_PER_POST

    run_input = {
        "directUrls": [post_url],
        "resultsLimit": limit,
    }

    run = client.actor(config.COMMENTS_SCRAPER_ACTOR).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    comments = []
    for c in items:
        text = c.get("text") or c.get("comment") or ""
        username = (
            c.get("ownerUsername")
            or c.get("username")
            or (c.get("owner") or {}).get("username")
            or "unknown"
        )
        if text:
            comments.append({"text": text, "username": username})
    return comments


def enrich_with_comments(matched_posts: list) -> list:
    """
    Takes the intersected post list and adds two fields to each:
    - 'comments': list of comment text strings (used for Gemini classification)
    - 'commenter_usernames': list of usernames who commented (for the raw_log sheet)
    """
    client = _get_client()
    enriched = []
    for post in matched_posts:
        if not post.get("url"):
            post["comments"] = []
            post["commenter_usernames"] = []
        else:
            comment_records = scrape_comments(client, post["url"])
            post["comments"] = [c["text"] for c in comment_records]
            post["commenter_usernames"] = [c["username"] for c in comment_records]
        enriched.append(post)
    return enriched